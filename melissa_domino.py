from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any, Dict, List, Optional


OPENCLAW_WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")


def _normalize(text: str) -> str:
    normalized = (text or "").strip().lower()
    normalized = normalized.replace("0", "o")
    normalized = normalized.replace("¡", "").replace("¿", "")
    normalized = re.sub(r"[!?.,;:]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _compact_markdown(text: str, *, max_chars: int = 900) -> str:
    if not text:
        return ""
    pieces: List[str] = []
    size = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line in {"---", "EOF"}:
            continue
        if line.startswith("#"):
            continue
        line = re.sub(r"[*_`>]+", "", line).strip()
        if not line:
            continue
        pieces.append(line)
        size += len(line) + 1
        if size >= max_chars:
            break
    return " ".join(pieces).strip()


def _read_workspace_file(name: str, *, max_chars: int = 900) -> str:
    path = OPENCLAW_WORKSPACE / name
    if not path.exists():
        return ""
    try:
        return _compact_markdown(path.read_text(encoding="utf-8"), max_chars=max_chars)
    except Exception:
        return ""


def _sanitize_memory_markdown(text: str) -> str:
    raw = (text or "").strip()
    lowered = raw.lower()
    poison_markers = (
        "run your session startup sequence",
        "read the required files before responding",
        "do not mention internal steps",
        "conversation info (untrusted metadata)",
        "sender (untrusted metadata)",
        "current time:",
        "session key",
        "session id",
        "source: telegram",
        "new session started",
        "message_id",
        "sender_id",
    )
    if any(marker in lowered for marker in poison_markers):
        return ""
    return _compact_markdown(raw, max_chars=700)


def _soul_excerpt(text: str) -> str:
    compact = _compact_markdown(text or "", max_chars=900)
    if not compact:
        return ""
    preferred_markers = (
        "be genuinely helpful",
        "have opinions",
        "be resourceful before asking",
        "earn trust through competence",
        "not a corporate drone",
        "not a sycophant",
    )
    pieces: List[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", compact):
        lowered = sentence.lower()
        if any(marker in lowered for marker in preferred_markers):
            pieces.append(sentence.strip())
    if pieces:
        return " ".join(pieces)[:520].strip()
    return compact[:420].strip()


@lru_cache(maxsize=1)
def load_domino_sources() -> Dict[str, str]:
    latest_memory = ""
    memory_dir = OPENCLAW_WORKSPACE / "memory"
    if memory_dir.exists():
        latest_files = sorted(memory_dir.glob("*.md"))
        if latest_files:
            latest_memory = _sanitize_memory_markdown(
                latest_files[-1].read_text(encoding="utf-8")
            )
    return {
        "soul": _read_workspace_file("SOUL.md", max_chars=900),
        "identity": _read_workspace_file("IDENTITY.md", max_chars=400),
        "user": _read_workspace_file("USER.md", max_chars=500),
        "memory": latest_memory,
    }


def _history_block(history: List[Dict[str, Any]], limit: int = 6) -> str:
    rows: List[str] = []
    for item in history[-limit:]:
        role = "dueño" if item.get("role") == "user" else "melissa"
        content = str(item.get("content") or "").replace("|||", " | ").strip()
        if content:
            rows.append(f"{role}: {content}")
    return "\n".join(rows) if rows else "sin historial"


def _business_memory_block(business_name: str, business_ctx: str, found_online: bool) -> str:
    if not business_name:
        return "Aún no sabes cómo se llama el negocio."
    parts = [f"Ya sabes que el negocio es: {business_name}."]
    cleaned_ctx = (business_ctx or "").strip()
    if found_online and cleaned_ctx:
        compact = re.sub(r"\s+", " ", cleaned_ctx)[:600].strip()
        parts.append(f"Contexto útil encontrado: {compact}")
    elif cleaned_ctx:
        compact = re.sub(r"\s+", " ", cleaned_ctx)[:280].strip()
        parts.append(f"Contexto débil todavía: {compact}")
    else:
        parts.append("Todavía no hay contexto externo fiable; no inventes nada.")
    return " ".join(parts)


def demo_opening_tone_issues(text: str) -> List[str]:
    normalized = _normalize(text)
    issues: List[str] = []
    abstract_markers = (
        "de manera efectiva",
        "de manera mas efectiva",
        "de manera más precisa",
        "de manera precisa",
        "de manera mas precisa",
        "de la mejor manera",
        "relevante",
        "relevantes",
        "útiles para ti",
        "utiles para ti",
        "tipo de empresa",
        "quiero asegurarme",
        "asegurarme de que",
        "me permitirá",
        "me permitira",
        "entender mejor el contexto",
        "entender mejor cómo",
        "entender mejor como",
        "idea más clara",
        "idea mas clara",
        "mejor atención",
        "mejor atencion",
        "personalizada",
    )
    consultive_markers = (
        "gestion de tus mensajes",
        "gestión de tus mensajes",
        "puedo apoyarte",
        "puedo ayudarte",
        "estoy para ayudarte",
        "responder a las consultas",
        "responder consultas",
        "con el que estoy trabajando",
        "con el que estoy interactuando",
        "interactuando",
        "proceder con el trabajo",
        "para darte una mejor",
        "asi podre",
        "así podré",
        "empezar a trabajar",
        "optimizar",
        "areas de mejora",
        "áreas de mejora",
        "procesos",
        "soluciones",
    )
    scripted_markers = (
        "que bueno tenerte por aca",
        "qué bueno tenerte por acá",
        "retomamos desde donde lo dejamos",
        "te ubico rapido",
        "te ubico rápido",
        "seguimos con la demo",
    )
    if any(marker in normalized for marker in abstract_markers):
        issues.append("tono abstracto o marketinero")
    if any(marker in normalized for marker in consultive_markers):
        issues.append("tono consultivo o de onboarding")
    if any(marker in normalized for marker in scripted_markers):
        issues.append("continuidad prefabricada o libreto heredado")
    return issues


def _is_greeting(normalized: str) -> bool:
    return normalized in {
        "hola",
        "hola buenas",
        "hola melissa",
        "buenas",
        "buenas tardes",
        "buenos dias",
        "buenas noches",
        "hey",
        "holi",
        "que mas",
        "que tal",
        "hola otra vez",
    }


def _is_confused(normalized: str) -> bool:
    markers = (
        "a que te refieres",
        "que quieres decir",
        "no te entiendo",
        "explícamelo",
        "explicamelo",
        "para que",
        "para qué",
        "como asi",
        "cómo así",
        "hablame claro",
        "háblame claro",
        "bajalo a tierra",
        "bájalo a tierra",
        "en donde quedamos",
        "donde quedamos",
        "me ubicas",
        "me ubicas rapido",
        "me ubicas rápido",
        "que sigue",
        "qué sigue",
        "como arrancamos",
        "cómo arrancamos",
    )
    return any(marker in normalized for marker in markers)


def _is_identity_or_meta_probe(normalized: str) -> bool:
    markers = (
        "que eres",
        "qué eres",
        "quien eres",
        "quién eres",
        "como funcionas",
        "cómo funcionas",
        "que haces",
        "qué haces",
        "quiero probarte",
        "quiero una demo",
        "quiero demo",
        "tengo un negocio",
        "tengo una empresa",
        "como trabajas",
        "cómo trabajas",
        "lo llevas tu sola",
        "lo llevas tú sola",
        "recuerdas lo que te digo",
        "como recuerdas",
        "cómo recuerdas",
        "para que necesitas",
        "para qué necesitas",
        "en que quedamos",
        "en qué quedamos",
    )
    return any(marker in normalized for marker in markers)


def _is_reset_request(normalized: str) -> bool:
    markers = (
        "empezar de nuevo",
        "volver a empezar",
        "reset",
        "reiniciar",
        "ese no es mi negocio",
        "no es mi negocio",
        "cambiar negocio",
        "cambia negocio",
        "otro negocio",
    )
    return any(marker in normalized for marker in markers)


def _is_business_submission(normalized: str) -> bool:
    markers = (
        "mi negocio se llama",
        "nuestro negocio se llama",
        "mi empresa se llama",
        "nuestra empresa se llama",
        "el nombre de mi negocio es",
        "el nombre del negocio es",
        "la clinica se llama",
        "la clínica se llama",
        "se llama ",
        "negocio es ",
        "empresa es ",
    )
    return any(marker in normalized for marker in markers)


def should_route_demo_to_domino(
    *,
    user_text: str,
    business_name: str,
    history: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    # En demo, toda la conversación debe pasar por la misma capa de identidad
    # para no rebotar entre prompts legacy y respuestas de onboarding.
    return True


def _domino_stage(
    *,
    normalized: str,
    business_name: str,
    explain_name: bool,
    force_stage: Optional[str] = None,
) -> Dict[str, str]:
    if force_stage == "reset-demo":
        return {
            "stage": "reset-demo",
            "objective": "reiniciar la demo sin sonar a reset mecánico y volver a conseguir el nombre del negocio",
            "action": "confirma que arrancan de cero y pide de nuevo solo el nombre del negocio, sin formularios ni branding",
        }
    if force_stage == "bind-business":
        return {
            "stage": "bind-business",
            "objective": "mostrar que ya aterrizaste el negocio y mover al dueño a una simulación real",
            "action": "reacciona como alguien que acaba de ubicarse en el negocio, usa el contexto encontrado solo si es fiable y empuja a una prueba real de cliente",
        }
    if not business_name:
        if explain_name or _is_confused(normalized):
            return {
                "stage": "clarify-demo",
                "objective": "explicar para qué necesitas el nombre del negocio y conseguirlo sin sonar a formulario",
                "action": "baja la idea a tierra, explica tu función dentro del chat y pide una sola pieza de contexto: el nombre del negocio",
            }
        return {
            "stage": "enter-demo",
            "objective": "ubicar a la persona en la demo y conseguir el nombre del negocio con naturalidad",
            "action": "explica desde adentro del trabajo qué harías aquí y pide el nombre del negocio para aterrizar la prueba",
        }
    if _is_reset_request(normalized):
        return {
            "stage": "reset-demo",
            "objective": "arrancar de cero sin arrastrar negocio previo ni sonar a sistema",
            "action": "di que arrancan otra vez y pide el nombre del negocio de forma directa y limpia",
        }
    if _is_business_submission(normalized):
        return {
            "stage": "bind-business",
            "objective": "activar el contexto del negocio recién entregado y llevar la demo a simulación real",
            "action": "deja claro que ya te ubicastes con ese negocio y pide que te hablen como cliente real",
        }
    if _is_greeting(normalized) or _is_confused(normalized) or _is_identity_or_meta_probe(normalized):
        return {
            "stage": "re-ground",
            "objective": "retomar desde el negocio ya conocido y llevar al dueño a una simulación real",
            "action": "no vuelvas a presentarte; si pregunta por qué querías el nombre o qué haces, responde eso primero y luego empuja a que te hablen como cliente real",
        }
    return {
        "stage": "simulate",
        "objective": "responder como si ya llevaras el WhatsApp del negocio real",
        "action": "responde con criterio operativo, cuida el contexto y haz avanzar la conversación sin inventar ni volver meta la demo",
    }


def build_demo_domino_payload(
    *,
    user_text: str,
    history: Optional[List[Dict[str, Any]]],
    business_name: str,
    business_ctx: str,
    found_online: bool,
    explain_name: bool = False,
    force_stage: Optional[str] = None,
) -> Dict[str, str]:
    normalized = _normalize(user_text)
    stage_info = _domino_stage(
        normalized=normalized,
        business_name=business_name,
        explain_name=explain_name,
        force_stage=force_stage,
    )
    sources = load_domino_sources()
    history_block = _history_block(list(history or []))
    business_memory = _business_memory_block(business_name, business_ctx, found_online)

    soul = (
        "Sé útil de verdad, no performativa. Ten criterio. Primero entiende y luego responde. "
        "No rellenes ni suenes a pitch."
    )
    soul_seed = _soul_excerpt(sources["soul"])
    if soul_seed:
        soul += f" Base OpenClaw: {soul_seed}"

    owner = (
        "Tu dueño es Santiago y esta prueba le sirve para decidir si te confiaría chats reales. "
        "No lo menciones. No hables como consultora, software ni recepcionista. "
        "Responde como alguien que ya se hizo cargo del chat y sabe moverse ahí adentro."
    )

    identity = (
        f"Eres Melissa dentro del WhatsApp de {business_name} para esta demo."
        if business_name
        else "Eres Melissa en demo privada. Todavía no puedes asumir un negocio concreto."
    )

    memory = business_memory
    if sources["memory"]:
        memory += f" Memoria OpenClaw útil: {sources['memory']}"

    stage_rules_map = {
        "enter-demo": """
- no abras con un saludo adornado o de recepcionista
- ubica rápido qué harías en ese chat y pide solo el nombre del negocio
- no uses frases vacías de seguimiento ni continuidad automática
- usa verbos cotidianos como llevar, responder, mover o atender
- no uses apoyar, gestionar, proceder, permitir, asegurar ni comprender mejor
- responde en 2 o 3 burbujas
- deja completas las ideas; no cierres en una frase colgada
- deja claro qué haces dentro de ese chat
- deja claro para qué te sirve saber el nombre del negocio
- termina pidiendo el nombre del negocio de forma directa
""",
        "clarify-demo": """
- explica simple para qué te sirve el nombre del negocio
- no suenes a consultora, onboarding ni software
- no digas que vas a "aterrizar el contexto"; dilo como alguien dentro del chat
- evita apoyarte en lenguaje abstracto o profesionalizante
- responde en 2 o 3 burbujas
- deja completas las ideas; no cierres en una frase colgada
- baja la idea a tierra
- explica tu función dentro del WhatsApp del negocio
- termina pidiendo el nombre del negocio sin rodeos
""",
        "bind-business": """
- reacciona como alguien que ya cayó en el negocio correcto
- si encontraste algo útil, úsalo sin narrar el proceso ni decir "encontré contexto"
- después de ubicarte, invita a seguir la conversación desde el chat real
- responde en 2 o 3 burbujas
- deja completas las ideas; no cierres en una frase colgada
- deja claro que ya te ubicaste con ese negocio
- deja claro que ya tienes el contexto del negocio, sin inventar
- termina invitando a que te hablen como un cliente real
- no digas que ya quedaste al frente ni uses lenguaje de takeover
""",
        "reset-demo": """
- no hables de reset, sistema ni memoria
- suena como alguien que arrancó limpio la conversación
- pide otra vez solo el nombre del negocio
""",
        "re-ground": """
- no digas "qué bueno tenerte por acá", "retomamos", "te ubico rápido" ni nada parecido
- no vuelvas a presentarte
- vuelve a poner el chat en marcha desde el negocio que ya conoces
- si la persona pregunta por qué necesitabas el nombre, responde eso sin volver a pedirlo como si no lo supieras
- si la persona se va por quién te hizo, si aceptas audios o si esto es una estafa, responde eso de frente y luego vuelve al negocio ya conocido
""",
        "simulate": """
- deja de hablar de demo, prueba, simulación o cliente real
- no menciones negocio, contexto, branding ni el sistema
- responde como si ya fueras la persona que lleva ese WhatsApp y punto
""",
    }
    stage_rules = stage_rules_map.get(stage_info["stage"], "").strip()

    system = f"""ANTES DE ESCRIBIR, RECORRE ESTA CADENA EN ORDEN Y DEJA QUE CADA CAPA EMPUJE LA SIGUIENTE.

1. ALMA
{soul}

2. AMO / DUEÑO
{owner}

3. MEMORIA / ESTADO
{memory}

4. IDENTIDAD ACTIVA
{identity}

5. ACCIÓN DE ESTE TURNO
ETAPA: {stage_info['stage']}
OBJETIVO: {stage_info['objective']}
ACCIÓN: {stage_info['action']}

REGLAS ESPECÍFICAS DE ESTA ETAPA
{stage_rules}

REGLAS DE SALIDA
- decide tú el wording; no recites plantillas
- no menciones Clínica Las Américas ni branding heredado
- no te describas como bot, software, recepcionista virtual o producto
- no uses saludos corporativos, frases de acompañamiento vacías ni continuidad automática prefabricada
- no uses lenguaje de consultor, onboarding o preventa B2B
- no hables de tareas, procesos, optimización, pendientes, áreas de mejora ni trabajo interno
- no uses frases como "puedo apoyarte", "de manera efectiva", "relevante", "útil para ti", "tipo de empresa", "gestión de mensajes" o "quiero asegurarme"
- evita palabras abstractas como contexto, colaborar, esfuerzos, efectiva, personalizada o relevante
- si ya conoces el negocio, no vuelvas a pedirlo
- si ya conoces el negocio, no te presentes otra vez ni digas que eres "del equipo" de nadie
- si no conoces el negocio, pide solo esa pieza de contexto y nada más
- si el contexto externo es débil, no inventes precio, disponibilidad, stock ni reputación
- responde en 2 o 3 burbujas separadas por |||
- una idea accionable por burbuja
- cada burbuja debe ser una idea completa; no dejes frases truncas ni subordinadas abiertas
- tono humano, directo, ubicado, colombiano neutro, sin emojis

EJEMPLOS DE DECISIÓN
- si dicen "me mandaron tu número y no entiendo qué haces", explicas claro que respondes clientes, filtras interesados, orientas y ayudas con citas; después pides el nombre del negocio
- si dicen "para qué quieres el nombre de mi negocio", explicas que lo necesitas para sonar como el chat real de ese negocio, no para llenar formularios
- si ya te dijeron el negocio y luego preguntan "para qué querías el nombre", respondes eso sin tratar la pregunta como si fuera un nombre nuevo
- si preguntan "quién te hizo", dices BlackBoss, Santiago Rubio y 3124348669
- si preguntan por audios, PDFs o documentos, confirmas que sí, cuando el canal lo permite, puedes transcribir, leer y usar eso
- si sospechan estafa, respondes directo y breve; no te pones defensiva ni repites el pitch
"""

    user_block = (
        f"historial reciente:\n{history_block}\n\n"
        f"mensaje actual del dueño:\n{user_text}"
    )

    return {
        "stage": stage_info["stage"],
        "objective": stage_info["objective"],
        "action": stage_info["action"],
        "system": system,
        "user": user_block,
    }
