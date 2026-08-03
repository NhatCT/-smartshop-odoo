---
name: accounting-skill
description: Kịch bản tra cứu công nợ, AR/AP và cash flow từ Odoo 19 SaaS Enterprise.
---

# Accounting Skill

Skill này hướng dẫn Agent xử lý các nghiệp vụ Kế toán và Tài chính trên Odoo 19.

## Phạm vi quyền hạn
- Chỉ Role **accountant** và **sales_manager** mới được truy cập thông tin tài chính.
- Role **sales_staff** và **inventory_staff** bị từ chối truy cập các model kế toán.

## Quy trình tra cứu Công nợ (AR — Accounts Receivable)

### 1. Tìm Khách hàng
Gọi `search_records(model='res.partner', query=<tên khách hàng>, fields=['id','name','credit','debit','credit_limit'])`

### 2. Xem Công nợ Phải thu
- **credit**: Tổng tiền khách hàng đã thanh toán
- **debit**: Tổng tiền khách hàng còn nợ (= AR balance)
- **credit_limit**: Hạn mức tín dụng

### 3. Danh sách Hóa đơn Chưa thanh toán
Gọi `search_records(model='account.move', query=<tên khách>, fields=['name','invoice_date_due','amount_residual','payment_state','state'])`
- Lọc `payment_state != 'paid'` và `state = 'posted'`

## Quy trình tra cứu Công nợ Phải trả (AP — Accounts Payable)

### 1. Tìm Nhà cung cấp
Gọi `search_records(model='res.partner', query=<tên NCC>, fields=['id','name','credit','debit'])`

### 2. Xem Hóa đơn NCC Chưa thanh toán
Gọi `search_records(model='account.move', query=<tên NCC>, fields=['name','invoice_date_due','amount_residual','move_type'])`
- Lọc `move_type = 'in_invoice'` và `payment_state != 'paid'`

## Quy trình Cash Flow nhanh (7 ngày tới)

1. Lấy các hóa đơn khách hàng đến hạn trong 7 ngày: `account.move` với `invoice_date_due <= <ngày+7>`
2. Tính tổng `amount_residual` → **Dự kiến thu**
3. Lấy hóa đơn NCC đến hạn 7 ngày: `account.move` với `move_type = 'in_invoice'`
4. Tính tổng → **Dự kiến chi**
5. **Net Cash Flow** = Dự kiến thu - Dự kiến chi

## Format Kết quả Chuẩn

```
📊 TỔNG HỢP CÔNG NỢ — [Tên Khách hàng]

• Công nợ phải thu (AR): X,XXX,XXX VNĐ
• Hạn mức tín dụng: X,XXX,XXX VNĐ
• Trạng thái: ⚠️ Vượt hạn mức / ✅ Trong hạn mức

📋 Hóa đơn chưa thanh toán:
| Số HĐ | Ngày đến hạn | Số tiền còn lại | Trạng thái |
|-------|-------------|-----------------|------------|
| INV/001 | 15/08/2026 | 5,000,000 VNĐ  | Quá hạn    |
```

## Cảnh báo quan trọng
- **KHÔNG** truy cập `account.move` với `move_type = 'entry'` (bút toán nội bộ — không liên quan)
- **KHÔNG** tiết lộ thông tin tài chính của partner khác với role thấp hơn
- Luôn làm tròn số tiền về đơn vị VNĐ (không hiển thị xu)
