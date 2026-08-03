---
name: product-skill
description: Kịch bản tra cứu sản phẩm, kiểm kho và tư vấn biến thể từ Odoo 19 SaaS Enterprise.
---

# Product Skill

Skill này hướng dẫn Claude Code / Agent tra cứu sản phẩm và kiểm tra tồn kho trực tiếp từ Odoo ERP:

## Quy trình xử lý
1. **Tra cứu sản phẩm (Product Search)**:
   - Sử dụng tool `odoo:search_records` trên model `product.product` hoặc `product.template`.
   - Lọc theo mã `default_code` hoặc tên `name`.

2. **Kiểm tra tồn kho khả dụng (Inventory Check)**:
   - Đọc trường `qty_available` và `virtual_available`.
   - Chỉ tư vấn các sản phẩm có tồn kho `qty_available > 0`.

3. **Trả kết quả cho người dùng**:
   - Định dạng bảng Markdown hiển thị Tên sản phẩm, Mã SKU, Giá bán VNĐ và Tồn kho.
