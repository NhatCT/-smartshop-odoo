"""
Script kiểm tra kết nối Odoo MCP Server trước khi cắm vào Hermes Agent.
"""

import os
import sys
from dotenv import load_dotenv

# Reconfigure stdout for UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

def check_environment():
    print("[1/3] Kiểm tra các biến môi trường Odoo...")
    odoo_url = os.getenv("ODOO_URL")
    odoo_db = os.getenv("ODOO_DB")
    odoo_user = os.getenv("ODOO_USERNAME")
    odoo_pass = os.getenv("ODOO_PASSWORD")
    
    if not all([odoo_url, odoo_db, odoo_user, odoo_pass]):
        print("[!] CẢNH BÁO: Thiếu biến môi trường Odoo trong file .env!")
        return False
    
    print(f"  [OK] ODOO_URL: {odoo_url}")
    print(f"  [OK] ODOO_DB: {odoo_db}")
    print(f"  [OK] ODOO_USERNAME: {odoo_user}")
    print("  [OK] ODOO_PASSWORD: ********")
    return True

def check_odoo_mcp_import():
    print("\n[2/3] Kiểm tra module odoo_mcp...")
    try:
        import odoo_mcp
        print("  [OK] Module 'odoo_mcp' đã được cài đặt thành công.")
        return True
    except ImportError:
        print("[X] LỖI: Chưa cài đặt package 'odoo-mcp'. Vui lòng chạy: pip install odoo-mcp")
        return False

def main():
    print("=" * 60)
    print("SMART SHOP - HERMES AGENT & ODOO MCP AUDIT")
    print("=" * 60)
    
    env_ok = check_environment()
    mcp_ok = check_odoo_mcp_import()
    
    print("\n------------------------------------------------------------")
    if env_ok and mcp_ok:
        print("[SUCCESS] TẤT CẢ ĐÃ SẴN SÀNG! Bạn có thể cắm Odoo MCP vào Hermes Agent.")
        print("Huong dan chi tiet tai: docs/HERMES_AGENT_ODOO_TEST_GUIDE.md")
    else:
        print("[!] Vui lòng sửa các lỗi trên trước khi cấu hình Hermes Agent.")
    print("=" * 60)

if __name__ == "__main__":
    main()


