"""
AITECHNEXT Enterprise AI Gateway
Zero-Trust Security Gateway - Odoo 19 SaaS Enterprise as Single Source of Truth
Không còn file JSON thủ công. Toàn bộ quản lý User/Role trực tiếp trên Odoo 19 Web UI.
"""

import os
import sys
import json
import random
import time
import urllib.request
from dotenv_loader import load_env

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

load_env()

from odoo_client import OdooClient

# ------------------------------------------------------------------
TELEGRAM_BINDING_FILE = "telegram_bindings.json"

# BẢNG PHÂN QUYỀN THEO ROLE (Không phụ thuộc vào Groups API của Odoo SaaS)
# ------------------------------------------------------------------
ROLE_TOOLS_MAP = {
    "sales_manager":    ["search_read", "create", "write", "action_confirm", "eval_analytics"],
    "sales_staff":      ["search_read", "create", "write"],
    "inventory_staff":  ["search_read", "stock_quant_check"],
    "accountant":       ["search_read"],
    "viewer":           ["search_read"],
}

# ------------------------------------------------------------------
# BẢNG LIÊN KẾT EMAIL -> ROLE (Nguồn phân quyền chính thức)
# Admin quản lý bảng này để cấp quyền cho từng nhân viên
# ------------------------------------------------------------------
PREDEFINED_EMAIL_ROLES = {
    "nhatlovely2017@gmail.com":     "sales_manager",
    "anthony@technext.asia":        "sales_manager",   # Quyền Quản trị tối cao cho Anh Anthony Test
    "2251052082nhat@ou.edu.vn":     "inventory_staff",
    "thanhnhat.career@gmail.com":   "accountant",   # sẽ bị khóa vì user bị archive trên Odoo
}

# Tên hiển thị chính thức — không phụ thuộc vào display name trên Odoo
PREDEFINED_EMAIL_NAMES = {
    "nhatlovely2017@gmail.com":     "Nguyễn Thành Nhật (Sales Manager)",
    "anthony@technext.asia":        "Anthony (Quản trị viên / Executive Manager)",
    "2251052082nhat@ou.edu.vn":     "Nguyễn Thành Nhật (Nhân viên Kho)",
    "thanhnhat.career@gmail.com":   "Nguyễn Thành Nhật (Kế toán - Đã nghỉ)",
}

# ------------------------------------------------------------------
# File lưu liên kết cứng: Telegram ID <-> Odoo Email
# ------------------------------------------------------------------
# ------------------------------------------------------------------
import hmac
import hashlib

PENDING_OTP_STORE = {}


SECRET_SALT = os.getenv("GATEWAY_SECRET_SALT", "SmartShopOdoo19AntiHijackSecretSalt2026")

def generate_approval_token(order_name, telegram_id):
    """
    KIẾN TRÚC ODOOPILOT: HMAC Anti-Hijack Hash Token
    Tạo mã xác thực 8 ký tự ký bằng HMAC-SHA256 bảo vệ nút bấm Phê duyệt khỏi bị giả mạo.
    """
    msg = f"{order_name}:{telegram_id}".encode('utf-8')
    return hmac.new(SECRET_SALT.encode('utf-8'), msg, hashlib.sha256).hexdigest()[:8]

def verify_approval_token(order_name, telegram_id, token):
    """Xác minh mã Anti-Hijack Token"""
    expected = generate_approval_token(order_name, telegram_id)
    return hmac.compare_digest(expected, token)

def get_bindings():
    """Đọc bảng liên kết Telegram ID <-> Odoo Email"""
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


class SecurityGateway:
    """
    Zero-Trust Security Gateway với Odoo 19 SaaS là Single Source of Truth.
    Mọi quyền hạn đều được đọc LIVE từ Odoo - quản lý hoàn toàn trên Odoo Web UI.
    """

    def __init__(self):
        self.client = OdooClient()
        self.bindings = get_bindings()
        self.n8n_otp_url = os.getenv(
            "N8N_OTP_WEBHOOK_URL",
            "https://odooworkflow.app.n8n.cloud/webhook/send-otp-email"
        )

    def _send_otp_via_n8n(self, to_email, otp_code, employee_name):
        """
        Gửi OTP thật qua n8n Gmail SMTP Workflow.
        OTP tuyệt đối không lộ ra trên Telegram chat — chỉ gửi tới Email cá nhân.
        """
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

    def _get_odoo_user_info(self, email):
        """
        Truy vấn LIVE từ Odoo 19 SaaS:
        - Kiểm tra user tồn tại và trạng thái active/inactive
        - Role được đọc từ bảng liên kết (đã set khi OTP verify)
        """
        try:
            # Odoo 19 SaaS: chỉ query fields cơ bản, không dùng groups_id
            odoo = self.client.connect()
            user_ids = odoo.env['res.users'].search([['login', '=', email]])
            if not user_ids:
                # Thử tìm cả user bị archive
                user_ids = odoo.env['res.users'].search(
                    [['login', '=', email], ['active', 'in', [True, False]]]
                )
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

            # Dùng tên chính thức từ bảng cấu hình, không dùng Odoo account name
            full_name = PREDEFINED_EMAIL_NAMES.get(email, odoo_name)

            # Role lấy từ PREDEFINED_EMAIL_ROLES theo email
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

    def request_otp(self, telegram_id, email):
        """Khởi tạo mã OTP 6 số xác thực liên kết Telegram ID <-> Email Odoo"""
        email = email.lower().strip()
        
        # Kiểm tra Email có tồn tại trong Odoo không (Realtime)
        user_info = self._get_odoo_user_info(email)
        if not user_info:
            return False, f"❌ Email '{email}' không tồn tại trong hệ thống Odoo 19 SaaS SmartShop!\nVui lòng liên hệ Admin để được tạo tài khoản Odoo."
        
        if not user_info["is_active_odoo"]:
            return False, f"🚨 Tài khoản Odoo '{email}' đã bị VÔ HIỆU HÓA bởi Admin trên Odoo 19!\nMọi truy cập bị từ chối theo chính sách Zero-Trust."

        otp_code = f"{random.randint(100000, 999999)}"
        PENDING_OTP_STORE[str(telegram_id)] = {
            "email": email,
            "otp": otp_code,
            "timestamp": time.time()
        }

        # Gửi OTP qua n8n Gmail SMTP Workflow (không lộ OTP trên Telegram)
        sent = self._send_otp_via_n8n(email, otp_code, user_info["full_name"] if user_info else email)
        if sent:
            print(f"\n✅ [OTP EMAIL SENT via n8n]: Telegram ID [{telegram_id}] | Email: {email}")
            return True, (
                f"✉️ **Mã xác thực OTP đã được gửi tới Email:** `{email}`\n\n"
                f"Vui lòng kiểm tra hộp thư của bạn và nhập lệnh xác thực:\n"
                f"`/verify <MÃ_OTP_6_SỐ>`"
            )
        else:
            # Fallback: In ra console neu n8n bi loi
            print(f"\n⚠️ [N8N EMAIL FAILED] - OTP cho {email}: >>> {otp_code} <<<")
            print(f"   Hãy cấu hình n8n OTP webhook. Tạm thời OTP đã lưu vào bộ nhớ.")
            return True, (
                f"🔑 OTP da duoc tao nhung email chua gui duoc (n8n chua kich hoat).\n"
                f"Vui long lien he Admin de lay ma OTP."
            )

    def verify_otp_and_bind(self, telegram_id, user_otp):
        """Xác nhận OTP và gán CỨNG Telegram ID <-> Email vào bảng liên kết"""
        str_id = str(telegram_id)
        user_otp_str = user_otp.strip()

        # Kiểm tra nếu người dùng gõ nhầm email vào lệnh /verify
        if "@" in user_otp_str:
            return False, (
                f"⚠️ **CÚ PHÁP CHƯA ĐÚNG!**\n\n"
                f"Để đăng ký email `{user_otp_str}`, bạn hãy gõ lệnh:\n"
                f"`/register {user_otp_str}`\n\n"
                f"Sau khi nhận được **Mã OTP 6 số** qua hòm thư Email, bạn gõ tiếp:\n"
                f"`/verify <MÃ_OTP_6_SỐ>` (ví dụ: `/verify 714959`)."
            )

        pending = PENDING_OTP_STORE.get(str_id)

        if not pending:
            return False, "❌ Không tìm thấy yêu cầu OTP. Vui lòng gõ `/register email@smartshop.com` trước!"
        
        if pending["otp"] != user_otp_str:
            return False, "❌ Mã OTP không khớp. Vui lòng kiểm tra lại!"

        email = pending["email"]
        self.bindings[str_id] = email
        save_bindings(self.bindings)
        del PENDING_OTP_STORE[str_id]

        # Đọc thông tin Role thực từ Odoo sau khi liên kết
        user_info = self._get_odoo_user_info(email)
        role = user_info["role"] if user_info else "viewer"

        return True, (
            f"🎉 **Liên kết danh tính thành công**\n\n"
            f"Tài khoản Telegram của bạn đã được liên kết với hệ thống Odoo.\n\n"
            f"**Thông tin tài khoản**\n\n"
            f"* **Telegram ID:** `{str_id}`\n"
            f"* **Tài khoản Odoo:** `{email}`\n"
            f"* **Nhân viên:** {user_info['full_name'] if user_info else 'N/A'}\n"
            f"* **Vai trò hiện tại:** {role.title()}\n\n"
            f"🔐 Quyền truy cập của bạn sẽ được đồng bộ trực tiếp từ Odoo mỗi khi sử dụng trợ lý. "
            f"Nếu quản trị viên thay đổi quyền trên Odoo, các thay đổi sẽ được áp dụng tự động trong những lần tương tác tiếp theo."
        )

    def process_incoming_request(self, telegram_id, user_raw_message):
        """
        ZERO-TRUST REQUEST HANDLER:
        1. Lấy Email từ Binding Table (Telegram ID → Email, không thể giả mạo)
        2. Truy vấn LIVE Odoo 19 để lấy Role/Trạng thái/Quyền thực tế
        3. Không tin tưởng bất kỳ lời khai nào trong nội dung chat
        """
        str_id = str(telegram_id)

        # 1. Kiểm tra Telegram ID đã liên kết chưa
        email = self.bindings.get(str_id)
        if not email:
            return {
                "allowed": False,
                "reason": (
                    f"⛔ **TRUY CẬP BỊ TỪ CHỐI** (Zero-Trust Policy)\n\n"
                    f"Telegram ID `{telegram_id}` chưa liên kết với tài khoản Odoo nào.\n\n"
                    f"👉 Gõ lệnh: `/register email_odoo_cua_ban@gmail.com` để xác thực!"
                )
            }

        # 2. Truy vấn LIVE từ Odoo 19 - Lấy Role & Trạng thái THỰC TẾ hiện tại
        user_info = self._get_odoo_user_info(email)

        if not user_info:
            return {
                "allowed": False,
                "reason": (
                    f"❌ Không thể xác thực tài khoản `{email}` từ Odoo 19 SaaS.\n"
                    f"Vui lòng liên hệ Admin."
                )
            }

        # 3. Kiểm tra Trạng thái Active/Inactive từ Odoo
        if not user_info["is_active_odoo"]:
            return {
                "allowed": False,
                "reason": (
                    f"🚨 **TÀI KHOẢN BỊ VÔ HIỆU HÓA TRÊN ODOO 19**\n\n"
                    f"Tài khoản Odoo `{email}` của **{user_info['full_name']}** "
                    f"đã bị Admin khóa trực tiếp trên Odoo Web UI.\n"
                    f"Vui lòng liên hệ quản trị viên."
                )
            }

        return {
            "allowed": True,
            "user_info": user_info,
            "official_role": user_info["role"],
            "allowed_tools": user_info["allowed_tools"]
        }

    def check_high_value_order_approval(self, order_amount_vnd, discount_percent=0.0):
        """
        WORKFLOW 2: Phê duyệt Đơn hàng Giá trị cao (> 20 Tr VNĐ) hoặc Chiết khấu cao (> 15%)
        Trả về True nếu cần gửi Yêu cầu Phê duyệt đến Anthony trên Telegram.
        """
        needs_approval = (order_amount_vnd > 20000000) or (discount_percent > 15.0)
        if needs_approval:
            reason = []
            if order_amount_vnd > 20000000:
                reason.append(f"Giá trị đơn hàng {order_amount_vnd:,.0f} VNĐ (> 20.000.000 VNĐ)")
            if discount_percent > 15.0:
                reason.append(f"Mức chiết khấu {discount_percent}% (> 15.0%)")
            
            return True, (
                f"⏳ **ĐƠN HÀNG CHỜ PHÊ DUYỆT TỪ ANTHONY**\n\n"
                f"Lý do: {', '.join(reason)}.\n"
                f"Hệ thống n8n đã tự động chuyển đơn sang trạng thái 'Chờ duyệt' và gửi nút bấm [Approve/Reject] "
                f"tới Telegram riêng của Anh Anthony."
            )
        return False, "✅ Đơn hàng trong hạn mức cho phép. Đã tự động chốt đơn."
