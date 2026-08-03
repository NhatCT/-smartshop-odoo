"""
Fulfillment Agent — Tầng 3: Workflow Agents
Skill: Tạo đơn hàng, chốt sale, ghi Odoo Chatter, gửi xác nhận.
Pipeline position: LAST (Recommendation → Validation → Fulfillment)
"""

from __future__ import annotations
import asyncio
from typing import Any
import anthropic
import os

from .base_agent import BaseAgent, AgentResult
from data_layer.connectors.odoo_rpc import OdooClient

_anthropic_client = None


def _get_client():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _anthropic_client


CLAUDE_MODEL = "claude-haiku-4-5-20251001"

FULFILLMENT_SYSTEM_PROMPT = """\
Bạn là Fulfillment Agent của SmartShop Odoo 19.
Nhiệm vụ: Tạo đơn hàng (sale.order) theo yêu cầu.

QUY TRÌNH BẮT BUỘC khi tạo đơn:
1. Tìm partner_id qua search_records(model='res.partner', query=<tên khách>)
2. Tìm product_id qua search_records(model='product.product', query=<tên sản phẩm>)  
3. Tạo sale.order qua execute_method với các thông tin đầy đủ
4. Xác nhận đơn hàng nếu user yêu cầu "chốt đơn"
5. Trả kết quả dạng:
   ✅ Đơn hàng [TÊN] đã tạo thành công!
   • Khách hàng: [TÊN]
   • Sản phẩm: [DANH SÁCH]
   • Tổng tiền: [SỐ TIỀN] VNĐ
   • Trạng thái: [TRẠNG THÁI]

Luôn ghi nhật ký vào Odoo Chatter sau khi hoàn thành.
"""


class FulfillmentAgent(BaseAgent):
    """
    Fulfillment Agent: Tạo đơn hàng và chốt sale trên Odoo.
    Ghi Odoo Chatter để audit trail.
    """

    def __init__(self):
        super().__init__(name="fulfillment")
        self._odoo = OdooClient()
        self._tool_schemas = [
            {
                "name": "search_records",
                "description": "Search Odoo. model='res.partner' for customers, 'product.product' for products.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "query": {"type": "string"},
                        "fields": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["model"]
                }
            },
            {
                "name": "execute_method",
                "description": "Execute Odoo ORM method. Use to create sale.order, confirm orders.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "method": {"type": "string"},
                        "args": {"type": "array"},
                        "kwargs": {"type": "object"}
                    },
                    "required": ["model", "method"]
                },
                "cache_control": {"type": "ephemeral"}
            }
        ]

    async def run(
        self,
        user_id: str,
        user_text: str,
        user_info: dict,
        mcp_session: Any,
        context: dict | None = None,
    ) -> AgentResult:
        context = context or {}
        role = user_info.get("official_role", "viewer")
        full_name = user_info.get("user_info", {}).get("full_name", "")

        system_blocks = [
            {
                "type": "text",
                "text": f"{FULFILLMENT_SYSTEM_PROMPT}\nUser: {full_name} | Role: {role.upper()}",
                "cache_control": {"type": "ephemeral"}
            }
        ]

        messages = [{"role": "user", "content": user_text}]
        client = _get_client()
        order_id = None
        order_name = None

        for _ in range(5):  # Fulfillment có thể cần nhiều tool calls hơn
            response = await asyncio.to_thread(
                lambda: client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=800,
                    system=system_blocks,
                    tools=self._tool_schemas,
                    messages=messages
                )
            )

            if response.stop_reason == "end_turn":
                text = "".join(b.text for b in response.content if hasattr(b, "text"))

                # Ghi Odoo Chatter nếu đã tạo đơn
                if order_id:
                    await self._write_chatter(order_id, full_name, role, user_text, text)

                return AgentResult(
                    success=True,
                    response=text,
                    metadata={**context, "order_id": order_id, "order_name": order_name}
                )

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        try:
                            res = await mcp_session.call_tool(block.name, block.input or {})
                            output = res.content[0].text if res.content else "OK"
                            output = output[:2000] + "..." if len(output) > 2000 else output

                            # Capture order info từ response
                            if block.name == "execute_method" and "sale.order" in str(block.input):
                                try:
                                    import json
                                    data = json.loads(output) if isinstance(output, str) else output
                                    if isinstance(data, dict):
                                        order_id = data.get("id") or order_id
                                        order_name = data.get("name") or order_name
                                except Exception:
                                    pass
                        except Exception as ex:
                            output = f"Lỗi MCP: {ex}"

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": output
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                continue
            break

        return AgentResult(
            success=False,
            response="❌ Không thể hoàn tất tạo đơn hàng. Vui lòng thử lại.",
        )

    async def _write_chatter(
        self,
        order_id: int,
        user_name: str,
        role: str,
        query: str,
        result: str
    ) -> None:
        """Ghi audit trail vào Odoo Chatter (message_post)."""
        try:
            body = (
                f"<b>🤖 AI Fulfillment Agent — SmartShop</b><br/>"
                f"<b>Nhân viên:</b> {user_name} ({role})<br/>"
                f"<b>Yêu cầu:</b> {query[:200]}<br/>"
                f"<b>Kết quả:</b> Đơn hàng đã được tạo thành công."
            )
            await asyncio.to_thread(
                lambda: self._odoo.execute_method(
                    "sale.order", "message_post",
                    [order_id],
                    **{"body": body, "message_type": "comment", "subtype_xmlid": "mail.mt_note"}
                )
            )
        except Exception as e:
            print(f"   ⚠️ [CHATTER WRITE FAILED]: {e}")
