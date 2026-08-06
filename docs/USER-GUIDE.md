# 📘 User Guide — SmartShop AI Gateway v3.0

> **SmartShop AI Gateway** is an AI-powered conversational assistant that integrates **Odoo 19 SaaS Enterprise** with **Telegram**. Powered by Claude AI and automated n8n workflows, it enables teams to check inventory, query prices, create sales orders, check customer balances, and trigger automated manager approvals using natural language.

---

## 📋 Table of Contents

1. [System Overview](#-system-overview)
2. [Quick Links](#-quick-links)
3. [Getting Started & Authentication](#-getting-started--authentication)
4. [Command Reference](#-command-reference)
5. [Core Features & Usage Examples](#-core-features--usage-examples)
   - [1. Product & Price Queries](#1-product--price-queries)
   - [2. Inventory & Stock Checking](#2-inventory--stock-checking)
   - [3. Sales Orders & Quotations](#3-sales-orders--quotations)
   - [4. High-Value Order Approval Flow (> 20M VND)](#4-high-value-order-approval-flow--20m-vnd)
   - [5. Financial & Customer Debt Enquiries](#5-financial--customer-debt-enquiries)
   - [6. Automated Daily Reports](#6-automated-daily-reports)
6. [Role-Based Access Control (RBAC) & Security](#-role-based-access-control-rbac--security)
7. [Troubleshooting & Frequently Asked Questions](#-troubleshooting--frequently-asked-questions)

---

## ⚙️ System Overview

SmartShop AI Gateway bridges field operations and management directly with your Odoo 19 ERP via a secure Telegram interface.

```
┌─────────────────────────────────────────────────────────┐
│                     TELEGRAM USER                       │
│  (Sales Reps, Inventory Staff, Accountant, Manager)     │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────┐
│              SMARTShop AI GATEWAY (Render)              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │   FastAPI    │  │  Claude AI   │  │ Approval Gate │  │
│  │ Webhook/Bot  │  │ (Tool Loop)  │  │  (>20M VND)   │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
└─────────┼─────────────────┼──────────────────┼──────────┘
          │                 │                  │
┌─────────▼─────┐   ┌───────▼──────┐   ┌───────▼──────────┐
│   Odoo 19     │   │  n8n Cloud   │   │   Telegram Bot   │
│ (ERP System)  │   │  (Workflows) │   │ (Notifications)  │
└───────────────┘   └──────────────┘   └──────────────────┘
```

---

## 🔗 Quick Links

| Service | Access Link / Detail | Description |
|---|---|---|
| **Telegram Bot** | [@SmartShopAIBot](https://t.me/SmartShopAIBot) | Main AI assistant bot for all user queries and approval actions |
| **Odoo 19 ERP** | [smartshop-odoo.odoo.com](https://smartshop-odoo.odoo.com) | Central ERP platform hosting database, products, and sales orders |
| **n8n Automation** | [odooworkflow.app.n8n.cloud](https://odooworkflow.app.n8n.cloud) | Workflow engine handling email OTP dispatch & approval webhooks |
| **Gateway Host** | [smartshop-ai-gateway.onrender.com](https://smartshop-ai-gateway.onrender.com) | Live FastAPI application running the AI Gateway |

---

## 🔐 Getting Started & Authentication

To interact with company data on Odoo, users must verify their identity by linking their Telegram account with their company email registered in Odoo.

### Step 1: Open Telegram Bot
Search for **@SmartShopAIBot** on Telegram or open [t.me/SmartShopAIBot](https://t.me/SmartShopAIBot) and click **Start**.

### Step 2: Request Verification OTP
Type the `/register` command along with your registered Odoo email:
```text
/register employee@yourcompany.com
```
*The system will validate your email address against Odoo and send a 6-digit OTP code to your inbox via n8n.*

### Step 3: Enter the OTP Code
Check your email inbox and respond with the `/verify` command:
```text
/verify 123456
```
*(Replace `123456` with the actual 6-digit OTP code received).*

Upon successful verification, the bot will display your mapped user profile and assigned Odoo access permissions.

---

## 💻 Command Reference

| Command | Syntax | Description |
|---|---|---|
| `/start` or `/help` | `/start` | Displays initial greetings, system status, and guidance menu |
| `/register` | `/register <email>` | Initiates Telegram account binding with your company email |
| `/verify` | `/verify <otp_code>` | Validates the 6-digit OTP sent to your email |
| `/my_role` | `/my_role` | Checks your current Odoo permissions and role classification |
| `/clear` | `/clear` | Resets the current AI conversation context/memory buffer |

---

## 💡 Core Features & Usage Examples

SmartShop AI Gateway understands natural language in both **English** and **Vietnamese**.

### 1. Product & Price Queries

Users can ask for product pricing, available variants, or product descriptions.

* **Example Prompt (English):**
  > "What is the price of iPhone 15 Pro Max?"
* **Example Prompt (Vietnamese):**
  > "Giá iPhone 15 Pro Max bao nhiêu?"
* **Bot Response:**
  Retrieves unit price, tax details, and product variants directly from Odoo product catalogue.

---

### 2. Inventory & Stock Checking

Query warehouse stock levels and stock availability across locations.

* **Example Prompt (English):**
  > "Check stock availability for Dell XPS laptops."
* **Example Prompt (Vietnamese):**
  > "Kiểm tra tồn kho laptop Dell XPS."
* **Bot Response:**
  Displays quantity on hand, predicted availability, and location breakdown (subject to user's Inventory permissions).

---

### 3. Sales Orders & Quotations

Create draft quotations or sales orders directly in Odoo without navigating the web UI.

* **Example Prompt (English):**
  > "Create a quote for customer Alice for 2 units of iPhone 15 with a 5% discount."
* **Example Prompt (Vietnamese):**
  > "Tạo báo giá cho khách hàng Alice 2 cái iPhone 15 chiết khấu 5%."
* **Bot Response:**
  Creates a quotation draft on Odoo and returns the Quotation Reference Number (e.g., `SO0042`) along with total order value.

---

### 4. High-Value Order Approval Flow (> 20M VND)

For risk control, any order exceeding **20,000,000 VND** (~$800 USD) triggers an automatic **Approval Gate**.

#### How the EZ Direct Approval Gate Works:

```text
User requests order > 20M VND via Telegram Bot
         │
         ▼
AI detects total > 20M VND → Holds order & generates secure HMAC token
         │
         ▼
Bot sends direct Telegram inline buttons to Manager ([ ✅ Approve ] / [ ❌ Reject ])
         │
         ▼
Manager clicks [ ✅ Approve ] directly inside Telegram
         │
         ▼
SmartShop Gateway verifies HMAC token & creates Sale Order on Odoo (Approve) or cancels (Reject)
```

* **Example Request:**
  > "Create order worth 30M VND for customer Alice: 5 Laptops."
* **System Action:**
  1. The bot pauses immediate order creation and responds:
     > *"⚠️ Order exceeds threshold of 20,000,000 VND. An approval request has been forwarded to the Manager."*
  2. The **Manager** receives a direct Telegram message with interactive buttons:
     * Customer: Alice
     * Total Amount: 30,000,000 VND
     * Requested items: 5 Laptops
     * Buttons: `[ ✅ Phê duyệt ]` | `[ ❌ Từ chối ]`
  3. Clicking `[ ✅ Phê duyệt ]` verifies the cryptographic signature natively and generates the Sale Order on Odoo, notifying the employee instantly.

---

### 5. Financial & Customer Debt Enquiries

Authorized accounting and management users can inquire about customer balances and outstanding accounts receivable (AR).

* **Example Prompt (English):**
  > "What is the outstanding debt for customer ACME Corp?"
* **Example Prompt (Vietnamese):**
  > "Xem công nợ hiện tại của khách hàng ACME Corp."
* **Bot Response:**
  Queries Odoo accounting records and returns total uninvoiced/unpaid balance details.

---

### 6. Automated Daily Reports

The platform automatically broadcasts operational reports via n8n cron schedules:

* **08:00 AM (Daily):** Low Stock Warning Report — lists products reaching or falling below reorder points.
* **06:00 PM (Daily):** Sales Summary Report — daily revenue breakdown, new quotations, and completed sales orders.

---

## 🛡️ Role-Based Access Control (RBAC) & Security

SmartShop AI Gateway implements a **Zero-Trust Security Architecture**. Permissions are evaluated **live** against Odoo access groups on every request without local caching.

### Access Levels Matrix

| Odoo Group / Role | Product / Price Lookup | Create Quotation / Order | View Inventory Stock | View Financial / AR Reports | Approve Orders > 20M VND |
|---|:---:|:---:|:---:|:---:|:---:|
| **Sales Administrator / Manager** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Sales User** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Inventory User** | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Accounting User** | ✅ | ❌ | ❌ | ✅ | ❌ |
| **Unauthenticated / Guest** | 🌐 Public items | ❌ | ❌ | ❌ | ❌ |

### Additional Security Controls:
* **Rate Limiting:** Maximum 30 requests per minute per user to prevent abuse.
* **Idempotency Protection:** Prevents duplicate order creation caused by duplicate button clicks or network retries.
* **HMAC Signature Verification:** Webhooks between n8n and SmartShop Gateway are verified using SHA-256 HMAC signatures (`X-Webhook-Signature`).

---

## ❓ Troubleshooting & Frequently Asked Questions

### Q1: I ran `/register` but didn't receive an OTP email. What should I do?
* **Solution:** 
  1. Check your email Spam/Junk folder.
  2. Verify that the email entered matches your exact user login email registered in Odoo.
  3. Ask your system admin to confirm n8n SMTP credentials.

### Q2: Why does the bot say "Permission Denied" when I request stock level or customer debt?
* **Solution:**
  Your Odoo account user does not belong to the required group (`Inventory User` or `Accounting User`). Request your Odoo administrator to update your user security roles in Odoo Settings.

### Q3: How do I clear conversation context if the AI seems confused?
* **Solution:**
  Type `/clear`. This resets the prompt context window and lets you start a fresh interaction.

### Q4: What happens if an approval request is rejected by the Manager?
* **Solution:**
  The draft order is discarded, and a notification is sent back to the employee explaining that the order was not approved.

---

*SmartShop AI Gateway v3.0 — Powered by Claude AI & Odoo 19 SaaS Enterprise.*
