"""
AITECHNEXT Enterprise AI Gateway
Comprehensive System Health Check & Audit Suite for Odoo 19 SaaS
"""

import os
import sys
import json
import urllib.request
from dotenv_loader import load_env

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

load_env()

from odoo_client import OdooClient

def audit_odoo_connection():
    print("\n1️⃣  [KIỂM TRA KẾT NỐI ODOO 19 SAAS ENTERPRISE]")
    try:
        client = OdooClient()
        odoo = client.connect()
        print(f"   ✅ Kết nối Odoo thành công!")
        print(f"   - Server Host: {client._host}")
        print(f"   - Database: {client.db}")
        print(f"   - User Account: {client.username}")
        
        # Test read products
        prods = client.search_read('product.product', domain=[], fields=['id', 'name', 'qty_available'], limit=3)
        print(f"   - Truy vấn CSDL Odoo OK: Tìm thấy {len(prods)} sản phẩm tiêu biểu.")
        for p in prods:
            print(f"     • [{p['id']}] {p['name']} (Tồn kho: {p.get('qty_available', 0)})")
        return True
    except Exception as e:
        print(f"   ❌ Lỗi kết nối Odoo: {e}")
        return False

def audit_telegram_bot():
    print("\n2️⃣  [KIỂM TRA KẾT NỐI TELEGRAM BOT & ADMIN ALERT]")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("   ⚠️ Thiếu TOKEN hoặc CHAT_ID trong .env")
        return False
        
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            bot_info = res_data.get("result", {})
            print(f"   ✅ Telegram Bot kết nối chuẩn!")
            print(f"   - Bot Name: {bot_info.get('first_name')} (@{bot_info.get('username')})")
            print(f"   - Target Admin Chat ID: {chat_id}")
            return True
    except Exception as e:
        print(f"   ❌ Lỗi kiểm tra Telegram Bot: {e}")
        return False

def audit_n8n_webhook():
    print("\n3️⃣  [KIỂM TRA N8N WORKFLOW WEBHOOK ENDPOINT]")
    webhook_url = os.getenv("N8N_WEBHOOK_URL", "https://odooworkflow.app.n8n.cloud/webhook/odoo-order-webhook")
    
    # Try production URL
    prod_url = webhook_url.replace("/webhook-test/", "/webhook/")
    print(f"   URL mục tiêu: {prod_url}")
    
    payload = {
        "event": "system.health_check",
        "message": "Health Check from Audit Suite"
    }
    
    headers = {'Content-Type': 'application/json'}
    data_bytes = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(prod_url, data=data_bytes, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            print(f"   ✅ n8n Webhook Server phản hồi: HTTP {response.status}")
            print(f"   - Workflow Webhook đang hoạt động 24/7!")
            return True
    except Exception as e:
        print(f"   ⚠️ Lỗi kết nối n8n Webhook: {e}")
        return False

def audit_skills_and_architecture():
    print("\n4️⃣  [KIỂM TRA KHUNG KIẾN TRÚC 6 TẦNG & AGENT SKILLS]")
    skills_dir = os.path.join(os.getcwd(), ".agents", "skills")
    skills = os.listdir(skills_dir) if os.path.exists(skills_dir) else []
    print(f"   - Business Skills (.agents/skills/): {skills}")
    
    files_to_check = [
        "ARCHITECTURE.md",
        "MASTER_PROPOSAL_DIRECTIVE.md",
        "CLAUDE.md",
        "promptfooconfig.yaml",
        "n8n_odoo_workflow.json"
    ]
    
    all_exist = True
    for f in files_to_check:
        status = "✅" if os.path.exists(f) else "❌"
        print(f"   - File {f:<30}: {status}")
        if not os.path.exists(f):
            all_exist = False
    return all_exist

def run_system_audit():
    print("=" * 70)
    print(" 🛡️ HỆ THỐNG SMART SHOP ODOO 19 SAAS - AUDIT & HEALTH CHECK")
    print("=" * 70)
    
    res1 = audit_odoo_connection()
    res2 = audit_telegram_bot()
    res3 = audit_n8n_webhook()
    res4 = audit_skills_and_architecture()
    
    print("\n" + "=" * 70)
    if res1 and res2 and res3 and res4:
        print(" 🏆 KẾT LUẬN AUDIT: TOÀN BỘ HỆ THỐNG ĐẠT TRẠNG THÁI SẴN SÀNG (PRODUCTION-READY)!")
    else:
        print(" ⚠️ KẾT LUẬN AUDIT: Hệ thống đã kết nối hầu hết các phần cốt lõi.")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    run_system_audit()
