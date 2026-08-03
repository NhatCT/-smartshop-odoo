from gateway.services.permission_service import PermissionService
from gateway.services.otp_service import OTPService
from gateway.config.constants import ROLE_TOOLS_MAP, PREDEFINED_EMAIL_ROLES
from gateway.repositories.binding_repository import get_bindings, save_bindings
from gateway.core.security import generate_approval_token, verify_approval_token

class SecurityGateway:
    def __init__(self):
        self.permission_service = PermissionService()
        self.otp_service = OTPService()
    
    def process_incoming_request(self, telegram_id: int):
        return self.permission_service.process_incoming_request(telegram_id)
        
    def request_otp(self, telegram_id, email):
        return self.otp_service.request_otp(telegram_id, email)
        
    def verify_otp_and_bind(self, telegram_id, user_otp):
        return self.otp_service.verify_otp_and_bind(telegram_id, user_otp)

__all__ = ["SecurityGateway", "ROLE_TOOLS_MAP", "PREDEFINED_EMAIL_ROLES", "generate_approval_token", "verify_approval_token", "get_bindings", "save_bindings"]
