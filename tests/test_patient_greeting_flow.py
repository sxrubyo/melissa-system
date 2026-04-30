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


def test_process_message_demo_mode_still_allows_auth_flow() -> None:
    module = load_melissa_module()
    module.Config.DEMO_MODE = True
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
    melissa._handle_demo_message = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("demo no debería interceptar auth"))

    class FakeAuth:
        def is_auth_message(self, chat_id, text):
            return text == "/login"

        async def process(self, chat_id, text):
            return ["flujo auth"]

    module.auth_engine = FakeAuth()
    module.db = types.SimpleNamespace(
        get_clinic=lambda: {
            "name": "Melissa Demo",
            "sector": "estetica",
            "setup_done": 1,
            "admin_chat_ids": [],
            "pricing": {},
            "services": ["Botox"],
        },
        get_admin=lambda chat_id: None,
    )

    bubbles = asyncio.run(melissa.process_message("7000001099", "/login"))
    assert bubbles == ["flujo auth"]


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


def test_normalize_first_patient_turn_repairs_low_quality_whatsapp_greeting() -> None:
    module = load_melissa_module()
    generator = module.ResponseGenerator.__new__(module.ResponseGenerator)
    clinic = {"name": "Clinica de las americas", "sector": "estetica", "services": ["Botox", "Rellenos"]}
    personality = types.SimpleNamespace(name="Melissa", archetype="amigable")

    result = generator._normalize_first_patient_turn(
        response="hola! Soy Melissa, la asistente virtual. hoy?",
        clinic=clinic,
        personality=personality,
        user_msg="hola",
        history=[],
    )

    lowered = result.lower()
    assert "asistente virtual" not in lowered
    assert "hoy?" not in lowered
    assert "botox" in lowered or "rellenos" in lowered
    assert "hola, soy melissa" in lowered
    assert "asesora virtual" in lowered


def test_conversation_engine_identity_probe_for_whatsapp_stays_human() -> None:
    from melissa_core.conversation_engine import ConversationEngine
    from melissa_core.persona_registry import PersonaRegistry

    core_root = MODULE_PATH.parent
    registry = PersonaRegistry(core_root / "personas" / "melissa" / "base")
    engine = ConversationEngine(registry)

    result = engine.handle(
        clinic={
            "name": "Clinica de las americas",
            "sector": "estetica",
            "persona_key": "estetica_whatsapp",
            "channel": "whatsapp",
        },
        user_msg="quien eres",
        history=[],
        is_admin=False,
        channel="whatsapp",
    )

    joined = " ".join(result.bubbles).lower()
    assert result.handled is True
    assert "recepcionista virtual" not in joined
    assert "asistente virtual" not in joined
    assert "melissa" in joined
    assert "tratamientos" in joined or "valoración" in joined or "valoracion" in joined


def test_brain_v10_normalize_wrapper_does_not_bypass_low_quality_first_turn() -> None:
    import melissa_brain_v10 as brain_v10

    calls = []

    def original_fn(self, response, clinic, personality, user_msg, history):
        calls.append((response, user_msg))
        return "normalized"

    wrapped = brain_v10._make_llm_first_normalize(original_fn)

    result = wrapped(
        object(),
        "hola! Soy Melissa, la asistente virtual. hoy?",
        {"name": "Clinica de las americas", "sector": "estetica"},
        types.SimpleNamespace(name="Melissa"),
        "hola",
        [],
    )

    assert result == "normalized"
    assert calls == [("hola! Soy Melissa, la asistente virtual. hoy?", "hola")]


def test_normalize_first_contact_response_rewrites_bad_greeting_followup() -> None:
    module = load_melissa_module()

    result = module._normalize_first_contact_response(
        "hola! Soy Melissa, tu. hoy?",
        {"name": "la clínica", "services": ["Botox"], "sector": "estetica"},
        "hola",
    )

    lowered = result.lower()
    assert "soy melissa, tu. hoy?" not in lowered
    assert "qué te gustaría revisar" in lowered or "que te gustaria revisar" in lowered


def test_looks_fragmented_reply_detects_dangling_prepositions() -> None:
    module = load_melissa_module()

    assert module.looks_fragmented_reply("Soy Melissa, asesora de")
    assert module.looks_fragmented_reply("No tengo esa información de los")
    assert not module.looks_fragmented_reply("Soy Melissa, asesora virtual de la clínica.")


def test_admin_local_fallback_explains_creator_and_capabilities() -> None:
    module = load_melissa_module()
    module.db = types.SimpleNamespace(get_admin=lambda chat_id: {"name": "Santiago"})
    runtime = module.MelissaUltra.__new__(module.MelissaUltra)

    creator = runtime._admin_local_fallback(
        "quien te hizo",
        "quien te hizo",
        {"services": ["Botox"]},
        "Melissa",
        "6908159885",
    )
    audio = runtime._admin_local_fallback(
        "aceptas audios y pdf?",
        "aceptas audios y pdf?",
        {"services": ["Botox"]},
        "Melissa",
        "6908159885",
    )

    joined_creator = " ".join(creator).lower()
    joined_audio = " ".join(audio).lower()
    assert "blackboss" in joined_creator
    assert "3124348669" in joined_creator
    assert "audios" in joined_audio
    assert "pdf" in joined_audio


def test_is_synthetic_chat_id_filters_probe_like_demo_ids() -> None:
    module = load_melissa_module()
    runtime = module.MelissaUltra.__new__(module.MelissaUltra)

    assert runtime._is_synthetic_chat_id("owner-demo-1")
    assert runtime._is_synthetic_chat_id("wa_style_probe_live_40")
    assert runtime._is_synthetic_chat_id("fresh_greeting_fix_5")
    assert runtime._is_synthetic_chat_id("120363227381635534@newsletter")
    assert not runtime._is_synthetic_chat_id("573001112233@s.whatsapp.net")


def test_extract_conversation_selection_understands_conversation_number_phrase() -> None:
    from melissa_core.first_turn_ops import _extract_conversation_selection

    assert _extract_conversation_selection("muestrame la conversacion 1") == 1
    assert _extract_conversation_selection("quiero ver el chat numero 2") == 2


def test_normalize_first_contact_response_drops_duplicate_intro_bubble() -> None:
    module = load_melissa_module()

    result = module._normalize_first_contact_response(
        "Melissa por acá, del equipo de la clínica. ||| Botox lo manejan acá. Si quieres, te cuento cómo lo trabajan y qué suelen revisar para que se vea natural.",
        {"name": "la clínica", "services": ["Botox"], "sector": "estetica"},
        "quiero una cita para botox",
    )

    lowered = result.lower()
    assert lowered.count("hola, soy melissa") == 1
    assert "asesora virtual" in lowered
    assert "botox lo manejan acá" in lowered or "botox lo manejan aca" in lowered


def test_first_contact_intro_defaults_to_uppercase_virtual_advisor_voice() -> None:
    module = load_melissa_module()

    intro = module._first_contact_intro({"name": "la clínica"})

    assert intro.startswith("Hola")
    assert "asesora virtual" in intro.lower()
    assert "del equipo de" not in intro.lower()
    assert not intro.endswith(".")


def test_identity_probe_bubbles_admit_virtual_role_without_robotic_copy() -> None:
    module = load_melissa_module()
    generator = module.ResponseGenerator.__new__(module.ResponseGenerator)
    clinic = {"name": "la clínica", "sector": "estetica", "services": ["Botox", "Rellenos"]}
    personality = types.SimpleNamespace(name="Melissa")

    bubbles = generator._build_identity_probe_bubbles(clinic, personality, "quien eres")

    joined = " ".join(bubbles).lower()
    assert "asesora virtual" in joined
    assert "recepcionista virtual" not in joined
    assert "del equipo de" not in joined
    assert " ia " in f" {joined} " or "inteligencia artificial" in joined
    assert all(not bubble.strip().endswith(".") for bubble in bubbles)


def test_conversation_engine_identity_probe_uses_virtual_advisor_voice() -> None:
    from melissa_core.conversation_engine import ConversationEngine
    from melissa_core.persona_registry import PersonaRegistry

    core_root = MODULE_PATH.parent
    registry = PersonaRegistry(core_root / "personas" / "melissa" / "base")
    engine = ConversationEngine(registry)

    result = engine.handle(
        clinic={"name": "la clínica", "sector": "estetica", "persona_key": "estetica_whatsapp"},
        user_msg="quien eres",
        history=[],
        is_admin=False,
        channel="whatsapp",
    )

    joined = " ".join(result.bubbles).lower()
    assert result.handled is True
    assert "asesora virtual" in joined
    assert "recepcionista virtual" not in joined
    assert "del equipo de" not in joined


def test_owner_style_controller_can_keep_lowercase_start_when_requested() -> None:
    module = load_melissa_module()
    controller = module.OwnerStyleController()
    controller._loaded = True

    result = controller.apply_instruction("para pacientes usa minúscula al inicio")

    assert result["ok"] is True

    rendered = controller.enforce_output(
        "Hola, soy Melissa ||| Te ayudo con información",
        is_admin=False,
        first_turn=False,
        clinic={"name": "la clínica"},
        user_msg="hola",
    )

    first_bubble = rendered.split("|||")[0].strip()
    assert first_bubble.startswith("hola")


def test_calc_smart_wait_holds_first_contact_greeting_for_five_minutes() -> None:
    module = load_melissa_module()
    module.Config.DEMO_MODE = False
    module.Config.GREETING_ONLY_IDLE_SECONDS = 300
    module.db = types.SimpleNamespace(
        get_clinic=lambda: {"setup_done": 1},
        get_history=lambda chat_id, limit=None: [],
    )

    runtime = module.MelissaUltra.__new__(module.MelissaUltra)

    wait = runtime._calc_smart_wait("7000001004", "buenas tardes")

    assert wait == 300.0


def test_owner_style_controller_renders_three_bubble_welcome_for_pure_greeting() -> None:
    module = load_melissa_module()
    controller = module.OwnerStyleController()
    controller._loaded = True

    rendered = controller.enforce_output(
        "respuesta provisional",
        is_admin=False,
        first_turn=True,
        chat_id="",
        clinic={"name": "la clínica"},
        user_msg="buenas tardes",
    )

    bubbles = [part.strip() for part in rendered.split("|||") if part.strip()]
    assert len(bubbles) == 3
    assert bubbles[0].lower().startswith("hola, buenas tardes")
    assert "bienvenido a la clínica" in bubbles[0].lower() or "bienvenido a la clinica" in bubbles[0].lower()
    assert "asesora virtual" in bubbles[1].lower()
    assert bubbles[2] == "Cómo podemos ayudarte?"


def test_admin_recent_conversation_browser_shows_six_and_stores_context() -> None:
    module = load_melissa_module()
    runtime = module.MelissaUltra.__new__(module.MelissaUltra)
    runtime._admin_pending = {}

    module.db = types.SimpleNamespace(
        get_recent_patient_chats=lambda limit=10: (
            [
                {
                    "chat_id": "owner-demo-1",
                    "name": "Sintético",
                    "message_count": 99,
                    "last_message": "2026-04-27T05:30:00",
                    "last_user_msg": "probe",
                }
            ]
            + [
                {
                    "chat_id": f"57300000000{i}",
                    "name": f"Paciente {i}",
                    "message_count": 10 + i,
                    "last_message": "2026-04-27T04:30:00",
                    "last_user_msg": f"mensaje {i}",
                }
                for i in range(1, 9)
            ]
        )[:limit]
    )

    result = asyncio.run(runtime._admin_show_recent_conversation_browser("admin-1", limit=6))

    text = result[0]
    assert "Últimas 6 conversaciones" in text
    assert "Sintético" not in text
    assert "Paciente 1" in text
    assert "Paciente 6" in text
    assert "Paciente 7" not in text
    assert runtime._admin_pending["admin-1"]["action"] == "conversation_browser"
    assert len(runtime._admin_pending["admin-1"]["items"]) == 6


def test_admin_patient_chat_preview_defaults_to_last_ten_messages() -> None:
    module = load_melissa_module()
    runtime = module.MelissaUltra.__new__(module.MelissaUltra)
    runtime._admin_pending = {}

    module.db = types.SimpleNamespace(
        get_patient_conversation=lambda chat_id, limit=30: [
            {"role": "user" if i % 2 == 0 else "assistant", "ts": f"2026-04-27T04:{i:02d}:00", "content": f"mensaje {i}"}
            for i in range(1, 15)
        ][-limit:],
        _conn=None,
    )

    result = asyncio.run(runtime._admin_show_patient_chat_preview("573000000001", admin_chat_id="admin-1"))

    text = result[0]
    assert "Últimos 10 mensajes" in text
    assert "mensaje 5" in text
    assert "mensaje 6" in text
    assert "mensaje 14" in text
    assert runtime._admin_pending["admin-1"]["selected_chat_id"] == "573000000001"


def test_admin_recent_conversation_selection_opens_preview_without_pending_browser() -> None:
    module = load_melissa_module()
    runtime = module.MelissaUltra.__new__(module.MelissaUltra)
    runtime._admin_pending = {}
    runtime._last_reviewed_chat = None

    module.db = types.SimpleNamespace(
        get_recent_patient_chats=lambda limit=10: [
            {
                "chat_id": "owner-demo-1",
                "name": "Sintético",
                "message_count": 3,
                "last_message": "2026-04-27T05:30:00",
                "last_user_msg": "probe",
            },
            {
                "chat_id": "573000000001",
                "name": "Paciente Uno",
                "message_count": 8,
                "last_message": "2026-04-27T04:30:00",
                "last_user_msg": "hola",
            },
            {
                "chat_id": "573000000002",
                "name": "Paciente Dos",
                "message_count": 6,
                "last_message": "2026-04-27T04:20:00",
                "last_user_msg": "precio",
            },
        ][:limit],
        get_patient_conversation=lambda chat_id, limit=30: [
            {"role": "user", "ts": "2026-04-27T04:20:00", "content": "hola"},
            {"role": "assistant", "ts": "2026-04-27T04:21:00", "content": "respuesta"},
        ],
        _conn=None,
    )

    result = asyncio.run(
        runtime._admin_show_recent_conversation_selection("admin-1", 1)
    )

    text = result[0]
    assert "Paciente Uno" in text
    assert "Sintético" not in text
    assert runtime._admin_pending["admin-1"]["selected_chat_id"] == "573000000001"


def test_admin_handler_understands_direct_conversation_selection_without_pending_browser() -> None:
    module = load_melissa_module()
    runtime = module.MelissaUltra.__new__(module.MelissaUltra)
    runtime._admin_pending = {}
    runtime._pending_buffers = {}
    runtime._chat_routes = {}
    runtime._remember_route = lambda chat_id, route=None: None
    runtime._resolve_route = lambda chat_id, route=None: {"platform": "whatsapp"}
    runtime._apply_admin_output_pipeline = lambda text, *args, **kwargs: text
    runtime._split_bubbles = lambda text, **kwargs: [part.strip() for part in text.split("|||") if part.strip()]

    module.owner_style_controller = None
    module.prompt_evolver = None
    module.trainer_gateway = None
    module._NOVA_AVAILABLE = False
    module.Config.NOVA_ENABLED = False
    module.kb = None

    module.db = types.SimpleNamespace(
        get_admin=lambda chat_id: {"name": "Santiago"},
        get_history=lambda chat_id, limit=8: [],
        save_message=lambda *args, **kwargs: None,
        get_recent_patient_chats=lambda limit=10: [
            {
                "chat_id": "owner-demo-1",
                "name": "Sintético",
                "message_count": 3,
                "last_message": "2026-04-27T05:30:00",
                "last_user_msg": "probe",
            },
            {
                "chat_id": "573000000001",
                "name": "Paciente Uno",
                "message_count": 8,
                "last_message": "2026-04-27T04:30:00",
                "last_user_msg": "hola",
            },
        ][:limit],
        get_patient_conversation=lambda chat_id, limit=30: [
            {"role": "user", "ts": "2026-04-27T04:20:00", "content": "hola"},
            {"role": "assistant", "ts": "2026-04-27T04:21:00", "content": "respuesta"},
        ],
        _conn=None,
    )

    result = asyncio.run(
        runtime._handle_admin_or_setup(
            "admin-1",
            "muestrame que has hablado en la conversacion 1",
            {"name": "Melissa Demo", "admin_chat_ids": ["admin-1"], "setup_done": True},
        )
    )

    text = result[0]
    assert "Paciente Uno" in text
    assert "Últimos 2 mensajes" in text


def test_persona_forbidden_patterns_include_helpdesk_openers() -> None:
    from melissa_core.persona_registry import PersonaRegistry

    registry = PersonaRegistry(MODULE_PATH.parent / "personas" / "melissa" / "base")
    profile = registry.get("estetica_whatsapp")
    assert profile is not None

    banned = " / ".join(profile.forbidden_patterns).lower()
    assert "buenas, en qué te ayudo" in banned
    assert "hola, en qué te ayudo" in banned
    assert "cuéntame en qué te ayudo" in banned
    assert "cómo puedo ayudarte" in banned


def test_system_prompt_explicitly_forbids_helpdesk_openers() -> None:
    module = load_melissa_module()
    generator = module.ResponseGenerator.__new__(module.ResponseGenerator)
    from melissa_core.persona_registry import PersonaRegistry

    generator._conversation_registry = PersonaRegistry(MODULE_PATH.parent / "personas" / "melissa" / "base")
    module.owner_style_controller = None
    module.db = types.SimpleNamespace(
        get_core_memory_block=lambda: "",
        get_trust_rules=lambda limit=4: [],
        get_behavior_playbooks=lambda limit=3: [],
    )
    personality = types.SimpleNamespace(
        name="Melissa",
        tone_instruction="",
        custom_phrases={},
        forbidden_words=[],
    )

    prompt = generator._build_compact_system_prompt(
        clinic={"name": "la clínica", "sector": "estetica", "services": ["Botox", "Rellenos"]},
        patient={"name": "", "visits": 0, "is_new": True, "last_service": ""},
        personality=personality,
        search_context="",
        reasoning={},
        kb_context="",
        context_summary="",
        pre_prompt_injection="",
        chat_id="test-chat",
        history=[],
    )

    lowered = prompt.lower()
    assert "buenas, en qué te ayudo" in lowered
    assert "hola, en qué te ayudo" in lowered
    assert "cuéntame en qué te ayudo" in lowered


def test_full_system_prompt_accepts_explicit_user_message() -> None:
    module = load_melissa_module()
    generator = module.ResponseGenerator.__new__(module.ResponseGenerator)
    generator._conversation_registry = None
    module.owner_style_controller = None
    module.db = types.SimpleNamespace(
        get_core_memory_block=lambda: "",
        get_all_trust_rules=lambda: [],
        get_behavior_playbooks=lambda limit=8: [],
    )
    module.v8_build_quality_system_prompt_addon = lambda **kwargs: ""
    module.trainer_get_system_prompt_addon = lambda *args, **kwargs: ""

    personality = types.SimpleNamespace(
        name="Melissa",
        tone_instruction="",
        custom_phrases={},
        forbidden_words=[],
        formality_level=0.5,
        archetype="amigable",
    )

    prompt = generator._build_system_prompt(
        clinic={"name": "la clínica", "sector": "estetica", "services": ["Botox"]},
        patient={"name": "", "visits": 0, "is_new": True, "last_service": "", "language": "es"},
        personality=personality,
        search_context="",
        reasoning={},
        kb_context="",
        user_msg="hola quiero botox",
        chat_id="test-chat",
        history=[],
    )

    lowered = prompt.lower()
    assert "soy melissa" in lowered
    assert "asi respondo cuando alguien me escribe" in lowered
