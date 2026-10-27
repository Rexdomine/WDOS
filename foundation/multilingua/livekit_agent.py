"""
WDOS Server-Side LiveKit Translation Agent (`wdos-translator-bot`)
==================================================================
Follows the official LiveKit Python RTC SDK (`livekit.rtc`) and Azure AI Speech SDK
(`azure.cognitiveservices.speech`) architecture:
1. Joins active LiveKit rooms as an invisible server participant (`wdos-translator-bot`).
2. Subscribes to each human speaker's WebRTC audio track (`rtc.AudioStream` at 16kHz mono PCM)
   so mobile/Android speakers only ever send a single standard WebRTC microphone stream.
3. Pipes each speaker's PCM stream into Azure Speech Translation (`PushAudioInputStream` +
   `TranslationRecognizer`) on the server.
4. Broadcasts low-latency interim and finalized captions + translations over LiveKit Data
   Packets (`topic="wdos_caption"`) and persists `LiveTranscriptSegment` rows in PostgreSQL.
5. Publishes dedicated per-language WebRTC audio channels (`lang:en`, `lang:fr`, `lang:pt`,
   `lang:ar`, `lang:sw`, `lang:ha`, `lang:yo`, `lang:ig`) using `rtc.AudioSource(24000, 1)`
   and streams Azure Neural TTS 24kHz PCM frames directly to listeners.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import sys
import threading
import time
import uuid
from typing import Any, Dict, Optional, Set

from asgiref.sync import sync_to_async
from django.db import close_old_connections
from django.utils import timezone

from foundation.models import LiveTranscriptSegment, MeetingRoomSession, RoomParticipantSession
from foundation.multilingua.azure_speech_adapter import AzureSpeechAdapter
from foundation.multilingua.zoom_adapter import LiveKitAdapter

logger = logging.getLogger(__name__)

try:
    from livekit import rtc
except ImportError:  # pragma: no cover
    rtc = None

try:
    import azure.cognitiveservices.speech as speechsdk
    from azure.cognitiveservices.speech.audio import AudioConfig, AudioStreamFormat, PushAudioInputStream
    from azure.cognitiveservices.speech.translation import SpeechTranslationConfig, TranslationRecognizer
except ImportError:  # pragma: no cover
    speechsdk = None


BOT_IDENTITY_PREFIX = "wdos-translator-bot"
AZURE_DIRECT_TRANSLATION_SOURCES = {"en-US", "fr-FR", "pt-BR", "ar-EG", "sw-KE"}
AZURE_TARGET_SHORT_LANGS = ("en", "fr", "pt", "ar", "sw")
ALL_SHORT_LANGS = ("en", "fr", "pt", "ar", "sw", "ha", "yo", "ig")
SHORT_TO_BCP47 = {
    "en": "en-US",
    "fr": "fr-FR",
    "pt": "pt-BR",
    "ar": "ar-EG",
    "sw": "sw-KE",
    "ha": "ha-NG",
    "yo": "yo-NG",
    "ig": "ig-NG",
}
BCP47_TO_SHORT = {v: k for k, v in SHORT_TO_BCP47.items()}


def _normalize_bcp47(lang: Optional[str], default: str = "en-US") -> str:
    raw = (lang or "").strip()
    if not raw:
        return default
    if raw in AzureSpeechAdapter.SUPPORTED_LANGUAGES:
        return raw
    short = raw.split("-")[0].lower()
    return SHORT_TO_BCP47.get(short, default)


class SpeakerAudioPipeline:
    """
    Manages the 16kHz PCM audio stream from a single remote human participant in LiveKit
    and feeds it into an Azure `TranslationRecognizer` (or `SpeechRecognizer`) on the server.
    """

    def __init__(
        self,
        bot: "RoomTranslationBot",
        participant_identity: str,
        participant_name: str,
        participant_metadata: str,
        track: Any,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.bot = bot
        self.participant_identity = participant_identity
        self.participant_id = participant_identity.split("__")[0]
        self.participant_name = participant_name or "Speaker"
        self.speaking_lang = "en-US"
        self.track = track
        self.loop = loop
        self.closed = False
        self.is_muted = False
        self._unmuted_event = asyncio.Event()
        self._unmuted_event.set()
        self._audio_stream: Optional[Any] = None
        self._last_interim_sent_at = 0.0
        self._last_interim_text = ""
        self._last_flushed_utt_key = ""
        self._pending_interim_text = ""
        self._pending_interim_translations: Dict[str, str] = {}
        self._pending_utt_key = ""
        self._silence_flush_handle: Optional[asyncio.TimerHandle] = None
        self._push_stream: Optional[ Any ] = None
        self._recognizer: Optional[ Any ] = None
        self._active_recognizer_lang = ""
        self._needs_recognizer_restart = False
        self._task: Optional[asyncio.Task] = None

        self.apply_metadata(participant_metadata)

    def apply_metadata(self, raw_meta: str) -> None:
        if not raw_meta:
            return
        try:
            meta = json.loads(raw_meta)
            if isinstance(meta, dict):
                if meta.get("speaking_lang"):
                    new_lang = _normalize_bcp47(meta["speaking_lang"], self.speaking_lang)
                    if new_lang != self.speaking_lang:
                        self.speaking_lang = new_lang
                        if self._active_recognizer_lang and self._active_recognizer_lang != new_lang:
                            self._needs_recognizer_restart = True
                if meta.get("participant_id"):
                    self.participant_id = str(meta["participant_id"])
        except Exception:
            pass

    def update_speaker_info(self, name: Optional[str], speaking_lang: Optional[str]) -> None:
        if name and name.strip():
            self.participant_name = name.strip()
        if speaking_lang:
            norm = _normalize_bcp47(speaking_lang, self.speaking_lang)
            if norm != self.speaking_lang:
                self.speaking_lang = norm
                if self._active_recognizer_lang and self._active_recognizer_lang != norm:
                    self._needs_recognizer_restart = True

    def set_muted(self, muted: bool) -> None:
        if self.closed or self.is_muted == muted:
            return
        self.is_muted = muted
        if muted:
            self._unmuted_event.clear()
            if self._silence_flush_handle:
                self._silence_flush_handle.cancel()
                self._silence_flush_handle = None
            if self._pending_interim_text:
                self._flush_pending_interim_on_silence()
            self._stop_azure_recognizer()
            if self._audio_stream is not None:
                stream_to_close = self._audio_stream
                self._audio_stream = None
                self.loop.create_task(self._close_audio_stream_quietly(stream_to_close))
        else:
            self._needs_recognizer_restart = True
            self._unmuted_event.set()

    async def _close_audio_stream_quietly(self, stream: Any) -> None:
        try:
            await stream.aclose()
        except Exception:
            pass

    def start(self) -> None:
        if self._task is None:
            self._task = self.loop.create_task(self._run_audio_pump())

    async def stop(self) -> None:
        self.closed = True
        if self._silence_flush_handle:
            self._silence_flush_handle.cancel()
            self._silence_flush_handle = None
        self._stop_azure_recognizer()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    def _start_azure_recognizer(self) -> bool:
        if speechsdk is None:
            return False
        creds = AzureSpeechAdapter.get_azure_credentials()
        if not creds:
            return False
        speech_key, speech_region = creds
        self._stop_azure_recognizer()

        try:
            stream_format = AudioStreamFormat(samples_per_second=16000, bits_per_sample=16, channels=1)
            push_stream = PushAudioInputStream(stream_format=stream_format)
            audio_config = AudioConfig(stream=push_stream)

            lang = _normalize_bcp47(self.speaking_lang, "en-US")
            self._active_recognizer_lang = lang
            self._needs_recognizer_restart = False

            if lang in AZURE_DIRECT_TRANSLATION_SOURCES:
                speech_config = SpeechTranslationConfig(subscription=speech_key, region=speech_region)
                speech_config.speech_recognition_language = lang
                for t_short in AZURE_TARGET_SHORT_LANGS:
                    speech_config.add_target_language(t_short)
                try:
                    speech_config.set_profanity(speechsdk.ProfanityOption.Raw)
                except Exception:
                    pass
                try:
                    speech_config.set_property(speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs, "650")
                    speech_config.set_property_by_name("SpeechServiceResponse_PostProcessingOption", "TrueText")
                except Exception:
                    pass
                recognizer = TranslationRecognizer(translation_config=speech_config, audio_config=audio_config)
                is_translation_rec = True
            else:
                speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
                speech_config.speech_recognition_language = lang
                try:
                    speech_config.set_profanity(speechsdk.ProfanityOption.Raw)
                except Exception:
                    pass
                try:
                    speech_config.set_property(speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs, "650")
                    speech_config.set_property_by_name("SpeechServiceResponse_PostProcessingOption", "TrueText")
                except Exception:
                    pass
                recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
                is_translation_rec = False

            def on_recognizing(evt: Any) -> None:
                if self.closed or not evt.result or not evt.result.text:
                    return
                text = evt.result.text.strip()
                if not text or AzureSpeechAdapter.is_system_echo_phrase(text):
                    return
                translations: Dict[str, str] = {}
                if is_translation_rec and getattr(evt.result, "translations", None):
                    for t_short in AZURE_TARGET_SHORT_LANGS:
                        t_val = evt.result.translations.get(t_short)
                        if t_val and t_val.strip():
                            translations[t_short] = t_val.strip()
                utt_key = f"{self.participant_id}_{getattr(evt.result, 'offset', 0) or getattr(evt.result, 'result_id', '')}"
                self.loop.call_soon_threadsafe(
                    self._on_interim_main_thread,
                    text,
                    translations,
                    utt_key,
                )

            def on_recognized(evt: Any) -> None:
                if self.closed or not evt.result or not evt.result.text:
                    return
                text = evt.result.text.strip()
                if not text or AzureSpeechAdapter.is_system_echo_phrase(text):
                    return
                translations: Dict[str, str] = {}
                if is_translation_rec and getattr(evt.result, "translations", None):
                    for t_short in AZURE_TARGET_SHORT_LANGS:
                        t_val = evt.result.translations.get(t_short)
                        if t_val and t_val.strip():
                            translations[t_short] = t_val.strip()
                utt_key = f"{self.participant_id}_{getattr(evt.result, 'offset', 0) or getattr(evt.result, 'result_id', '')}"
                self.loop.call_soon_threadsafe(
                    self._on_final_main_thread,
                    text,
                    translations,
                    utt_key,
                )

            def on_canceled(evt: Any) -> None:
                if not self.closed:
                    self._needs_recognizer_restart = True

            def on_stopped(evt: Any) -> None:
                if not self.closed:
                    self._needs_recognizer_restart = True

            recognizer.recognizing.connect(on_recognizing)
            recognizer.recognized.connect(on_recognized)
            recognizer.canceled.connect(on_canceled)
            recognizer.session_stopped.connect(on_stopped)
            recognizer.start_continuous_recognition_async()

            self._push_stream = push_stream
            self._recognizer = recognizer
            return True
        except Exception as exc:
            logger.warning("Failed to start Azure recognizer for %s: %s", self.participant_name, exc)
            return False

    def _stop_azure_recognizer(self) -> None:
        rec = self._recognizer
        stream = self._push_stream
        self._recognizer = None
        self._push_stream = None
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass
        if rec is not None:
            try:
                rec.stop_continuous_recognition_async()
            except Exception:
                pass

    def _on_interim_main_thread(self, text: str, translations: Dict[str, str], utt_key: str) -> None:
        if self.closed:
            return
        self._pending_interim_text = text
        self._pending_interim_translations = translations
        self._pending_utt_key = utt_key

        if self._silence_flush_handle:
            self._silence_flush_handle.cancel()
        self._silence_flush_handle = self.loop.call_later(1.35, self._flush_pending_interim_on_silence)

        now = time.monotonic()
        if now - self._last_interim_sent_at < 0.28 and text == self._last_interim_text:
            return
        if now - self._last_interim_sent_at < 0.22:
            return
        self._last_interim_sent_at = now
        self._last_interim_text = text
        self.loop.create_task(
            self.bot.handle_interim_speech(
                speaker_name=self.participant_name,
                speaking_lang=self.speaking_lang,
                original_text=text,
                translations=translations,
            )
        )

    def _flush_pending_interim_on_silence(self) -> None:
        self._silence_flush_handle = None
        if self.closed:
            return
        text = (self._pending_interim_text or "").strip()
        translations = dict(self._pending_interim_translations or {})
        utt_key = self._pending_utt_key
        self._pending_interim_text = ""
        if not text or not utt_key or self._last_flushed_utt_key == utt_key:
            return
        self._last_flushed_utt_key = utt_key
        self.loop.create_task(
            self.bot.handle_final_speech(
                speaker_id=self.participant_id,
                speaker_name=self.participant_name,
                speaking_lang=self.speaking_lang,
                original_text=text,
                raw_translations=translations,
            )
        )

    def _on_final_main_thread(self, text: str, translations: Dict[str, str], utt_key: str) -> None:
        if self._silence_flush_handle:
            self._silence_flush_handle.cancel()
            self._silence_flush_handle = None
        self._pending_interim_text = ""
        if self.closed:
            return
        if utt_key and self._last_flushed_utt_key == utt_key:
            return
        if utt_key:
            self._last_flushed_utt_key = utt_key
        self.loop.create_task(
            self.bot.handle_final_speech(
                speaker_id=self.participant_id,
                speaker_name=self.participant_name,
                speaking_lang=self.speaking_lang,
                original_text=text,
                raw_translations=translations,
            )
        )

    async def _run_audio_pump(self) -> None:
        if rtc is None:
            return
        try:
            await self.bot.refresh_participant_db_info(self)
            last_db_refresh = time.monotonic()

            while not self.closed:
                await self._unmuted_event.wait()
                if self.closed:
                    break
                self._start_azure_recognizer()
                audio_stream = rtc.AudioStream(self.track, sample_rate=16000, num_channels=1)
                self._audio_stream = audio_stream
                try:
                    async for frame_event in audio_stream:
                        if self.closed or self.is_muted:
                            break
                        now = time.monotonic()
                        if now - last_db_refresh > 2.5:
                            last_db_refresh = now
                            self.loop.create_task(self.bot.refresh_participant_db_info(self))
                        if self._needs_recognizer_restart or self._push_stream is None:
                            self._start_azure_recognizer()
                        if self._push_stream is not None and frame_event and frame_event.frame:
                            try:
                                self._push_stream.write(bytes(frame_event.frame.data))
                            except Exception:
                                self._needs_recognizer_restart = True
                finally:
                    if self._audio_stream is audio_stream:
                        self._audio_stream = None
                    await self._close_audio_stream_quietly(audio_stream)
                    self._stop_azure_recognizer()
                if not self.closed and not self.is_muted:
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("Audio pump ended for %s: %s", self.participant_name, exc)
        finally:
            self._stop_azure_recognizer()


class RoomTranslationBot:
    """
    Invisible server-side participant that connects to a single LiveKit room,
    listens to all human speakers, runs Azure translation, broadcasts live captions,
    and streams translated neural speech onto per-language LiveKit audio tracks (`lang:<short>`).
    """

    def __init__(self, room_session_id: str, room_code: str, session_name: str, loop: asyncio.AbstractEventLoop) -> None:
        self.room_session_id = str(room_session_id)
        self.room_code = room_code
        self.session_name = session_name
        self.loop = loop
        self.room: Optional[Any] = None
        self.closed = False
        self.pipelines: Dict[str, SpeakerAudioPipeline] = {}
        self.lang_sources: Dict[str, Any] = {}
        self.lang_tracks: Dict[str, Any] = {}
        self.lang_queues: Dict[str, asyncio.Queue] = {}
        self.lang_workers: Dict[str, asyncio.Task] = {}
        self._publish_lock = asyncio.Lock()

    async def start(self) -> bool:
        if rtc is None or not LiveKitAdapter.is_configured():
            return False
        if "test" in sys.argv:
            return True
        try:
            bot_identity = f"{BOT_IDENTITY_PREFIX}-{self.room_code.lower()}"
            url = LiveKitAdapter.generate_session_payload(
                session_name=self.session_name,
                user_id=bot_identity,
                participant_name="WDOS Translation Agent",
                role_type=1,
            )["url"]
            token = LiveKitAdapter.generate_token(
                session_name=self.session_name,
                user_id=bot_identity,
                participant_name="WDOS Translation Agent",
                role_type=1,
                metadata=json.dumps({"is_translation_bot": True}),
            )
            self.room = rtc.Room(loop=self.loop)
            self._bind_room_events(self.room)
            await self.room.connect(url, token, options=rtc.RoomOptions(auto_subscribe=True))

            # Pre-publish the 5 primary language voice channels so browsers subscribe immediately on join
            for short_lang in AZURE_TARGET_TRANSLATION_CHANNELS:
                await self.ensure_language_channel(short_lang)

            # Attach to any audio tracks already published by participants in the room
            for remote_p in self.room.remote_participants.values():
                if remote_p.identity.startswith(BOT_IDENTITY_PREFIX):
                    continue
                for pub in remote_p.track_publications.values():
                    if pub.track and pub.track.kind == rtc.TrackKind.KIND_AUDIO:
                        self._attach_speaker_track(pub.track, pub, remote_p)

            print(
                f"[WDOS Translation Agent] Connected to room {self.room_code} (session={self.session_name}, participants={len(self.room.remote_participants)})",
                flush=True,
            )
            return True
        except Exception as exc:
            print(f"[WDOS Translation Agent] Failed to connect to {self.room_code}: {exc}", flush=True)
            await self.stop()
            return False

    async def stop(self) -> None:
        self.closed = True
        for pipeline in list(self.pipelines.values()):
            await pipeline.stop()
        self.pipelines.clear()

        for worker in list(self.lang_workers.values()):
            worker.cancel()
        self.lang_workers.clear()
        self.lang_queues.clear()
        self.lang_sources.clear()
        self.lang_tracks.clear()

        if self.room is not None:
            try:
                await self.room.disconnect()
            except Exception:
                pass
            self.room = None

    def is_healthy(self) -> bool:
        if self.closed or self.room is None:
            return False
        try:
            return self.room.connection_state == rtc.ConnectionState.CONN_CONNECTED
        except Exception:
            return True

    def _bind_room_events(self, room: Any) -> None:
        @room.on("disconnected")
        def _on_disconnected(*_args: Any) -> None:
            if not self.closed:
                print(f"[WDOS Translation Agent] Disconnected from room {self.room_code}; scheduling reconnect.", flush=True)
                self.closed = True

        @room.on("track_published")
        def _on_track_published(publication: Any, participant: Any) -> None:
            if self.closed or participant.identity.startswith(BOT_IDENTITY_PREFIX):
                return
            # Enterprise optimization for 100+ participants: never subscribe the server bot to video streams
            if getattr(publication, "kind", None) == rtc.TrackKind.KIND_VIDEO:
                try:
                    publication.set_subscribed(False)
                except Exception:
                    pass

        @room.on("track_subscribed")
        def _on_track_subscribed(track: Any, publication: Any, participant: Any) -> None:
            if self.closed or participant.identity.startswith(BOT_IDENTITY_PREFIX):
                return
            if track.kind == rtc.TrackKind.KIND_VIDEO:
                try:
                    publication.set_subscribed(False)
                except Exception:
                    pass
                return
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                self._attach_speaker_track(track, publication, participant)

        @room.on("track_muted")
        def _on_track_muted(participant: Any, publication: Any) -> None:
            prefix = f"{participant.identity}:"
            for key, pipeline in self.pipelines.items():
                if key.startswith(prefix):
                    pipeline.set_muted(True)

        @room.on("track_unmuted")
        def _on_track_unmuted(participant: Any, publication: Any) -> None:
            prefix = f"{participant.identity}:"
            for key, pipeline in self.pipelines.items():
                if key.startswith(prefix):
                    pipeline.set_muted(False)

        @room.on("track_unsubscribed")
        def _on_track_unsubscribed(track: Any, publication: Any, participant: Any) -> None:
            key = f"{participant.identity}:{getattr(publication, 'sid', '') or getattr(track, 'sid', '')}"
            pipeline = self.pipelines.pop(key, None)
            if pipeline:
                self.loop.create_task(pipeline.stop())

        @room.on("participant_disconnected")
        def _on_participant_disconnected(participant: Any) -> None:
            prefix = f"{participant.identity}:"
            for key in [k for k in self.pipelines if k.startswith(prefix)]:
                pipeline = self.pipelines.pop(key, None)
                if pipeline:
                    self.loop.create_task(pipeline.stop())

        @room.on("participant_metadata_changed")
        def _on_metadata_changed(participant: Any, old_metadata: str, new_metadata: str) -> None:
            prefix = f"{participant.identity}:"
            for key, pipeline in self.pipelines.items():
                if key.startswith(prefix):
                    pipeline.apply_metadata(new_metadata)

        @room.on("data_received")
        def _on_data_received(data_packet: Any) -> None:
            try:
                raw_bytes = bytes(data_packet.data)
                msg = json.loads(raw_bytes.decode("utf-8"))
                if not isinstance(msg, dict):
                    return
                if msg.get("type") == "lang_change":
                    p_ident = getattr(getattr(data_packet, "participant", None), "identity", "") or ""
                    spk_lang = msg.get("speaking_lang")
                    lis_lang = msg.get("listening_lang")
                    if spk_lang and p_ident:
                        prefix = f"{p_ident}:"
                        for key, pipeline in self.pipelines.items():
                            if key.startswith(prefix):
                                pipeline.update_speaker_info(None, spk_lang)
                    if lis_lang:
                        short_lis = _normalize_bcp47(lis_lang, "fr-FR").split("-")[0].lower()
                        self.loop.create_task(self.ensure_language_channel(short_lis))
            except Exception:
                pass

    def _attach_speaker_track(self, track: Any, publication: Any, participant: Any) -> None:
        key = f"{participant.identity}:{getattr(publication, 'sid', '') or getattr(track, 'sid', '')}"
        if key in self.pipelines:
            return
        pipeline = SpeakerAudioPipeline(
            bot=self,
            participant_identity=participant.identity,
            participant_name=participant.name or participant.identity,
            participant_metadata=participant.metadata or "",
            track=track,
            loop=self.loop,
        )
        if getattr(publication, "muted", False):
            pipeline.set_muted(True)
        self.pipelines[key] = pipeline
        pipeline.start()
        print(
            f"[WDOS Translation Agent] Subscribed to speaker '{pipeline.participant_name}' ({pipeline.speaking_lang}) in {self.room_code}",
            flush=True,
        )

    async def ensure_language_channel(self, short_lang: str) -> Optional[Any]:
        if self.closed or self.room is None or rtc is None:
            return None
        short_lang = (short_lang or "fr").split("-")[0].lower()
        if short_lang not in SHORT_TO_BCP47:
            return None
        if short_lang in self.lang_sources:
            return self.lang_sources[short_lang]

        async with self._publish_lock:
            if short_lang in self.lang_sources:
                return self.lang_sources[short_lang]
            try:
                source = rtc.AudioSource(sample_rate=24000, num_channels=1, queue_size_ms=20000)
                track = rtc.LocalAudioTrack.create_audio_track(f"lang:{short_lang}", source)
                options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
                await self.room.local_participant.publish_track(track, options)
                queue: asyncio.Queue = asyncio.Queue(maxsize=25)
                self.lang_sources[short_lang] = source
                self.lang_tracks[short_lang] = track
                self.lang_queues[short_lang] = queue
                self.lang_workers[short_lang] = self.loop.create_task(self._language_audio_worker(short_lang, source, queue))
                return source
            except Exception as exc:
                logger.warning("Failed to publish language track lang:%s in %s: %s", short_lang, self.room_code, exc)
                return None

    async def _language_audio_worker(self, short_lang: str, source: Any, queue: asyncio.Queue) -> None:
        """
        Streams synthesized 24kHz 16-bit mono PCM audio frames (20ms = 480 samples = 960 bytes)
        onto the dedicated LiveKit language track (`lang:<short_lang>`).
        """
        bcp47_lang = SHORT_TO_BCP47.get(short_lang, "fr-FR")
        bytes_per_20ms_frame = 480 * 2  # 480 samples * 2 bytes (16-bit mono) = 960 bytes
        while not self.closed:
            try:
                item = await queue.get()
                if item is None:
                    break
                text, speaker_name, speaker_id = item if len(item) == 3 else (*item, "")
                pcm_bytes = await self.loop.run_in_executor(
                    None,
                    AzureSpeechAdapter.synthesize_speech_pcm24k,
                    text,
                    bcp47_lang,
                )
                if not pcm_bytes:
                    continue

                # Notify browsers reliably which speaker's utterance is about to play on this language track
                await self._publish_caption_packet(
                    {
                        "type": "bot_tts_state",
                        "lang": short_lang,
                        "speaker_name": speaker_name,
                        "speaker_id": speaker_id,
                        "speaking": True,
                    },
                    reliable=True,
                )
                await asyncio.sleep(0.03)

                total_len = len(pcm_bytes)
                offset = 0
                while offset < total_len and not self.closed:
                    chunk = pcm_bytes[offset : offset + bytes_per_20ms_frame]
                    offset += bytes_per_20ms_frame
                    if len(chunk) < bytes_per_20ms_frame:
                        chunk = chunk + b"\x00" * (bytes_per_20ms_frame - len(chunk))
                    frame = rtc.AudioFrame(
                        data=chunk,
                        sample_rate=24000,
                        num_channels=1,
                        samples_per_channel=480,
                    )
                    await source.capture_frame(frame)

                try:
                    await source.wait_for_playout()
                except Exception:
                    pass

                await self._publish_caption_packet(
                    {
                        "type": "bot_tts_state",
                        "lang": short_lang,
                        "speaker_name": speaker_name,
                        "speaker_id": speaker_id,
                        "speaking": False,
                    },
                    reliable=True,
                )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("Language worker warning on lang:%s: %s", short_lang, exc)

    async def _publish_caption_packet(self, payload_dict: Dict[str, Any], reliable: bool = True) -> None:
        if self.closed or self.room is None or not self.room.local_participant:
            return
        try:
            raw = json.dumps(payload_dict).encode("utf-8")
            await self.room.local_participant.publish_data(raw, reliable=reliable, topic="wdos_caption")
        except Exception:
            pass

    def _refresh_participant_db_info_sync(self, pipeline: SpeakerAudioPipeline) -> None:
        if "test" not in sys.argv:
            close_old_connections()
        try:
            p = None
            try:
                p_uuid = uuid.UUID(str(pipeline.participant_id))
                p = RoomParticipantSession.objects.filter(id=p_uuid, room_session_id=self.room_session_id).first()
            except (ValueError, TypeError):
                pass
            if p is None and pipeline.participant_name:
                p = RoomParticipantSession.objects.filter(
                    room_session_id=self.room_session_id,
                    participant_name__iexact=pipeline.participant_name,
                ).first()
            if p is not None:
                pipeline.update_speaker_info(p.participant_name, p.speaking_language)
        except Exception:
            pass

    async def refresh_participant_db_info(self, pipeline: SpeakerAudioPipeline) -> None:
        await sync_to_async(self._refresh_participant_db_info_sync, thread_sensitive=True)(pipeline)

    def _save_interim_to_db_sync(self, speaker_name: str, speaking_lang: str, original_text: str, translations: Dict[str, str]) -> None:
        if "test" not in sys.argv:
            close_old_connections()
        try:
            from foundation.multilingua_events_views import _set_room_live_interim

            room_session = MeetingRoomSession.objects.filter(id=self.room_session_id).first()
            if not room_session:
                return
            now_ts = timezone.now().timestamp()
            _set_room_live_interim(
                room_session,
                str(room_session.id),
                {
                    "speaker_name": speaker_name,
                    "original_language": speaking_lang,
                    "original_text": original_text[:500],
                    "translations": translations,
                    "ts": now_ts,
                },
                now_ts,
            )
        except Exception:
            pass

    async def _save_interim_to_db(self, speaker_name: str, speaking_lang: str, original_text: str, translations: Dict[str, str]) -> None:
        await sync_to_async(self._save_interim_to_db_sync, thread_sensitive=True)(speaker_name, speaking_lang, original_text, translations)

    def _persist_final_segment_and_get_targets_sync(
        self,
        speaker_id: str,
        speaker_name: str,
        speaking_lang: str,
        original_text: str,
        translations: Dict[str, str],
    ) -> tuple[Optional[Dict[str, Any]], Set[str]]:
        if "test" not in sys.argv:
            close_old_connections()
        try:
            from foundation.multilingua_events_views import _set_room_live_interim

            room_session = MeetingRoomSession.objects.filter(id=self.room_session_id).first()
            if not room_session:
                return None, set()

            now_ts = timezone.now().timestamp()
            _set_room_live_interim(room_session, str(room_session.id), None, now_ts)

            # Deduplicate against recent segments within 2.5s
            recent_segs = list(room_session.transcript_segments.order_by("-sequence_number")[:3])
            norm_incoming = original_text.strip().lower().rstrip(".!?,")
            for r_seg in recent_segs:
                if (
                    r_seg.speaker_name == speaker_name
                    and r_seg.timestamp
                    and (timezone.now() - r_seg.timestamp).total_seconds() < 2.5
                ):
                    r_orig = (r_seg.original_text or "").strip().lower().rstrip(".!?,")
                    if norm_incoming == r_orig:
                        return None, set()

            participant = None
            try:
                participant = RoomParticipantSession.objects.filter(
                    id=uuid.UUID(str(speaker_id)),
                    room_session=room_session,
                ).first()
            except (ValueError, TypeError):
                pass
            if participant is None:
                participant = RoomParticipantSession.objects.filter(
                    room_session=room_session,
                    participant_name__iexact=speaker_name,
                ).first()

            speaker_profile = participant.person_profile if participant else None
            role_prefix = participant.meeting_role if participant else "Speaker"

            next_seq = room_session.transcript_segments.count() + 1
            seg = LiveTranscriptSegment.objects.create(
                room_session=room_session,
                speaker_profile=speaker_profile,
                speaker_name=speaker_name,
                original_language=speaking_lang,
                original_text=original_text,
                translations=translations,
                sequence_number=next_seq,
            )
            lang_meta = AzureSpeechAdapter.SUPPORTED_LANGUAGES.get(speaking_lang, {"name": "English"})
            room_session.active_speaker_name = speaker_name
            room_session.active_speaker_role = f"{role_prefix} · speaking in {lang_meta['name']}"
            room_session.save(update_fields=["active_speaker_name", "active_speaker_role"])

            active_listening_shorts: Set[str] = set()
            for p_row in room_session.participants.filter(admission_status="ADMITTED"):
                short_l = _normalize_bcp47(p_row.listening_language, "fr-FR").split("-")[0].lower()
                if short_l in SHORT_TO_BCP47:
                    active_listening_shorts.add(short_l)

            seg_dict = {
                "id": str(seg.id),
                "sequence_number": seg.sequence_number,
                "speaker_name": seg.speaker_name,
                "original_language": seg.original_language,
                "original_text": seg.original_text,
                "translations": seg.translations,
                "timestamp": seg.timestamp.isoformat() if seg.timestamp else "",
            }
            return seg_dict, active_listening_shorts
        except Exception as exc:
            logger.warning("Failed to persist final segment in %s: %s", self.room_code, exc)
            return None, set()

    async def _persist_final_segment_and_get_targets(
        self,
        speaker_id: str,
        speaker_name: str,
        speaking_lang: str,
        original_text: str,
        translations: Dict[str, str],
    ) -> tuple[Optional[Dict[str, Any]], Set[str]]:
        return await sync_to_async(self._persist_final_segment_and_get_targets_sync, thread_sensitive=True)(
            speaker_id, speaker_name, speaking_lang, original_text, translations
        )

    async def handle_interim_speech(
        self,
        speaker_name: str,
        speaking_lang: str,
        original_text: str,
        translations: Dict[str, str],
    ) -> None:
        if self.closed or not original_text:
            return
        await self._publish_caption_packet(
            {
                "type": "live_interim",
                "speaker_name": speaker_name,
                "original_language": speaking_lang,
                "original_text": original_text,
                "translations": translations,
                "ts": time.time(),
            },
            reliable=False,
        )
        await self._save_interim_to_db(speaker_name, speaking_lang, original_text, translations)

    async def handle_final_speech(
        self,
        speaker_id: str,
        speaker_name: str,
        speaking_lang: str,
        original_text: str,
        raw_translations: Dict[str, str],
    ) -> None:
        if self.closed or not original_text:
            return

        # 1. Ensure translations for all supported languages are populated
        translations = await self.loop.run_in_executor(
            None,
            AzureSpeechAdapter.translate_segment,
            original_text,
            speaking_lang,
            raw_translations,
        )
        detected_bcp47 = translations.pop("_detected_source", None)
        if detected_bcp47 and detected_bcp47 in AzureSpeechAdapter.SUPPORTED_LANGUAGES:
            speaking_lang = detected_bcp47

        # 2. Save to PostgreSQL and discover which listening languages are active in the room
        seg_dict, active_listening_shorts = await self._persist_final_segment_and_get_targets(
            speaker_id=speaker_id,
            speaker_name=speaker_name,
            speaking_lang=speaking_lang,
            original_text=original_text,
            translations=translations,
        )
        if not seg_dict:
            return

        # 3. Broadcast finalized segment immediately via LiveKit Data Packet
        if "test" not in sys.argv:
            print(
                f"[WDOS Translation Agent] [{self.room_code}] {speaker_name} ({speaking_lang}): '{original_text[:80]}'",
                flush=True,
            )
        await self._publish_caption_packet(
            {
                "type": "final_segment",
                "segment": seg_dict,
            },
            reliable=True,
        )

        # 4. Synthesize and stream neural voice over each active target language's LiveKit audio channel
        speaker_short = _normalize_bcp47(speaking_lang, "en-US").split("-")[0].lower()
        target_channels = set(active_listening_shorts) | set(AZURE_TARGET_TRANSLATION_CHANNELS)
        for target_short in target_channels:
            # Listeners whose listening language equals the speaker's spoken language hear the speaker's real human voice directly
            if target_short == speaker_short:
                continue
            translated_text = (translations.get(target_short) or original_text).strip()
            if not translated_text:
                continue
            await self.ensure_language_channel(target_short)
            q = self.lang_queues.get(target_short)
            if q is not None:
                if q.full():
                    try:
                        q.get_nowait()
                    except Exception:
                        pass
                await q.put((translated_text, speaker_name, speaker_id))


AZURE_TARGET_TRANSLATION_CHANNELS = ("en", "fr", "pt", "ar", "sw")


class TranslationAgentSupervisor:
    """
    Horizontally scalable LiveKit Room Translation Agent supervisor.
    Polls the database for active `MeetingRoomSession` instances, coordinates room ownership
    across multiple worker processes via distributed Redis/cache leases (`wdos_agent_lease:<room_id>`),
    and maintains a connected `RoomTranslationBot` for every leased room.
    """

    def __init__(self, worker_id: str = "", max_rooms: int = 25, is_standalone_worker: bool = False) -> None:
        import uuid
        from django.core.cache import cache
        self._cache = cache
        self.worker_id = worker_id or f"worker-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.max_rooms = max(1, int(max_rooms))
        self.is_standalone_worker = bool(is_standalone_worker)
        self.bots: Dict[str, RoomTranslationBot] = {}
        self._room_backoff: Dict[str, tuple[int, float]] = {}

    def _acquire_or_renew_room_lease(self, room_id: str) -> bool:
        lease_key = f"wdos_agent_lease:{room_id}"
        try:
            owner = self._cache.get(lease_key)
            if owner is None:
                return bool(self._cache.add(lease_key, self.worker_id, timeout=18))
            if owner == self.worker_id:
                self._cache.set(lease_key, self.worker_id, timeout=18)
                return True
            return False
        except Exception:
            return True

    def _release_room_lease(self, room_id: str) -> None:
        lease_key = f"wdos_agent_lease:{room_id}"
        try:
            if self._cache.get(lease_key) == self.worker_id:
                self._cache.delete(lease_key)
        except Exception:
            pass

    def _publish_worker_heartbeat(self) -> None:
        if not self.is_standalone_worker:
            return
        try:
            self._cache.set("wdos_agent_worker_active", self.worker_id, timeout=20)
        except Exception:
            pass

    def _fetch_active_rooms_sync(self) -> list[dict[str, str]]:
        if "test" not in sys.argv:
            close_old_connections()
        if not LiveKitAdapter.is_configured():
            return []
        cutoff = timezone.now() - datetime.timedelta(hours=4)
        qs = MeetingRoomSession.objects.filter(
            status__in=["LIVE", "WAITING"],
        ).order_by("-opened_at")[: self.max_rooms]
        rooms: list[dict[str, str]] = []
        for r in qs:
            # Never connect a translation bot to a room with zero admitted human participants
            if not r.participants.filter(admission_status="ADMITTED").exclude(participant_name="").exists():
                continue
            if r.opened_at and r.opened_at < cutoff:
                continue
            rooms.append(
                {
                    "id": str(r.id),
                    "room_code": r.room_code,
                    "session_name": r.session_name,
                }
            )
        return rooms

    async def _fetch_active_rooms(self) -> list[dict[str, str]]:
        return await sync_to_async(self._fetch_active_rooms_sync, thread_sensitive=True)()

    async def reconcile_once(self) -> int:
        self._publish_worker_heartbeat()
        loop = asyncio.get_running_loop()
        now_mono = time.monotonic()
        active_rooms = await self._fetch_active_rooms()
        active_ids = {r["id"] for r in active_rooms}

        # Stop bots for rooms that have ended, lost lease, are unhealthy, or have 0 human participants for >60s
        for room_id in list(self.bots.keys()):
            bot = self.bots[room_id]
            remote_humans = 0
            if bot.room is not None:
                try:
                    remote_humans = sum(
                        1 for p in bot.room.remote_participants.values()
                        if not getattr(p, "identity", "").startswith(BOT_IDENTITY_PREFIX)
                    )
                except Exception:
                    remote_humans = 1
            if remote_humans == 0:
                empty_since = getattr(bot, "_empty_since", 0.0) or now_mono
                bot._empty_since = empty_since
                idle_too_long = (now_mono - empty_since) > 60.0
            else:
                bot._empty_since = 0.0
                idle_too_long = False

            if room_id not in active_ids or not bot.is_healthy() or idle_too_long or not self._acquire_or_renew_room_lease(room_id):
                await bot.stop()
                self._release_room_lease(room_id)
                self.bots.pop(room_id, None)
                if idle_too_long:
                    # Wait 30s before re-probing an idle room
                    self._room_backoff[room_id] = (1, now_mono + 30.0)

        # Start bots for newly active rooms where this worker acquires the distributed lease
        for r_info in active_rooms:
            room_id = r_info["id"]
            if room_id not in self.bots:
                fail_count, retry_at = self._room_backoff.get(room_id, (0, 0.0))
                if now_mono < retry_at:
                    continue
                if not self._acquire_or_renew_room_lease(room_id):
                    continue
                bot = RoomTranslationBot(
                    room_session_id=room_id,
                    room_code=r_info["room_code"],
                    session_name=r_info["session_name"],
                    loop=loop,
                )
                ok = await bot.start()
                if ok:
                    self._room_backoff.pop(room_id, None)
                    self.bots[room_id] = bot
                else:
                    self._release_room_lease(room_id)
                    next_fails = fail_count + 1
                    backoff_sec = min(300.0, 30.0 * (2 ** (next_fails - 1)))
                    self._room_backoff[room_id] = (next_fails, now_mono + backoff_sec)

        return len(self.bots)

    async def shutdown(self) -> None:
        for room_id, bot in list(self.bots.items()):
            await bot.stop()
            self._release_room_lease(room_id)
        self.bots.clear()


_SUPERVISOR_DAEMON_LOCK = threading.Lock()
_SUPERVISOR_DAEMON_STARTED = False
_SUPERVISOR_WAKE_EVENT = threading.Event()


def ensure_translation_supervisor_daemon() -> bool:
    """
    Ensures the LiveKit TranslationAgentSupervisor is running when no dedicated external
    translation worker (`run_translation_agent` / `run_livekit_translation_worker`) is active,
    and wakes it on room join events instead of tight-polling when idle.
    """
    global _SUPERVISOR_DAEMON_STARTED
    _SUPERVISOR_WAKE_EVENT.set()
    if _SUPERVISOR_DAEMON_STARTED:
        return True
    if "test" in sys.argv:
        return False
    if getattr(settings, "LIVEKIT_WORKER_DEDICATED", False) or os.environ.get("WDOS_EXTERNAL_TRANSLATION_WORKER", "").strip().lower() in ("1", "true", "yes"):
        return False
    try:
        from django.core.cache import cache
        if cache.get("wdos_agent_worker_active"):
            return False
    except Exception:
        pass
    if rtc is None or not LiveKitAdapter.is_configured():
        return False

    with _SUPERVISOR_DAEMON_LOCK:
        if _SUPERVISOR_DAEMON_STARTED:
            return True
        _SUPERVISOR_DAEMON_STARTED = True

        def _daemon_runner() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            supervisor = TranslationAgentSupervisor(is_standalone_worker=False)

            async def _run_forever() -> None:
                while True:
                    active_bots = 0
                    try:
                        from django.core.cache import cache
                        if cache.get("wdos_agent_worker_active"):
                            await supervisor.shutdown()
                            await loop.run_in_executor(None, _SUPERVISOR_WAKE_EVENT.wait, 30.0)
                            _SUPERVISOR_WAKE_EVENT.clear()
                            continue
                        active_bots = await supervisor.reconcile_once()
                    except Exception as exc:
                        logger.debug("Translation supervisor reconcile error: %s", exc)
                    wait_sec = 12.0 if active_bots > 0 else 60.0
                    await loop.run_in_executor(None, _SUPERVISOR_WAKE_EVENT.wait, wait_sec)
                    _SUPERVISOR_WAKE_EVENT.clear()

            try:
                loop.run_until_complete(_run_forever())
            except Exception:
                pass

        t = threading.Thread(target=_daemon_runner, name="wdos-livekit-translation-daemon", daemon=True)
        t.start()
        return True

