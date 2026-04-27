import importlib.util
import sys
import uuid
from pathlib import Path


MODULE_PATH = Path("/home/ubuntu/melissa/melissa.py")


def load_melissa_module():
    module_name = f"melissa_telegram_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_telegram_webhook_mode_prefers_direct_for_mixed_whatsapp_instance() -> None:
    module = load_melissa_module()
    module.Config.BASE_URL = "https://example.com"
    module.Config.TELEGRAM_TOKEN = "token"
    module.Config.PLATFORM = "whatsapp"
    module.Config.TELEGRAM_SHARED = True
    module.Config.TELEGRAM_SHARED_ROUTER = False

    assert module._telegram_webhook_mode() == "direct"


def test_telegram_webhook_mode_uses_shared_when_router_enabled() -> None:
    module = load_melissa_module()
    module.Config.BASE_URL = "https://example.com"
    module.Config.TELEGRAM_TOKEN = "token"
    module.Config.PLATFORM = "whatsapp"
    module.Config.TELEGRAM_SHARED = True
    module.Config.TELEGRAM_SHARED_ROUTER = True

    assert module._telegram_webhook_mode() == "shared"


def test_telegram_webhook_mode_disables_without_token_or_base_url() -> None:
    module = load_melissa_module()
    module.Config.BASE_URL = ""
    module.Config.TELEGRAM_TOKEN = ""
    module.Config.PLATFORM = "telegram"
    module.Config.TELEGRAM_SHARED = False
    module.Config.TELEGRAM_SHARED_ROUTER = False

    assert module._telegram_webhook_mode() == "disabled"


def test_telegram_status_route_exists() -> None:
    module = load_melissa_module()
    paths = {route.path for route in module.app.routes}
    assert "/telegram/status" in paths
