import os
import json
import anthropic
from gateway.services.notification_service import NotificationService

_anthropic_client = None
def get_client():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _anthropic_client

SYSTEM_PROMPT = """Bạn là Bộ não AI duy nhất của SmartShop Odoo 19.
Nhiệm vụ: Tư vấn sản phẩm, kiểm kho, xem báo cáo doanh số, và tạo báo giá (Sale Order).

LUẬT BẮT BUỘC:
1. TRA CỨU & BÁO CÁO DOANH SỐ:
   - Khi user hỏi "xem báo cáo doanh số", "doanh số tổng quan", "xem báo cáo": BẮT BUỘC GỌI NGAY tool `search_records` (model='sale.order', fields=['name','amount_total','state','date_order'], limit=50) hoặc `aggregate_records` ĐỂ LẤY DỮ LIỆU THẬT TỪ ODOO NGAY LẬP TỨC.
   - TUYỆT ĐỐI KHÔNG HỎI LẠI TIÊU CHÍ VỚI USER! Hãy tự động tính tổng doanh số, đếm số lượng đơn theo trạng thái (Draft, Sale Order, Done) và trình bày dưới dạng bảng Markdown sạch sẽ, đẹp mắt.
2. TẠO ĐƠN < 20 triệu: Dùng tool `create_sale_order` để tạo đơn ngay.
3. TẠO ĐƠN >= 20 triệu (QUY TRÌNH DUYỆT):
   - ĐỪNG tạo đơn trên Odoo ngay!
   - Hãy báo cho user biết đơn cần Manager duyệt.
   - Trả về ĐÚNG chuỗi text này ở cuối câu trả lời: `[NEED_APPROVAL] {"order_name": "Đơn Hàng Lớn", "total": <tổng_tiền_chính_xác>}`
4. KHI MANAGER ĐÃ DUYỆT: User sẽ nhắn "[MANAGER_APPROVED] Tạo đơn đi". Lúc này bạn DÙNG TOOL để tạo đơn thật trên Odoo.
"""

class ClaudeAdapter:
    def __init__(self):
        self.notification_service = NotificationService()

    async def handle_message(self, user_id: str, text: str, user_info: dict, mcp_session) -> str:
        role = user_info.get("official_role", "viewer")
        
        # Nếu nhận lệnh duyệt từ Webhook (thông qua user message giả)
        if text.startswith("[MANAGER_APPROVED]"):
            text = text + "\nManager đã duyệt. Hãy tiến hành tạo Sale Order trên Odoo."

        tools = []
        if mcp_session:
            try:
                mcp_tools = await mcp_session.list_tools()
                for t in mcp_tools.tools:
                    tools.append({
                        "name": t.name,
                        "description": t.description,
                        "input_schema": getattr(t, "input_schema", getattr(t, "inputSchema", {}))
                    })
            except Exception as e:
                print(f"⚠️ [ClaudeAdapter] Error listing MCP tools: {e}")

        client = get_client()
        model_name = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        messages = [{"role": "user", "content": text}]
        final_text = ""

        try:
            max_turns = 4
            for _ in range(max_turns):
                response = client.messages.create(
                    model=model_name,
                    max_tokens=1500,
                    system=SYSTEM_PROMPT + f"\nQuyền của User: {role}",
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

            # Xử lý Trigger Approval nếu có
            if "[NEED_APPROVAL]" in final_text:
                try:
                    import re
                    match = re.search(r'\[NEED_APPROVAL\]\s*(.*)', final_text)
                    if match:
                        data = json.loads(match.group(1))
                        manager_chat_id = os.getenv("ADMIN_CHAT_ID", "123456789")
                        success = self.notification_service.send_approval_request(
                            data.get("order_name", "Order"),
                            data.get("total", 0),
                            user_info.get("user_info", {}).get("full_name", user_id),
                            manager_chat_id
                        )
                        if success:
                            final_text = final_text.replace(match.group(0), "")
                            final_text += "\n\n⏳ **Đơn hàng > 20 triệu đã được chuyển đến n8n để xin phép Manager.** Vui lòng chờ phê duyệt."
                        else:
                            final_text += "\n\n⚠️ Lỗi gọi webhook n8n xin phép duyệt."
                except Exception as e:
                    print(f"Error parsing NEED_APPROVAL: {e}")

            return final_text if final_text else "Tôi đã thực hiện xong."

        except Exception as e:
            return f"❌ Lỗi từ Claude API: {e}"
