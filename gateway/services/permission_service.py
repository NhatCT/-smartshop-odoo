from data_layer.connectors.odoo_rpc import OdooClient
from gateway.services.binding_service import get_bindings

class PermissionService:
    """
    Zero-Trust Dynamic Permission Service:
    Query trực tiếp từ Odoo 19 SaaS `res.users` table.
    - Đọc Tên hiển thị (name)
    - Đọc Trạng thái Kích hoạt (active)
    - Đọc Vai trò thực tế trên Odoo UI (role: group_system -> sales_manager, group_user -> sales_staff)
    """
    def __init__(self):
        self.odoo_client = OdooClient()

    def _map_odoo_role_to_system_role(self, odoo_role: str, user_name: str) -> str:
        name_lower = (user_name or "").lower()
        if "kho" in name_lower or "inventory" in name_lower:
            return "inventory_staff"
        if "kế toán" in name_lower or "accountant" in name_lower:
            return "accountant"

        if odoo_role == "group_system":
            return "sales_manager"
        elif odoo_role == "group_user":
            return "sales_staff"
        return "viewer"

    def process_incoming_request(self, telegram_id: int):
        bindings = get_bindings()
        str_id = str(telegram_id)
        email = bindings.get(str_id)
        if not email:
            return {
                "allowed": False,
                "reason": (
                    f"⛔ **TRUY CẬP BỊ TỪ CHỐI** (Zero-Trust Policy)\n\n"
                    f"Telegram ID `{telegram_id}` chưa liên kết với tài khoản Odoo nào.\n\n"
                    f"👉 Gõ lệnh: `/register email_odoo_cua_ban@gmail.com` để xác thực!"
                )
            }

        # Query trực tiếp từ bảng res.users của Odoo SaaS
        try:
            records = self.odoo_client.search_read(
                model="res.users",
                domain=[["login", "=", email], ["active", "in", [True, False]]],
                fields=["id", "name", "login", "active", "role"],
                limit=1
            )
        except Exception as e:
            print(f"⚠️ [PermissionService] Lỗi query res.users từ Odoo: {e}")
            records = []

        if not records:
            return {
                "allowed": False,
                "reason": f"❌ Không tìm thấy tài khoản Odoo với email `{email}`."
            }

        user = records[0]
        full_name = user.get("name") or email.split("@", 1)[0].replace(".", " ").title()
        is_active = user.get("active", True)
        odoo_role = user.get("role", "group_user")

        if not is_active:
            return {
                "allowed": False,
                "reason": (
                    f"🚨 **TÀI KHOẢN BỊ VÔ HIỆU HÓA TRÊN ODOO 19**\n\n"
                    f"Tài khoản Odoo `{email}` của **{full_name}** "
                    f"đã bị Admin khóa/archive trực tiếp trên Odoo Web UI.\n"
                    f"Vui lòng liên hệ quản trị viên."
                )
            }

        assigned_role = self._map_odoo_role_to_system_role(odoo_role, full_name)

        user_info = {
            "odoo_user_id": user.get("id"),
            "email": email,
            "full_name": full_name,
            "role": assigned_role,
            "odoo_raw_role": odoo_role,
            "is_active_odoo": is_active,
        }

        return {
            "allowed": True,
            "email": email,
            "user_info": user_info,
            "official_role": assigned_role,
        }
