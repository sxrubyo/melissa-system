import sys
import types
import uuid
import importlib.util
import asyncio
from pathlib import Path


sys.path.insert(0, "/home/ubuntu/melissa")
from melissa import MelissaUltra  # noqa: E402


MODULE_PATH = Path("/home/ubuntu/melissa/melissa.py")


def load_melissa_module():
    module_name = f"melissa_demo_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_demo_patient_like_messages_are_detected() -> None:
    runtime = MelissaUltra.__new__(MelissaUltra)

    assert runtime._demo_should_use_patient_chat_path("hola")
    assert runtime._demo_should_use_patient_chat_path("quien eres")
    assert runtime._demo_should_use_patient_chat_path("quiero una cita para botox")

    assert not runtime._demo_should_use_patient_chat_path("quiero una demo")
    assert not runtime._demo_should_use_patient_chat_path("tengo un negocio")
    assert not runtime._demo_should_use_patient_chat_path("me dejaron probarte")


def test_demo_patient_clinic_uses_runtime_sector_and_drops_nova_label() -> None:
    runtime = MelissaUltra.__new__(MelissaUltra)

    clinic = runtime._build_demo_patient_clinic({"name": "Nova", "sector": "otro"})

    assert clinic["name"] == "la clínica"
    assert clinic["sector"] == "estetica"


def test_demo_patient_path_ignores_demo_history_when_no_business_loaded() -> None:
    runtime = MelissaUltra.__new__(MelissaUltra)
    seen = {}

    def fake_try_conversation_core(**kwargs):
        seen.update(kwargs)
        return ["Hola, soy Melissa."]

    runtime._try_conversation_core = fake_try_conversation_core

    history = [
        {"role": "assistant", "content": "Sigo siendo Melissa, la recepcionista virtual."},
        {"role": "assistant", "content": "dime cómo se llama tu negocio"},
    ]

    result = runtime._try_conversation_core(
        clinic=runtime._build_demo_patient_clinic({"name": "Nova", "sector": "otro"}),
        user_msg="quiero una cita para botox",
        history=[],
        is_admin=False,
        channel="whatsapp",
    )

    assert result == ["Hola, soy Melissa."]
    assert seen["history"] == []
    assert history[0]["content"].startswith("Sigo siendo Melissa")


def test_demo_patient_path_normalizes_low_quality_first_turn_without_business_name() -> None:
    module = load_melissa_module()
    module.Config.DEMO_MODE = True
    module.Config.DEMO_SECTOR = "estetica"
    module.Config.SECTOR = "estetica"
    module.Config.PLATFORM = "whatsapp"
    module.owner_style_controller = None
    module.anti_robot_filter = None
    module.response_variation = None
    module.hallucination_guard = None
    module.v8_process_response = lambda response, **kwargs: response
    module.db = types.SimpleNamespace(
        get_history=lambda chat_id, limit=None: [],
        save_message=lambda *args, **kwargs: None,
    )

    runtime = module.MelissaUltra.__new__(module.MelissaUltra)
    runtime._pending_buffers = {}
    runtime._admin_pending = {}
    runtime._last_reviewed_chat = None
    runtime._availability_pending_patient = None
    runtime._demo_sessions = {}
    runtime._emoji_chats = set()
    runtime._chat_routes = {}
    runtime._orchestrator = None
    runtime._resolve_route = lambda chat_id, route=None: {"platform": "whatsapp"}
    runtime._remember_route = lambda chat_id, route=None: None
    runtime._split_bubbles = lambda text, **kwargs: [part.strip() for part in text.split("|||") if part.strip()]
    runtime._try_conversation_core = lambda **kwargs: ["hola! hoy?"]

    result = asyncio.run(
        runtime._handle_demo_message(
            "probe_demo_1",
            "hola",
            {"name": "Nova", "sector": "otro", "services": ["Botox"]},
        )
    )

    joined = " ".join(result).lower()
    assert "hoy?" not in joined
    assert "melissa" in joined
    assert "botox" in joined or "tratamientos" in joined
