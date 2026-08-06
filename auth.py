"""Auth — Zero-Trust Gateway: OTP, permission, rate limit, idempotency, config."""

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.request
from collections import OrderedDict, defaultdict, deque
from pathlib import Path

from odoo import OdooClient

# ─── Config Registry ───
BINDING_FILE = Path(__file__).parent / "telegram_bindings.json"
PARAM_BINDINGS = "smartshop.telegram_bindings"
REQUIRES_ADMIN_APPROVAL = set()

_odoo = OdooClient()


def get_bindings() -> dict:
    local = {}
    if BINDING_FILE.exists():
        try:
            local = json.loads(BINDING_FILE.read_text(encoding="utf-8"))
        except Exception:
            local = {}
    try:
        val = _odoo.search_read("ir.config_parameter", [["key", "=", PARAM_BINDINGS]], ["value"], 1)
        if val and val[0].get("value"):
            parsed = json.loads(val[0]["value"])
            if isinstance(parsed, dict) and parsed:
                return parsed
    except Exception:
        pass
    return local


def save_bindings(bindings: dict) -> bool:
    try:
        BINDING_FILE.write_text(json.dumps(bindings, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    try:
        odoo = _odoo.connect()
        existing = _odoo.search_read("ir.config_parameter", [["key", "=", PARAM_BINDINGS]], ["id"], 1)
        json_str = json.dumps(bindings, ensure_ascii=False)
        if existing:
            odoo.env["ir.config_parameter"].browse([existing[0]["id"]]).write({"value": json_str})
        else:
            odoo.env["ir.config_parameter"].create({"key": PARAM_BINDINGS, "value": json_str})
        return True
    except Exception:
        return False


# ─── Permission (Zero-Trust, đọc LIVE từ Odoo) ───
def fetch_user_context(email: str) -> dict | None:
    """Đọc res.users + res.groups LIVE từ Odoo mỗi request — không cache."""
    clean = email.lower().strip()
    try:
        users = _odoo.search_read("res.users", ["|", ["login", "=ilike", clean], ["email", "=ilike", clean]],
                                  ["id", "name", "login", "active", "company_id", "all_group_ids"], 1)
    except Exception as e:
        print(f"[ODOO SEARCH ERROR] fetch_user_context: {e}")
        return None
    if not users:
        return None
    u = users[0]
    groups = []
    gids = u.get("all_group_ids", [])
    if gids:
        try:
            raw = _odoo.search_read("res.groups", [["id", "in", gids]], ["full_name", "display_name", "name"], 100)
            skip = ["Technical", "Bỏ qua", "Địa chỉ", "Trình chỉnh", "Trang web"]
            groups = [g.get("full_name") or g.get("display_name") or g.get("name", "")
                      for g in raw if g.get("full_name") or g.get("display_name") or g.get("name")]
            groups = [g for g in groups if not any(k in g for k in skip)]
        except Exception:
            pass

    is_admin = any("Quản trị / Thiết lập" in g or "Administration / Settings" in g or "Access Rights" in g for g in groups)
    is_sales_mgr = any("Bán hàng / Quản trị viên" in g or "Sales / Administrator" in g for g in groups)
    is_sales = is_sales_mgr or any("Bán hàng" in g or "Sales" in g for g in groups)
    is_inv_mgr = any("Tồn kho / Quản trị viên" in g or "Inventory / Administrator" in g for g in groups)
    is_inv = is_inv_mgr or any("Tồn kho" in g or "Inventory" in g for g in groups)
    is_acc_mgr = any("Kế toán / Quản trị viên" in g or "Accounting / Administrator" in g for g in groups)
    is_acc = is_acc_mgr or any("Kế toán" in g or "Accounting" in g or "Invoicing" in g for g in groups)

    tools = {"search_records", "list_products"}
    models = {"product.template", "product.product"}
    if is_sales or is_sales_mgr or is_admin:
        tools.update(["create_sale_order", "create_record", "update_record", "get_sale_order", "execute_method",
                      "preview_write", "validate_write", "execute_approved_write"])
        models.update(["sale.order", "sale.order.line", "res.partner"])
    if is_inv or is_inv_mgr or is_admin:
        tools.update(["get_stock_quant"])
        models.update(["stock.quant", "stock.picking", "stock.location"])
    if is_acc or is_acc_mgr or is_sales_mgr or is_admin:
        tools.update(["aggregate_records"])
        models.update(["account.move", "account.move.line", "res.partner"])

    if is_admin or is_sales_mgr:
        role = "sales_manager"
    elif is_sales:
        role = "sales_staff"
    elif is_inv_mgr or is_inv:
        role = "inventory_staff"
    elif is_acc:
        role = "accountant"
    else:
        role = "viewer"

    comp = u.get("company_id")
    company_id = comp[0] if isinstance(comp, (list, tuple)) and comp else comp
    print(f"[PERMISSION LIVE] {email} | role={role} | groups={len(groups)} | tools={len(tools)} | models={len(models)}")
    print(f"[PERMISSION LIVE] tools_list={sorted(tools)}")
    return {
        "odoo_user_id": u.get("id"), "email": email,
        "full_name": u.get("name") or email.split("@")[0].replace(".", " ").title(),
        "is_active_odoo": u.get("active", True), "odoo_groups": groups,
        "role_category": role, "role": role,
        "allowed_tools": list(tools), "allowed_models": list(models),
        "company_id": company_id,
    }


def check_permission(telegram_id: str) -> dict:
    """Zero-Trust: binding → Odoo quyền live → allow/deny."""
    bindings = get_bindings()
    email = bindings.get(str(telegram_id).strip())
    if not email:
        return {"allowed": False, "reason": f"⛔ Telegram ID `{telegram_id}` chưa liên kết. Gõ `/register email@company.com`"}
    ctx = fetch_user_context(email)
    if not ctx:
        return {"allowed": False, "reason": f"❌ Không tìm thấy tài khoản Odoo `{email}`."}
    if not ctx["is_active_odoo"]:
        return {"allowed": False, "reason": f"🚨 Tài khoản `{email}` đã bị vô hiệu hóa trên Odoo."}
    return {"allowed": True, "email": email, "user_info": ctx, "official_role": ctx["role_category"]}


# ─── OTP ───
_pending_otp: dict[str, dict] = {}
_pending_approval: dict[str, dict] = {}
OTP_TTL = 300


def request_otp(telegram_id, email) -> tuple[bool, str]:
    email = email.lower().strip()
    try:
        users = _odoo.search_read("res.users", ["|", ["login", "=ilike", email], ["email", "=ilike", email]],
                                  ["id", "name", "login", "active", "email"], 1)
        print(f"[ODOO SEARCH] request_otp email={email} results={len(users)} users={[u.get('login') or u.get('email') for u in users]}")
    except Exception as e:
        print(f"[ODOO SEARCH ERROR] request_otp: {e}")
        return False, f"❌ Lỗi kết nối Odoo: {e}"
    if not users:
        return False, f"❌ Email '{email}' không tồn tại trong Odoo."
    if not users[0].get("active", True):
        return False, f"🚨 Tài khoản '{email}' đã bị vô hiệu hóa."
    import random
    otp = f"{random.randint(100000, 999999)}"
    _pending_otp[str(telegram_id)] = {"email": email, "otp": otp, "ts": time.time()}
    if email in REQUIRES_ADMIN_APPROVAL:
        _pending_approval[str(telegram_id)] = {"email": email, "ts": time.time()}
    # Gửi OTP qua n8n
    url = os.getenv("N8N_OTP_WEBHOOK_URL", "https://odooworkflow.app.n8n.cloud/webhook/send-otp-email")
    try:
        payload = json.dumps({"to_email": email, "otp_code": otp, "employee_name": users[0].get("name", email)}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=8)
        return True, f"✉️ Mã OTP đã gửi tới `{email}`. Gõ `/verify <MÃ_OTP_6_SỐ>`"
    except Exception as e:
        return False, f"❌ Không thể gửi OTP: {e}"


def verify_otp(telegram_id, user_otp) -> tuple[bool, str]:
    sid = str(telegram_id)
    pending = _pending_otp.get(sid)
    if not pending:
        return False, "❌ Không tìm thấy yêu cầu OTP. Gõ `/register email` trước."
    if time.time() - pending["ts"] > OTP_TTL:
        del _pending_otp[sid]
        return False, "❌ Mã OTP đã hết hạn (5 phút)."
    if pending["otp"] != user_otp.strip():
        return False, "❌ Mã OTP không khớp."
    email = pending["email"]
    if sid in _pending_approval:
        del _pending_otp[sid]
        return False, f"⏳ Tài khoản `{email}` cần Admin phê duyệt trước khi kích hoạt."
    try:
        bindings = get_bindings()
        bindings[sid] = email
        save_bindings(bindings)
    except Exception as e:
        return False, f"❌ Lỗi lưu binding: {e}"
    del _pending_otp[sid]
    ctx = fetch_user_context(email) or {}
    return True, (
        f"✅ XÁC THỰC THÀNH CÔNG!\nTài khoản: `{email}`\n"
        f"Họ tên: {ctx.get('full_name', email)}\n"
        f"Vai trò: {ctx.get('role_category', 'viewer').upper()}"
    )


# ─── Rate Limiter (30 req/min) ───
class RateLimiter:
    def __init__(self, max_req=30, window=60):
        self._max = max_req
        self._window = window
        self._store: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, user_id: str) -> tuple[bool, dict]:
        now = time.time()
        with self._lock:
            w = self._store[str(user_id)]
            while w and w[0] < now - self._window:
                w.popleft()
            if len(w) >= self._max:
                return False, {"message": f"⚠️ Quá {self._max} tin/phút. Đợi {int(self._window - (now - w[0])) + 1}s."}
            w.append(now)
            return True, {}


_rate_limiter = RateLimiter()


def rate_limit_check(user_id: str) -> tuple[bool, str]:
    ok, info = _rate_limiter.is_allowed(user_id)
    return ok, info.get("message", "")


# ─── Idempotency (5 phút) ───
_idem: OrderedDict = OrderedDict()
_idem_lock = threading.Lock()
SKIP_DEDUP = {"/register", "/verify", "/clear", "/reset", "/my_role", "/start"}


def idempotency_check(user_id: str, text: str) -> tuple[bool, str | None]:
    msg = text.strip().lower()
    if any(msg.startswith(p) for p in SKIP_DEDUP):
        return False, None
    key = hashlib.sha256(f"{user_id}:{text.strip().lower()[:200]}".encode()).hexdigest()[:16]
    now = time.time()
    with _idem_lock:
        if key in _idem:
            entry = _idem[key]
            if now - entry["ts"] < 300:
                _idem.move_to_end(key)
                return True, entry["response"]
            del _idem[key]
    return False, None


def idempotency_store(user_id: str, text: str, response: str):
    msg = text.strip().lower()
    if any(msg.startswith(p) for p in SKIP_DEDUP):
        return
    key = hashlib.sha256(f"{user_id}:{text.strip().lower()[:200]}".encode()).hexdigest()[:16]
    with _idem_lock:
        if len(_idem) >= 10000:
            _idem.popitem(last=False)
        _idem[key] = {"response": response, "ts": time.time()}
        _idem.move_to_end(key)


# ─── Approval Token (HMAC) ───
_APPROVAL_SECRET = os.getenv("APPROVAL_TOKEN_SECRET") or os.getenv("ODOO_PASSWORD") or secrets.token_urlsafe(32)


def generate_approval_token(order_name: str, approver_id: str, ttl=86400) -> str:
    ts = str(int(time.time()))
    payload = f"{order_name}:{approver_id}:{ts}:{ttl}"
    sig = hmac.new(_APPROVAL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{ts}.{ttl}.{sig}"


def verify_approval_token(order_name: str, approver_id: str, token: str) -> bool:
    try:
        ts_s, ttl_s, sig = token.split(".", 2)
        ts, ttl = int(ts_s), int(ttl_s)
    except Exception:
        return False
    if time.time() > ts + ttl:
        return False
    payload = f"{order_name}:{approver_id}:{ts}:{ttl}"
    expected = hmac.new(_APPROVAL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:24]
    return hmac.compare_digest(sig, expected)


# ─── Notification (EZ Direct Telegram Inline Buttons + n8n Fallback) ───
def send_approval_request(order_name, total, employee_name, manager_chat_id, telegram_id=None):
    target_chat_id = manager_chat_id if (manager_chat_id and str(manager_chat_id) not in ("123456789", "N/A", "")) else (telegram_id or os.getenv("ADMIN_CHAT_ID", "6553206564"))
    token = generate_approval_token(order_name, str(target_chat_id))
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    text_md = (
        f"⚠️ *YÊU CẦU PHÊ DUYỆT ĐƠN HÀNG GIÁ TRỊ LỚN*\n\n"
        f"• Mã đơn: `{order_name}`\n"
        f"• Nhân viên yêu cầu: *{employee_name}*\n"
        f"• Tổng giá trị: *{total:,.0f} VNĐ* (> 20.000.000 VNĐ)\n\n"
        f"👉 Vui lòng chọn hành động bên dưới:"
    )
    text_plain = (
        f"⚠️ YÊU CẦU PHÊ DUYỆT ĐƠN HÀNG GIÁ TRỊ LỚN\n\n"
        f"• Mã đơn: {order_name}\n"
        f"• Nhân viên yêu cầu: {employee_name}\n"
        f"• Tổng giá trị: {total:,.0f} VNĐ (> 20.000.000 VNĐ)\n\n"
        f"👉 Vui lòng chọn hành động bên dưới:"
    )
    
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Phê duyệt", "callback_data": f"approve_{order_name}_{token}"},
                {"text": "❌ Từ chối", "callback_data": f"reject_{order_name}_{token}"}
            ]
        ]
    }
    
    # 1. Direct Telegram Send (EZ Workflow with retry fallback)
    if bot_token and target_chat_id:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        for pmode, txt in [("Markdown", text_md), (None, text_plain)]:
            try:
                body = {"chat_id": target_chat_id, "text": txt, "reply_markup": reply_markup}
                if pmode:
                    body["parse_mode"] = pmode
                payload = json.dumps(body).encode()
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                urllib.request.urlopen(req, timeout=8)
                print(f"[APPROVAL EZ] Direct Telegram approval button sent to chat_id={target_chat_id}")
                return True
            except Exception as e:
                print(f"[APPROVAL EZ ERROR] Direct Telegram send failed (pmode={pmode}): {e}")
    
    # 2. Fallback to n8n if direct Telegram failed or URL provided
    url = os.getenv("N8N_APPROVAL_WEBHOOK_URL", "")
    if url:
        try:
            payload = json.dumps({"order_name": order_name, "total_amount": total,
                                  "employee_name": employee_name, "manager_chat_id": target_chat_id,
                                  "telegram_id": telegram_id}).encode()
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=8)
            return True
        except Exception as e:
            print(f"[N8N APPROVAL ERROR] {e}")
            return False
    return False
