from data_layer.connectors.odoo_rpc import OdooClient
from gateway.services.binding_service import get_bindings

class PermissionService:
    """
    Zero-Trust Auth Gateway — Minimal Surface.
    Chỉ làm đúng 1 việc: Xác minh User tồn tại & active trên Odoo.
    Không map role, không phán xét quyền → Giao toàn bộ cho Claude suy luận từ raw groups.
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

        # Xác minh user tồn tại và đang active trên Odoo SaaS
        try:
            records = self.odoo_client.search_read(
                model="res.users",
                domain=[["login", "=", email], ["active", "in", [True, False]]],
                fields=["id", "name", "login", "active", "all_group_ids"],
                limit=1
            )
        except Exception as e:
            print(f"⚠️ [PermissionService] Lỗi query res.users: {e}")
            records = []

        if not records:
            return {
                "allowed": False,
                "reason": f"❌ Không tìm thấy tài khoản Odoo với email `{email}`."
            }

        user = records[0]
        full_name = user.get("name") or email.split("@", 1)[0].replace(".", " ").title()
        is_active = user.get("active", True)

        if not is_active:
            return {
                "allowed": False,
                "reason": (
                    f"🚨 **TÀI KHOẢN BỊ VÔ HIỆU HÓA TRÊN ODOO 19**\n\n"
                    f"Tài khoản `{email}` của **{full_name}** đã bị Admin khóa.\n"
                    f"Vui lòng liên hệ quản trị viên."
                )
            }

        # Đọc danh sách nhóm quyền thực tế từ Odoo — gửi thẳng cho Claude suy luận
        odoo_groups = []
        gids = user.get("all_group_ids", [])
        if gids:
            try:
                groups = self.odoo_client.search_read(
                    model="res.groups",
                    domain=[["id", "in", gids]],
                    fields=["id", "full_name"],
                    limit=100
                )
                odoo_groups = [str(g.get("full_name", "")) for g in groups if g.get("full_name")]
            except Exception as e:
                print(f"⚠️ [PermissionService] Lỗi read res.groups: {e}")

        user_info = {
            "odoo_user_id": user.get("id"),
            "email": email,
            "full_name": full_name,
            "is_active_odoo": is_active,
            "odoo_groups": odoo_groups,
        }

        return {
            "allowed": True,
            "email": email,
            "user_info": user_info,
            "official_role": "authenticated",   # Tương thích backward, Claude không dùng
        }
