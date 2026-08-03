import os

def create_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# ----------------- gateway/core/security.py -----------------
security_py = """import os
import hmac
import hashlib

SECRET_SALT = os.getenv("GATEWAY_SECRET_SALT", "SmartShopOdoo19AntiHijackSecretSalt2026")

def generate_approval_token(order_name, telegram_id):
    msg = f"{order_name}:{telegram_id}".encode('utf-8')
    return hmac.new(SECRET_SALT.encode('utf-8'), msg, hashlib.sha256).hexdigest()[:8]

def verify_approval_token(order_name, telegram_id, token):
    expected = generate_approval_token(order_name, telegram_id)
    return hmac.compare_digest(expected, token)
"""
create_file("gateway/core/security.py", security_py)

# ----------------- gateway/repositories/binding_repository.py -----------------
binding_repo_py = """import os
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
create_file("gateway/repositories/binding_repository.py", binding_repo_py)

# ----------------- gateway/config/constants.py -----------------
constants_py = """
ROLE_TOOLS_MAP = {
    "sales_manager":    ["search_read", "create", "write", "action_confirm", "eval_analytics"],
    "sales_staff":      ["search_read", "create", "write"],
    "inventory_staff":  ["search_read", "stock_quant_check"],
    "accountant":       ["search_read"],
    "viewer":           ["search_read"],
}

PREDEFINED_EMAIL_ROLES = {
    "nhatlovely2017@gmail.com":     "sales_manager",
    "anthony@technext.asia":        "sales_manager",
    "2251052082nhat@ou.edu.vn":     "inventory_staff",
    "thanhnhat.career@gmail.com":   "accountant",
}

PREDEFINED_EMAIL_NAMES = {
    "nhatlovely2017@gmail.com":     "Nguyễn Thành Nhật (Sales Manager)",
    "anthony@technext.asia":        "Anthony (Quản trị viên / Executive Manager)",
    "2251052082nhat@ou.edu.vn":     "Nguyễn Thành Nhật (Nhân viên Kho)",
    "thanhnhat.career@gmail.com":   "Nguyễn Thành Nhật (Kế toán - Đã nghỉ)",
}
"""
create_file("gateway/config/constants.py", constants_py)

# ----------------- gateway/services/notification_service.py -----------------
notification_service_py = """import os
import json
import urllib.request

class NotificationService:
    def __init__(self):
        self.n8n_otp_url = os.getenv(
            "N8N_OTP_WEBHOOK_URL",
            "https://odooworkflow.app.n8n.cloud/webhook/send-otp-email"
        )

    def send_otp_via_n8n(self, to_email, otp_code, employee_name):
        try:
            payload = json.dumps({
                "to_email": to_email,
                "otp_code": otp_code,
                "employee_name": employee_name
            }).encode('utf-8')
            req = urllib.request.Request(
                self.n8n_otp_url,
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return result.get("ok", False) or resp.status == 200
        except Exception as e:
            print(f"   ⚠️ [N8N OTP EMAIL ERROR]: {e}")
            return False
"""
create_file("gateway/services/notification_service.py", notification_service_py)

# ----------------- gateway/repositories/user_repository.py -----------------
user_repository_py = """from data_layer.connectors.odoo_rpc import OdooClient
from gateway.config.constants import PREDEFINED_EMAIL_NAMES, PREDEFINED_EMAIL_ROLES, ROLE_TOOLS_MAP

class UserRepository:
    def __init__(self):
        self.client = OdooClient()

    def get_odoo_user_info(self, email):
        try:
            odoo = self.client.connect()
            user_ids = odoo.env['res.users'].search([['login', '=', email]])
            if not user_ids:
                user_ids = odoo.env['res.users'].search([['login', '=', email], ['active', 'in', [True, False]]])
            if not user_ids:
                return None

            uid = user_ids[0] if isinstance(user_ids, list) else user_ids
            user = odoo.env['res.users'].browse(uid)

            try:
                is_active = bool(user.active)
                odoo_name = user.name
            except Exception:
                is_active = True
                odoo_name = email.split('@')[0]

            full_name = PREDEFINED_EMAIL_NAMES.get(email, odoo_name)
            role_label = PREDEFINED_EMAIL_ROLES.get(email, "viewer")
            allowed_tools = ROLE_TOOLS_MAP.get(role_label, ROLE_TOOLS_MAP["viewer"])

            return {
                "odoo_user_id": uid,
                "full_name": full_name,
                "email": email,
                "is_active_odoo": is_active,
                "role": role_label,
                "allowed_tools": allowed_tools
            }
        except Exception as e:
            print(f"   ⚠️ Lỗi truy vấn Odoo: {e}")
            return None
"""
create_file("gateway/repositories/user_repository.py", user_repository_py)

# ----------------- gateway/services/permission_service.py -----------------
permission_service_py = """from gateway.repositories.binding_repository import get_bindings
from gateway.repositories.user_repository import UserRepository

class PermissionService:
    def __init__(self):
        self.user_repo = UserRepository()

    def process_incoming_request(self, telegram_id: int):
        bindings = get_bindings()
        str_id = str(telegram_id)
        email = bindings.get(str_id)
        if not email:
            return {
                "allowed": False,
                "reason": (
                    f"⛔ **TRUY CẬP BỊ TỪ CHỐI** (Zero-Trust Policy)\\n\\n"
                    f"Telegram ID `{telegram_id}` chưa liên kết với tài khoản Odoo nào.\\n\\n"
                    f"👉 Gõ lệnh: `/register email_odoo_cua_ban@gmail.com` để xác thực!"
                )
            }

        user_info = self.user_repo.get_odoo_user_info(email)

        if not user_info:
            return {
                "allowed": False,
                "reason": (
                    f"❌ Không thể xác thực tài khoản `{email}` từ Odoo 19 SaaS.\\n"
                    f"Vui lòng liên hệ Admin."
                )
            }

        if not user_info["is_active_odoo"]:
            return {
                "allowed": False,
                "reason": (
                    f"🚨 **TÀI KHOẢN BỊ VÔ HIỆU HÓA TRÊN ODOO 19**\\n\\n"
                    f"Tài khoản Odoo `{email}` của **{user_info['full_name']}** "
                    f"đã bị Admin khóa trực tiếp trên Odoo Web UI.\\n"
                    f"Vui lòng liên hệ quản trị viên."
                )
            }

        return {
            "allowed": True,
            "email": email,
            "user_info": user_info,
            "official_role": user_info["role"]
        }
"""
create_file("gateway/services/permission_service.py", permission_service_py)

# ----------------- gateway/services/otp_service.py -----------------
otp_service_py = """import time
import random
from gateway.services.notification_service import NotificationService
from gateway.repositories.user_repository import UserRepository
from gateway.repositories.binding_repository import get_bindings, save_bindings

PENDING_OTP_STORE = {}

class OTPService:
    def __init__(self):
        self.notification_service = NotificationService()
        self.user_repo = UserRepository()

    def request_otp(self, telegram_id, email):
        email = email.lower().strip()
        user_info = self.user_repo.get_odoo_user_info(email)
        if not user_info:
            return False, f"❌ Email '{email}' không tồn tại trong hệ thống Odoo 19 SaaS SmartShop!\\nVui lòng liên hệ Admin để được tạo tài khoản Odoo."
        
        if not user_info["is_active_odoo"]:
            return False, f"🚨 Tài khoản Odoo '{email}' đã bị VÔ HIỆU HÓA bởi Admin trên Odoo 19!\\nMọi truy cập bị từ chối theo chính sách Zero-Trust."

        otp_code = f"{random.randint(100000, 999999)}"
        PENDING_OTP_STORE[str(telegram_id)] = {
            "email": email,
            "otp": otp_code,
            "timestamp": time.time()
        }

        sent = self.notification_service.send_otp_via_n8n(email, otp_code, user_info["full_name"] if user_info else email)
        if sent:
            print(f"\\n✅ [OTP EMAIL SENT via n8n]: Telegram ID [{telegram_id}] | Email: {email}")
            return True, (
                f"✉️ **Mã xác thực OTP đã được gửi tới Email:** `{email}`\\n\\n"
                f"Vui lòng kiểm tra hộp thư của bạn và nhập lệnh xác thực:\\n"
                f"`/verify <MÃ_OTP_6_SỐ>`"
            )
        else:
            print(f"\\n⚠️ [N8N EMAIL FAILED] - OTP cho {email}: >>> {otp_code} <<<")
            return True, (
                f"🔑 OTP da duoc tao nhung email chua gui duoc (n8n chua kich hoat).\\n"
                f"Vui long lien he Admin de lay ma OTP."
            )

    def verify_otp_and_bind(self, telegram_id, user_otp):
        str_id = str(telegram_id)
        user_otp_str = user_otp.strip()

        if "@" in user_otp_str:
            return False, (
                f"⚠️ **CÚ PHÁP CHƯA ĐÚNG!**\\n\\n"
                f"Để đăng ký email `{user_otp_str}`, bạn hãy gõ lệnh:\\n"
                f"`/register {user_otp_str}`\\n\\n"
                f"Sau khi nhận được **Mã OTP 6 số** qua hòm thư Email, bạn gõ tiếp:\\n"
                f"`/verify <MÃ_OTP_6_SỐ>` (ví dụ: `/verify 714959`)."
            )

        pending = PENDING_OTP_STORE.get(str_id)
        if not pending:
            return False, "❌ Không tìm thấy yêu cầu OTP. Vui lòng gõ `/register email@smartshop.com` trước!"
        if pending["otp"] != user_otp_str:
            return False, "❌ Mã OTP không khớp. Vui lòng kiểm tra lại!"

        email = pending["email"]
        bindings = get_bindings()
        bindings[str_id] = email
        save_bindings(bindings)
        del PENDING_OTP_STORE[str_id]

        user_info = self.user_repo.get_odoo_user_info(email)
        role = user_info["role"] if user_info else "viewer"

        return True, (
            f"✅ **XÁC THỰC THÀNH CÔNG!**\\n\\n"
            f"Tài khoản Odoo: `{email}`\\n"
            f"Phân quyền: **{role.upper()}**\\n\\n"
            f"Bây giờ bạn đã có thể bắt đầu chat với tôi để tra cứu thông tin!"
        )
"""
create_file("gateway/services/otp_service.py", otp_service_py)

# ----------------- gateway/core/rate_limiter.py -----------------
rate_limiter_py = """import time
import asyncio
from collections import defaultdict

class RateLimiter:
    def __init__(self, limit=30, window=60):
        self.limit = limit
        self.window = window
        self._requests = defaultdict(list)
        self._lock = asyncio.Lock()

    async def acquire(self, user_id: str) -> bool:
        now = time.time()
        async with self._lock:
            timestamps = self._requests[user_id]
            valid_timestamps = [ts for ts in timestamps if now - ts < self.window]
            self._requests[user_id] = valid_timestamps
            if len(valid_timestamps) >= self.limit:
                return False
            self._requests[user_id].append(now)
            return True

_global_rate_limiter = None
def get_rate_limiter(limit=30, window=60):
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(limit, window)
    return _global_rate_limiter
"""
create_file("gateway/core/rate_limiter.py", rate_limiter_py)

# ----------------- gateway/core/idempotency.py -----------------
idempotency_py = """import time
import asyncio

class IdempotencyGuard:
    def __init__(self, ttl_seconds=10):
        self.ttl_seconds = ttl_seconds
        self._processed = {}
        self._lock = asyncio.Lock()

    async def check_and_record(self, key: str) -> bool:
        now = time.time()
        async with self._lock:
            if key in self._processed:
                timestamp = self._processed[key]
                if now - timestamp < self.ttl_seconds:
                    return False
            self._processed[key] = now
            return True

_global_idempotency_guard = None
def get_idempotency_guard(ttl_seconds=10):
    global _global_idempotency_guard
    if _global_idempotency_guard is None:
        _global_idempotency_guard = IdempotencyGuard(ttl_seconds)
    return _global_idempotency_guard
"""
create_file("gateway/core/idempotency.py", idempotency_py)

# ----------------- gateway/auth.py (Facade) -----------------
auth_py = """from gateway.services.permission_service import PermissionService
from gateway.services.otp_service import OTPService
from gateway.config.constants import ROLE_TOOLS_MAP, PREDEFINED_EMAIL_ROLES
from gateway.repositories.binding_repository import get_bindings, save_bindings
from gateway.core.security import generate_approval_token, verify_approval_token

class SecurityGateway:
    def __init__(self):
        self.permission_service = PermissionService()
        self.otp_service = OTPService()
    
    def process_incoming_request(self, telegram_id: int):
        return self.permission_service.process_incoming_request(telegram_id)
        
    def request_otp(self, telegram_id, email):
        return self.otp_service.request_otp(telegram_id, email)
        
    def verify_otp_and_bind(self, telegram_id, user_otp):
        return self.otp_service.verify_otp_and_bind(telegram_id, user_otp)

__all__ = ["SecurityGateway", "ROLE_TOOLS_MAP", "PREDEFINED_EMAIL_ROLES", "generate_approval_token", "verify_approval_token", "get_bindings", "save_bindings"]
"""
create_file("gateway/auth.py", auth_py)

# ----------------- gateway/__init__.py -----------------
init_py = """from .auth import SecurityGateway
from .core.rate_limiter import RateLimiter, get_rate_limiter
from .core.idempotency import IdempotencyGuard, get_idempotency_guard

__all__ = ["SecurityGateway", "RateLimiter", "get_rate_limiter", "IdempotencyGuard", "get_idempotency_guard"]
"""
create_file("gateway/__init__.py", init_py)
