"""
Odoo Role & Context Service — SmartShop Odoo 19
Lớp chuyên trách pull thông tin Người dùng, Nhóm quyền (res.groups) từ Odoo SaaS theo thời gian thực (Live Runtime).
Cung cấp Permission Context Card chuẩn hóa để gửi vào System Prompt và Python Security Gateway.
"""

import time
from dataclasses import dataclass, field
from data_layer.connectors.odoo_rpc import OdooClient


@dataclass
class OdooUserContext:
    user_id: int
    email: str
    full_name: str
    is_active: bool
    odoo_groups: list[str] = field(default_factory=list)
    role_category: str = "viewer"
    allowed_tools: list[str] = field(default_factory=list)
    allowed_models: list[str] = field(default_factory=list)
    company_id: int | None = None

    def format_prompt_block(self) -> str:
        """Tạo thẻ Context phân quyền sạch sẽ để bơm trực tiếp vào System Prompt cho Claude."""
        if self.odoo_groups:
            groups_str = "\n".join(f"    • {g}" for g in self.odoo_groups)
        else:
            groups_str = "    • (Không có nhóm nghiệp vụ — chỉ cho phép tra cứu thông tin công khai)"

        return (
            f"  Họ và Tên    : {self.full_name}\n"
            f"  Email Odoo   : {self.email}\n"
            f"  Vai trò chính: {self.role_category.upper()}\n"
            f"  Nhóm Odoo (res.groups):\n{groups_str}"
        )

    def to_dict(self) -> dict:
        return {
            "odoo_user_id": self.user_id,
            "email": self.email,
            "full_name": self.full_name,
            "is_active_odoo": self.is_active,
            "odoo_groups": self.odoo_groups,
            "role_category": self.role_category,
            "role": self.role_category,
            "allowed_tools": self.allowed_tools,
            "allowed_models": self.allowed_models,
            "company_id": self.company_id,
            "prompt_block": self.format_prompt_block(),
        }


class OdooRoleContextService:
    """
    Service kéo Role và Quyền hạn live từ Odoo với In-Memory TTL Cache (5 phút).
    Tiết kiệm ~150ms RPC call cho các tin nhắn liên tiếp của cùng 1 user.
    """
    _cache: dict[str, tuple[float, OdooUserContext]] = {}

    def __init__(self, odoo_client: OdooClient | None = None, cache_ttl_seconds: int = 60):
        self.odoo_client = odoo_client or OdooClient()
        self.cache_ttl_seconds = cache_ttl_seconds

    @classmethod
    def clear_cache(cls, email: str | None = None):
        if email:
            cls._cache.pop(email.lower().strip(), None)
        else:
            cls._cache.clear()

    def fetch_user_context(self, email: str, force_refresh: bool = False) -> OdooUserContext | None:
        key = email.lower().strip()
        now = time.time()

        if not force_refresh and key in self._cache:
            cached_time, cached_ctx = self._cache[key]
            if now - cached_time < self.cache_ttl_seconds:
                return cached_ctx

        ctx = self._do_fetch_user_context(email)
        if ctx:
            self._cache[key] = (now, ctx)
        elif key in self._cache:
            del self._cache[key]
        return ctx

    def _do_fetch_user_context(self, email: str) -> OdooUserContext | None:
        """Kéo thông tin người dùng và danh sách nhóm res.groups trực tiếp từ Odoo RPC."""
        clean_email = email.lower().strip()
        try:
            records = self.odoo_client.search_read(
                model="res.users",
                domain=["|", ["login", "=ilike", clean_email], ["email", "=ilike", clean_email]],
                fields=["id", "name", "login", "active", "company_id", "all_group_ids"],
                limit=1
            )
        except Exception as e:
            print(f"[OdooRoleContextService] Error querying res.users: {e}")
            return None

        if not records:
            return None

        user = records[0]
        full_name = user.get("name") or email.split("@", 1)[0].replace(".", " ").title()
        is_active = user.get("active", True)

        comp = user.get("company_id")
        company_id = comp[0] if (isinstance(comp, (list, tuple)) and comp) else comp

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
                skip = ["Technical", "Bỏ qua", "Địa chỉ", "Trình chỉnh", "Trang web"]
                odoo_groups = [
                    str(g.get("full_name", "")) for g in groups 
                    if g.get("full_name") and not any(k in str(g.get("full_name", "")) for k in skip)
                ]
            except Exception as e:
                print(f"⚠️ [OdooRoleContextService] Lỗi read res.groups: {e}")

        # Phán xét vai trò & Tool Whitelist tự động từ nhóm Odoo
        is_sys_admin = any(
            "Quản trị / Thiết lập" in g or "Administration / Settings" in g or 
            "Quản trị viên hệ thống" in g or "Access Rights" in g
            for g in odoo_groups
        )
        is_sales_mgr = any("Bán hàng / Quản trị viên" in g or "Sales / Administrator" in g for g in odoo_groups)
        is_sales_staff = is_sales_mgr or any("Bán hàng" in g or "Sales" in g for g in odoo_groups)
        is_inventory_mgr = any("Tồn kho / Quản trị viên" in g or "Inventory / Administrator" in g for g in odoo_groups)
        is_inventory_staff = is_inventory_mgr or any("Tồn kho" in g or "Inventory" in g for g in odoo_groups)
        is_accountant_mgr = any("Kế toán / Quản trị viên" in g or "Accounting / Administrator" in g for g in odoo_groups)
        is_accountant = is_accountant_mgr or any("Kế toán" in g or "Accounting" in g or "Invoicing" in g for g in odoo_groups)

        allowed_tools = set(["search_records", "list_products"])
        allowed_models = set(["product.template", "product.product"])

        if is_sales_staff or is_sales_mgr or is_sys_admin:
            allowed_tools.update(["create_sale_order", "create_record", "update_record", "get_sale_order"])
            allowed_models.update(["sale.order", "sale.order.line", "res.partner"])

        if is_inventory_staff or is_inventory_mgr or is_sys_admin:
            allowed_tools.update(["get_stock_quant", "search_records"])
            allowed_models.update(["stock.quant", "stock.picking", "stock.location"])

        if is_accountant or is_accountant_mgr or is_sales_mgr or is_sys_admin:
            allowed_tools.update(["aggregate_records"])
            allowed_models.update(["account.move", "account.move.line", "res.partner"])

        if is_sys_admin or is_sales_mgr:
            role_cat = "sales_manager"
        elif is_sales_staff:
            role_cat = "sales_staff"
        elif is_inventory_mgr or is_inventory_staff:
            role_cat = "inventory_staff"
        elif is_accountant:
            role_cat = "accountant"
        else:
            role_cat = "viewer"

        return OdooUserContext(
            user_id=user.get("id"),
            email=email,
            full_name=full_name,
            is_active=is_active,
            odoo_groups=odoo_groups,
            role_category=role_cat,
            allowed_tools=list(allowed_tools),
            allowed_models=list(allowed_models),
            company_id=company_id
        )
