"""
Enterprise Dynamic Prompt Generator — SmartShop Odoo 19 AI Gateway
Single Source of Truth: Quản lý Prompt từ Odoo System Parameter (ir.config_parameter) & User Context.
"""

import os
from gateway.services.config_registry_service import ConfigRegistryService

_config_registry = None
def get_config_registry():
    global _config_registry
    if _config_registry is None:
        _config_registry = ConfigRegistryService()
    return _config_registry

DEFAULT_BASE_PROMPT = """Bạn là Trợ lý AI Điều hành Doanh nghiệp Odoo 19.
Nhiệm vụ: Hỗ trợ người dùng tra cứu thông tin, quản lý nghiệp vụ và thực thi quy trình tự động.

THÔNG TIN NGƯỜI DÙNG XÁC THỰC:
- Họ và Tên: {full_name}
- Email Odoo: {email}
- Vai trò: {role}
- Nhóm quyền Odoo: {groups_summary}

CHÍNH SÁCH BẢO MẬT & PHÂN QUYỀN (ZERO-TRUST POLICY):
{permission_directives}

QUY TRÌNH THỰC THI CHUẨN:
1. GỌI DỮ LIỆU THỰC TẾ: Sử dụng các MCP Tool được cấp phép để truy vấn dữ liệu trực tiếp từ Odoo.
2. ĐỊNH DẠNG BÁO CÁO: Luôn trả về kết quả dạng bảng Markdown sạch sẽ, rõ ràng, có tổng số và nhận xét ngắn gọn.
3. PHÊ DUYỆT ĐƠN HÀNG LỚN (>= 20 TRIỆU):
   - Đơn hàng >= 20 triệu không được tạo trực tiếp. Báo cho người dùng biết cần xin duyệt Manager.
   - Trả về chuỗi JSON ở cuối câu trả lời: `[NEED_APPROVAL] {{"order_name": "Đơn Hàng Lớn", "total": <tổng_tiền>}}`
4. XÁC NHẬN DUYỆT: Nhận tin nhắn "[MANAGER_APPROVED] Tạo đơn đi" ➔ Dùng Tool tạo Sale Order trên Odoo.
"""

def build_system_prompt(user_info: dict, role: str) -> str:
    """
    Sinh System Prompt ĐỘNG theo từng lượt chat dựa trên thông tin Odoo.
    Nếu Admin chỉnh sửa Prompt trên Odoo UI (ir.config_parameter), tự động nạp Prompt mới!
    """
    full_name = user_info.get("full_name", "Khách hàng")
    email = user_info.get("email", "unknown")
    groups = user_info.get("odoo_groups", [])
    
    groups_summary = ", ".join(groups[:4]) if groups else "Người dùng tiêu chuẩn"
    if len(groups) > 4:
        groups_summary += f" (+{len(groups)-4} nhóm)"

    # Đọc Custom System Prompt từ Odoo ir.config_parameter (nếu Admin cấu hình trên Odoo UI)
    try:
        registry = get_config_registry()
        custom_base = registry.get_parameter("smartshop.ai_system_prompt")
        base_template = custom_base if custom_base else DEFAULT_BASE_PROMPT
    except Exception as e:
        print(f"⚠️ [prompts] Fallback to default prompt: {e}")
        base_template = DEFAULT_BASE_PROMPT

    # Sinh chỉ thị phân quyền động theo Role
    if role == "sales_manager":
        permission_directives = (
            "- TOÀN QUYỀN QUẢN TRỊ (sales_manager):\n"
            "  + Được xem Báo cáo Doanh số tài chính tổng quan (`sale.order`).\n"
            "  + Được tạo đơn hàng & duyệt các đơn hàng lớn (> 20 triệu).\n"
            "  + Được tra cứu kho, sản phẩm và khách hàng toàn hệ thống."
        )
    elif role == "inventory_staff":
        permission_directives = (
            "- HẠN CHẾ QUYỀN KHO (inventory_staff):\n"
            "  + CHỈ ĐƯỢC TRUY CẬP: Tra cứu thông tin sản phẩm (`product.product`) và kiểm tra tồn kho (`stock.quant`).\n"
            "  + ⛔ BỊ CHẶN TUYỆT ĐỐI: Xem Báo cáo Doanh số tài chính (`sale.order`) và Tạo đơn hàng.\n"
            "  + NẾU USER YÊU CẦU XEM DOANH SỐ HOẶC TẠO ĐƠN ➔ TUYỆT ĐỐI KHÔNG GỌI TOOL. "
            "Trả lời ngay: '⛔ **TRUY CẬP BỊ TỪ CHỐI (Zero-Trust Policy)**: Tài khoản Nhân viên Kho ({email}) không có quyền xem Báo cáo Doanh số tài chính công ty. Vui lòng liên hệ Admin!'"
        )
    elif role == "accountant":
        permission_directives = (
            "- QUYỀN KẾ TOÁN (accountant):\n"
            "  + Được xem Báo cáo Doanh số, Hóa đơn tài chính (`account.move`).\n"
            "  + ⛔ BỊ CHẶN: Không được tự ý Tạo Sale Order."
        )
    elif role == "sales_staff":
        permission_directives = (
            "- QUYỀN BÁN HÀNG (sales_staff):\n"
            "  + Được tư vấn sản phẩm, kiểm kho và tạo báo giá/đơn hàng < 20 triệu.\n"
            "  + ⛔ BỊ CHẶN: Xem Báo cáo Doanh số tổng quan toàn công ty."
        )
    else:
        permission_directives = (
            "- HẠN CHẾ KHÁCH (viewer):\n"
            "  + Chỉ tra cứu sản phẩm công khai.\n"
            "  + ⛔ BỊ CHẶN: Không xem doanh số, không tạo đơn."
        )

    try:
        return base_template.format(
            full_name=full_name,
            email=email,
            role=role,
            groups_summary=groups_summary,
            permission_directives=permission_directives
        )
    except Exception:
        # Trong trường hợp custom prompt từ Odoo thiếu placeholder
        return base_template + f"\nUser: {full_name} ({email}) | Role: {role}\n{permission_directives}"
