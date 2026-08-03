from data_layer.connectors.odoo_rpc import OdooClient
from gateway.services.binding_service import get_bindings

class PermissionService:
    """
    Zero-Trust Dynamic Permission Service:
    Query trực tiếp từ Odoo 19 SaaS `res.users` & `res.groups` (Native Odoo Access Rights).
    - Đọc Tên hiển thị (name)
    - Đọc Trạng thái Kích hoạt (active)
    - Đọc nhóm quyền gốc trên Odoo UI (Bán hàng, Tồn kho, Kế toán, Quản trị viên)
    """
    def __init__(self):
        self.odoo_client = OdooClient()

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

        # Query trực tiếp từ bảng res.users của Odoo SaaS kèm all_group_ids
        try:
            records = self.odoo_client.search_read(
                model="res.users",
                domain=[["login", "=", email], ["active", "in", [True, False]]],
                fields=["id", "name", "login", "active", "role", "all_group_ids"],
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

        # Query trực tiếp các nhóm quyền (res.groups) mà user thuộc về trên Odoo
        full_group_names = []
        gids = user.get("all_group_ids", [])
        if gids:
            try:
                groups = self.odoo_client.search_read(
                    model="res.groups",
                    domain=[["id", "in", gids]],
                    fields=["id", "name", "full_name"],
                    limit=100
                )
                full_group_names = [str(g.get("full_name", "")) for g in groups]
            except Exception as e:
                print(f"⚠️ [PermissionService] Lỗi read res.groups: {e}")

        # Phân vai trò động 100% dựa trên Nhóm quyền thực tế từ giao diện Odoo UI
        has_sales_admin = any("Bán hàng / Quản trị viên" in fn or "Sales / Administrator" in fn for fn in full_group_names)
        has_sales_user = any("Bán hàng" in fn or "Sales" in fn for fn in full_group_names)
        has_inventory = any("Tồn kho" in fn or "Inventory" in fn for fn in full_group_names)
        has_accounting = any("Kế toán" in fn or "Accounting" in fn for fn in full_group_names)
        is_system_admin = odoo_role == "group_system" or any("Vai trò / Quản trị viên" in fn for fn in full_group_names)

        if is_system_admin or has_sales_admin:
            assigned_role = "sales_manager"
        elif has_sales_user:
            assigned_role = "sales_staff"
        elif has_inventory:
            assigned_role = "inventory_staff"
        elif has_accounting:
            assigned_role = "accountant"
        else:
            assigned_role = "viewer"

        user_info = {
            "odoo_user_id": user.get("id"),
            "email": email,
            "full_name": full_name,
            "role": assigned_role,
            "odoo_raw_role": odoo_role,
            "is_active_odoo": is_active,
            "odoo_groups": full_group_names
        }

        return {
            "allowed": True,
            "email": email,
            "user_info": user_info,
            "official_role": assigned_role,
        }
