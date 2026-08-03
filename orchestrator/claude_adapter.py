import os
import re
import json
import anthropic
from gateway.services.notification_service import NotificationService
from orchestrator.prompts import build_system_prompt

_anthropic_client = None
def get_client():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _anthropic_client


class ClaudeAdapter:
    def __init__(self):
        self.notification_service = NotificationService()

    async def handle_message(self, user_id: str, text: str, user_info: dict, mcp_session) -> str:
        u_info = user_info.get("user_info", {})

        # Sinh System Prompt từ raw Odoo groups — Claude tự suy luận quyền
        system_prompt = build_system_prompt(u_info)

        # Nếu nhận lệnh duyệt từ Webhook
        if text.startswith("[MANAGER_APPROVED]"):
            text = text + "\nManager đã duyệt. Hãy tiến hành tạo Sale Order trên Odoo."

        # Chỉ truyền các tool nghiệp vụ — loại bỏ tool debug/developer để Haiku không bị nhiễu
        BUSINESS_TOOLS = {
            "search_records",
            "aggregate_records",
            "create_record",
            "update_record",
            "create_sale_order",
            "get_sale_order",
            "list_products",
            "get_stock_quant",
        }

        tools = []
        if mcp_session:
            try:
                mcp_tools = await mcp_session.list_tools()
                for t in mcp_tools.tools:
                    if t.name in BUSINESS_TOOLS:
                        tools.append({
                            "name": t.name,
                            "description": t.description,
                            "input_schema": getattr(t, "input_schema", getattr(t, "inputSchema", {}))
                        })
                print(f"[ClaudeAdapter] Tools available: {[t['name'] for t in tools]}")
            except Exception as e:
                print(f"⚠️ [ClaudeAdapter] Error listing MCP tools: {e}")

        client = get_client()
        model_name = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        # Thêm planning-hint để Haiku lên kế hoạch trước khi gọi Tool
        PLANNING_HINT = (
            "[SYSTEM HINT] Trước khi gọi Tool, hãy phân tích yêu cầu và xác định:\n"
            "1. Cần truy vấn model Odoo nào? Theo thứ tự nào?\n"
            "2. Có thể kết hợp dữ liệu từ các tool trong cùng 1 lượt không?\n"
            "Sau đó thực thi ngay và trình bày kết quả cuối cùng bằng tiếng Việt."
        )
        messages = [
            {"role": "user", "content": PLANNING_HINT},
            {"role": "assistant", "content": "Đã hiểu. Tôi sẽ lên kế hoạch trước khi thực thi."},
            {"role": "user", "content": text},
        ]
        final_text = ""

        try:
            max_turns = 4
            for _ in range(max_turns):
                response = client.messages.create(
                    model=model_name,
                    max_tokens=1500,
                    system=system_prompt,
                    messages=messages,
                    tools=tools if tools else anthropic.NOT_GIVEN
                )

                messages.append({"role": "assistant", "content": response.content})

                # Check if Claude requested tool calls
                tool_uses = [b for b in response.content if b.type == "tool_use"]
                if not tool_uses:
                    # Final text response from Claude
                    for b in response.content:
                        if b.type == "text":
                            final_text += b.text
                    break

                # Execute MCP tool calls and feed results back to Claude
                if not mcp_session:
                    final_text = "⚠️ Không thể kết nối MCP session để thực thi lệnh."
                    break

                tool_results = []
                for tu in tool_uses:
                    tool_name = tu.name
                    tool_args = tu.input
                    tool_id = tu.id
                    try:
                        res = await mcp_session.call_tool(tool_name, arguments=tool_args)
                        if hasattr(res, "content") and res.content and hasattr(res.content[0], "text"):
                            res_str = res.content[0].text
                        else:
                            res_str = str(res)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": res_str[:4000]
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": f"Lỗi gọi tool {tool_name}: {e}",
                            "is_error": True
                        })

                messages.append({"role": "user", "content": tool_results})

            # Nếu Claude gọi tool liên tục nhưng không trả lời text (hết max_turns)
            # → Yêu cầu Claude tổng hợp kết quả từ dữ liệu đã thu thập
            if not final_text and messages:
                try:
                    messages.append({
                        "role": "user",
                        "content": "Dựa trên kết quả các tool vừa trả về, hãy tổng hợp và trình bày câu trả lời cuối cùng cho người dùng bằng tiếng Việt."
                    })
                    summary_resp = client.messages.create(
                        model=model_name,
                        max_tokens=2048,
                        system=system_prompt,
                        messages=messages,
                    )
                    for b in summary_resp.content:
                        if hasattr(b, "text"):
                            final_text += b.text
                except Exception as e:
                    print(f"⚠️ [ClaudeAdapter] Force-summarize failed: {e}")

            if "[NEED_APPROVAL]" in final_text:
                try:
                    match = re.search(r'\[NEED_APPROVAL\]\s*(.*)', final_text)
                    if match:
                        data = json.loads(match.group(1))
                        total = data.get("total", 0)
                        total_fmt = f"{float(total):,.0f} VNĐ" if total else "N/A"
                        manager_chat_id = os.getenv("ADMIN_CHAT_ID", "123456789")
                        success = self.notification_service.send_approval_request(
                            data.get("order_name", "Order"),
                            total,
                            u_info.get("full_name", user_id),
                            manager_chat_id
                        )
                        if success:
                            final_text = final_text.replace(match.group(0), "")
                            final_text += f"\n\n⏳ **Đơn hàng {total_fmt} đã được chuyển để xin phép Manager.** Vui lòng chờ phê duyệt."
                        else:
                            final_text += "\n\n⚠️ Lỗi gọi webhook n8n xin phép duyệt."
                except Exception as e:
                    print(f"Error parsing NEED_APPROVAL: {e}")

            return final_text if final_text else "Tôi đã thực hiện xong."

        except Exception as e:
            return f"❌ Lỗi từ Claude API: {e}"
