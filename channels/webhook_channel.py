from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from typing import Awaitable, Callable

from fastapi import APIRouter, Request

from .base_channel import BaseChannel, ChannelMessage

webhook_router = APIRouter()
_message_handler: Callable[[ChannelMessage], Awaitable[str]] | None = None

WEBHOOK_SECRET = os.getenv("N8N_APPROVAL_WEBHOOK_SECRET", "")
if not WEBHOOK_SECRET:
    print("⚠️ [WEBHOOK] N8N_APPROVAL_WEBHOOK_SECRET chưa được cấu hình — mọi request approval sẽ bị từ chối.")


def _verify_webhook_signature(payload: bytes, signature_header: str) -> bool:
    """Xác thực HMAC-SHA256 signature từ n8n (X-Webhook-Signature header)."""
    if not WEBHOOK_SECRET or not signature_header:
        return False
    expected = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature_header, expected)


class WebhookChannel(BaseChannel):
    def __init__(self):
        super().__init__(name="webhook")

    def set_handler(self, handler: Callable[[ChannelMessage], Awaitable[str]]) -> None:
        global _message_handler
        _message_handler = handler

    async def send_message(self, user_id: str, text: str, metadata: dict | None = None) -> bool:
        # Webhook là inbound-only trong bản hiện tại.
        return True

    async def run(self, message_handler) -> None:
        self.set_handler(message_handler)
        self._running = True
        while self._running:
            await asyncio.sleep(3600)

@webhook_router.post("/api/webhook/approval")
async def n8n_approval_callback(request: Request):
    # 🔐 Xác thực HMAC signature trước khi xử lý bất kỳ request nào
    raw_body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")
    if not _verify_webhook_signature(raw_body, signature):
        return {"status": "error", "message": "Invalid webhook signature"}, 401

    data = await request.json()
    action = data.get("action")  # "approve" or "reject"
    order_name = data.get("order_name")
    telegram_id = data.get("telegram_id")

    if action == "approve":
        # Truyền message đặc biệt vào luồng xử lý
        class DummyMsg:
            def __init__(self):
                self.user_id = telegram_id
                self.text = f"[MANAGER_APPROVED] Order: {order_name}"
                self.channel = "webhook"
                self.metadata = {}
        msg = DummyMsg()
        if _message_handler is None:
            return {"status": "error", "message": "Webhook handler chưa được khởi tạo"}
        await _message_handler(msg)
        return {"status": "ok", "message": "Approval sent to Claude"}
    else:
        return {"status": "ok", "message": "Order rejected"}
