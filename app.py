"""SmartShop AI Gateway — Main entrypoint (FastAPI + Telegram + Webhook)."""

import asyncio
import hashlib
import hmac
import json
import os
import sys
import threading
import urllib.request

# Load .env
if os.path.exists(".env"):
    for line in open(".env", encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from fastapi import FastAPI, Request
import uvicorn

import ai
from auth import (check_permission, request_otp, verify_otp, rate_limit_check,
                  idempotency_check, idempotency_store, verify_approval_token)

# ─── FastAPI ───
app = FastAPI(title="SmartShop AI Gateway", version="3.0")
_mcp_session = None
WEBHOOK_SECRET = os.getenv("N8N_APPROVAL_WEBHOOK_SECRET", "")

if not WEBHOOK_SECRET:
    print("[WEBHOOK] N8N_APPROVAL_WEBHOOK_SECRET chua cau hinh — approval callback se bi tu choi.")


@app.get("/")
def root():
    return {"service": "SmartShop AI Gateway v3.0", "status": "online", "mcp_ready": _mcp_session is not None}


@app.get("/health")
def health():
    return {"status": "ok"}


def _verify_sig(payload: bytes, sig: str) -> bool:
    if not WEBHOOK_SECRET or not sig:
        return False
    expected = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


@app.post("/api/webhook/approval")
async def approval_callback(request: Request):
    raw = await request.body()
    sig = request.headers.get("X-Webhook-Signature", "")
    if not _verify_sig(raw, sig):
        return {"status": "error", "message": "Invalid signature"}, 401
    data = await request.json()
    action = data.get("action")
    order_name = data.get("order_name")
    telegram_id = data.get("telegram_id")
    if action == "approve":
        ok, msg = ai.approve_order(order_name, telegram_id)
        return {"status": "ok" if ok else "error", "message": msg}
    else:
        ok, msg = ai.reject_order(order_name, telegram_id)
        return {"status": "ok", "message": msg}


# ─── Telegram Bot ───
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6553206564")
SYSTEM_CMDS = {"/start", "/register", "/verify", "/my_role", "/clear", "/reset", "/help"}


async def tg_send(user_id, text, parse_mode="Markdown"):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": user_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        await asyncio.to_thread(lambda: urllib.request.urlopen(req, timeout=8).read())
        print(f"[TG] Sent to {user_id}: {text[:80]}...")
        return True
    except Exception as e:
        print(f"[TG] FAILED to {user_id}: {e}")
        if parse_mode:
            try:
                return await tg_send(user_id, text, parse_mode=None)
            except Exception as e2:
                print(f"[TG] FAILED retry to {user_id}: {e2}")
        return False


async def handle_callback(callback, message_handler):
    cb_id = callback.get("id", "")
    data = callback.get("data", "")
    user_id = str(callback.get("from", {}).get("id", ""))
    try:
        ack = urllib.request.Request(f"{BASE_URL}/answerCallbackQuery",
                                     data=json.dumps({"callback_query_id": cb_id}).encode(),
                                     headers={"Content-Type": "application/json"})
        await asyncio.to_thread(lambda: urllib.request.urlopen(ack, timeout=5).read())
    except Exception:
        pass
    # Convert callback to text
    if data.startswith("approve_") or data.startswith("reject_"):
        parts = data.split("_")
        action = parts[0]
        order_name = "_".join(parts[1:-1])
        token = parts[-1]
        if not verify_approval_token(order_name, user_id, token):
            await tg_send(user_id, "Token khong hop le.", parse_mode=None)
            return
        if action == "approve":
            _, msg = ai.approve_order(order_name)
        else:
            _, msg = ai.reject_order(order_name)
        await tg_send(user_id, msg, parse_mode=None)
        return
    # Other callbacks → delegate to AI
    text = data
    if data.startswith("action:draft_order:"):
        text = f"Tao don hang nhap cho san pham so {data.split(':')[-1]}"
    elif data.startswith("action:check_stock:"):
        text = f"Kiem tra ton kho san pham so {data.split(':')[-1]}"
    await message_handler(user_id, text)


async def handle_system_cmd(user_id, text):
    lower = text.lower()
    print(f"[CMD] user={user_id} cmd={lower}")
    if lower in ("/start", "/help"):
        await tg_send(user_id, (
            "👋 SMARTSHOP AI ASSISTANT\n\n"
            "• 🔍 Tra cứu sản phẩm & giá\n• 📦 Kiểm tra tồn kho\n"
            "• 📋 Tạo báo giá & đơn hàng\n• 📊 Xem công nợ\n\n"
            "Lệnh: /register /verify /my_role /clear"
        ), parse_mode=None)
        return
    if lower.startswith("/register"):
        parts = text.split()
        if len(parts) < 2:
            await tg_send(user_id, "Cu phap: /register email@company.com", parse_mode=None)
            return
        ok, msg = request_otp(user_id, parts[1])
        print(f"[CMD] /register result={ok} msg={msg}")
        await tg_send(user_id, msg.replace("`", "").replace("**", ""), parse_mode=None)
        return
    if lower.startswith("/verify"):
        parts = text.split()
        if len(parts) < 2:
            await tg_send(user_id, "Cu phap: /verify MA_OTP", parse_mode=None)
            return
        ok, msg = verify_otp(user_id, parts[1])
        print(f"[CMD] /verify result={ok} msg={msg}")
        await tg_send(user_id, msg.replace("`", "").replace("**", ""), parse_mode=None)
        return
    if lower == "/my_role":
        from auth import check_permission
        auth = check_permission(user_id)
        if not auth["allowed"]:
            await tg_send(user_id, auth["reason"], parse_mode=None)
        else:
            u = auth["user_info"]
            groups = u.get("odoo_groups", [])
            g_str = "\n".join(f"  • {g}" for g in groups) if groups else "  • (Khong co)"
            await tg_send(user_id,
                f"👤 TAI KHOAN ODOO\n• Ho ten: {u.get('full_name')}\n• Email: {u.get('email')}\n"
                f"• Vai tro: {u.get('role_category', 'viewer').upper()}\n\nNhom quyen:\n{g_str}",
                parse_mode=None)
        return
    if lower in ("/clear", "/reset"):
        ai.clear_memory(user_id)
        ai.clear_draft(user_id)
        await tg_send(user_id, "🧹 Da xoa bo nho hoi thoai!", parse_mode=None)
        return


async def message_handler(user_id: str, text: str):
    """Core: Auth → AI → Response."""
    auth = check_permission(user_id)
    if not auth["allowed"]:
        return auth["reason"]
    user_info = auth["user_info"]

    if _mcp_session is None:
        return "⚠️ MCP session chua san sang."
    return await ai.handle_message(user_id, text, user_info, _mcp_session)


async def telegram_loop():
    global _mcp_session
    print("🤖 [TELEGRAM] Starting bot + MCP session...")
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as e:
        print(f"❌ [TELEGRAM] MCP package not ready: {e}")
        return

    server_params = StdioServerParameters(command="python", args=["-m", "odoo_mcp"], env=dict(os.environ))
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            _mcp_session = session
            print("✅ [MCP] Session ready!")
            offset = 0
            while True:
                try:
                    url = f"{BASE_URL}/getUpdates?offset={offset}&timeout=10"
                    data = await asyncio.to_thread(
                        lambda: json.loads(urllib.request.urlopen(url, timeout=12).read().decode("utf-8")))
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        msg = update.get("message", {})
                        chat = msg.get("chat", {})
                        uid = str(chat.get("id", ""))
                        text = msg.get("text", "").strip()
                        callback = update.get("callback_query", {})
                        if callback:
                            await handle_callback(callback, message_handler)
                            continue
                        if not uid or not text:
                            continue
                        if any(text.lower().startswith(c) for c in SYSTEM_CMDS):
                            await handle_system_cmd(uid, text)
                            continue
                        # Rate limit
                        ok, rate_msg = rate_limit_check(uid)
                        if not ok:
                            await tg_send(uid, rate_msg, parse_mode=None)
                            continue
                        # Idempotency
                        is_dup, cached = idempotency_check(uid, text)
                        if is_dup and cached:
                            await tg_send(uid, cached)
                            continue
                        # AI pipeline
                        try:
                            resp = await message_handler(uid, text)
                            if resp:
                                await tg_send(uid, resp)
                                idempotency_store(uid, text, resp)
                        except Exception as ex:
                            await tg_send(uid, f"❌ Loi: {str(ex)[:150]}", parse_mode=None)
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"⚠️ [POLL ERROR]: {e}")
                    await asyncio.sleep(2)


# ─── Main ───
if __name__ == "__main__":
    print("=" * 60)
    print("  SMARTSHOP AI GATEWAY v3.0 — SIMPLIFIED")
    print("=" * 60)

    # Start Telegram bot in background
    print("🔄 Starting Telegram bot thread...")
    tg_thread = threading.Thread(target=lambda: asyncio.run(telegram_loop()), daemon=True)
    tg_thread.start()
    print("✅ Telegram bot thread started")

    # Start FastAPI
    port = int(os.getenv("PORT", 8000))
    print(f"\n🚀 Web Gateway on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
