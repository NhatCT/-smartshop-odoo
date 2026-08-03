import os
import json
import urllib.request

class NotificationService:
    def __init__(self):
        self.n8n_otp_url = os.getenv(
            "N8N_OTP_WEBHOOK_URL",
            "https://odooworkflow.app.n8n.cloud/webhook/send-otp-email"
        )

    def send_otp_via_n8n(self, to_email, otp_code, employee_name):
        try:
            payload = json.dumps({
                "to_email": to_email,
                "otp_code": otp_code,
                "employee_name": employee_name
            }).encode('utf-8')
            req = urllib.request.Request(
                self.n8n_otp_url,
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return result.get("ok", False) or resp.status == 200
        except Exception as e:
            print(f"   ⚠️ [N8N OTP EMAIL ERROR]: {e}")
            return False
