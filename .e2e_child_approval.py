import sys
from shared.utils import load_env

load_env()

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from gateway.services.otp_service import OTPService, PENDING_OTP_STORE, PENDING_APPROVAL_STORE
from gateway.services.binding_service import get_bindings

telegram_id = 6553206564
child_email = "2251052082nhat@ou.edu.vn"

service = OTPService()

ok, register_msg = service.request_otp(telegram_id, child_email)
print("register_ok", ok)
print("register_msg", register_msg.encode("ascii", "ignore").decode("ascii").replace("\n", " | "))

pending = PENDING_OTP_STORE.get(str(telegram_id))
print("otp_pending", pending is not None)

if not pending:
    raise SystemExit(1)

otp = pending["otp"]
ok, verify_msg = service.verify_otp_and_bind(telegram_id, otp)
print("verify_ok", ok)
print("verify_msg", verify_msg.encode("ascii", "ignore").decode("ascii").replace("\n", " | "))
print("binding_after_verify", get_bindings().get(str(telegram_id)))
print("approval_pending", PENDING_APPROVAL_STORE.get(str(telegram_id)))

ok, approve_msg = service.approve_pending_registration(telegram_id, approver_name="admin")
print("approve_ok", ok)
print("approve_msg", approve_msg.encode("ascii", "ignore").decode("ascii").replace("\n", " | "))
print("binding_after_approve", get_bindings().get(str(telegram_id)))
