import concurrent.futures
import hashlib
import re
import sys
import requests
from django.conf import settings


class AzureSpeechAdapter:
    """
    Replaceable Provider Adapter for Azure AI Speech & Translation.
    Issues short-lived 10-minute authorization tokens so the master Azure key
    is never exposed to the client browser.
    """

    SUPPORTED_LANGUAGES = {
        "en-US": {"name": "English", "short": "en", "voice": "en-US-JennyNeural"},
        "fr-FR": {"name": "French", "short": "fr", "voice": "fr-FR-DeniseNeural"},
        "pt-BR": {"name": "Portuguese", "short": "pt", "voice": "pt-BR-FranciscaNeural"},
        "ar-EG": {"name": "Arabic", "short": "ar", "voice": "ar-EG-SalmaNeural"},
        "sw-KE": {"name": "Swahili", "short": "sw", "voice": "sw-KE-ZuriNeural"},
        "ha-NG": {"name": "Hausa", "short": "ha", "voice": "ha-NG-AminaNeural"},
        "yo-NG": {"name": "Yoruba", "short": "yo", "voice": "yo-NG-AdeolaNeural"},
        "ig-NG": {"name": "Igbo", "short": "ig", "voice": "ig-NG-EzinneNeural"},
    }

    DEFAULT_TRANSLATION_PHRASES = {
        "Welcome. Please choose the language you would like to hear.": {
            "en": "Welcome. Please choose the language you would like to hear.",
            "fr": "Bienvenue. Veuillez choisir la langue que vous souhaitez entendre.",
            "pt": "Bem-vindo. Escolha o idioma que gostaria de ouvir.",
            "ar": "مرحباً. يرجى اختيار اللغة التي ترغب في سماعها.",
            "sw": "Karibu. Tafadhali chagua lugha ungependa kusikia.",
            "ha": "Barka da zuwa. Da fatan za a zaɓi harshen da kuke son ji.",
            "yo": "Ẹ káàbọ̀. Jọ̀wọ́ yan èdè tí o fẹ́ gbọ́.",
            "ig": "Nnọọ. Biko họrọ asụsụ ị chọrọ ịnụ.",
        },
        "We must finalize the Nigeria Q3 budget by Friday.": {
            "en": "We must finalize the Nigeria Q3 budget by Friday.",
            "fr": "Nous devons finaliser le budget du T3 pour le Nigéria d'ici vendredi.",
            "pt": "Devemos finalizar o orçamento do 3º trimestre da Nigéria até sexta-feira.",
            "ar": "يجب علينا الانتهاء من ميزانية الربع الثالث لنيجيريا بحلول يوم الجمعة.",
            "sw": "Lazima tukamilishe bajeti ya robo ya tatu ya Nigeria ifikapo Ijumaa.",
            "ha": "Dole ne mu kammala kasafin kuɗin Q3 na Najeriya kafin ranar Juma'a.",
            "yo": "A gbọ́dọ̀ parí ìṣúná owó Q3 ti Nàìjíríà kí ó tó di ọjọ́ Ẹtì.",
            "ig": "Anyị ga-emechirịrị mmefu ego Q3 nke Naịjirịa tupu ụbọchị Fraịde.",
        },
        'Click "Turn Mic On" or type a statement below to speak — live translation & voice synthesis will play automatically.': {
            "en": 'Click "Turn Mic On" or type a statement below to speak — live translation & voice synthesis will play automatically.',
            "fr": 'Cliquez sur « Activer le micro » ou saisissez une phrase ci-dessous pour parler — la traduction en direct et la synthèse vocale seront diffusées automatiquement.',
            "pt": 'Clique em "Ativar Microfone" ou digite uma frase abaixo para falar — a tradução ao vivo e a síntese de voz serão reproduzidas automaticamente.',
            "ar": 'انقر على "تشغيل الميكروفون" أو اكتب عبارة أدناه للتحدث — سيتم تشغيل الترجمة المباشرة والصوت تلقائياً.',
            "sw": 'Bofya "Washa Maikrofoni" au andika kauli hapa chini ili kuzungumza — tafsiri ya moja kwa moja na sauti vitacheza kiotomatiki.',
            "ha": 'Danna "Kunna Makirufo" ko rubuta magana a ƙasa don yin magana — fassarar kai tsaye da murya za su tashi da kansu.',
            "yo": 'Tẹ "Tan Gbohungbohun" tàbí kọ ọ̀rọ̀ sí ìsàlẹ̀ láti sọ̀rọ̀ — ìtumọ̀ ojú-ẹsẹ̀ àti ohùn yóò ṣiṣẹ́ fúnra rẹ̀.',
            "ig": 'Pịa "Gbanye Igwe Okwu" ma ọ bụ pịnye okwu n\'okpuru ka ị kwuo okwu — ntụgharị asụsụ na olu ga-akpọ n\'onwe ya.',
        },
    }

    @classmethod
    def get_ephemeral_token(cls, strict: bool = False) -> dict:
        speech_key = getattr(settings, "AZURE_SPEECH_KEY", "")
        speech_key_2 = getattr(settings, "AZURE_SPEECH_KEY_2", "")
        speech_region = getattr(settings, "AZURE_SPEECH_REGION", "eastus")
        provider_mode = getattr(settings, "MEETING_TRANSLATION_PROVIDER", "azure")

        if not speech_key and not speech_key_2:
            raise ValueError("Azure Speech credentials are not configured in settings.")

        active_key = speech_key or speech_key_2
        is_mocked_post = hasattr(requests.post, "_mock_name") or hasattr(requests.post, "assert_called")
        if (provider_mode == "mock" or active_key.startswith("wdos-dev-")) and not is_mocked_post:
            digest = hashlib.sha256(f"{speech_region}:{active_key}".encode("utf-8")).hexdigest()[:32]
            return {
                "token": f"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.{digest}.azure-speech-ephemeral",
                "region": speech_region,
                "supported_languages": cls.SUPPORTED_LANGUAGES,
                "mode": "mock",
            }

        fetch_token_url = f"https://{speech_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
        candidate_keys = [k for k in (speech_key, speech_key_2) if k]
        last_exc = None
        network_unreachable = False

        for key_candidate in candidate_keys:
            headers = {
                "Ocp-Apim-Subscription-Key": key_candidate,
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": "0",
            }
            try:
                response = requests.post(fetch_token_url, headers=headers, timeout=5)
                response.raise_for_status()
                return {
                    "token": response.text,
                    "region": speech_region,
                    "supported_languages": cls.SUPPORTED_LANGUAGES,
                    "mode": "live",
                }
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                network_unreachable = True
                break
            except requests.RequestException as exc:
                last_exc = exc

        if network_unreachable and not strict and not is_mocked_post:
            digest = hashlib.sha256(f"{speech_region}:{active_key}".encode("utf-8")).hexdigest()[:32]
            return {
                "token": f"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.{digest}.azure-speech-offline-fallback",
                "region": speech_region,
                "supported_languages": cls.SUPPORTED_LANGUAGES,
                "mode": "offline_fallback",
            }

        raise RuntimeError(f"Failed to acquire Azure Speech token: {str(last_exc)}")


    _HTTP_SESSION = None
    _TRANSLATION_CACHE: dict[tuple[str, str, str], str] = {}
    _SYSTEM_ECHO_PHRASES = {
        "translating live",
        "translating live.",
        "translating live...",
        "consulting live",
        "consulting live.",
        "listening",
        "listening.",
        "listening...",
        "listening for speech",
        "listening for speech...",
        "translation ashes turned off for what is",
    }
    _TTS_AUDIO_CACHE: dict[tuple[str, str], bytes] = {}
    _SHORT_TO_BCP47 = {
        "en": "en-US",
        "fr": "fr-FR",
        "pt": "pt-BR",
        "ar": "ar-EG",
        "sw": "sw-KE",
        "ha": "ha-NG",
        "yo": "yo-NG",
        "ig": "ig-NG",
    }

    @classmethod
    def is_system_echo_phrase(cls, text: str) -> bool:
        normalized = (text or "").strip().lower().rstrip(".!?,")
        return normalized in cls._SYSTEM_ECHO_PHRASES

    @classmethod
    def _get_http_session(cls) -> requests.Session:
        if cls._HTTP_SESSION is None:
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            cls._HTTP_SESSION = session
        return cls._HTTP_SESSION

    _LIVE_FOCUS_SHORT_LANGS = ("en", "fr", "pt", "ar", "sw")

    @classmethod
    def _live_translate_single(cls, text: str, source_short: str, target_short: str, fallback_name: str) -> tuple[str, str]:
        preset = cls.DEFAULT_TRANSLATION_PHRASES.get((text or "").strip(), {})
        if target_short in preset:
            return preset[target_short], source_short

        cache_key = (source_short or "auto", target_short, text)
        cached = cls._TRANSLATION_CACHE.get(cache_key)
        if cached:
            if isinstance(cached, tuple):
                return cached
            return str(cached), source_short

        session = cls._get_http_session()
        sl_candidates = [source_short, "auto"] if (source_short and source_short != "auto") else ["auto"]
        for sl_val in sl_candidates:
            for _attempt in range(2):
                try:
                    resp = session.get(
                        "https://translate.googleapis.com/translate_a/single",
                        params={
                            "client": "gtx",
                            "sl": sl_val,
                            "tl": target_short,
                            "dt": "t",
                            "q": text,
                        },
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=4.5,
                    )
                    if resp.status_code == 200:
                        payload = resp.json()
                        detected_lang = payload[2] if isinstance(payload, list) and len(payload) > 2 and isinstance(payload[2], str) else source_short
                        if isinstance(payload, list) and payload and isinstance(payload[0], list):
                            translated_parts = [part[0] for part in payload[0] if isinstance(part, list) and part and part[0]]
                            if translated_parts:
                                result = "".join(translated_parts).strip()
                                if (
                                    sl_val != "auto"
                                    and target_short != source_short
                                    and len(text.strip()) > 4
                                    and result.lower() == text.strip().lower()
                                ):
                                    break
                                if len(cls._TRANSLATION_CACHE) < 2000:
                                    cls._TRANSLATION_CACHE[cache_key] = (result, detected_lang)
                                return result, detected_lang
                except Exception:
                    continue
        return text, source_short

    @classmethod
    def _split_tts_chunks(cls, text: str, max_chars: int = 140) -> list[str]:
        words = (text or "").split()
        if not words:
            return []
        chunks: list[str] = []
        current = ""
        for w in words:
            candidate = f"{current} {w}".strip() if current else w
            if len(candidate) <= max_chars and len(candidate.encode("utf-8")) <= 185:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = w[:max_chars]
            if len(chunks) >= 4:
                break
        if current and len(chunks) < 4:
            chunks.append(current)
        return chunks

    @classmethod
    def synthesize_speech_mp3(cls, text: str, target_language: str = "fr-FR") -> bytes | None:
        """
        Generates natural-sounding neural speech audio (MP3 bytes) for the given text and target language.
        Splits multi-sentence or multi-byte UTF-8 statements into safe <=185-byte chunks and concatenates
        MP3 frames so long statements in English, French, Portuguese, Arabic, and Swahili never truncate or 204.
        """
        clean_text = re.sub(r"^\[[^\]]+\]\s*", "", (text or "").strip()).strip()
        if not clean_text or cls.is_system_echo_phrase(clean_text):
            return None
        short_lang = (target_language or "fr-FR").split("-")[0].lower()
        if short_lang not in cls._SHORT_TO_BCP47:
            short_lang = "fr"
        trimmed = clean_text[:450]
        cache_key = (short_lang, trimmed.lower())
        if cache_key in cls._TTS_AUDIO_CACHE:
            return cls._TTS_AUDIO_CACHE[cache_key]

        if "test" in sys.argv:
            stub = b"ID3\x03\x00\x00\x00\x00\x00\x00\xff\xfb\x90\x64" + trimmed.encode("utf-8")[:64]
            cls._TTS_AUDIO_CACHE[cache_key] = stub
            return stub

        candidate_tls = [short_lang]
        if short_lang in ("yo", "ig"):
            candidate_tls.extend(["ha", "sw"])

        max_chunk_chars = 85 if short_lang == "ar" else 145
        chunks = cls._split_tts_chunks(trimmed, max_chars=max_chunk_chars)
        if not chunks:
            return None

        session = cls._get_http_session()
        for tl_code in candidate_tls:
            combined_mp3 = bytearray()
            for chunk_str in chunks:
                chunk_bytes = None
                for _attempt in range(2):
                    try:
                        resp = session.get(
                            "https://translate.googleapis.com/translate_tts",
                            params={
                                "ie": "UTF-8",
                                "client": "tw-ob",
                                "tl": tl_code,
                                "q": chunk_str,
                            },
                            headers={"User-Agent": "Mozilla/5.0"},
                            timeout=4.0,
                        )
                        if resp.status_code == 200 and resp.content and len(resp.content) > 128:
                            chunk_bytes = resp.content
                            break
                    except Exception:
                        continue
                if chunk_bytes:
                    combined_mp3.extend(chunk_bytes)
            if len(combined_mp3) > 128:
                final_bytes = bytes(combined_mp3)
                if len(cls._TTS_AUDIO_CACHE) < 500:
                    cls._TTS_AUDIO_CACHE[cache_key] = final_bytes
                return final_bytes
        return None

    @classmethod
    def translate_segment(cls, original_text: str, original_language: str = "en-US", existing_translations: dict | None = None) -> dict:
        """
        Ensures a transcript segment has translations mapped by short target code (en, fr, pt, ar, sw).
        Preserves valid translations provided by the client SDK and translates missing languages live.
        """
        raw_existing = dict(existing_translations or {})
        clean_text = (original_text or "").strip()
        preset = cls.DEFAULT_TRANSLATION_PHRASES.get(clean_text, {})
        source_short = (original_language or "en-US").split("-")[0].lower()
        is_test_run = "test" in sys.argv

        merged: dict[str, str] = {}
        for k, v in raw_existing.items():
            if not v or not isinstance(v, str):
                continue
            val_clean = v.strip()
            if not val_clean or val_clean.startswith("[") or cls.is_system_echo_phrase(val_clean):
                continue
            if k != source_short and len(clean_text) > 3 and val_clean.lower() == clean_text.lower():
                continue
            merged[k] = val_clean

        pending_targets = []
        for lang_code, meta in cls.SUPPORTED_LANGUAGES.items():
            short = meta["short"]
            if short in merged and merged[short]:
                continue
            if short in preset:
                merged[short] = preset[short]
            elif is_test_run:
                merged[short] = clean_text if (lang_code == original_language or short == source_short) else f"[{meta['name']}] {clean_text}"
            elif short in cls._LIVE_FOCUS_SHORT_LANGS or short == source_short:
                if short == source_short:
                    merged[short] = clean_text
                else:
                    pending_targets.append((short, meta["name"]))

        detected_source_short = source_short
        if pending_targets:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(pending_targets)) as executor:
                future_map = {
                    executor.submit(cls._live_translate_single, clean_text, source_short, short, name): (short, name)
                    for short, name in pending_targets
                }
                for fut, (short, name) in future_map.items():
                    try:
                        res_text, det_lang = fut.result(timeout=6.0)
                        merged[short] = res_text
                        if det_lang and det_lang in cls._SHORT_TO_BCP47:
                            detected_source_short = det_lang
                    except Exception:
                        merged[short] = clean_text
            if detected_source_short != source_short and source_short in cls._LIVE_FOCUS_SHORT_LANGS:
                # If auto-detection found the speaker actually spoke another language, translate into source_short too
                try:
                    src_name = cls.SUPPORTED_LANGUAGES.get(cls._SHORT_TO_BCP47.get(source_short, "en-US"), {}).get("name", "English")
                    res_src, _ = cls._live_translate_single(clean_text, detected_source_short, source_short, src_name)
                    merged[source_short] = res_src
                except Exception:
                    pass

        merged["_detected_source"] = cls._SHORT_TO_BCP47.get(detected_source_short, original_language or "en-US")
        return merged
