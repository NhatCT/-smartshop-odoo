import os
import shutil

def create_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# ---------------------------------------------------------
# 1. GATEWAY REFACTOR
# ---------------------------------------------------------
# notification_service.py
notification_service_py = """import os
import json
import urllib.request

class NotificationService:
    def __init__(self):
        self.n8n_otp_url = os.getenv("N8N_OTP_WEBHOOK_URL")
        self.n8n_approval_url = os.getenv("N8N_APPROVAL_WEBHOOK_URL")

    def send_otp_via_n8n(self, to_email, otp_code, employee_name):
        if not self.n8n_otp_url:
            return False
        try:
            payload = json.dumps({
                "to_email": to_email,
                "otp_code": otp_code,
                "employee_name": employee_name
            }).encode('utf-8')
            req = urllib.request.Request(self.n8n_otp_url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"⚠️ [N8N OTP ERROR]: {e}")
            return False

    def send_approval_request(self, order_name, total_amount, employee_name, manager_chat_id):
        if not self.n8n_approval_url:
            print("⚠️ N8N_APPROVAL_WEBHOOK_URL not configured")
            return False
        try:
            payload = json.dumps({
                "order_name": order_name,
                "total_amount": total_amount,
                "employee_name": employee_name,
                "manager_chat_id": manager_chat_id
            }).encode('utf-8')
            req = urllib.request.Request(self.n8n_approval_url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"⚠️ [N8N APPROVAL ERROR]: {e}")
            return False
"""
create_file("gateway/services/notification_service.py", notification_service_py)

# binding_service.py (Merging binding_repository logic)
binding_service_py = """import os
import json

TELEGRAM_BINDING_FILE = "telegram_bindings.json"

def get_bindings():
    if not os.path.exists(TELEGRAM_BINDING_FILE):
        default = {"6553206564": "nhatlovely2017@gmail.com"}
        with open(TELEGRAM_BINDING_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    with open(TELEGRAM_BINDING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_bindings(bindings):
    with open(TELEGRAM_BINDING_FILE, "w", encoding="utf-8") as f:
        json.dump(bindings, f, ensure_ascii=False, indent=2)
"""
create_file("gateway/services/binding_service.py", binding_service_py)

# Move rate_limiter.py
if os.path.exists("gateway/core/rate_limiter.py"):
    shutil.move("gateway/core/rate_limiter.py", "gateway/rate_limiter.py")

# ---------------------------------------------------------
# 2. ORCHESTRATOR - CLAUDE ADAPTER
# ---------------------------------------------------------
claude_adapter_py = """import os
import json
import anthropic
from gateway.services.notification_service import NotificationService

_anthropic_client = None
def get_client():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _anthropic_client

SYSTEM_PROMPT = \"\"\"Bạn là Bộ não AI duy nhất của SmartShop Odoo 19.
Nhiệm vụ: Tư vấn sản phẩm, kiểm kho, và tạo báo giá (Sale Order).

LUẬT BẮT BUỘC:
1. TRA CỨU: Dùng tool `search_records` để tìm sản phẩm/khách hàng. Luôn hiển thị dữ liệu thật từ Odoo.
2. TẠO ĐƠN < 20 triệu: Dùng tool `create_sale_order` để tạo đơn ngay.
3. TẠO ĐƠN >= 20 triệu (QUY TRÌNH DUYỆT):
   - ĐỪNG tạo đơn trên Odoo ngay!
   - Hãy báo cho user biết đơn cần Manager duyệt.
   - Hãy trả về ĐÚNG chuỗi text này ở cuối câu trả lời: `[NEED_APPROVAL] {"order_name": "Đơn Hàng Lớn", "total": <tổng_tiền_chính_xác>}`
4. KHI MANAGER ĐÃ DUYỆT: User sẽ nhắn "[MANAGER_APPROVED] Tạo đơn đi". Lúc này bạn DÙNG TOOL để tạo đơn thật trên Odoo.
\"\"\"

class ClaudeAdapter:
    def __init__(self):
        self.notification_service = NotificationService()

    async def handle_message(self, user_id: str, text: str, user_info: dict, mcp_session) -> str:
        role = user_info.get("official_role", "viewer")
        
        # Nếu nhận lệnh duyệt từ Webhook (thông qua user message giả)
        if text.startswith("[MANAGER_APPROVED]"):
            text = text + "\\nManager đã duyệt. Hãy tiến hành tạo Sale Order trên Odoo."

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
                system=SYSTEM_PROMPT + f"\\nQuyền của User: {role}",
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
                        final_text += f"\\n✅ Đã gọi: {tool_name} thành công!"
                    except Exception as e:
                        final_text += f"\\n❌ Lỗi gọi tool {tool_name}: {e}"

            # Xử lý Trigger Approval
            if "[NEED_APPROVAL]" in final_text:
                try:
                    import re
                    match = re.search(r'\\[NEED_APPROVAL\\]\\s*(.*)', final_text)
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
                            final_text += "\\n\\n⏳ **Đơn hàng > 20 triệu đã được chuyển đến n8n để xin phép Manager.** Vui lòng chờ phê duyệt."
                        else:
                            final_text += "\\n\\n⚠️ Lỗi gọi webhook n8n xin phép duyệt."
                except Exception as e:
                    print(f"Error parsing NEED_APPROVAL: {e}")

            return final_text if final_text else "Tôi đã thực hiện xong."

        except Exception as e:
            return f"❌ Lỗi từ Claude API: {e}"
"""
create_file("orchestrator/claude_adapter.py", claude_adapter_py)

# ---------------------------------------------------------
# 3. CHANNELS - WEBHOOK APPROVAL
# ---------------------------------------------------------
webhook_channel_py = """from fastapi import APIRouter, Request

webhook_router = APIRouter()

@webhook_router.post("/api/webhook/approval")
async def n8n_approval_callback(request: Request):
    data = await request.json()
    action = data.get("action")  # "approve" or "reject"
    order_name = data.get("order_name")
    telegram_id = data.get("telegram_id")

    if action == "approve":
        # Truyền message đặc biệt vào luồng xử lý
        from app_entrypoint import handle_message
        class DummyMsg:
            def __init__(self):
                self.user_id = telegram_id
                self.text = f"[MANAGER_APPROVED] Order: {order_name}"
                self.channel = "webhook"
                self.metadata = {}
        msg = DummyMsg()
        import asyncio
        asyncio.create_task(handle_message(msg))
        return {"status": "ok", "message": "Approval sent to Claude"}
    else:
        return {"status": "ok", "message": "Order rejected"}
"""
create_file("channels/webhook_channel.py", webhook_channel_py)

# ---------------------------------------------------------
# 4. APP_ENTRYPOINT.PY UPDATE
# ---------------------------------------------------------
# Read entrypoint, replace agent execution with claude_adapter
entrypoint_path = "app_entrypoint.py"
if os.path.exists(entrypoint_path):
    with open(entrypoint_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace agent imports
    content = content.replace("from agents import RecommendationAgent, ValidationAgent, FulfillmentAgent", "from orchestrator.claude_adapter import ClaudeAdapter")
    
    # Replace global agents
    content = content.replace("_recommendation_agent = RecommendationAgent()", "_claude_adapter = ClaudeAdapter()")
    content = content.replace("_validation_agent = ValidationAgent()", "")
    content = content.replace("_fulfillment_agent = FulfillmentAgent()", "")

    # Clean up traced handle_message
    new_traced = """@observe()
async def _traced_handle_message(channel_msg, obs_ctx) -> str:
    user_id = channel_msg.user_id
    text = channel_msg.text
    
    if _mcp_wrapper is None:
        return "⚠️ MCP session chưa sẵn sàng."

    result = await _claude_adapter.handle_message(
        user_id, text, obs_ctx, _mcp_wrapper
    )
    _update_trace_output(result)
    return result
"""
    import re
    content = re.sub(r"@observe\(\)\nasync def _traced_handle_message.*?(?=\ndef _update_trace_output)", new_traced, content, flags=re.DOTALL)
    
    with open(entrypoint_path, "w", encoding="utf-8") as f:
        f.write(content)

print("✅ Refactored to N8N-centric architecture successfully.")
