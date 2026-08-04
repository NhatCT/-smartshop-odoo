"""Gateway facade for auth, OTP, and approval tokens."""

from __future__ import annotations

import hashlib
import hmac
import os
import time

from gateway.config.constants import ROLE_TOOLS_MAP
from gateway.services.binding_service import get_bindings, save_bindings
from gateway.services.otp_service import OTPService
from gateway.services.permission_service import PermissionService

import secrets

_APPROVAL_SECRET = os.getenv("APPROVAL_TOKEN_SECRET") or os.getenv("ODOO_PASSWORD")
if not _APPROVAL_SECRET:
    _APPROVAL_SECRET = secrets.token_urlsafe(32)
    print("⚠️ [SecurityGateway] APPROVAL_TOKEN_SECRET is missing from env. Using secure ephemeral secret.")


def generate_approval_token(order_name: str, approver_id: str, ttl_seconds: int = 86400) -> str:
    """Generate a signed approval token for callback validation."""
    issued_at = str(int(time.time()))
    payload = f"{order_name}:{approver_id}:{issued_at}:{ttl_seconds}"
    signature = hmac.new(_APPROVAL_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    return f"{issued_at}.{ttl_seconds}.{signature}"


def verify_approval_token(order_name: str, approver_id: str, token: str) -> bool:
    """Verify approval token format, signature, and expiration."""
    try:
        issued_at_s, ttl_s, signature = token.split(".", 2)
        issued_at = int(issued_at_s)
        ttl_seconds = int(ttl_s)
    except Exception:
        return False

    if time.time() > issued_at + ttl_seconds:
        return False

    payload = f"{order_name}:{approver_id}:{issued_at}:{ttl_seconds}"
    expected = hmac.new(_APPROVAL_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    return hmac.compare_digest(signature, expected)


class SecurityGateway:
    def __init__(self) -> None:
        self.permission_service = PermissionService()
        self.otp_service = OTPService()

    def process_incoming_request(self, telegram_id: int | str) -> dict:
        return self.permission_service.process_incoming_request(telegram_id)

    def request_otp(self, telegram_id: int | str, email: str) -> tuple[bool, str]:
        return self.otp_service.request_otp(telegram_id, email)

    def verify_otp_and_bind(self, telegram_id: int | str, user_otp: str) -> tuple[bool, str]:
        return self.otp_service.verify_otp_and_bind(telegram_id, user_otp)


__all__ = [
    "SecurityGateway",
    "ROLE_TOOLS_MAP",
    "generate_approval_token",
    "verify_approval_token",
    "get_bindings",
    "save_bindings",
]
