import os
import json
import urllib.request

class NotificationService:
    def __init__(self):
        self.n8n_otp_url = os.getenv("N8N_OTP_WEBHOOK_URL")
        self.n8n_approval_url = os.getenv("N8N_APPROVAL_WEBHOOK_URL")

    def send_otp_via_n8n(self, to_email, otp_code, employee_name):
        if not self.n8n_otp_url:
            return False
        try:
            payload = json.dumps({
                "to_email": to_email,
                "otp_code": otp_code,
                "employee_name": employee_name
            }).encode('utf-8')
            req = urllib.request.Request(self.n8n_otp_url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"⚠️ [N8N OTP ERROR]: {e}")
            return False

    def send_approval_request(self, order_name, total_amount, employee_name, manager_chat_id):
        if not self.n8n_approval_url:
            print("⚠️ N8N_APPROVAL_WEBHOOK_URL not configured")
            return False
        try:
            payload = json.dumps({
                "order_name": order_name,
                "total_amount": total_amount,
                "employee_name": employee_name,
                "manager_chat_id": manager_chat_id
            }).encode('utf-8')
            req = urllib.request.Request(self.n8n_approval_url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"⚠️ [N8N APPROVAL ERROR]: {e}")
            return False
