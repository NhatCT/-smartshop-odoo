"""
SmartShop AI Gateway — Tầng Kênh Giao tiếp
Layer 1: Multi-Channel Interface
  Telegram (24/7) + Odoo Live Chat + API Webhook
"""
from .base_channel import BaseChannel, ChannelMessage
from .telegram_channel import TelegramChannel
from .webhook_channel import WebhookChannel
from .livechat_channel import LiveChatChannel

__all__ = ["BaseChannel", "ChannelMessage", "TelegramChannel", "WebhookChannel", "LiveChatChannel"]
