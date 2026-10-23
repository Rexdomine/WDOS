import base64
import hashlib
import hmac
import json
import time
from django.conf import settings

try:
    import jwt
except ImportError:  # pragma: no cover
    jwt = None


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _encode_hs256_fallback(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


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

        if jwt is not None:
            token = jwt.encode(payload, sdk_secret, algorithm="HS256")
            return token if isinstance(token, str) else token.decode("utf-8")
        return _encode_hs256_fallback(payload, sdk_secret)

    @staticmethod
    def decode_token(token: str) -> dict:
        sdk_secret = getattr(settings, "ZOOM_SDK_SECRET", "")
        if jwt is not None and sdk_secret:
            return jwt.decode(token, sdk_secret, algorithms=["HS256"])
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed JWT token.")
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
