from __future__ import annotations
import asyncio
from typing import Callable, Awaitable

from .base_channel import BaseChannel, ChannelMessage
from data_layer.connectors.odoo_rpc import OdooClient
from gateway.rate_limiter import RateLimiter, get_rate_limiter
from gateway.idempotency import get_idempotency_guard, should_dedup

LIVECHAT_POLL_INTERVAL = 5
BOT_AUTHOR_PREFIX = "SmartShop AI"

class LiveChatChannel(BaseChannel):
    """
    Odoo Live Chat Channel — poll-based integration.
    """

    def __init__(self):
        super().__init__(name="livechat")
        self._odoo = OdooClient()
        self._processed_msg_ids: set[int] = set()
        self._channel_watermarks: dict[int, int] = {}
        self._rate_limiter: RateLimiter = get_rate_limiter()
        self._idempotency = get_idempotency_guard()

    async def send_message(
        self,
        user_id: str,
        text: str,
        metadata: dict | None = None
    ) -> bool:
        channel_id = int(user_id)
        try:
            await asyncio.to_thread(
                lambda: self._odoo.execute_method(
                    "discuss.channel", "message_post",
                    [channel_id],
                    **{
                        "body": text.replace("\n", "<br/>"),
                        "message_type": "comment",
                        "subtype_xmlid": "mail.mt_comment"
                    }
                )
            )
            return True
        except Exception as e:
            print(f"   ❌ [LIVECHAT SEND] channel {channel_id}: {e}")
            return False

    async def run(self, message_handler: Callable[[ChannelMessage], Awaitable[str]]) -> None:
        self._running = True
        print(f"✅ [{self.name.upper()} CHANNEL] Polling Odoo Live Chat every {LIVECHAT_POLL_INTERVAL}s")

        while self._running:
            try:
                await self._poll_and_dispatch(message_handler)
            except Exception as e:
                print(f"   ⚠️ [LIVECHAT POLL ERROR]: {e}")
            await asyncio.sleep(LIVECHAT_POLL_INTERVAL)

    async def _poll_and_dispatch(
        self,
        message_handler: Callable[[ChannelMessage], Awaitable[str]]
    ) -> None:
        channels = await asyncio.to_thread(
            lambda: self._odoo.search_read(
                "discuss.channel",
                domain=[
                    ["channel_type", "=", "livechat"],
                    ["is_member", "=", True]
                ],
                fields=["id", "name", "channel_type"],
                limit=50
            )
        )

        for channel in channels:
            channel_id = channel["id"]
            watermark = self._channel_watermarks.get(channel_id, 0)

            messages = await asyncio.to_thread(
                lambda cid=channel_id, wm=watermark: self._odoo.search_read(
                    "mail.message",
                    domain=[
                        ["res_id", "=", cid],
                        ["model", "=", "discuss.channel"],
                        ["id", ">", wm],
                        ["message_type", "=", "comment"],
                        ["author_id.name", "not ilike", BOT_AUTHOR_PREFIX]
                    ],
                    fields=["id", "body", "author_id", "date", "partner_ids"],
                    limit=10
                )
            )

            for msg in messages:
                msg_id = msg["id"]
                if msg_id in self._processed_msg_ids:
                    continue
                self._processed_msg_ids.add(msg_id)
                self._channel_watermarks[channel_id] = max(
                    self._channel_watermarks.get(channel_id, 0),
                    msg_id
                )

                author = msg.get("author_id", [0, "Unknown"])
                partner_id = str(author[0]) if isinstance(author, list) else "0"
                author_name = author[1] if isinstance(author, list) else "Unknown"

                body = self._strip_html(msg.get("body", ""))
                if not body or len(body) < 2:
                    continue

                # Lọc tuyệt đối để chặn Self-Echo Loop trong Odoo LiveChat
                if any(body.startswith(p) for p in ["⛔", "✅", "❌", "🤖", "⚠️", "💬"]) or "TRUY CẬP BỊ TỪ CHỐI" in body:
                    continue

                print(f"   💬 [LIVECHAT] Channel {channel_id} | {author_name}: {body[:50]}")

                # Rate limiting
                allowed, rate_info = self._rate_limiter.is_allowed(str(channel_id))
                if not allowed:
                    await self.send_message(str(channel_id), rate_info["message"])
                    continue

                # Idempotency check
                if should_dedup(body):
                    is_dup, cached = self._idempotency.check(str(channel_id), body)
                    if is_dup and cached:
                        await self.send_message(str(channel_id), cached)
                        continue

                channel_msg = ChannelMessage(
                    channel="livechat",
                    user_id=str(channel_id),
                    text=body,
                    raw=msg,
                    metadata={
                        "channel_id": channel_id,
                        "partner_id": partner_id,
                        "author_name": author_name,
                        "msg_id": msg_id
                    }
                )

                try:
                    response = await message_handler(channel_msg)
                    if response:
                        await self.send_message(str(channel_id), response)
                        if should_dedup(body):
                            self._idempotency.store(str(channel_id), body, response)
                except Exception as ex:
                    print(f"   ❌ [LIVECHAT HANDLER]: {ex}")

        if len(self._processed_msg_ids) > 10000:
            sorted_ids = sorted(self._processed_msg_ids)
            self._processed_msg_ids = set(sorted_ids[-5000:])

    @staticmethod
    def _strip_html(html: str) -> str:
        import re
        clean = re.sub(r"<[^>]+>", "", html)
        return clean.strip()
