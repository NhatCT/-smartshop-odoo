"""
AITECHNEXT Enterprise AI Gateway
Live Telegram Bot Listener - MICRO-HAIKU OPTIMIZED ENGINE
Tối ưu tuyệt đối cho Claude Haiku: ~2.000 Tokens / ~65 VNĐ mỗi prompt.
"""

import os
import sys
import json
import time
import asyncio
import urllib.request
from dotenv_loader import load_env

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

load_env()

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import anthropic

from auth_gateway import SecurityGateway

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8835716387:AAGxnOylWpuvJP0r43RPMqM_txbagLkds5I")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# 2 Universal Tools duy nhất
ULTRA_MINIMAL_TOOL_NAMES = [
    "search_records",
    "execute_method"
]

RESTRICTED_TOOLS_FOR_INVENTORY = [
    "execute_method"
]

CONVERSATION_HISTORY = {}
MCP_SESSION = None
MCP_ALL_TOOLS = []

def send_plain_text(chat_id, text):
    """Gửi plain text về Telegram"""
    url = f"{BASE_URL}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            pass
    except Exception as e:
        print(f"   ❌ [SEND FAILED]: {e}")

def build_claude_tool_schema_micro(mcp_tool):
    """Schema siêu nhẹ: Giảm 60% token tool definition"""
    schema = mcp_tool.input_schema or {"type": "object", "properties": {}}
    if "properties" in schema and isinstance(schema["properties"], dict):
        clean_props = {}
        for k, v in schema["properties"].items():
            if k == "fields":
                clean_props[k] = {"type": "array", "items": {"type": "string"}}
            else:
                p_type = v.get("type", "string") if isinstance(v, dict) else "string"
                clean_props[k] = {"type": p_type}
        schema = {"type": "object", "properties": clean_props}

    desc = "Search Odoo records. For products, set model='product.product'." if mcp_tool.name == "search_records" else (mcp_tool.description or "")[:80]
    return {
        "name": mcp_tool.name,
        "description": desc,
        "input_schema": schema
    }

async def query_claude_ai_agent(session, telegram_id, user_text, user_info):
    """
    TRUY VẤN HAIKU SIÊU TIẾT KIỆM CHỈ ~65 VNĐ/PROMPT:
    1. 2 Micro Universal Tools
    2. Prompt Caching cho System Prompt + Tools
    3. Output Tool truncation max 1200 chars (đủ chứa thông tin giá & tồn kho)
    4. Max 4 tin nhắn thoại gần nhất
    """
    role = user_info["official_role"]
    full_name = user_info["user_info"]["full_name"]

    available_mcp_tools = []
    for t in MCP_ALL_TOOLS:
        if t.name in ULTRA_MINIMAL_TOOL_NAMES:
            if role == "inventory_staff" and t.name in RESTRICTED_TOOLS_FOR_INVENTORY:
                continue
            available_mcp_tools.append(t)

    claude_tools = [build_claude_tool_schema_micro(t) for t in available_mcp_tools]

    if claude_tools:
        claude_tools[-1]["cache_control"] = {"type": "ephemeral"}

    system_prompt_blocks = [
        {
            "type": "text",
            "text": (
                f"Odoo 19 Agent ({role.upper()}). "
                f"Khi người dùng hỏi tra cứu giá, tồn kho, sản phẩm, "
                f"TỰ ĐỘNG GỌI NGAY tool `search_records` với model='product.product', query=<từ_khóa>, và fields=['name','default_code','qty_available','list_price']. "
                f"Lấy trực tiếp giá trị tồn kho (qty_available) và giá bán (list_price) từ Odoo để hiển thị. KHÔNG BAO GIỜ hiển thị chữ 'Đang tải...'. "
                f"Trả lời ngay dạng bảng Markdown ngắn gọn Tiếng Việt."
            ),
            "cache_control": {"type": "ephemeral"}
        }
    ]

    if telegram_id not in CONVERSATION_HISTORY:
        CONVERSATION_HISTORY[telegram_id] = []

    history = CONVERSATION_HISTORY[telegram_id]
    request_messages = list(history)
    request_messages.append({"role": "user", "content": user_text})

    if len(request_messages) > 4:
        request_messages = request_messages[-4:]

    max_tool_loops = 3
    for _ in range(max_tool_loops):
        response = await asyncio.to_thread(
            lambda: anthropic_client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=450,
                system=system_prompt_blocks,
                tools=claude_tools,
                messages=request_messages
            )
        )

        if response.stop_reason == "end_turn":
            final_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    final_text += block.text
            
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": final_text})
            CONVERSATION_HISTORY[telegram_id] = history[-4:]
            return final_text if final_text else "Đã tra cứu xong từ Odoo 19."

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    fn_name = block.name
                    fn_input = block.input or {}
                    print(f"   ⚡ [HAIKU MCP TOOL]: {fn_name}({fn_input})")

                    try:
                        tool_res = await session.call_tool(fn_name, fn_input)
                        output_text = tool_res.content[0].text if tool_res.content else "OK"
                        if len(output_text) > 1200:
                            output_text = output_text[:1200] + "..."
                    except Exception as ex:
                        output_text = f"Lỗi MCP tool: {str(ex)}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output_text
                    })

            request_messages.append({"role": "assistant", "content": response.content})
            request_messages.append({"role": "user", "content": tool_results})
            continue

        break

    return "Đã tra cứu xong từ Odoo 19."

async def process_telegram_message_async(session, telegram_id, user_text):
    """Xử lý 1 tin nhắn với Claude Haiku Micro Engine"""
    clean_text = user_text.strip()
    print(f"\n📩 [ID={telegram_id}] Text: '{clean_text}'")
    gateway = SecurityGateway()

    if clean_text.lower().startswith("/register"):
        parts = clean_text.split()
        if len(parts) < 2:
            send_plain_text(telegram_id, "Cú pháp: /register email_cua_ban@gmail.com")
            return
        email = parts[1].lower().strip()
        ok, msg = gateway.request_otp(telegram_id, email)
        send_plain_text(telegram_id, msg.replace('`', '').replace('**', ''))
        return

    if clean_text.lower().startswith("/verify"):
        parts = clean_text.split()
        if len(parts) < 2:
            send_plain_text(telegram_id, "Cú pháp: /verify MA_OTP")
            return
        ok, msg = gateway.verify_otp_and_bind(telegram_id, parts[1].strip())
        send_plain_text(telegram_id, msg.replace('`', '').replace('**', ''))
        return

    if clean_text == "/my_role":
        auth_res = gateway.process_incoming_request(telegram_id, user_text)
        if not auth_res["allowed"]:
            send_plain_text(telegram_id, auth_res["reason"])
        else:
            u = auth_res["user_info"]
            send_plain_text(telegram_id,
                f"👤 TÀI KHOẢN:\n"
                f"• Tên: {u['full_name']}\n"
                f"• Role: {u['role'].upper()}\n"
                f"• Email: {u['email']}\n"
                f"• Engine: Claude Haiku Micro (~65 VNĐ/prompt)"
            )
        return

    if clean_text in ["/clear", "/reset"]:
        if telegram_id in CONVERSATION_HISTORY:
            del CONVERSATION_HISTORY[telegram_id]
        send_plain_text(telegram_id, "🧹 Đã xóa sạch bộ nhớ hội thoại!")
        return

    auth_res = gateway.process_incoming_request(telegram_id, user_text)
    if not auth_res["allowed"]:
        send_plain_text(telegram_id, auth_res["reason"])
        return

    print(f"   ✅ AUTH OK: {auth_res['user_info']['full_name']} | Role={auth_res['official_role']}")

    start_t = time.time()
    try:
        reply = await query_claude_ai_agent(session, telegram_id, clean_text, auth_res)
        elapsed = time.time() - start_t
        print(f"   ⏱️ [MICRO HAIKU RESPONSE TIME]: {elapsed:.2f}s")
        send_plain_text(telegram_id, reply)
    except Exception as e:
        print(f"   ❌ [ERROR]: {e}")
        send_plain_text(telegram_id, f"Lỗi truy vấn: {str(e)[:150]}")

async def run_persistent_bot():
    """Main Event Loop duy trì kết nối MCP Session 24/7"""
    global MCP_SESSION, MCP_ALL_TOOLS
    print("=" * 65)
    print(" SMARTSHOP AI GATEWAY - CLAUDE HAIKU MICRO ENGINE")
    print(f" Model: {CLAUDE_MODEL} | Micro Schema & Prompt Caching Active")
    print("=" * 65)

    env = dict(os.environ)
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "odoo_mcp"],
        env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_tools_res = await session.list_tools()
            MCP_SESSION = session
            MCP_ALL_TOOLS = mcp_tools_res.tools

            print(f"✅ Claude Haiku Micro Session Ready!")

            admin_chat_id = os.getenv("TELEGRAM_CHAT_ID", "6553206564")
            send_plain_text(admin_chat_id,
                f"🛍️ **CHÀO MỪNG BẠN ĐẾN VỚI TRỢ LÝ AI SMARTSHOP ODOO 19!**\n\n"
                f"🔒 Để đảm bảo an toàn CSDL Doanh nghiệp, vui lòng kích hoạt tài khoản theo 2 bước:\n\n"
                f"1️⃣ Gửi lệnh đăng ký Email nhân viên:\n"
                f"`/register email_cua_ban@gmail.com`\n\n"
                f"2️⃣ Nhập mã xác thực OTP:\n"
                f"`/verify 123456`\n\n"
                f"💡 *Sau khi kích hoạt, bạn có thể tự do hỏi thông tin tồn kho, giá bán và tạo báo giá trực tiếp!*"
            )

            offset = 0
            while True:
                try:
                    url = f"{BASE_URL}/getUpdates?offset={offset}&timeout=10"
                    req = urllib.request.Request(url)
                    resp_data = await asyncio.to_thread(lambda: json.loads(urllib.request.urlopen(req, timeout=12).read().decode('utf-8')))

                    for update in resp_data.get("result", []):
                        offset = update["update_id"] + 1
                        msg = update.get("message", {})
                        chat = msg.get("chat", {})
                        telegram_id = chat.get("id")
                        text = msg.get("text", "")
                        if telegram_id and text:
                            try:
                                await process_telegram_message_async(session, telegram_id, text)
                            except Exception as ex:
                                print(f"   ❌ [UPDATE ERROR]: {ex}")
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"   ⚠️ [POLL ERROR]: {e}")
                    await asyncio.sleep(2)

def main():
    """Entry point for background thread execution"""
    asyncio.run(run_persistent_bot())

if __name__ == "__main__":
    main()
