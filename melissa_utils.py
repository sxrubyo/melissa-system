from __future__ import annotations
import hashlib
import json
import secrets
import re
from typing import Any, Dict, List, Optional

ACTIVATION_PREFIX = "ACTV-"
INVITE_PREFIX = "JINV-"

def is_activation_token(text: str) -> bool:
    """Detecta si el mensaje es un token de activacion."""
    t = text.strip().upper()
    return t.startswith(ACTIVATION_PREFIX) and len(t) >= 30

def is_invite_token(text: str) -> bool:
    """Detecta si el mensaje es un token de invitacion."""
    t = text.strip().upper()
    return t.startswith(INVITE_PREFIX) and len(t) >= 15

def hash_password(password: str) -> str:
    """Hash de contrasena con PBKDF2 + salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        260_000
    ).hex()
    return f"{salt}:{key}"

def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica contrasena contra hash almacenado."""
    try:
        salt, key = stored_hash.split(":", 1)
        test = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            260_000
        ).hex()
        return test == key
    except Exception:
        return False

def _parse_admin_ids(raw) -> list:
    """Parsea admin_chat_ids de forma segura."""
    if not raw: return []
    if isinstance(raw, list): return [str(i) for i in raw]
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            if isinstance(data, list): return [str(i) for i in data]
            return [str(data)]
        except Exception:
            return [i.strip() for i in raw.split(",") if i.strip()]
    return []

def extract_model_request_from_text(text: str) -> Optional[str]:
    """Extrae solicitud de cambio de modelo del lenguaje natural."""
    t = text.lower().strip()
    if not t.startswith("/modelo"):
        if "cambia el modelo a" in t: return t.split("cambia el modelo a")[-1].strip()
        if "usa el modelo" in t: return t.split("usa el modelo")[-1].strip()
        return None
    parts = t.split()
    return parts[1] if len(parts) > 1 else "reset"

def normalize_model_arg(arg: str) -> str:
    """Normaliza el nombre del modelo solicitado."""
    m = arg.lower().strip()
    if m in ("flash", "gemini"): return "google/gemini-2.5-flash"
    if m in ("pro", "sonnet"): return "anthropic/claude-3-5-sonnet"
    if m in ("fast", "haiku"): return "anthropic/claude-3-haiku"
    return m
