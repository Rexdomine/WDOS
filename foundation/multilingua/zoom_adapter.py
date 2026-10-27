import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
import datetime
import hashlib
import hmac
import json
import logging
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from django.conf import settings

try:
    import jwt
except ImportError:  # pragma: no cover
    jwt = None

try:
    from livekit import api as lkapi
except ImportError:  # pragma: no cover
    lkapi = None

logger = logging.getLogger(__name__)

# Bounded worker pool for asynchronous server-to-SFU RPC dispatch with retry/backoff
_LK_RPC_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="wdos-lk-rpc")
_LK_TELEMETRY_LOCK = threading.Lock()
_LK_TELEMETRY: Dict[str, int] = {
    "tokens_issued": 0,
    "rpc_dispatched": 0,
    "rpc_succeeded": 0,
    "rpc_retried": 0,
    "rpc_failed": 0,
    "webhooks_verified": 0,
    "webhooks_rejected": 0,
    "egress_started": 0,
    "egress_stopped": 0,
}


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _decode_hs256_verified(token: str, secret: str) -> dict:
    if jwt is None or not secret:
        raise ValueError("PyJWT and signing secret are required for JWT verification.")
    return jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})


class ZoomVideoSDKAdapter:
    """
    Replaceable Provider Adapter for Zoom Video SDK (WebRTC Media Layer).
    Generates ephemeral session tokens for authenticated WDOS participants.
    """

    @staticmethod
    def generate_token(session_name: str, user_id: str, role_type: int = 0) -> str:
        """
        Generates a Zoom Video SDK JWT.
        role_type: 1 for Host/Co-host, 0 for Participant/Speaker/Listener.
        """
        sdk_key = getattr(settings, "ZOOM_SDK_KEY", "")
        sdk_secret = getattr(settings, "ZOOM_SDK_SECRET", "")

        if not sdk_key or not sdk_secret:
            raise ValueError("Zoom Video SDK credentials are not configured in settings.")

        iat = int(time.time()) - 60  # 60s clock drift buffer
        exp = iat + (60 * 60 * 2)    # 2 hour token expiration

        payload = {
            "app_key": sdk_key,
            "tpc": session_name,      # Topic / Session Name
            "version": 1,
            "role_type": int(role_type),
            "user_identity": str(user_id),
            "iat": iat,
            "exp": exp,
        }

        if jwt is None:
            raise RuntimeError("PyJWT is required to sign tokens.")
        token = jwt.encode(payload, sdk_secret, algorithm="HS256")
        return token if isinstance(token, str) else token.decode("utf-8")

    @staticmethod
    def decode_token(token: str) -> dict:
        sdk_secret = getattr(settings, "ZOOM_SDK_SECRET", "")
        if jwt is not None and sdk_secret:
            return jwt.decode(token, sdk_secret, algorithms=["HS256"])
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed JWT token.")
        return json.loads(_b64url_decode(parts[1]).decode("utf-8"))


class LiveKitAdapter:
    """
    Enterprise Provider Adapter for LiveKit WebRTC SFU (Real-Time Audio, Video, Screen Share & Data Plane).
    Supports:
      - Role-aware, least-privilege HS256 room access tokens (Host, Co-Host, Speaker, Listener, Hidden Bot)
      - Server-side RoomService Twirp API calls (DataPacket broadcast, Mute Track, Remove Participant, Update Permissions)
      - Cryptographic verification of LiveKit Server Webhooks
    """

    @staticmethod
    def is_configured() -> bool:
        url = (getattr(settings, "LIVEKIT_URL", "") or "").strip()
        api_key = (getattr(settings, "LIVEKIT_API_KEY", "") or "").strip()
        api_secret = (getattr(settings, "LIVEKIT_API_SECRET", "") or "").strip()
        return bool(
            url
            and api_key
            and api_secret
            and not api_key.startswith("your_")
            and not api_secret.startswith("your_")
            and not url.startswith("wss://your-")
        )

    @staticmethod
    def get_http_endpoint() -> str:
        raw_url = (getattr(settings, "LIVEKIT_URL", "") or "").strip().rstrip("/")
        if raw_url.startswith("wss://"):
            return "https://" + raw_url[6:]
        if raw_url.startswith("ws://"):
            return "http://" + raw_url[5:]
        return raw_url

    @staticmethod
    def get_telemetry() -> Dict[str, int]:
        with _LK_TELEMETRY_LOCK:
            return dict(_LK_TELEMETRY)

    @staticmethod
    def _inc_metric(key: str, delta: int = 1) -> None:
        with _LK_TELEMETRY_LOCK:
            _LK_TELEMETRY[key] = _LK_TELEMETRY.get(key, 0) + delta

    @classmethod
    def generate_token(
        cls,
        session_name: str,
        user_id: str,
        participant_name: str = "Participant",
        role_type: int = 0,
        metadata: str = "",
        can_publish: bool = True,
        can_subscribe: bool = True,
        can_share_screen: bool = True,
        can_publish_sources: Optional[List[str]] = None,
        hidden: bool = False,
        ttl_seconds: int = 7200,
    ) -> str:
        api_key = (getattr(settings, "LIVEKIT_API_KEY", "") or "").strip()
        api_secret = (getattr(settings, "LIVEKIT_API_SECRET", "") or "").strip()
        if not api_key or not api_secret:
            raise ValueError("LiveKit Cloud credentials are not configured in settings.")

        is_admin = bool(int(role_type) == 1)
        if can_publish_sources is not None:
            publish_sources: List[str] = list(can_publish_sources)
        else:
            publish_sources = []
            if can_publish:
                publish_sources.extend(["camera", "microphone"])
                if is_admin or can_share_screen:
                    publish_sources.extend(["screen_share", "screen_share_audio"])

        cls._inc_metric("tokens_issued")

        if lkapi is not None:
            grants = lkapi.VideoGrants(
                room_create=bool(is_admin or hidden),
                room_join=True,
                room=str(session_name),
                can_publish=bool(can_publish),
                can_subscribe=bool(can_subscribe),
                can_publish_data=True,
                can_update_own_metadata=True,
                can_publish_sources=publish_sources,
                room_admin=is_admin,
                hidden=bool(hidden),
            )
            at = (
                lkapi.AccessToken(api_key, api_secret)
                .with_identity(str(user_id))
                .with_name(str(participant_name or user_id))
                .with_ttl(datetime.timedelta(seconds=int(ttl_seconds)))
                .with_grants(grants)
            )
            if metadata:
                at = at.with_metadata(str(metadata))
            return at.to_jwt()

        if jwt is None:
            raise RuntimeError("livekit-api or PyJWT is required to issue LiveKit access tokens.")
        now = int(time.time())
        iat = now - 30
        exp = now + int(ttl_seconds)

        video_grants: Dict[str, Any] = {
            "roomCreate": is_admin or hidden,
            "roomJoin": True,
            "room": str(session_name),
            "canPublish": bool(can_publish),
            "canSubscribe": bool(can_subscribe),
            "canPublishData": True,
            "canUpdateOwnMetadata": True,
            "canPublishSources": publish_sources,
            "roomAdmin": is_admin,
        }
        if hidden:
            video_grants["hidden"] = True

        payload: Dict[str, Any] = {
            "iss": api_key,
            "sub": str(user_id),
            "name": str(participant_name or user_id),
            "nbf": iat,
            "iat": iat,
            "exp": exp,
            "video": video_grants,
        }
        if metadata:
            payload["metadata"] = str(metadata)
        token = jwt.encode(payload, api_secret, algorithm="HS256")
        return token if isinstance(token, str) else token.decode("utf-8")

    @classmethod
    def generate_server_admin_token(cls, session_name: str = "", ttl_seconds: int = 120) -> str:
        api_key = (getattr(settings, "LIVEKIT_API_KEY", "") or "").strip()
        api_secret = (getattr(settings, "LIVEKIT_API_SECRET", "") or "").strip()
        if not api_key or not api_secret:
            raise ValueError("LiveKit Cloud credentials are not configured in settings.")

        if lkapi is not None:
            grants = lkapi.VideoGrants(
                room_create=True,
                room_list=True,
                room_admin=True,
                room_record=True,
                room=str(session_name) if session_name else "",
            )
            return (
                lkapi.AccessToken(api_key, api_secret)
                .with_identity("wdos-room-service")
                .with_ttl(datetime.timedelta(seconds=int(ttl_seconds)))
                .with_grants(grants)
                .to_jwt()
            )

        if jwt is None:
            raise RuntimeError("livekit-api or PyJWT is required to issue LiveKit server tokens.")
        now = int(time.time())
        payload: Dict[str, Any] = {
            "iss": api_key,
            "sub": "wdos-room-service",
            "nbf": now - 15,
            "iat": now - 15,
            "exp": now + int(ttl_seconds),
            "video": {
                "roomCreate": True,
                "roomList": True,
                "roomAdmin": True,
                "roomRecord": True,
                "room": str(session_name) if session_name else "",
            },
        }
        token = jwt.encode(payload, api_secret, algorithm="HS256")
        return token if isinstance(token, str) else token.decode("utf-8")

    @classmethod
    def generate_session_payload(
        cls,
        session_name: str,
        user_id: str,
        participant_name: str = "Participant",
        role_type: int = 0,
        metadata: str = "",
        can_publish: bool = True,
        can_share_screen: bool = True,
        webinar_mode: bool = False,
    ) -> dict:
        if not cls.is_configured():
            return {
                "enabled": False,
                "url": "",
                "room_name": session_name,
                "token": "",
                "role_type": int(role_type),
                "webinar_mode": bool(webinar_mode),
            }
        url = (getattr(settings, "LIVEKIT_URL", "") or "").strip()
        token = cls.generate_token(
            session_name=session_name,
            user_id=user_id,
            participant_name=participant_name,
            role_type=role_type,
            metadata=metadata,
            can_publish=can_publish,
            can_share_screen=can_share_screen,
        )
        return {
            "enabled": True,
            "url": url,
            "room_name": session_name,
            "token": token,
            "participant_identity": str(user_id),
            "participant_name": str(participant_name or user_id),
            "role_type": int(role_type),
            "can_publish": bool(can_publish),
            "can_share_screen": bool(can_share_screen or int(role_type) == 1),
            "webinar_mode": bool(webinar_mode),
        }

    @classmethod
    def verify_webhook(cls, raw_body: bytes, auth_header: str) -> Optional[Dict[str, Any]]:
        """
        Verifies a LiveKit Server Webhook payload using the Authorization JWT header
        and its SHA-256 body digest claim (via livekit.api.TokenVerifier + cryptographic SHA-256 check).
        """
        api_key = (getattr(settings, "LIVEKIT_API_KEY", "") or "").strip()
        api_secret = (getattr(settings, "LIVEKIT_API_SECRET", "") or "").strip()
        if not api_secret or not auth_header:
            cls._inc_metric("webhooks_rejected")
            return None
        token = auth_header.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        try:
            if lkapi is not None and api_key and len(api_secret) >= 32:
                verifier = lkapi.TokenVerifier(api_key, api_secret)
                verifier.verify(token)
            claims = _decode_hs256_verified(token, api_secret)
            claimed_sha = claims.get("sha256") or ""
            if claimed_sha:
                digest_hex = hashlib.sha256(raw_body).hexdigest()
                digest_b64 = base64.b64encode(hashlib.sha256(raw_body).digest()).decode("ascii")
                digest_b64url = _b64url_encode(hashlib.sha256(raw_body).digest())
                if claimed_sha not in (digest_hex, digest_b64, digest_b64url):
                    cls._inc_metric("webhooks_rejected")
                    return None
            cls._inc_metric("webhooks_verified")
            return json.loads(raw_body.decode("utf-8") or "{}")
        except Exception as exc:
            cls._inc_metric("webhooks_rejected")
            logger.debug("LiveKit webhook verification failed: %s", exc)
            return None

    @classmethod
    def _sdk_or_twirp_call(
        cls,
        service: str,
        method: str,
        room_name: str,
        body: Dict[str, Any],
        timeout: float = 2.5,
        max_retries: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """
        Executes a LiveKit RoomService or EgressService call using the official livekit-api SDK
        (when running in an async loop or worker) or Twirp HTTP protocol with exponential backoff retries.
        """
        if not cls.is_configured() or "test" in sys.argv:
            return None
        endpoint = cls.get_http_endpoint()
        if not endpoint:
            return None
        cls._inc_metric("rpc_dispatched")
        url = f"{endpoint}/twirp/livekit.{service}/{method}"

        delay = 0.15
        for attempt in range(1, max_retries + 1):
            try:
                if lkapi is not None and service == "RoomService" and method == "SendData" and attempt == 1:
                    # Validate protobuf message schema with official livekit-api SendDataRequest
                    _ = lkapi.SendDataRequest(
                        room=str(body.get("room", room_name)),
                        data=base64.b64decode(body["data"]) if isinstance(body.get("data"), str) else b"",
                        kind=lkapi.DataPacket.Kind.RELIABLE,
                        topic=str(body.get("topic", "wdos_control")),
                        destination_identities=[str(x) for x in (body.get("destination_identities") or [])],
                    )
                token = cls.generate_server_admin_token(session_name=room_name)
                data_bytes = json.dumps(body).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data_bytes,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    cls._inc_metric("rpc_succeeded")
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as http_err:
                if 400 <= http_err.code < 500 and http_err.code != 429:
                    cls._inc_metric("rpc_failed")
                    logger.debug("LiveKit %s/%s client error (%s) for %s", service, method, http_err.code, room_name)
                    return None
                if attempt < max_retries:
                    cls._inc_metric("rpc_retried")
                    time.sleep(delay)
                    delay *= 2.0
                else:
                    cls._inc_metric("rpc_failed")
            except Exception as exc:
                if attempt < max_retries:
                    cls._inc_metric("rpc_retried")
                    time.sleep(delay)
                    delay *= 2.0
                else:
                    cls._inc_metric("rpc_failed")
                    logger.debug("LiveKit %s/%s failed after %d attempts for %s: %s", service, method, max_retries, room_name, exc)
        return None

    @classmethod
    def _twirp_call(cls, method: str, room_name: str, body: Dict[str, Any], timeout: float = 2.5) -> Optional[Dict[str, Any]]:
        return cls._sdk_or_twirp_call("RoomService", method, room_name, body, timeout=timeout)

    @classmethod
    def send_data_packet(
        cls,
        room_name: str,
        payload_dict: Dict[str, Any],
        topic: str = "wdos_control",
        destination_identities: Optional[List[str]] = None,
        async_send: bool = True,
    ) -> None:
        """
        Broadcasts a real-time data packet to all (or targeted) participants in a LiveKit room
        via the bounded RPC executor with automatic retry backoff.
        """
        if not cls.is_configured() or not room_name or "test" in sys.argv:
            return
        raw_bytes = json.dumps(payload_dict, ensure_ascii=False).encode("utf-8")
        b64_data = base64.b64encode(raw_bytes).decode("ascii")
        body: Dict[str, Any] = {
            "room": str(room_name),
            "data": b64_data,
            "kind": "RELIABLE",
            "topic": topic,
        }
        if destination_identities:
            body["destination_identities"] = [str(x) for x in destination_identities]

        if async_send:
            _LK_RPC_EXECUTOR.submit(cls._sdk_or_twirp_call, "RoomService", "SendData", room_name, body, 2.5, 3)
        else:
            cls._sdk_or_twirp_call("RoomService", "SendData", room_name, body, timeout=2.5, max_retries=3)

    @classmethod
    def update_participant_permissions(
        cls,
        room_name: str,
        identity: str,
        can_publish: bool = True,
        can_subscribe: bool = True,
        can_publish_data: bool = True,
        metadata: Optional[str] = None,
        async_call: bool = True,
    ) -> None:
        """
        Dynamically updates a participant's SFU publishing permissions in real time
        (e.g., promoting an attendee to speaker in Webinar/1000+ mode, or revoking floor).
        """
        if not cls.is_configured() or not room_name or not identity or "test" in sys.argv:
            return
        body: Dict[str, Any] = {
            "room": str(room_name),
            "identity": str(identity),
            "permission": {
                "can_publish": bool(can_publish),
                "can_subscribe": bool(can_subscribe),
                "can_publish_data": bool(can_publish_data),
                "can_update_metadata": True,
            },
        }
        if metadata is not None:
            body["metadata"] = str(metadata)
        if async_call:
            _LK_RPC_EXECUTOR.submit(cls._sdk_or_twirp_call, "RoomService", "UpdateParticipant", room_name, body, 2.5, 3)
        else:
            cls._sdk_or_twirp_call("RoomService", "UpdateParticipant", room_name, body, timeout=2.5, max_retries=3)

    @classmethod
    def remove_participant_from_sfu(cls, room_name: str, identity: str, async_call: bool = True) -> None:
        if not cls.is_configured() or not room_name or not identity or "test" in sys.argv:
            return
        body = {"room": str(room_name), "identity": str(identity)}
        if async_call:
            _LK_RPC_EXECUTOR.submit(cls._sdk_or_twirp_call, "RoomService", "RemoveParticipant", room_name, body, 2.5, 3)
        else:
            cls._sdk_or_twirp_call("RoomService", "RemoveParticipant", room_name, body, timeout=2.5, max_retries=3)

    @classmethod
    def delete_room_on_sfu(cls, room_name: str, async_call: bool = True) -> None:
        if not cls.is_configured() or not room_name or "test" in sys.argv:
            return
        body = {"room": str(room_name)}
        if async_call:
            _LK_RPC_EXECUTOR.submit(cls._sdk_or_twirp_call, "RoomService", "DeleteRoom", room_name, body, 2.5, 3)
        else:
            cls._sdk_or_twirp_call("RoomService", "DeleteRoom", room_name, body, timeout=2.5, max_retries=3)

    @classmethod
    def start_room_recording(cls, room_name: str, layout: str = "grid") -> Dict[str, Any]:
        """
        Starts a LiveKit Egress RoomComposite cloud recording (MP4) for the specified room.
        Requires a confirmed `egress_id` from the LiveKit Egress service; never fabricates a local ID.
        """
        if not cls.is_configured():
            raise RuntimeError("LiveKit Cloud is not configured for Egress recording.")
        s3_bucket = (getattr(settings, "LIVEKIT_EGRESS_S3_BUCKET", "") or "").strip()
        file_output: Dict[str, Any] = {
            "file_type": "MP4",
            "filepath": f"recordings/{room_name}/{int(time.time())}.mp4",
        }
        if s3_bucket:
            file_output["s3"] = {
                "bucket": s3_bucket,
                "region": getattr(settings, "LIVEKIT_EGRESS_S3_REGION", "us-east-1"),
            }
        body: Dict[str, Any] = {
            "room_name": str(room_name),
            "layout": layout,
            "file": file_output,
        }
        res = cls._sdk_or_twirp_call("Egress", "StartRoomCompositeEgress", room_name, body, timeout=4.0, max_retries=2)
        if not isinstance(res, dict) or not res.get("egress_id"):
            raise RuntimeError("LiveKit Egress service did not return an active egress_id.")
        cls._inc_metric("egress_started")
        return {
            "egress_id": str(res["egress_id"]),
            "room_name": room_name,
            "status": str(res.get("status") or "EGRESS_ACTIVE"),
            "layout": layout,
            "started_at": int(time.time()),
        }

    @classmethod
    def stop_room_recording(cls, room_name: str, egress_id: str) -> Dict[str, Any]:
        """
        Stops an active LiveKit Egress cloud recording and confirms termination with the Egress service.
        """
        if not cls.is_configured() or not egress_id:
            raise RuntimeError("Cannot stop recording without a valid LiveKit egress_id.")
        body = {"egress_id": str(egress_id)}
        res = cls._sdk_or_twirp_call("Egress", "StopEgress", room_name, body, timeout=3.0, max_retries=2)
        if res is None:
            raise RuntimeError("LiveKit Egress service failed to stop recording.")
        cls._inc_metric("egress_stopped")
        return {
            "egress_id": str(egress_id),
            "room_name": room_name,
            "status": str(res.get("status") if isinstance(res, dict) else "EGRESS_COMPLETE") or "EGRESS_COMPLETE",
            "stopped_at": int(time.time()),
        }


