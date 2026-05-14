from __future__ import annotations

import re
from typing import Any, Callable, Dict, Optional


def _normalize_conv_text(text: str) -> str:
    text = (text or "").lower()
    replacements = str.maketrans({
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n",
    })
    text = text.translate(replacements)
    text = re.sub(r"[^a-z0-9@\+\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_GREETING_SIGNAL_TOKENS = {
    "hola", "buenas", "buenos", "dias", "tardes", "noches",
    "hey", "holi", "ey", "saludos",
}
_GREETING_FILLER_TOKENS = {
    "que", "tal", "como", "estas", "esta", "todo", "bien", "mas", "pues",
    "holaa", "holaaa", "buena", "buen", "va",
}


def _is_greeting_only(text: str) -> bool:
    norm = _normalize_conv_text(text)
    if not norm:
        return False
    tokens = norm.split()
    if not tokens or len(tokens) > 7:
        return False
    if not any(tok in _GREETING_SIGNAL_TOKENS for tok in tokens):
        return False
    return all(tok in _GREETING_SIGNAL_TOKENS or tok in _GREETING_FILLER_TOKENS for tok in tokens)


def _strip_leading_greeting(text: str) -> str:
    cleaned = re.sub(
        r"^(?:hola(?:\s+buenas|\s+que\s+tal)?|holaa+|buenas(?:\s+tardes|\s+noches)?|buenos\s+dias|hey|holi|ey|saludos)[,!. ]*",
        "",
        (text or "").strip(),
        flags=re.IGNORECASE,
    ).strip()
    return cleaned.lstrip(",. ").strip()


def _first_contact_intro(clinic: Dict[str, Any], agent_name: str = "Melissa") -> str:
    clinic_name = (clinic.get("name") or "").strip()
    if clinic_name:
        return f"Hola! Soy {agent_name} de {clinic_name}."
    return f"Hola! Soy {agent_name}."


def _first_contact_welcome_line(clinic: Dict[str, Any], user_msg: str) -> str:
    clinic_name = (clinic.get("name") or "").strip()
    normalized = _normalize_conv_text(user_msg or "")
    if "buenas tardes" in normalized:
        opening = "Hola, buenas tardes"
    elif "buenos dias" in normalized:
        opening = "Hola, buenos días"
    elif "buenas noches" in normalized:
        opening = "Hola, buenas noches"
    elif "buenas" in normalized:
        opening = "Hola, buenas"
    else:
        opening = "Hola"
    
    if clinic_name:
        return f"{opening}! Bienvenido a {clinic_name}."
    return f"{opening}! Cómo estás?"


def _first_contact_identity_line(clinic: Dict[str, Any], agent_name: str = "Melissa") -> str:
    clinic_name = (clinic.get("name") or "").strip()
    if clinic_name:
        return f"Soy {agent_name}, me encargo de la recepción en {clinic_name}."
    return f"Soy {agent_name}, estoy aquí para ayudarte."


def _first_contact_question_line() -> str:
    return "Cuéntame, qué necesitas?"


def _first_contact_followup(clinic: Dict[str, Any]) -> str:
    services = clinic.get("services") if isinstance(clinic.get("services"), list) else []
    if services:
        lead_services = ", ".join(str(service).strip() for service in services[:3] if str(service).strip())
        if lead_services:
            return (
                f"Te puedo ayudar con citas, precios o info de {lead_services}. "
                "Qué te gustaría saber?"
            )
    return "Te puedo ayudar con citas, horarios o lo que necesites. Qué tienes en mente?"


def _clean_first_contact_part(text: str) -> str:
    part = _strip_leading_greeting(text)
    part = re.sub(
        r"^(melissa\s+por\s+ac[aá]\s*,?\s*del\s+equipo\s+de\s+[^.?!]+[.?!]?\s*)",
        "",
        part,
        flags=re.IGNORECASE,
    ).strip()
    part = re.sub(r"^(soy\s+melissa[^.?!]*[.?!]?\s*)", "", part, flags=re.IGNORECASE).strip()
    part = re.sub(r"^(te\s+habla\s+melissa[^.?!]*[.?!]?\s*)", "", part, flags=re.IGNORECASE).strip()
    return part


_ADMIN_CONVERSATION_ORDINALS = {
    "1": 1,
    "uno": 1,
    "primero": 1,
    "primera": 1,
    "2": 2,
    "dos": 2,
    "segundo": 2,
    "segunda": 2,
    "3": 3,
    "tres": 3,
    "tercero": 3,
    "tercera": 3,
    "4": 4,
    "cuatro": 4,
    "cuarto": 4,
    "cuarta": 4,
    "5": 5,
    "cinco": 5,
    "quinto": 5,
    "quinta": 5,
    "6": 6,
    "seis": 6,
    "sexto": 6,
    "sexta": 6,
}


def _wants_recent_conversation_browser(text: str) -> bool:
    normalized = _normalize_conv_text(text)
    if not normalized:
        return False
    has_recent = any(
        token in normalized
        for token in ("ultimas", "ultimos", "recientes", "conversaciones", "chats", "mensajes")
    )
    has_subject = any(
        token in normalized
        for token in ("convers", "chat", "paciente", "persona", "cliente")
    )
    return has_recent and has_subject


def _extract_conversation_selection(text: str) -> Optional[int]:
    normalized = _normalize_conv_text(text)
    if not normalized:
        return None
    match = re.search(r"\b(?:ver|chat|conversacion|conversación)\s+(\d{1,2})\b", normalized)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(?:conversacion|conversación|chat)\s+numero\s+(\d{1,2})\b", normalized)
    if match:
        return int(match.group(1))
    for token, idx in _ADMIN_CONVERSATION_ORDINALS.items():
        if re.search(
            rf"\b(?:ver|mostrar|muestrame|muéstrame|ensename|enséñame|conversacion|conversación|chat)?\s*{re.escape(token)}\b",
            normalized,
        ):
            return idx
    return None


def _wants_all_messages(text: str) -> bool:
    normalized = _normalize_conv_text(text)
    return any(
        phrase in normalized
        for phrase in (
            "ver todo",
            "todos los mensajes",
            "toda la conversacion",
            "toda la conversación",
            "completa",
            "completo",
        )
    )


def _is_low_quality_first_contact_part(
    text: str,
    *,
    is_fragmented: Optional[Callable[[str], bool]] = None,
) -> bool:
    current = (text or "").strip()
    if not current:
        return True
    normalized = _normalize_conv_text(current)
    if not normalized:
        return True
    if is_fragmented and is_fragmented(current):
        return True
    if len(normalized.split()) <= 2:
        return True
    if any(
        marker in normalized
        for marker in (
            "soy melissa",
            "te habla melissa",
            "asistente virtual",
            "recepcionista virtual",
            "tu hoy",
            "hoy",
        )
    ):
        return True
    return normalized in {"hola", "hoy", "tu hoy", "soy melissa tu hoy"}


def _normalize_first_contact_response(
    response: str,
    clinic: Dict[str, Any],
    user_msg: str,
    agent_name: str = "Melissa",
    *,
    is_fragmented: Optional[Callable[[str], bool]] = None,
) -> str:
    intro = _first_contact_intro(clinic, agent_name=agent_name)
    parts = [part.strip() for part in (response or "").split("|||") if part.strip()]
    parts = [_clean_first_contact_part(part) for part in parts]
    parts = [part for part in parts if part]
    intro_norm = _normalize_conv_text(intro)
    parts = [part for part in parts if _normalize_conv_text(part) != intro_norm]

    if _is_greeting_only(user_msg):
        followup = next(
            (
                part
                for part in parts
                if not _is_low_quality_first_contact_part(part, is_fragmented=is_fragmented)
            ),
            "",
        )
        if not followup:
            followup = _first_contact_followup(clinic)
        return " ||| ".join([intro, followup][:2])

    if parts and "soy melissa" in _normalize_conv_text(parts[0]) and not _is_low_quality_first_contact_part(
        parts[0],
        is_fragmented=is_fragmented,
    ):
        return " ||| ".join(parts[:3])

    filtered_parts = [
        part
        for part in parts
        if not _is_low_quality_first_contact_part(part, is_fragmented=is_fragmented)
    ]
    if not filtered_parts:
        filtered_parts = [_first_contact_followup(clinic)]
    return " ||| ".join(([intro] + filtered_parts)[:3])


__all__ = [
    "_clean_first_contact_part",
    "_extract_conversation_selection",
    "_first_contact_followup",
    "_first_contact_identity_line",
    "_first_contact_intro",
    "_first_contact_question_line",
    "_first_contact_welcome_line",
    "_is_greeting_only",
    "_is_low_quality_first_contact_part",
    "_normalize_conv_text",
    "_normalize_first_contact_response",
    "_strip_leading_greeting",
    "_wants_all_messages",
    "_wants_recent_conversation_browser",
]
