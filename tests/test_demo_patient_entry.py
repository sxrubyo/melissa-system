import sys
import types
import uuid
import importlib.util
import asyncio
from pathlib import Path
import melissa_domino


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


class _DemoDb:
    def __init__(self) -> None:
        self.store = {}

    def get_history(self, chat_id, limit=None):
        data = self.store.get(chat_id, [])
        return data[-limit:] if limit else list(data)

    def save_message(self, chat_id, role, content, **kwargs):
        self.store.setdefault(chat_id, []).append({"role": role, "content": content})

    def get_admin(self, chat_id):
        return None

    def _conn(self):
        class _DummyConn:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def execute(self, *args, **kwargs):
                return None

        return _DummyConn()


def _build_demo_runtime(module, engine):
    module.Config.DEMO_MODE = True
    module.Config.DEMO_SECTOR = "estetica"
    module.Config.SECTOR = "estetica"
    module.Config.PLATFORM = "whatsapp"
    module.owner_style_controller = None
    module.anti_robot_filter = None
    module.response_variation = None
    module.hallucination_guard = None
    module.v8_process_response = lambda response, **kwargs: response
    module.llm_engine = engine
    module.db = _DemoDb()

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
    runtime._try_conversation_core = lambda **kwargs: None
    runtime.generator = types.SimpleNamespace(_postprocess=lambda text, profile: text, llm=None)

    class _Search:
        async def search_business_link(self, name):
            return ("", "")

    runtime.search = _Search()
    return runtime, module.db


def test_demo_patient_like_messages_are_detected() -> None:
    runtime = MelissaUltra.__new__(MelissaUltra)

    assert not runtime._demo_should_use_patient_chat_path("hola")
    assert not runtime._demo_should_use_patient_chat_path("quien eres")
    assert not runtime._demo_should_use_patient_chat_path("cuanto es 5 x 4")
    assert not runtime._demo_should_use_patient_chat_path("cual es la capital de francia")
    assert runtime._demo_should_use_patient_chat_path("quiero una cita para botox")
    assert runtime._demo_should_use_patient_chat_path("me interesa botox")

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


def test_demo_owner_onboarding_replaces_low_quality_first_turn_without_business_name() -> None:
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
    assert "nova" not in joined
    assert "negocio" in joined


def test_demo_domino_does_not_treat_followup_question_as_new_business_name() -> None:
    payload = melissa_domino.build_demo_domino_payload(
        user_text="para que querias el nombre de mi negocio?",
        history=[{"role": "assistant", "content": "ya tengo Clínica América"}],
        business_name="Clínica América",
        business_ctx="Clínica estética en Bogotá",
        found_online=True,
    )

    assert payload["stage"] == "re-ground"


def test_demo_followup_meta_question_after_business_binding_uses_regrounded_llm() -> None:
    module = load_melissa_module()

    class _Engine:
        def __init__(self) -> None:
            self.meta_calls = 0

        async def complete(self, msgs, **kwargs):
            user = msgs[-1]["content"]
            if user.startswith("negocio: "):
                return (
                    "ya tengo Clínica América ||| ya me ubiqué con cómo tendría que sonar esto ||| escríbeme como si fueras un cliente",
                    {"provider": "fake", "model": "fake"},
                )
            if "para que querias el nombre de mi negocio" in user.lower():
                self.meta_calls += 1
                if self.meta_calls == 1:
                    return (
                        "te lo pedí para hablar como si ya llevara ese chat ||| así te muestro la demo sin inventar nada",
                        {"provider": "fake", "model": "fake"},
                    )
                return (
                    "te lo pedí para hablar como si ya llevara el chat de Clinica America ||| así la demo te muestra mejor cómo respondería de verdad",
                    {"provider": "fake", "model": "fake"},
                )
            return ("ok ||| sigo", {"provider": "fake", "model": "fake"})

    engine = _Engine()
    runtime, _db = _build_demo_runtime(module, engine)
    clinic = {"name": "Nova", "sector": "otro", "services": ["Botox"]}

    asyncio.run(runtime._handle_demo_message("owner_meta_1", "mi negocio se llama Clinica America", clinic))
    result = asyncio.run(
        runtime._handle_demo_message("owner_meta_1", "para que querias el nombre de mi negocio?", clinic)
    )

    joined = " ".join(result).lower()
    assert engine.meta_calls >= 2
    assert "te lo pedí para hablar como si ya llevara el chat de clinica america" in joined
    assert "te pido el nombre de tu negocio" not in joined
    assert "soy melissa" not in joined
    assert runtime._demo_sessions["demo_owner_meta_1_name"] == "Clinica America"


def test_demo_business_activation_repairs_fragmented_llm_binding_reply() -> None:
    module = load_melissa_module()

    class _Engine:
        def __init__(self) -> None:
            self.binding_calls = 0

        async def complete(self, msgs, **kwargs):
            user = msgs[-1]["content"]
            if user.startswith("negocio: "):
                self.binding_calls += 1
                if self.binding_calls == 1:
                    return ("ya tengo clínica america, un", {"provider": "fake", "model": "fake"})
                return (
                    "ya tengo Clínica América ||| ya me ubiqué con cómo tendría que sonar esto ||| escríbeme como si fueras un cliente",
                    {"provider": "fake", "model": "fake"},
                )
            return ("ok ||| sigo", {"provider": "fake", "model": "fake"})

    engine = _Engine()
    runtime, _db = _build_demo_runtime(module, engine)
    runtime.search = types.SimpleNamespace(
        search_business_link=lambda name: None,
    )

    async def _search_business_link(name):
        return (
            (
                "Clínica América es una clínica estética en Bogotá con valoración facial, botox, rellenos, "
                "atención médica especializada, agenda por WhatsApp y enfoque conservador en resultados naturales."
            ),
            "https://clinica-america.example",
        )

    runtime.search.search_business_link = _search_business_link
    clinic = {"name": "Nova", "sector": "otro", "services": ["Botox"]}

    result = asyncio.run(
        runtime._handle_demo_message("owner_bind_1", "mi negocio se llama Clinica America", clinic)
    )

    joined = " ".join(result).lower()
    assert engine.binding_calls >= 2
    assert "cliente" in joined
    assert ", un" not in joined


def test_demo_owner_can_explicitly_start_customer_simulation_after_business_binding() -> None:
    module = load_melissa_module()

    class _Engine:
        async def complete(self, msgs, **kwargs):
            user = msgs[-1]["content"]
            system = msgs[0]["content"]
            if user.startswith("negocio: "):
                return (
                    "ya tengo Clínica América ||| ya me ubiqué con cómo tendría que sonar esto ||| escríbeme como si fueras un cliente",
                    {"provider": "fake", "model": "fake"},
                )
            if "ya pueden empezar la demo" in system:
                return (
                    "de una ||| escríbeme como si fueras un cliente real y yo ya caigo en el chat",
                    {"provider": "fake", "model": "fake"},
                )
            return ("ok ||| sigo", {"provider": "fake", "model": "fake"})

    runtime, _db = _build_demo_runtime(module, _Engine())
    clinic = {"name": "Nova", "sector": "otro", "services": ["Botox"]}

    asyncio.run(runtime._handle_demo_message("owner_sim_1", "mi negocio se llama Clinica America", clinic))
    result = asyncio.run(
        runtime._handle_demo_message("owner_sim_1", "vale hagamos una demo entonces", clinic)
    )

    joined = " ".join(result).lower()
    assert "cliente real" in joined
    assert "soy melissa" not in joined


def test_demo_owner_simulation_start_repairs_truncated_launch_reply() -> None:
    module = load_melissa_module()

    class _Engine:
        def __init__(self) -> None:
            self.sim_calls = 0

        async def complete(self, msgs, **kwargs):
            user = msgs[-1]["content"]
            system = msgs[0]["content"]
            if user.startswith("negocio: "):
                return (
                    "ya tengo Clínica América ||| ya me ubiqué con cómo tendría que sonar esto ||| escríbeme como si fueras un cliente",
                    {"provider": "fake", "model": "fake"},
                )
            if "ya pueden empezar la demo" in system:
                self.sim_calls += 1
                if self.sim_calls == 1:
                    return ("Perfecto, entonces podemos", {"provider": "fake", "model": "fake"})
                return (
                    "de una ||| escríbeme como si fueras un cliente real y yo ya caigo en el chat",
                    {"provider": "fake", "model": "fake"},
                )
            return ("ok ||| sigo", {"provider": "fake", "model": "fake"})

    engine = _Engine()
    runtime, _db = _build_demo_runtime(module, engine)
    clinic = {"name": "Nova", "sector": "otro", "services": ["Botox"]}

    asyncio.run(runtime._handle_demo_message("owner_sim_bad_1", "mi negocio se llama Clinica America", clinic))
    result = asyncio.run(
        runtime._handle_demo_message("owner_sim_bad_1", "vale hagamos una demo entonces", clinic)
    )

    joined = " ".join(result).lower()
    assert engine.sim_calls >= 2
    assert "cliente real" in joined
    assert "perfecto, entonces podemos" not in joined


def test_demo_business_activation_without_public_info_avoids_hallucinating_context() -> None:
    module = load_melissa_module()

    class _Engine:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, msgs, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return (
                    "supongo que es un lugar donde ofrecen servicios medicos de calidad",
                    {"provider": "fake", "model": "fake"},
                )
            return (
                "listo, ya tengo Clinica America ||| todavía no encontré información pública confiable, así que la mejor demo es desde el chat mismo ||| escríbeme como si fueras un cliente y arranco",
                {"provider": "fake", "model": "fake"},
            )

    engine = _Engine()
    runtime, _db = _build_demo_runtime(module, engine)
    clinic = {"name": "Nova", "sector": "otro", "services": ["Botox"]}

    result = asyncio.run(
        runtime._handle_demo_message("owner_bind_noinfo_1", "mi negocio se llama Clinica America", clinic)
    )

    joined = " ".join(result).lower()
    assert engine.calls >= 2
    assert "todavía no encontré información pública confiable" in " ".join(result)
    assert "supongo que" not in joined


def test_demo_owner_onboarding_repairs_thin_capability_answer() -> None:
    module = load_melissa_module()

    class _Engine:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, msgs, **kwargs):
            self.calls += 1
            user = msgs[-1]["content"].lower()
            if "me mandaron tu numero" in user or "no entiendo que haces" in user:
                if self.calls == 1:
                    return ("Aquí lo que hago es llevar las conversaciones", {"provider": "fake", "model": "fake"})
                return (
                    "Respondo clientes, filtro interesados, oriento y ayudo con citas ||| también reporto lo que pasa en el chat y acepto feedback ||| si quieres verlo bien, pásame el nombre de tu negocio y arrancamos",
                    {"provider": "fake", "model": "fake"},
                )
            return ("ok ||| sigo", {"provider": "fake", "model": "fake"})

    engine = _Engine()
    runtime, _db = _build_demo_runtime(module, engine)
    clinic = {"name": "Nova", "sector": "otro", "services": ["Botox"]}

    result = asyncio.run(
        runtime._handle_demo_message("owner_cap_1", "me mandaron tu numero y no entiendo que haces", clinic)
    )

    joined = " ".join(result).lower()
    assert engine.calls >= 2
    assert any(token in joined for token in ("clientes", "citas", "respondo", "orient"))
    assert "dime cómo se llama tu negocio" not in joined


def test_demo_owner_onboarding_static_fallback_only_when_model_returns_nothing() -> None:
    module = load_melissa_module()

    class _Engine:
        async def complete(self, msgs, **kwargs):
            return ("", {"provider": "fake", "model": "fake"})

    runtime, _db = _build_demo_runtime(module, _Engine())
    clinic = {"name": "Nova", "sector": "otro", "services": ["Botox"]}

    result = asyncio.run(
        runtime._handle_demo_message("owner_cap_none_1", "me mandaron tu numero y no entiendo que haces", clinic)
    )

    joined = " ".join(result).lower()
    assert "respondo clientes" in joined
    assert "pásame el nombre de tu negocio" in " ".join(result).lower()


def test_demo_owner_onboarding_invalid_model_outputs_fall_back_to_owner_last_resort() -> None:
    module = load_melissa_module()

    class _Engine:
        async def complete(self, msgs, **kwargs):
            return ("Lo que hago es básicamente atender", {"provider": "fake", "model": "fake"})

    runtime, _db = _build_demo_runtime(module, _Engine())
    clinic = {"name": "Nova", "sector": "otro", "services": ["Botox"]}

    result = asyncio.run(
        runtime._handle_demo_message("owner_cap_invalid_1", "me mandaron tu numero y no entiendo que haces", clinic)
    )

    joined = " ".join(result).lower()
    assert "básicamente atender" not in " ".join(result).lower()
    assert any(token in joined for token in ("clientes", "citas", "negocio"))


def test_transcribe_audio_uses_groq_when_gemini_is_exhausted() -> None:
    module = load_melissa_module()
    module.Config.TELEGRAM_TOKEN = "tg-test"
    module.Config.GEMINI_API_KEY = "k1"
    module.Config.GEMINI_API_KEY_2 = "k2"
    module.Config.GEMINI_API_KEY_3 = "k3"
    module.Config.GEMINI_API_KEY_4 = "k4"
    module.Config.GEMINI_API_KEY_5 = "k5"
    module.Config.GEMINI_API_KEY_6 = "k6"
    module.Config.GROQ_API_KEY = "groq-test"
    module.Config.OPENROUTER_API_KEY = ""

    class _Resp:
        def __init__(self, status_code=200, json_data=None, text="", content=b""):
            self.status_code = status_code
            self._json = json_data or {}
            self.text = text
            self.content = content

        def json(self):
            return self._json

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None, headers=None):
            if "getFile" in url:
                return _Resp(json_data={"result": {"file_path": "voice/file_1.oga"}})
            if "/file/bot" in url:
                return _Resp(content=b"fake-audio")
            raise AssertionError(f"GET inesperado: {url}")

        async def post(self, url, json=None, files=None, data=None, headers=None):
            if "generativelanguage.googleapis.com" in url:
                return _Resp(status_code=429, text="rate limited")
            if "api.groq.com/openai/v1/audio/transcriptions" in url:
                return _Resp(status_code=200, json_data={"text": "hola, quiero información de botox"})
            raise AssertionError(f"POST inesperado: {url}")

    module.httpx.AsyncClient = _FakeAsyncClient
    runtime = module.MelissaUltra.__new__(module.MelissaUltra)

    text = asyncio.run(runtime.transcribe_audio("voice-1", platform="telegram"))
    assert "quiero información de botox" in text


def test_demo_simulation_mode_bypasses_core_for_same_chat_customer_turns() -> None:
    module = load_melissa_module()

    class _Engine:
        async def complete(self, msgs, **kwargs):
            user = msgs[-1]["content"]
            system = msgs[0]["content"]
            if user.startswith("negocio: "):
                return (
                    "ya tengo Clínica América ||| ya me ubiqué con cómo tendría que sonar esto ||| escríbeme como si fueras un cliente",
                    {"provider": "fake", "model": "fake"},
                )
            if "ya pueden empezar la demo" in system:
                return (
                    "de una ||| escríbeme como si fueras un cliente real y yo ya caigo en el chat",
                    {"provider": "fake", "model": "fake"},
                )
            if "Ya están en plena conversación con una persona interesada" in system:
                return (
                    "hola, bienvenida a Clínica América ||| qué te gustaría revisar",
                    {"provider": "fake", "model": "fake"},
                )
            return ("ok ||| sigo", {"provider": "fake", "model": "fake"})

    runtime, _db = _build_demo_runtime(module, _Engine())
    runtime._try_conversation_core = lambda **kwargs: ["hola que necesitas"]
    clinic = {"name": "Nova", "sector": "otro", "services": ["Botox"]}

    asyncio.run(runtime._handle_demo_message("owner_sim_live_1", "mi negocio se llama Clinica America", clinic))
    asyncio.run(runtime._handle_demo_message("owner_sim_live_1", "vale hagamos una demo entonces", clinic))
    result = asyncio.run(runtime._handle_demo_message("owner_sim_live_1", "hola buenas tardes", clinic))

    joined = " ".join(result).lower()
    assert "hola que necesitas" not in joined
    assert "qué te gustaría revisar" in " ".join(result).lower()


def test_demo_simulation_last_resort_keeps_continuity_when_models_fully_fail() -> None:
    module = load_melissa_module()

    class _Engine:
        def __init__(self) -> None:
            self.fail_customer_turn = False

        async def complete(self, msgs, **kwargs):
            user = msgs[-1]["content"]
            system = msgs[0]["content"]
            if user.startswith("negocio: "):
                return (
                    "ya tengo Clínica América ||| ya me ubiqué con cómo tendría que sonar esto ||| escríbeme como si fueras un cliente",
                    {"provider": "fake", "model": "fake"},
                )
            if "ya pueden empezar la demo" in system:
                return (
                    "de una ||| escríbeme como si fueras un cliente real y yo ya caigo en el chat",
                    {"provider": "fake", "model": "fake"},
                )
            if "Ya están en plena conversación con una persona interesada" in system:
                if self.fail_customer_turn:
                    raise RuntimeError("all providers failed")
                return (
                    "botox acá lo trabajan muy natural ||| qué zona te gustaría revisar",
                    {"provider": "fake", "model": "fake"},
                )
            return ("ok ||| sigo", {"provider": "fake", "model": "fake"})

    engine = _Engine()
    runtime, _db = _build_demo_runtime(module, engine)
    clinic = {"name": "Nova", "sector": "otro", "services": ["Botox"]}

    asyncio.run(runtime._handle_demo_message("owner_sim_fail_1", "mi negocio se llama Clinica America", clinic))
    asyncio.run(runtime._handle_demo_message("owner_sim_fail_1", "vale hagamos una demo entonces", clinic))
    asyncio.run(runtime._handle_demo_message("owner_sim_fail_1", "me interesa botox pero me da miedo quedar exagerada", clinic))
    engine.fail_customer_turn = True
    result = asyncio.run(runtime._handle_demo_message("owner_sim_fail_1", "si quiero cita como seguimos?", clinic))

    joined = " ".join(result).lower()
    assert "hola, soy melissa" not in joined
    assert "cuéntame un poco más y te voy guiando" not in joined
    assert any(token in joined for token in ("agendar", "horario", "siguiente paso", "nombre"))


def test_demo_owner_why_name_without_business_falls_back_to_real_explanation() -> None:
    module = load_melissa_module()

    class _Engine:
        async def complete(self, msgs, **kwargs):
            return ("", {"provider": "fake", "model": "fake"})

    runtime, _db = _build_demo_runtime(module, _Engine())
    clinic = {"name": "Nova", "sector": "otro", "services": ["Botox"]}

    result = asyncio.run(
        runtime._handle_demo_message("owner_why_1", "para que quieres el nombre de mi negocio?", clinic)
    )

    joined = " ".join(result).lower()
    assert "tono" in joined or "contexto" in joined
    assert "demo" in joined
    assert "pásame el nombre de tu negocio" not in joined


def test_demo_customer_simulation_rejects_hoy_fragment_and_repairs_greeting() -> None:
    module = load_melissa_module()

    class _Engine:
        def __init__(self) -> None:
            self.customer_calls = 0

        async def complete(self, msgs, **kwargs):
            user = msgs[-1]["content"]
            system = msgs[0]["content"]
            if user.startswith("negocio: "):
                return (
                    "ya tengo Clínica América ||| ya me ubiqué con cómo tendría que sonar esto ||| escríbeme como si fueras un cliente",
                    {"provider": "fake", "model": "fake"},
                )
            if "ya pueden empezar la demo" in system:
                return (
                    "de una ||| escríbeme como si fueras un cliente real y yo ya caigo en el chat",
                    {"provider": "fake", "model": "fake"},
                )
            if "Ya están en plena conversación con una persona interesada" in system:
                self.customer_calls += 1
                if self.customer_calls == 1:
                    return (
                        "Hola, buenas tardes. Soy Melissa de Clínica América ||| hoy?",
                        {"provider": "fake", "model": "fake"},
                    )
                return (
                    "hola, Melissa por acá en Clínica América ||| cuéntame qué te gustaría revisar",
                    {"provider": "fake", "model": "fake"},
                )
            return ("ok ||| sigo", {"provider": "fake", "model": "fake"})

    engine = _Engine()
    runtime, _db = _build_demo_runtime(module, engine)
    clinic = {"name": "Nova", "sector": "otro", "services": ["Botox"]}

    asyncio.run(runtime._handle_demo_message("owner_hoy_1", "mi negocio se llama Clinica America", clinic))
    asyncio.run(runtime._handle_demo_message("owner_hoy_1", "vale hagamos una demo entonces", clinic))
    result = asyncio.run(runtime._handle_demo_message("owner_hoy_1", "hola buenas tardes", clinic))

    joined = " ".join(result).lower()
    assert engine.customer_calls >= 2
    assert "hoy?" not in joined
    assert "melissa" in joined
    assert "revisar" in joined
