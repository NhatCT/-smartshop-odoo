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
Nhiệm vụ: Tư vấn sản phẩm, kiểm kho, và tạo báo giá (Sale Order).

LUẬT BẮT BUỘC:
1. TRA CỨU: Dùng tool `search_records` để tìm sản phẩm/khách hàng. Luôn hiển thị dữ liệu thật từ Odoo.
2. TẠO ĐƠN < 20 triệu: Dùng tool `create_sale_order` để tạo đơn ngay.
3. TẠO ĐƠN >= 20 triệu (QUY TRÌNH DUYỆT):
   - ĐỪNG tạo đơn trên Odoo ngay!
   - Hãy báo cho user biết đơn cần Manager duyệt.
   - Hãy trả về ĐÚNG chuỗi text này ở cuối câu trả lời: `[NEED_APPROVAL] {"order_name": "Đơn Hàng Lớn", "total": <tổng_tiền_chính_xác>}`
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
            mcp_tools = await mcp_session.list_tools()
            for t in mcp_tools.tools:
                tools.append({
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.inputSchema
                })

        client = get_client()
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                system=SYSTEM_PROMPT + f"\nQuyền của User: {role}",
                messages=[{"role": "user", "content": text}],
                tools=tools
            )

            final_text = ""
            for block in response.content:
                if block.type == "text":
                    final_text += block.text
                elif block.type == "tool_use":
                    # Tự động gọi tool (chạy MCP)
                    tool_name = block.name
                    tool_args = block.input
                    try:
                        result = await mcp_session.call_tool(tool_name, arguments=tool_args)
                        final_text += f"\n✅ Đã gọi: {tool_name} thành công!"
                    except Exception as e:
                        final_text += f"\n❌ Lỗi gọi tool {tool_name}: {e}"

            # Xử lý Trigger Approval
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
