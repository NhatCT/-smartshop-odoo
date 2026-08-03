"""
Base Channel — Abstract Interface cho tất cả SmartShop Communication Channels.
Mọi kênh (Telegram, Odoo Live Chat, Webhook) đều kế thừa BaseChannel.

Channel Adapter Pattern — thêm kênh mới chỉ cần implement 3 method:
- receive_message(): Nhận tin nhắn từ kênh
- send_message(): Gửi phản hồi về kênh
- run(): Event loop chính của kênh
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChannelMessage:
    """
    Tin nhắn chuẩn hóa từ bất kỳ kênh nào.
    Tất cả channels đều convert về ChannelMessage trước khi đưa vào Gateway.
    """
    channel: str              # "telegram" | "livechat" | "webhook" | "slack"
    user_id: str              # ID duy nhất trong channel (Telegram ID, Odoo partner ID, ...)
    text: str                 # Nội dung tin nhắn
    raw: dict = field(default_factory=dict)  # Raw payload từ channel
    metadata: dict = field(default_factory=dict)  # Extra context (thread_id, chat_id, ...)


class BaseChannel(ABC):
    """
    Abstract Channel Adapter cho SmartShop Multi-Channel Gateway.
    
    Để thêm Slack/Teams/SMS sau này, chỉ cần:
    1. Tạo class SlackChannel(BaseChannel)
    2. Implement 3 abstract methods
    3. Đăng ký vào app_entrypoint.py
    """

    def __init__(self, name: str):
        self.name = name
        self._running = False

    @abstractmethod
    async def send_message(self, user_id: str, text: str, metadata: dict | None = None) -> bool:
        """
        Gửi phản hồi về kênh.
        Returns: True nếu gửi thành công.
        """
        ...

    @abstractmethod
    async def run(self, message_handler) -> None:
        """
        Event loop chính: liên tục nhận và dispatch messages.
        message_handler: async callable(ChannelMessage) → str (response text)
        """
        ...

    def stop(self) -> None:
        """Dừng event loop của channel."""
        self._running = False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}' running={self._running}>"
