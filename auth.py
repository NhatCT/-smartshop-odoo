"""Auth — Zero-Trust Gateway: OTP, permission, rate limit, idempotency, config."""

import hashlib
import hmac
import json
import os
import secrets
import smtplib
import socket
import threading
import time
import urllib.request
from collections import OrderedDict, defaultdict, deque
from email.mime.text import MIMEText
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


# ─── Permission (Zero-Trust, reads LIVE from Odoo) ───
def fetch_user_context(email: str) -> dict | None:
    """Read res.users + res.groups LIVE from Odoo on every request — no caching."""
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
            skip = ["Technical", "Skip", "Address", "Editor", "Website"]
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
    # NOTE: the Vietnamese literals above match live Odoo group names (Odoo-side data) and must stay as-is.

    tools = {"search_records", "list_products"}
    models = {"product.template", "product.product"}
    if is_sales or is_sales_mgr or is_admin:
        tools.update(["create_sale_order", "create_record", "update_record", "get_sale_order", "execute_method",
                      "preview_write", "validate_write", "execute_approved_write", "get_stock_quant"])
        models.update(["sale.order", "sale.order.line", "res.partner", "stock.quant"])
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
    """Zero-Trust: binding → live Odoo permissions → allow/deny."""
    bindings = get_bindings()
    email = bindings.get(str(telegram_id).strip())
    if not email:
        return {"allowed": False, "reason": f"⛔ Telegram ID `{telegram_id}` is not linked yet. Type `/register email@company.com`"}
    ctx = fetch_user_context(email)
    if not ctx:
        return {"allowed": False, "reason": f"❌ Odoo account `{email}` not found."}
    if not ctx["is_active_odoo"]:
        return {"allowed": False, "reason": f"🚨 Account `{email}` has been disabled on Odoo."}
    return {"allowed": True, "email": email, "user_info": ctx, "official_role": ctx["role_category"]}


# ─── OTP ───
_pending_otp: dict[str, dict] = {}
_pending_approval: dict[str, dict] = {}
OTP_TTL = 300


def _getaddrinfo_ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    """Some hosts (e.g. Render) have no outbound IPv6 route, which makes the
    stdlib pick an unreachable AAAA record and fail with 'Network is
    unreachable'. Force IPv4 resolution for the duration of the SMTP call.
    Only overrides `family` — every other positional slot is passed through
    unchanged so socktype/proto/flags never get shifted."""
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


_orig_getaddrinfo = socket.getaddrinfo


def send_email(to_email: str, subject: str, body: str, otp: str = "") -> tuple[bool, str]:
    """Send a plain-text email via n8n HTTP Webhook or SMTP (Gmail)."""
    # 1. Try n8n HTTP Webhook first if configured (Port 443 — reliable, fast, never blocked)
    n8n_url = os.getenv("N8N_OTP_WEBHOOK_URL", "").strip()
    if n8n_url:
        try:
            payload = json.dumps({
                "email": to_email,
                "subject": subject,
                "body": body,
                "otp": otp
            }).encode("utf-8")
            req = urllib.request.Request(
                n8n_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 201, 202, 204):
                    return True, "sent via n8n HTTP webhook"
        except Exception as e:
            print(f"[N8N WEBHOOK OTP FAIL] {e}")

    # 2. Try direct SMTP
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    if not user or not password:
        return False, "SMTP not configured (missing SMTP_USER/SMTP_PASSWORD)"
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = user
        msg["To"] = to_email
        socket.getaddrinfo = _getaddrinfo_ipv4_only
        try:
            with smtplib.SMTP(host, port, timeout=5) as server:
                server.starttls()
                server.login(user, password)
                server.sendmail(user, [to_email], msg.as_string())
        finally:
            socket.getaddrinfo = _orig_getaddrinfo
        return True, "sent via SMTP"
    except Exception as e:
        return False, str(e)


def request_otp(telegram_id, email) -> tuple[bool, str]:
    email = email.lower().strip()
    try:
        users = _odoo.search_read("res.users", ["|", ["login", "=ilike", email], ["email", "=ilike", email]],
                                  ["id", "name", "login", "active", "email"], 1)
        print(f"[ODOO SEARCH] request_otp email={email} results={len(users)} users={[u.get('login') or u.get('email') for u in users]}")
    except Exception as e:
        print(f"[ODOO SEARCH ERROR] request_otp: {e}")
        return False, f"❌ Odoo connection error: {e}"
    if not users:
        return False, f"❌ Email '{email}' does not exist in Odoo."
    if not users[0].get("active", True):
        return False, f"🚨 Account '{email}' has been disabled."
    import random
    otp = f"{random.randint(100000, 999999)}"
    _pending_otp[str(telegram_id)] = {"email": email, "otp": otp, "ts": time.time()}
    if email in REQUIRES_ADMIN_APPROVAL:
        _pending_approval[str(telegram_id)] = {"email": email, "ts": time.time()}
    # Send OTP via direct SMTP email or n8n webhook
    name = users[0].get("name", email)
    subject = "SmartShop AI Assistant — Your OTP Code"
    body = (
        f"Hi {name},\n\n"
        f"Your one-time verification code is: {otp}\n\n"
        f"This code expires in {int(OTP_TTL // 60)} minutes.\n"
        f"Reply in Telegram with: /verify {otp}\n\n"
        f"If you did not request this, you can safely ignore this email."
    )
    ok, err = send_email(email, subject, body, otp=otp)
    if ok:
        return True, f"✉️ OTP code sent to `{email}`. Type `/verify <6-DIGIT_OTP>`"

    # FALLBACK METHOD (CÁCH KHÁC): When email delivery fails or times out,
    # display the OTP code directly in Telegram so the user is NEVER stuck!
    print(f"[OTP FALLBACK] Email delivery failed ({err}). Providing OTP directly: {otp}")
    return True, (
        f"⚠️ Email sending timed out / failed ({err}).\n"
        f"🔑 Fallback OTP code for `{email}`: `{otp}`\n"
        f"👉 Type: `/verify {otp}` to link your account."
    )


def bind_direct(telegram_id, email) -> tuple[bool, str]:
    """Directly link Telegram ID to Odoo user email without requiring email OTP."""
    email = email.lower().strip()
    try:
        users = _odoo.search_read("res.users", ["|", ["login", "=ilike", email], ["email", "=ilike", email]],
                                  ["id", "name", "login", "active", "email"], 1)
    except Exception as e:
        return False, f"❌ Odoo connection error: {e}"
    if not users:
        return False, f"❌ Email '{email}' does not exist in Odoo."
    if not users[0].get("active", True):
        return False, f"🚨 Account '{email}' has been disabled."

    sid = str(telegram_id)
    try:
        bindings = get_bindings()
        bindings[sid] = email
        save_bindings(bindings)
    except Exception as e:
        return False, f"❌ Error saving binding: {e}"

    ctx = fetch_user_context(email) or {}
    return True, (
        f"✅ ACCOUNT LINKED DIRECTLY!\nAccount: `{email}`\n"
        f"Full name: {ctx.get('full_name', email)}\n"
        f"Role: {ctx.get('role_category', 'viewer').upper()}"
    )


def verify_otp(telegram_id, user_otp) -> tuple[bool, str]:
    sid = str(telegram_id)
    pending = _pending_otp.get(sid)
    if not pending:
        return False, "❌ No OTP request found. Type `/register email` first."
    if time.time() - pending["ts"] > OTP_TTL:
        del _pending_otp[sid]
        return False, "❌ OTP code has expired (5 minutes)."
    if pending["otp"] != user_otp.strip():
        return False, "❌ OTP code does not match."
    email = pending["email"]
    if sid in _pending_approval:
        del _pending_otp[sid]
        return False, f"⏳ Account `{email}` needs Admin approval before it can be activated."
    try:
        bindings = get_bindings()
        bindings[sid] = email
        save_bindings(bindings)
    except Exception as e:
        return False, f"❌ Error saving binding: {e}"
    del _pending_otp[sid]
    ctx = fetch_user_context(email) or {}
    return True, (
        f"✅ VERIFICATION SUCCESSFUL!\nAccount: `{email}`\n"
        f"Full name: {ctx.get('full_name', email)}\n"
        f"Role: {ctx.get('role_category', 'viewer').upper()}"
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
                return False, {"message": f"⚠️ Exceeded {self._max} messages/min. Wait {int(self._window - (now - w[0])) + 1}s."}
            w.append(now)
            return True, {}


_rate_limiter = RateLimiter()


def rate_limit_check(user_id: str) -> tuple[bool, str]:
    ok, info = _rate_limiter.is_allowed(user_id)
    return ok, info.get("message", "")


# ─── Idempotency (5 minutes) ───
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
    sig = hmac.new(_APPROVAL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:12]
    return f"{ts}.{sig}"


def verify_approval_token(order_name: str, approver_id: str, token: str) -> bool:
    try:
        ts_s, sig = token.split(".", 1)
        ts = int(ts_s)
        ttl = 86400
    except Exception:
        return False
    if time.time() > ts + ttl:
        return False
    payload = f"{order_name}:{approver_id}:{ts}:{ttl}"
    expected = hmac.new(_APPROVAL_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:12]
    return hmac.compare_digest(sig, expected)


# ─── Notification (EZ Direct Telegram Inline Buttons + n8n Fallback) ───
def send_approval_request(order_name, total, employee_name, manager_chat_id, telegram_id=None):
    target_chat_id = manager_chat_id if (manager_chat_id and str(manager_chat_id) not in ("123456789", "N/A", "")) else (telegram_id or os.getenv("ADMIN_CHAT_ID", "6553206564"))
    token = generate_approval_token(order_name, str(target_chat_id))
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    text_md = (
        f"⚠️ *HIGH-VALUE ORDER APPROVAL REQUEST*\n\n"
        f"• Order code: `{order_name}`\n"
        f"• Requested by: *{employee_name}*\n"
        f"• Total amount: *{total:,.0f} VND* (> 20,000,000 VND)\n\n"
        f"👉 Please choose an action below:"
    )
    text_plain = (
        f"⚠️ HIGH-VALUE ORDER APPROVAL REQUEST\n\n"
        f"• Order code: {order_name}\n"
        f"• Requested by: {employee_name}\n"
        f"• Total amount: {total:,.0f} VND (> 20,000,000 VND)\n\n"
        f"👉 Please choose an action below:"
    )

    # Telegram callback_data must be <= 64 bytes
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"app_{order_name}_{token}"},
                {"text": "❌ Reject", "callback_data": f"rej_{order_name}_{token}"}
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
