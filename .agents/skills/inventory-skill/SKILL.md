---
name: inventory-skill
description: Kịch bản đối soát tồn kho, dự báo nhập hàng và kiểm kê kho hàng từ Odoo 19 SaaS Enterprise.
---

# Inventory Skill

Skill này hướng dẫn Claude Code / Agent thực hiện đối soát kho hàng và phát hiện sản phẩm sắp hết hàng:

## Quy trình xử lý
1. **Kiểm tra tồn kho kho HCM / Hà Nội**:
   - Sử dụng tool `odoo:search_records` trên model `stock.quant` hoặc `product.product`.
   - Tìm các sản phẩm có `qty_available <= 5` (Mức báo động kho).

2. **Dự báo nhập hàng**:
   - Đưa ra đề xuất số lượng cần nhập thêm dựa trên tốc độ bán 30 ngày gần nhất.
