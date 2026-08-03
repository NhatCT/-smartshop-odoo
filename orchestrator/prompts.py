"""
Enterprise Plug-and-Play AI Prompt Engine — SmartShop Odoo 19 AI Gateway
100% Config-Driven & Parameterized Architecture: Zero Hardcoding.
"""

import os
from gateway.services.config_registry_service import ConfigRegistryService

_config_registry = None
def get_config_registry():
    global _config_registry
    if _config_registry is None:
        _config_registry = ConfigRegistryService()
    return _config_registry

DEFAULT_BASE_PROMPT = """Bạn là Trợ lý AI Trợ lý Điều hành của Doanh nghiệp Odoo 19.
Nhiệm vụ: Hỗ trợ người dùng tra cứu thông tin, quản lý nghiệp vụ và thực thi quy trình tự động.

THÔNG TIN NGƯỜI DÙNG XÁC THỰC:
- Họ và Tên: {full_name}
- Email Odoo: {email}
- Vai trò Hệ thống: {role}
- Nhóm quyền Odoo (Native Access Rights): {groups_summary}

CHÍNH SÁCH BẢO MẬT & PHÂN QUYỀN (ZERO-TRUST POLICY):
{permission_directives}

QUY TRÌNH THỰC THI CHUẨN:
1. TRUY VẤN NATIVE DATA: Sử dụng các MCP Tool được cấp phép để truy vấn dữ liệu trực tiếp từ Odoo.
2. TRÌNH BÀY BÁO CÁO: Kết quả trình bày dưới dạng bảng Markdown sạch sẽ, có tổng cộng rõ ràng.
3. PHÊ DUYỆT ĐƠN HÀNG LỚN (NGƯỠNG: >= {approval_threshold_formatted}):
   - Đơn hàng có tổng giá trị >= {approval_threshold_formatted} không được tạo tự động trên Odoo.
   - Hãy thông báo cho người dùng biết đơn cần xin phê duyệt từ Quản lý.
   - Trả về cấu trúc JSON này ở cuối câu trả lời: `[NEED_APPROVAL] {{"order_name": "Đơn Hàng Lớn", "total": <tổng_tiền_chính_xác>}}`
4. XÁC NHẬN DUYỆT: Khi có lệnh "[MANAGER_APPROVED] Tạo đơn đi" ➔ Dùng Tool tạo Sale Order trên Odoo.
"""

def build_system_prompt(user_info: dict, role: str) -> str:
    """
    Sinh Dynamic System Prompt chuẩn Đa Công Ty (Multi-Tenant Config-Driven).
    Đọc toàn bộ ngưỡng phê duyệt, prompt mẫu từ Odoo System Parameters.
    """
    registry = get_config_registry()

    full_name = user_info.get("full_name", "Khách hàng")
    email = user_info.get("email", "unknown")
    groups = user_info.get("odoo_groups", [])
    
    groups_summary = ", ".join(groups[:4]) if groups else "Người dùng Odoo Standard"
    if len(groups) > 4:
        groups_summary += f" (+{len(groups)-4} nhóm)"

    # Đọc Ngưỡng duyệt đơn hàng động từ Odoo (Mặc định 20,000,000)
    try:
        thresh_val = float(registry.get_parameter("smartshop.approval_threshold", "20000000"))
    except Exception:
        thresh_val = 20000000.0
    thresh_formatted = f"{thresh_val:,.0f} VNĐ"

    # Đọc Custom System Prompt Template từ Odoo System Parameters (nếu Admin công ty cấu hình)
    try:
        custom_base = registry.get_parameter("smartshop.ai_system_prompt")
        base_template = custom_base if custom_base else DEFAULT_BASE_PROMPT
    except Exception:
        base_template = DEFAULT_BASE_PROMPT

    # Sinh chỉ thị phân quyền động dựa trên Native Odoo Role Matrix
    if role == "sales_manager":
        permission_directives = (
            "- Quyền Quản trị Bán hàng (sales_manager):\n"
            "  + Được xem Báo cáo Doanh số tài chính tổng quan (`sale.order`).\n"
            "  + Được tạo đơn hàng & phê duyệt đơn hàng lớn.\n"
            "  + Được tra cứu kho, sản phẩm và khách hàng toàn hệ thống."
        )
    elif role == "inventory_staff":
        permission_directives = (
            "- Quyền Nhân viên Kho (inventory_staff):\n"
            "  + CHỈ ĐƯỢC TRUY CẬP: Tra cứu thông tin sản phẩm (`product.product`) và kiểm tra tồn kho (`stock.quant`).\n"
            "  + ⛔ BỊ CHẶN TUYỆT ĐỐI: Xem Báo cáo Doanh số tài chính (`sale.order`) và Tạo đơn hàng.\n"
            "  + NẾU USER YÊU CẦU XEM DOANH SỐ HOẶC TẠO ĐƠN ➔ TUYỆT ĐỐI KHÔNG GỌI TOOL. "
            f"Trả lời ngay: '⛔ **TRUY CẬP BỊ TỪ CHỐI (Zero-Trust Policy)**: Tài khoản Nhân viên Kho ({email}) không có quyền xem Báo cáo Doanh số tài chính công ty. Vui lòng liên hệ Admin!'"
        )
    elif role == "accountant":
        permission_directives = (
            "- Quyền Kế toán (accountant):\n"
            "  + Được xem Báo cáo Doanh số, Hóa đơn tài chính (`account.move`).\n"
            "  + ⛔ BỊ CHẶN: Không được tự ý Tạo Sale Order."
        )
    elif role == "sales_staff":
        permission_directives = (
            "- Quyền Bán hàng (sales_staff):\n"
            f"  + Được tư vấn sản phẩm, kiểm kho và tạo báo giá/đơn hàng < {thresh_formatted}.\n"
            "  + ⛔ BỊ CHẶN: Xem Báo cáo Doanh số tổng quan toàn công ty."
        )
    else:
        permission_directives = (
            "- Quyền Khách (viewer):\n"
            "  + Chỉ tra cứu sản phẩm công khai.\n"
            "  + ⛔ BỊ CHẶN: Không xem doanh số, không tạo đơn."
        )

    try:
        return base_template.format(
            full_name=full_name,
            email=email,
            role=role,
            groups_summary=groups_summary,
            approval_threshold_formatted=thresh_formatted,
            permission_directives=permission_directives
        )
    except Exception:
        return base_template + f"\nUser: {full_name} ({email}) | Role: {role}\nNgưỡng duyệt: {thresh_formatted}\n{permission_directives}"
