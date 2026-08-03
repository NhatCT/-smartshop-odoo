from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from fastapi import APIRouter, Request

from .base_channel import BaseChannel, ChannelMessage

webhook_router = APIRouter()
_message_handler: Callable[[ChannelMessage], Awaitable[str]] | None = None


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
