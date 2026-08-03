---
name: sales-skill
description: Kịch bản tạo báo giá sale.order và kiểm tra công nợ res.partner từ Odoo 19 SaaS Enterprise.
---

# Sales Skill

Skill này hướng dẫn Claude Code / Agent xử lý quy trình Bán hàng và Tạo Báo giá:

## Quy trình xử lý
1. **Kiểm tra thông tin Khách hàng (`res.partner`)**:
   - Tra cứu ID khách hàng qua tool `odoo:search_records`.

2. **Khởi tạo Báo giá bản thảo (`sale.order`)**:
   - Gọi tool `odoo:create_record` tạo bản thảo Báo giá cho khách hàng.
   - Thêm các dòng sản phẩm `sale.order.line`.

3. **Ghi vết Chatter (Audit Trail)**:
   - Gọi tool `odoo:call_method` trên model `mail.thread` phương thức `message_post` để ghi chú vết thao tác AI.
