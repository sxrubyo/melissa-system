import asyncio
import importlib.util
import sys
import time
import types
import uuid
from pathlib import Path


MODULE_PATH = Path("/home/ubuntu/melissa/melissa.py")
sys.path.insert(0, str(MODULE_PATH.parent))


def load_melissa_module():
    module_name = f"melissa_runtime_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_search_business_link_parses_serpapi_local_results_dict() -> None:
    module = load_melissa_module()

    payload = {
        "local_results": {
            "places": [
                {
                    "title": "Clínica Las Américas Auna",
                    "type": "Hospital",
                    "address": "Antioquia",
                    "rating": 3.7,
                    "links": {
                        "website": "https://clinicalasamericas.example",
                        "directions": "https://maps.example/las-americas",
                    },
                }
            ]
        },
        "organic_results": [
            {"snippet": "Centro hospitalario ubicado en Medellín con urgencias y hospitalización."}
        ],
    }

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            return _Response()

    module.httpx.AsyncClient = _Client
    engine = module.WebSearchEngine.__new__(module.WebSearchEngine)
    engine._ext = None
    engine.serp_key = "serp"
    engine.brave_key = ""
    engine.apify_key = ""

    text, url = asyncio.run(engine.search_business_link("Clinica America"))

    assert url == "https://maps.example/las-americas"
    lowered = text.lower()
    assert "clínica las américas auna" in lowered
    assert "hospital" in lowered
    assert "antioquia" in lowered


def test_search_business_link_rejects_weak_clinic_match_and_falls_back_to_maps() -> None:
    module = load_melissa_module()

    payload = {
        "organic_results": [
            {
                "title": "Tatiana Arriaga (@spa.vidazen) · Medellín",
                "link": "https://www.instagram.com/spa.vidazen/",
                "snippet": "Estamos ubicados en Manrique carrera 45 # 77-55 y hacemos tratamientos estéticos.",
            },
            {
                "title": "Doctores de Medicina Estética en Medellín (Manrique)",
                "link": "https://www.clinicasesteticas.com.co/clinicas/medicina-estetica/medellin-manrique",
                "snippet": "Centros de Medicina Estética cerca de Medellín (Manrique).",
            },
            {
                "title": "Arancha Manrique - Medicina estética",
                "link": "https://aranchamanrique.com/",
                "snippet": "Tratamientos de medicina estética y antienvejecimiento.",
            },
        ]
    }

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            return _Response()

    module.httpx.AsyncClient = _Client
    engine = module.WebSearchEngine.__new__(module.WebSearchEngine)
    engine._ext = None
    engine.serp_key = "serp"
    engine.brave_key = ""
    engine.apify_key = ""
    engine.apify_keys = []

    text, url = asyncio.run(engine.search_business_link("Clinica Estetica Manrique"))

    assert text == ""
    assert url.startswith("https://www.google.com/maps/search/")
    assert "Clinica%20Estetica%20Manrique" in url


def test_llm_engine_prioritizes_recent_healthy_provider() -> None:
    module = load_melissa_module()

    class _Provider:
        def __init__(self, name):
            self.name = name

    engine = module.LLMEngine.__new__(module.LLMEngine)
    engine.providers = [_Provider("gemini_k1"), _Provider("gemini_k4"), _Provider("openrouter")]
    engine._failures = {"gemini_k1": 3, "gemini_k4": 0, "openrouter": 0}
    engine._last_success = {"gemini_k4": time.time(), "openrouter": time.time() - 30}

    ordered = [provider.name for provider in engine._ordered_providers("google/gemini-2.5-flash")]

    assert ordered[:3] == ["gemini_k4", "gemini_k1", "openrouter"]


def test_llm_engine_blocks_403_immediately() -> None:
    module = load_melissa_module()

    class _Error(Exception):
        def __init__(self):
            self.response = types.SimpleNamespace(status_code=403)
            super().__init__("403 forbidden")

    engine = module.LLMEngine.__new__(module.LLMEngine)
    engine._failures = {}
    engine._blocked_until = {}
    engine._blacklist_ttl = 60.0

    start = time.time()
    engine._register_failure("gemini_k3", _Error())

    assert engine._failures["gemini_k3"] == 1
    assert engine._blocked_until["gemini_k3"] >= start + 1700


def test_llm_engine_blocks_402_immediately() -> None:
    module = load_melissa_module()

    class _Error(Exception):
        def __init__(self):
            self.response = types.SimpleNamespace(status_code=402)
            super().__init__("402 payment required")

    engine = module.LLMEngine.__new__(module.LLMEngine)
    engine._failures = {}
    engine._blocked_until = {}
    engine._blacklist_ttl = 60.0

    start = time.time()
    engine._register_failure("openrouter", _Error())

    assert engine._failures["openrouter"] == 1
    assert engine._blocked_until["openrouter"] >= start + 1700


def test_config_collects_series_keys_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("TEST_CHAIN_KEY", "key1")
    monkeypatch.setenv("TEST_CHAIN_KEY_2", "key2")
    monkeypatch.setenv("TEST_CHAIN_KEYS", "key3,key4")

    module = load_melissa_module()

    assert module._collect_env_series("TEST_CHAIN_KEY") == ["key1", "key2", "key3", "key4"]
