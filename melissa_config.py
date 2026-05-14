#!/usr/bin/env python3
"""
melissa_config.py — All constants, templates and string literals from melissa.py
Extracted for Phase 3 split.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Set, Tuple

_MELISSA_HOME = os.getenv("MELISSA_HOME", str(Path.home() / ".melissa"))


class Config:
    """Configuración centralizada con validación."""

    TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN", "")
    GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY",   "")
    GEMINI_API_KEY_2   = os.getenv("GEMINI_API_KEY_2", "")
    GEMINI_API_KEY_3   = os.getenv("GEMINI_API_KEY_3", "")
    GEMINI_API_KEY_4   = os.getenv("GEMINI_API_KEY_4", "")
    GEMINI_API_KEY_5   = os.getenv("GEMINI_API_KEY_5", "")
    GEMINI_API_KEY_6   = os.getenv("GEMINI_API_KEY_6", "")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY",  "")
    BRAVE_API_KEY      = os.getenv("BRAVE_API_KEY",      "")
    APIFY_API_KEY      = os.getenv("APIFY_API_KEY",      "")
    SERP_API_KEY       = os.getenv("SERP_API_KEY",        "")
    CALENDLY_LINK      = os.getenv("CALENDLY_LINK",       "")
    GCAL_ACCESS_TOKEN  = os.getenv("GCAL_ACCESS_TOKEN",    "")
    GCAL_REFRESH_TOKEN = os.getenv("GCAL_REFRESH_TOKEN",   "")
    GCAL_CLIENT_ID     = os.getenv("GCAL_CLIENT_ID",      "")
    GCAL_CLIENT_SECRET = os.getenv("GCAL_CLIENT_SECRET",  "")
    GCAL_CALENDAR_ID   = os.getenv("GCAL_CALENDAR_ID",    "primary")
    META_APP_ID        = os.getenv("META_APP_ID",          "")
    META_APP_SECRET    = os.getenv("META_APP_SECRET",     "")
    NOVA_URL           = os.getenv("NOVA_URL", "http://localhost:9003")
    NOVA_TOKEN         = os.getenv("NOVA_TOKEN",   "")
    NOVA_API_KEY       = os.getenv("NOVA_API_KEY", "")
    NOVA_ENABLED       = os.getenv("NOVA_ENABLED", "false").lower() == "true"
    WEBHOOK_SECRET     = os.getenv("WEBHOOK_SECRET", "melissa_ultra_5")
    BASE_URL           = os.getenv("BASE_URL",           "")
    TELEGRAM_SHARED     = os.getenv("TELEGRAM_SHARED", "false").lower() == "true"
    TELEGRAM_SHARED_ROUTER = os.getenv("TELEGRAM_SHARED_ROUTER", "false").lower() == "true"
    TELEGRAM_SHARED_SECRET = os.getenv("TELEGRAM_SHARED_SECRET", "melissa_shared_telegram")
    TELEGRAM_DEFAULT_INSTANCE = os.getenv("TELEGRAM_DEFAULT_INSTANCE", "").strip()
    TELEGRAM_SHARED_ROUTES_PATH = os.getenv(
        "TELEGRAM_SHARED_ROUTES_PATH",
        str(Path(_MELISSA_HOME) / "shared_telegram_routes.json"),
    )
    TELEGRAM_SHARED_INSTANCES_DIR = os.getenv(
        "TELEGRAM_SHARED_INSTANCES_DIR",
        str(Path(_MELISSA_HOME) / "instances"),
    )
    PLATFORM           = os.getenv("PLATFORM", "telegram")
    WHATSAPP_BRIDGE_URL = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3000")
    SECTOR             = os.getenv("SECTOR", "otro")
    WA_PHONE_ID        = os.getenv("WA_PHONE_ID", "")
    WA_ACCESS_TOKEN    = os.getenv("WA_ACCESS_TOKEN", "")
    WA_VERIFY_TOKEN    = os.getenv("WA_VERIFY_TOKEN", "")
    EVOLUTION_URL      = os.getenv("EVOLUTION_URL",       "")
    EVOLUTION_API_KEY  = os.getenv("EVOLUTION_API_KEY",   "")
    EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE",  "melissa")
    MASTER_API_KEY     = os.getenv("MASTER_API_KEY",     "")
    N8N_WEBHOOK_URL   = os.getenv("N8N_WEBHOOK_URL",     "")
    TOKEN_EXPIRY_HOURS = int(os.getenv("TOKEN_EXPIRY_HOURS", "72"))
    DEMO_MODE          = os.getenv("DEMO_MODE", "false").lower() == "true"
    DEMO_BUSINESS_NAME = os.getenv("DEMO_BUSINESS_NAME", "tu negocio")
    DEMO_SECTOR        = os.getenv("DEMO_SECTOR", "estetica")
    DEMO_SESSION_TTL   = int(os.getenv("DEMO_SESSION_TTL", "1800"))
    GREETING_ONLY_IDLE_SECONDS = int(os.getenv("GREETING_ONLY_IDLE_SECONDS", "300"))
    V8_ACTIVE_MODEL_REASONING = os.getenv("V8_ACTIVE_MODEL_REASONING", "")
    V8_ACTIVE_MODEL_FAST      = os.getenv("V8_ACTIVE_MODEL_FAST",      "")
    V8_ACTIVE_MODEL_LITE      = os.getenv("V8_ACTIVE_MODEL_LITE",      "")
    V8_QUALITY_THRESHOLD  = float(os.getenv("V8_QUALITY_THRESHOLD", "0.72"))
    V8_MAX_RETRIES        = int(os.getenv("V8_MAX_RETRIES", "3"))
    MELISSA_COMPACT_PROMPT = os.getenv("MELISSA_COMPACT_PROMPT", "true").lower() in ("1", "true", "yes", "on")
    MELISSA_CONTEXT_RECENT_MESSAGES = int(os.getenv("MELISSA_CONTEXT_RECENT_MESSAGES", "12"))
    MELISSA_CORE_ENABLED = os.getenv("MELISSA_CORE_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    MELISSA_CORE_PERSONAS_DIR = os.getenv(
        "MELISSA_CORE_PERSONAS_DIR",
        str(Path(__file__).resolve().parent / "personas" / "melissa" / "base"),
    )
    V8_FILTER_LEVEL       = int(os.getenv("V8_FILTER_LEVEL", "2"))
    DB_PATH            = os.getenv("DB_PATH", "/home/ubuntu/melissa/melissa_ultra.db")
    VECTOR_DB_PATH     = os.getenv("VECTOR_DB_PATH", "/home/ubuntu/melissa/vectors.db")
    LLM_MODELS = {
        "reasoning": os.getenv("LLM_REASONING", "google/gemini-2.5-pro"),
        "fast": os.getenv("LLM_FAST", "google/gemini-2.5-flash"),
        "lite": os.getenv("LLM_LITE", "google/gemini-2.5-flash-lite"),
        "embedding": os.getenv("LLM_EMBEDDING", "openai/text-embedding-3-small"),
    }
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "openai/whisper-large-v3")
    BUFFER_WAIT_MIN    = int(os.getenv("BUFFER_WAIT_MIN", "25"))
    BUFFER_WAIT_MAX    = int(os.getenv("BUFFER_WAIT_MAX", "45"))
    BUBBLE_PAUSE_MIN   = float(os.getenv("BUBBLE_PAUSE_MIN", "1.2"))
    BUBBLE_PAUSE_MAX   = float(os.getenv("BUBBLE_PAUSE_MAX", "3.0"))
    BRAND_ASSETS_BASE_DIR = os.getenv(
        "BRAND_ASSETS_BASE_DIR",
        "/home/ubuntu/melissa/brand-assets",
    )
    SELF_IMPROVE_INTERVAL = int(os.getenv("SELF_IMPROVE_INTERVAL", "3600"))
    LEARNING_RATE         = float(os.getenv("LEARNING_RATE", "0.1"))
    MAX_CONTEXT_MESSAGES = int(os.getenv("MAX_CONTEXT", "50"))
    MAX_MEMORY_ITEMS     = int(os.getenv("MAX_MEMORY", "1000"))

    @classmethod
    def validate(cls) -> List[str]:
        errors = []
        if not cls.TELEGRAM_TOKEN:
            errors.append("TELEGRAM_TOKEN requerido")
        if not cls.OPENROUTER_API_KEY and not cls.GEMINI_API_KEY:
            errors.append("Se requiere al menos OPENROUTER_API_KEY o GEMINI_API_KEY")
        return errors


DEMO_COMMANDS: Dict[str, str] = {
    "/formal":"/formal", "/amigable":"/amigable", "/luxury":"/luxury",
    "/directa":"/directa", "/energica":"/energica", "/empatica":"/empatica",
    "/experta":"/experta", "/juvenil":"/juvenil",
    "/objecion":"/objecion", "/cita":"/cita", "/stats":"/stats",
    "/prueba":"/prueba", "/cierre":"/cierre", "/bot":"/bot",
    "/memoria":"/memoria", "/2am":"/2am", "/competencia":"/competencia",
    "/precio":"/precio", "/siguiente":"/siguiente",
}

DEMO_TRICKS_ORDER: List[Tuple[str, str]] = [
    ("/objecion",   "ver cómo manejo objeciones en vivo"),
    ("/cita",       "ver cómo agendo una cita completa"),
    ("/luxury",     "activar personalidad premium"),
    ("/empatica",   "cambiar a modo empático y de escucha"),
    ("/stats",      "ver el impacto en números reales"),
    ("/prueba",     "lanzarme el mensaje más difícil que tengas"),
    ("/cierre",     "ver cómo cierro una venta"),
    ("/directa",    "activar modo al grano sin rodeos"),
    ("/menu",       "ver modo bot con emojis y menú numerado"),
    ("/2am",        "verme responder a las 2 de la madrugada"),
    ("/memoria",    "ver qué recuerdo de esta conversación"),
    ("/experta",    "cambiar a modo técnico y preciso"),
    ("/modelo",     "cambiar el modelo de IA que me impulsa"),
]

DEMO_CMD_ALIASES: Dict[str, str] = {
    "formal":"formal","amigable":"amigable","luxury":"luxury","lujo":"luxury",
    "directa":"directa","energica":"energica","enérgica":"energica",
    "empatica":"empatica","empática":"empatica","experta":"experta",
    "juvenil":"juvenil","joven":"juvenil","profesional":"formal","objecion":"objecion","objeción":"objecion",
    "cita":"cita","agendar":"cita","stats":"stats","estadisticas":"stats",
    "prueba":"prueba","reto":"prueba","cierre":"cierre","bot":"bot",
    "memoria":"memoria","recuerdas":"memoria","2am":"2am","de noche":"2am",
    "competencia":"competencia","precio":"precio","caro":"precio",
    "siguiente":"siguiente","que mas":"siguiente","qué más":"siguiente",
    "menu":"menu_bot","menú":"menu_bot","modo bot":"menu_bot","bot menu":"menu_bot",
    "list":"list","lista":"list","comandos":"list","ayuda":"list","help":"list",
    "qué puedes hacer":"list","que puedes hacer":"list",
    "emojis":"emojis_on","con emojis":"emojis_on","activa emojis":"emojis_on",
    "sin emojis":"emojis_off","quita emojis":"emojis_off","desactiva emojis":"emojis_off",
    "modelo":"modelo","model":"modelo","cambiar modelo":"modelo",
}

MODEL_CATALOG: Dict[str, Tuple[str, str, str]] = {
    "claude-opus":   ("anthropic/claude-opus-4",          "reasoning", "Más inteligente. Más caro."),
    "claude-sonnet": ("anthropic/claude-sonnet-4",        "reasoning", "Balance inteligencia/costo."),
    "claude-haiku":  ("anthropic/claude-haiku-3-5",       "fast",      "Rapidísimo y económico."),
    "gemini-pro":    ("google/gemini-2.5-pro",            "reasoning", "Google Pro."),
    "gemini-flash":  ("google/gemini-2.5-flash",          "fast",      "Velocidad + calidad."),
    "gemini-lite":   ("google/gemini-2.5-flash-lite",     "lite",      "El más económico."),
    "llama-70b":     ("meta-llama/llama-3.3-70b-instruct","fast",      "Open source, excelente español."),
    "llama-8b":      ("meta-llama/llama-3.1-8b-instruct", "lite",      "Ultrarrápido, básico."),
    "gpt4o":         ("openai/gpt-4o",                    "reasoning", "OpenAI flagship."),
    "gpt4o-mini":   ("openai/gpt-4o-mini",               "fast",      "OpenAI económico."),
    "mistral-large": ("mistralai/mistral-large",          "reasoning", "Europeo, buen español."),
    "mistral-small": ("mistralai/mistral-small",          "fast",      "Rápido y asequible."),
}

INTERNAL_PHRASES_TO_BLOCK: List[str] = [
    "todavía no tengo este chat enlazado",
    "ya recibí tu mensaje",
    "no tengo este chat",
    "[error",
    "[internal",
    "{",
]

AUDIO_ERROR_MSG = "Recibí tu audio pero no lo pude procesar. ¿Puedes escribirlo?"
JSON_ERROR_MSG = "Entendido, déjame verificar eso."
UNKNOWN_CMD_MSG = "Comando no reconocido. Escribe /help para ver los disponibles."

DEMO_HELP_FULL = (
    "esto es lo que puedo mostrarte 👇\n\n"
    "🎭 Personalidades: /formal · /amigable · /luxury · /directa · /empatica · /experta · /juvenil\n\n"
    "💬 Situaciones reales:\n"
    "objecion — cliente difícil\n"
    "cita — agendamiento completo\n"
    "cierre — técnica de cierre\n"
    "competencia — ya fui a otro lado\n"
    "precio — está muy caro\n"
    "prueba — mándame el más difícil\n"
    "bot — soy un bot?\n"
    "2am — respuesta a las 2am\n\n"
    "📊 Demo y datos:\n"
    "stats — impacto en números\n"
    "memoria — qué recuerdo de ti\n"
    "menu — modo bot con emojis\n\n"
    "⚙️ Ajustes:\n"
    "usa emojis / sin emojis\n"
    "siguiente — próximo truco\n"
    "/modelo — cambiar el modelo\n"
    "reset — empezar de nuevo\n\n"
    "escribe sin slash para activar"
)