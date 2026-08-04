# 🛍️ SmartShop Odoo 19 Enterprise AI Gateway

[![CI Status](https://github.com/NhatCT/-smartshop-odoo/actions/workflows/ci.yml/badge.svg)](https://github.com/NhatCT/-smartshop-odoo/actions)
[![Python Version](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Anthropic Claude](https://img.shields.io/badge/AI-Claude%203.5%20%2F%20Haiku-purple.svg)](https://www.anthropic.com/)
[![Odoo Version](https://img.shields.io/badge/ERP-Odoo%2019%20SaaS-purple.svg)](https://www.odoo.com/)

**SmartShop Odoo 19 AI Gateway** là Hệ thống Trợ lý AI Điều hành Doanh nghiệp Cấp Doanh nghiệp (Enterprise-Grade AI Gateway), tích hợp trực tiếp **Anthropic Claude (Haiku & Sonnet)** với **Odoo 19 SaaS Enterprise** qua mô hình **Bảo mật Zero-Trust** và **Kiến trúc 6 Lớp Chuẩn Anthropic**.

---

## 🏛️ Sơ đồ Kiến trúc 6 Lớp (Anthropic 6-Layer Architecture)

```
                       [USER CHAT TELEGRAM / LIVECHAT / WEBHOOK]
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ LỚP 1: INTENT ROUTER (< 1ms, 0 tốn Token)                               │
│ • Phân loại: INVENTORY | PRODUCT_SEARCH | SALE_ORDER_CREATE | REPORT    │
└─────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ LỚP 2: ZERO-TRUST SECURITY & PERMISSION GATEWAY                         │
│ • Đọc live res.groups từ Odoo SaaS                                      │
│ • Cách ly Multi-Company (company_id) & Khóa cứng Model ACLs ở Python    │
└─────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ LỚP 3: DYNAMIC SKILL LOADER                                             │
│ • Nạp đúng 2-3 Tool tương ứng với Intent & Odoo Role                    │
└─────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ LỚP 4: ANTHROPIC PROMPT BUILDER & OUTPUT CONTROL                        │
│ • Chỉ dẫn tích cực: "Search Odoo trước khi hỏi"                         │
│ • Định dạng 3 mục: ### 📋 KẾT LUẬN | ### 📊 DỮ LIỆU | ### 🚀 BƯỚC SAU  │
└─────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ LỚP 5: DYNAMIC MODEL ROUTER                                             │
│ • Tra cứu đơn giản ──► Claude Haiku (< 1.5s, Tối ưu chi phí)            │
│ • Tạo đơn đa bước   ──► Claude 3.5 Sonnet                             │
└─────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ LỚP 6: EXECUTION, INTERACTIVE UI & AUDIT HARNESS                        │
│ • Per-stage turn quota = 2 (Chống ngốn Token API)                       │
│ • Telegram Inline Keyboards: [🛒 Tạo đơn] [📦 Kiểm kho] [📋 Xem đơn]     │
│ • Full ERP Decision Audit Trail & Promptfoo Eval Matrix                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Quick Start (Khởi chạy 3 bước)

### Bước 1: Clone Repository & Tạo biến môi trường `.env`
```bash
git clone https://github.com/NhatCT/-smartshop-odoo.git
cd -smartshop-odoo
cp .env.example .env
```

Cấu hình các biến môi trường trong tệp `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-api03-...
ODOO_URL=https://your-company.odoo.com
ODOO_DB=your-db
ODOO_USERNAME=admin@company.com
ODOO_PASSWORD=your-password
TELEGRAM_BOT_TOKEN=123456789:ABC...
```

### Bước 2: Cài đặt Dependencies & Biên dịch
```bash
python -m pip install -r requirements.txt
python -m py_compile orchestrator/*.py gateway/*.py channels/*.py
```

### Bước 3: Khởi chạy Gateway Service
```bash
python app_entrypoint.py
```

Hoặc chạy qua Docker Compose:
```bash
docker-compose up -d --build
```

---

## 🚀 Các Tính Năng Nổi Bật

- **🛍️ Telegram Inline Keyboards**: Bot tự động trả kết quả kèm nút bấm thao tác nhanh (`[🛒 Tạo đơn nháp]`, `[📦 Kiểm kho]`).
- **🛡️ Model-Level ACL Enforcement**: Chặn đứng truy vấn sai quyền Odoo Model ở tầng Python Security Gateway.
- **⚡ In-Memory TTL Cache (5 min)**: Tiết kiệm ~150ms RPC call cho các tin nhắn liên tiếp từ cùng một user.
- **📊 Langfuse Observability & ERP Audit Trail**: Ghi vết Latency (p50/p95), Token Usage, và Nhật ký quyết định tuân thủ ERP.

---

## 🧪 Chạy Bộ Đánh Giá Chất Lượng (Promptfoo Benchmark)

```bash
npx promptfoo eval
```

Bộ test tự động đo 4 chỉ số:
1. **Tool Called Accuracy**: Gọi đúng tool cần thiết.
2. **Tool Count Efficiency**: Tối ưu số lượt gọi tool.
3. **Zero Redundant Asks**: Không hỏi thừa thông tin Odoo tự tra ra được.
4. **Output Format Adherence**: Đúng cấu trúc Markdown 3 mục.

---

## 📄 License & Maintainer
Dự án được bảo trì bởi **SmartShop Odoo Engineering Team**.  
Mã nguồn mở cấp phép theo giấy phép **MIT License**.
