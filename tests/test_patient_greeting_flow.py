import asyncio
import importlib.util
import sys
import types
import uuid
from pathlib import Path


MODULE_PATH = Path("/home/ubuntu/melissa/melissa.py")
sys.path.insert(0, str(MODULE_PATH.parent))


def load_melissa_module():
    module_name = f"melissa_base_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_process_message_first_turn_short_greeting_uses_llm() -> None:
    module = load_melissa_module()
    module.Config.DEMO_MODE = False
    melissa = module.MelissaUltra.__new__(module.MelissaUltra)
    melissa._pending_buffers = {}
    melissa._admin_pending = {}
    melissa._last_reviewed_chat = None
    melissa._availability_pending_patient = None
    melissa._demo_sessions = {}
    melissa._emoji_chats = set()
    melissa._chat_routes = {}
    melissa._orchestrator = None
    melissa._remember_route = lambda chat_id, route=None: None
    melissa._resolve_route = lambda chat_id, route=None: {"platform": "whatsapp"}
    melissa._try_conversation_core = lambda **kwargs: None
    melissa.search = types.SimpleNamespace(detect_procedure=lambda text: None)
    module.auth_engine = None
    module.trainer_gateway = None
    module.nova_rule_sync = None
    module.kb = None
    module.calendar_bridge = None
    module.task_manager = None
    module.owner_style_controller = None
    module.anti_robot_filter = None
    module.response_variation = None
    module.hallucination_guard = None
    module.notify_omni = lambda *args, **kwargs: None
    module.v8_process_response = lambda response, **kwargs: response

    class FakeAnalyzer:
        def analyze(self, text, history):
            return types.SimpleNamespace(
                intent=module.IntentType.GENERAL_QUESTION,
                urgency=module.UrgencyLevel.NONE,
                language="es",
                requires_search=False,
                closing_score=0.0,
                lead_temperature="cold",
            )

    class FakeReasoning:
        async def reason(self, *args, **kwargs):
            return {"_metadata": {"model": "test_reasoning"}}

    class FakeGenerator:
        def __init__(self):
            self.generate_calls = 0

        def _get_default_personality(self, clinic):
            return types.SimpleNamespace(archetype="amigable")

        def _is_greeting_only(self, text):
            return True

        async def generate(self, *args, **kwargs):
            self.generate_calls += 1
            return "hola, aquí estoy. dime qué necesitas"

        def _normalize_first_patient_turn(self, response, **kwargs):
            return response or "fallback"

    melissa.analyzer = FakeAnalyzer()
    melissa.reasoning = FakeReasoning()
    melissa.generator = FakeGenerator()
    module.db = types.SimpleNamespace(
        get_clinic=lambda: {
            "name": "Clinica de las americas",
            "sector": "estetica",
            "setup_done": 1,
            "admin_chat_ids": [],
            "pricing": {},
            "services": ["Botox"],
        },
        get_admin=lambda chat_id: None,
        get_or_create_patient=lambda chat_id: {"is_new": True, "name": ""},
        get_history=lambda chat_id, limit=None: [],
        get_conversation_state=lambda chat_id: types.SimpleNamespace(turn_count=0, last_intent=None),
        save_message=lambda *args, **kwargs: None,
        save_conversation_state=lambda *args, **kwargs: None,
        record_metric=lambda *args, **kwargs: None,
    )

    bubbles = asyncio.run(melissa.process_message("7000001004", "hola"))

    assert melissa.generator.generate_calls == 1
    assert bubbles == ["hola, aquí estoy. dime qué necesitas"]


def test_normalize_first_patient_turn_keeps_meaningful_llm_greeting() -> None:
    module = load_melissa_module()
    generator = module.ResponseGenerator.__new__(module.ResponseGenerator)
    clinic = {"name": "Clinica de las americas", "sector": "estetica", "services": ["Botox"]}
    personality = types.SimpleNamespace(name="Melissa", archetype="amigable")

    result = generator._normalize_first_patient_turn(
        response="Hola, aquí estoy. Dime qué te gustaría revisar. ||| Si es botox, te ubico.",
        clinic=clinic,
        personality=personality,
        user_msg="hola",
        history=[],
    )

    lowered = result.lower()
    assert "hola, soy melissa" not in lowered
    assert "aquí estoy" in lowered or "aqui estoy" in lowered


def test_returning_greeting_drops_prefab_resume_copy() -> None:
    module = load_melissa_module()
    from melissa_core.conversation_engine import ConversationEngine
    from melissa_core.persona_registry import PersonaRegistry

    core_root = MODULE_PATH.parent
    registry = PersonaRegistry(core_root / "personas" / "melissa" / "base")
    engine = ConversationEngine(registry)
    persona = registry.resolve_for_clinic({"sector": "estetica"})

    bubbles = engine._build_returning_greeting(
        persona=persona,
        clinic={"name": "Clinica de las americas", "sector": "estetica"},
        history=[{"role": "assistant", "content": "te ayudo con botox"}],
        normalized="hola",
    )

    lowered = " ".join(bubbles).lower()
    assert "retomamos desde donde lo dejamos" not in lowered
    assert "qué bueno tenerte por acá" not in lowered


def test_conversation_engine_recognizes_status_greetings_as_llm_greetings() -> None:
    from melissa_core.conversation_engine import ConversationEngine
    from melissa_core.persona_registry import PersonaRegistry

    core_root = MODULE_PATH.parent
    registry = PersonaRegistry(core_root / "personas" / "melissa" / "base")
    engine = ConversationEngine(registry)

    result = engine.handle(
        clinic={"name": "Clinica de las americas", "sector": "estetica"},
        user_msg="hola, como vas",
        history=[],
        is_admin=False,
        channel="whatsapp",
    )

    assert result.handled is False
    assert result.reason == "llm_greeting"
