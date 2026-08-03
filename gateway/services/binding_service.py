from gateway.services.config_registry_service import ConfigRegistryService

_registry = ConfigRegistryService()

def get_bindings() -> dict:
    return _registry.get_telegram_bindings()

def save_bindings(bindings: dict) -> bool:
    return _registry.save_telegram_bindings(bindings)
