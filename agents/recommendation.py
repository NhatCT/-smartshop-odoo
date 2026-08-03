"""
Recommendation Agent — Tầng 3: Workflow Agents
Skill: Tìm kiếm sản phẩm, kiểm kho, tra giá, tính Sales Velocity.
Pipeline position: FIRST (Recommendation → Validation → Fulfillment)
"""

from __future__ import annotations
import asyncio
from typing import Any
import anthropic
import os

from .base_agent import BaseAgent, AgentResult

# Lazy import để tránh circular
_anthropic_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _anthropic_client


CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# System prompt tối ưu cho Recommendation Agent
RECOMMENDATION_SYSTEM_PROMPT = """\
Bạn là Recommendation Agent của SmartShop Odoo 19.
Nhiệm vụ: Tra cứu sản phẩm, kiểm kho và tư vấn.

LUẬT BẮT BUỘC:
1. Khi user hỏi sản phẩm/giá/tồn kho → GỌI NGAY `search_records` với:
   - model='product.product'
   - query=<từ khóa>
   - fields=['name','default_code','qty_available','list_price','categ_id']
2. Hiển thị kết quả dạng bảng Markdown gọn gàng bằng Tiếng Việt.
3. Nếu tồn kho < 10 đơn → cảnh báo "⚠️ Sắp hết hàng".
4. Nếu user muốn ĐẶT HÀNG hoặc TẠO BÁO GIÁ → trả lời có `[CẦN_TẠO_ĐƠN]` ở cuối.
5. KHÔNG BAO GIỜ bịa số liệu — chỉ dùng dữ liệu từ Odoo.
"""


class RecommendationAgent(BaseAgent):
    """
    Recommendation Agent: Tìm SP, kiểm kho, tra giá.
    Phát hiện intent "tạo đơn hàng" và chuyển sang FulfillmentAgent.
    """

    def __init__(self):
        super().__init__(name="recommendation")
        # Tool schemas micro — giảm token
        self._tool_schemas = [
            {
                "name": "search_records",
                "description": "Search Odoo records. For products use model='product.product'.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "query": {"type": "string"},
                        "fields": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer"}
                    },
                    "required": ["model"]
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
        role = user_info.get("official_role", "viewer")
        full_name = user_info.get("user_info", {}).get("full_name", "")

        system_blocks = [
            {
                "type": "text",
                "text": f"{RECOMMENDATION_SYSTEM_PROMPT}\nUser: {full_name} | Role: {role.upper()}",
                "cache_control": {"type": "ephemeral"}
            }
        ]

        messages = [{"role": "user", "content": user_text}]
        client = _get_anthropic_client()

        for _ in range(3):  # max 3 tool loops
            response = await asyncio.to_thread(
                lambda: client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=600,
                    system=system_blocks,
                    tools=self._tool_schemas,
                    messages=messages
                )
            )

            if response.stop_reason == "end_turn":
                text = "".join(
                    b.text for b in response.content if hasattr(b, "text")
                )
                # Phát hiện intent tạo đơn hàng
                needs_order = "[CẦN_TẠO_ĐƠN]" in text
                clean_text = text.replace("[CẦN_TẠO_ĐƠN]", "").strip()
                return AgentResult(
                    success=True,
                    response=clean_text,
                    next_agent="fulfillment" if needs_order else None,
                    metadata={"original_query": user_text, "role": role}
                )

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        try:
                            res = await mcp_session.call_tool(block.name, block.input or {})
                            output = res.content[0].text if res.content else "OK"
                            output = output[:1500] + "..." if len(output) > 1500 else output
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
            response="Xin lỗi, tôi không thể xử lý yêu cầu này lúc này.",
        )
