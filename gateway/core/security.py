import os
import hmac
import hashlib

SECRET_SALT = os.getenv("GATEWAY_SECRET_SALT", "SmartShopOdoo19AntiHijackSecretSalt2026")

def generate_approval_token(order_name, telegram_id):
    msg = f"{order_name}:{telegram_id}".encode('utf-8')
    return hmac.new(SECRET_SALT.encode('utf-8'), msg, hashlib.sha256).hexdigest()[:8]

def verify_approval_token(order_name, telegram_id, token):
    expected = generate_approval_token(order_name, telegram_id)
    return hmac.compare_digest(expected, token)
