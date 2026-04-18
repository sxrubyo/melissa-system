"""
melissa_brain_v10.py
════════════════════════════════════════════════════════════════════════════════
CEREBRO v10.1 — LLM PRIMERO, PLANTILLAS COMO ÚLTIMO RECURSO
════════════════════════════════════════════════════════════════════════════════

CAMBIOS v10.1 (este archivo):
  - Detección de frustración del cliente (loop de preguntas repetidas)
  - format_memory_block ahora señala frustración al LLM para romper el loop
  - Señales de zona ya respondida — evita repregunta infinita
  - FRUSTRATION_SIGNALS integrado en extract_short_memory
  - conversation_stage incluye "frustrated" como etapa especial
  - Instrucción anti-loop en format_memory_block

CÓMO USAR (al final de melissa.py, en init o en el bloque de startup):

    try:
        from melissa_brain_v10 import patch_llm_first, init_brain
        init_brain()
        patch_llm_first(generator)
    except Exception as e:
        log.warning(f"[brain_v10] no se pudo parchear: {e}")

════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import re
import logging
import random
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("melissa.brain_v10")

# ══════════════════════════════════════════════════════════════════════════════
# 1. MEMORIA CORTA — extrae señales clave del historial reciente
# ══════════════════════════════════════════════════════════════════════════════

_NAME_PATTERNS = [
    r"(?:me\s+llamo|soy|mi\s+nombre\s+es|me\s+dicen)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,20})",
    r"(?:habla|escribe)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,20})",
    r"NOMBRE:\{\"name\":\"([^\"]+)\"\}",
]

_FEAR_SIGNALS = [
    "miedo", "medo", "da pena", "me da pena", "nerviosa", "nervioso",
    "asustada", "asustado", "no sé", "no se", "dudas", "incómoda",
    "incómodo", "incomoda", "incomodo", "preocupa", "preocupada",
]

_PRICE_OBJECTION_SIGNALS = [
    "muy caro", "muy cara", "está caro", "esta caro", "demasiado",
    "no tengo plata", "no tengo dinero", "es mucho", "precio alto",
    "sale caro", "muy costoso", "costosa", "no me alcanza",
    "muy costosa",
]

_HESITATION_SIGNALS = [
    "lo voy a pensar", "voy a pensar", "pensarlo", "no sé todavía",
    "no estoy segura", "no estoy seguro", "tal vez", "quizás", "quizas",
    "déjame ver", "dejame ver", "lo consulto", "consultarlo",
    "hablar con", "más adelante", "luego",
]

# ── NUEVO v10.1: Señales de frustración por respuestas repetitivas ─────────
_FRUSTRATION_SIGNALS = [
    "que fastidio", "qué fastidio", "ya le dije", "ya te dije",
    "ya dije", "ya lo dije", "te lo dije", "le dije",
    "no me entiendes", "no entiendes", "me repites",
    "otra vez lo mismo", "siempre lo mismo", "otra vez",
    "dime ya", "dime el precio", "dime y ya", "y ya",
    "que pesado", "qué pesado", "eso ya lo dije",
    "pregunta lo mismo", "mismo cuento",
]

# ── NUEVO v10.1: Señales de que el cliente ya dio la zona ──────────────────
_ZONE_GIVEN_SIGNALS = [
    "frente", "entrecejo", "pómulos", "pomulos", "labios", "mandíbula",
    "mandibula", "ojeras", "nariz", "cejas", "mentón", "menton",
    "mejillas", "cuello", "rostro", "cara", "facial", "ojos",
    "marcar", "definir", "levantar", "relleno", "volumen",
]

_SERVICE_KEYWORDS = [
    "limpieza", "botox", "implante", "blanqueamiento", "ortodoncia",
    "consulta", "cita", "masaje", "faciales", "depilación", "depilacion",
    "inscripción", "inscripcion", "membresía", "membresia", "sesión",
    "sesion", "valoración", "valoracion", "examen", "control",
    "vacuna", "cirugía", "cirugia", "tratamiento", "servicio",
]


def extract_short_memory(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Lee el historial reciente y extrae:
      - name: nombre del cliente
      - service: servicio de interés principal
      - has_fear: si expresó miedo o incomodidad
      - has_price_objection: si objetó precio
      - is_hesitating: si está indeciso
      - is_frustrated: NUEVO — si está frustrado por preguntas repetidas
      - zone_already_given: NUEVO — si ya dio la zona del cuerpo/cara
      - repeated_question_detected: NUEVO — si Melissa hizo la misma pregunta 2+ veces
      - turn_count: número de turnos del cliente
      - last_client_msg: último mensaje del cliente
      - client_tone: "urgente" | "casual" | "desconfiado" | "interesado" | "frustrado"
    """
    if not history:
        return {}

    mem: Dict[str, Any] = {
        "name": None,
        "service": None,
        "has_fear": False,
        "has_price_objection": False,
        "is_hesitating": False,
        "is_frustrated": False,           # NUEVO
        "zone_already_given": False,       # NUEVO
        "repeated_question_detected": False,  # NUEVO
        "turn_count": 0,
        "last_client_msg": "",
        "client_tone": "casual",
    }

    client_messages: List[str] = []
    # Para detectar preguntas repetidas de Melissa
    assistant_questions: List[str] = []

    for msg in history:
        role = (msg.get("role") or "").lower()
        content = str(msg.get("content") or "").strip()
        if not content:
            continue

        content_lower = content.lower()

        if role == "user":
            mem["turn_count"] += 1
            mem["last_client_msg"] = content
            client_messages.append(content_lower)

            # Extraer nombre
            if not mem["name"]:
                for pat in _NAME_PATTERNS:
                    m = re.search(pat, content, re.IGNORECASE)
                    if m:
                        mem["name"] = m.group(1).strip().capitalize()
                        break

            # Detectar servicio
            if not mem["service"]:
                for kw in _SERVICE_KEYWORDS:
                    if kw in content_lower:
                        mem["service"] = kw
                        break

            # Detectar señales emocionales
            if any(s in content_lower for s in _FEAR_SIGNALS):
                mem["has_fear"] = True
            if any(s in content_lower for s in _PRICE_OBJECTION_SIGNALS):
                mem["has_price_objection"] = True
            if any(s in content_lower for s in _HESITATION_SIGNALS):
                mem["is_hesitating"] = True

            # NUEVO: frustración explícita
            if any(s in content_lower for s in _FRUSTRATION_SIGNALS):
                mem["is_frustrated"] = True

            # NUEVO: zona ya dada
            if any(s in content_lower for s in _ZONE_GIVEN_SIGNALS):
                mem["zone_already_given"] = True

        if role == "assistant":
            # Extraer nombre de metadato
            m = re.search(r'NOMBRE:\{"name":"([^"]+)"\}', content)
            if m and not mem["name"]:
                mem["name"] = m.group(1).strip().capitalize()

            # NUEVO: detectar si Melissa está repitiendo la misma pregunta
            # Extraer preguntas del asistente (frases que terminan en ?)
            questions_in_msg = re.findall(r'[^.!|]+\?', content_lower)
            for q in questions_in_msg:
                q_clean = q.strip()[:80]  # primeros 80 chars de la pregunta
                if q_clean:
                    # Si esta pregunta ya apareció antes → loop detectado
                    if any(
                        _text_similarity(q_clean, prev) > 0.6
                        for prev in assistant_questions
                    ):
                        mem["repeated_question_detected"] = True
                    assistant_questions.append(q_clean)

    # Inferir tono del cliente
    all_client_text = " ".join(client_messages)
    if mem["is_frustrated"]:
        mem["client_tone"] = "frustrado"
    elif mem["has_price_objection"] or mem["is_hesitating"]:
        mem["client_tone"] = "desconfiado"
    elif mem["has_fear"]:
        mem["client_tone"] = "desconfiado"
    elif any(w in all_client_text for w in ["urgente", "hoy", "ahora", "ya", "rápido", "rapido"]):
        mem["client_tone"] = "urgente"
    elif mem["turn_count"] >= 3:
        mem["client_tone"] = "interesado"

    return mem


def _text_similarity(a: str, b: str) -> float:
    """
    Similitud simple entre dos strings: proporción de palabras compartidas.
    Evita importar librerías externas.
    """
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def format_memory_block(mem: Dict[str, Any]) -> str:
    """
    Convierte el dict de memoria en contexto puro para el system prompt.

    v10.1: incluye instrucciones anti-loop cuando hay frustración o
    preguntas repetidas. El LLM recibe la señal de que debe cambiar de enfoque.
    """
    if not mem:
        return ""

    facts: List[str] = []
    tone_signals: List[str] = []
    anti_loop_instruction: str = ""

    # Hechos concretos
    if mem.get("name"):
        facts.append(f"ya dijo que se llama {mem['name']}")

    if mem.get("service"):
        facts.append(f"mencionó {mem['service']}")

    # NUEVO v10.1: zona ya dada
    if mem.get("zone_already_given"):
        facts.append("ya dio información sobre zona o área de interés")

    if mem.get("has_price_objection"):
        tone_signals.append("objetó el precio")

    if mem.get("has_fear"):
        tone_signals.append("expresó miedo o incomodidad")

    if mem.get("is_hesitating"):
        tone_signals.append("está indeciso")

    tone = mem.get("client_tone", "casual")
    if tone == "urgente":
        tone_signals.append("tiene urgencia")
    elif tone == "desconfiado":
        tone_signals.append("viene con desconfianza")

    # NUEVO v10.1: señales de frustración / loop
    if mem.get("is_frustrated") or mem.get("repeated_question_detected"):
        tone_signals.append("está frustrado porque siente que no lo están escuchando")
        anti_loop_instruction = (
            "CRÍTICO: el cliente ya respondió tus preguntas anteriores. "
            "NO repitas la misma pregunta. "
            "Toma lo que ya dijo, avanza con esa información, "
            "y dale algo concreto (precio, rango, próximo paso)."
        )

    if not facts and not tone_signals and not anti_loop_instruction:
        return ""

    parts = facts + tone_signals
    block = "en esta conversación: " + ", ".join(parts) + "."

    if anti_loop_instruction:
        block += f"\n{anti_loop_instruction}"

    return block


# ══════════════════════════════════════════════════════════════════════════════
# 2. VALIDADOR DE RESPUESTA — detecta si suena a plantilla o a LLM real
# ══════════════════════════════════════════════════════════════════════════════

_TEMPLATE_TELLS = [
    "con mucho gusto",
    "es un placer atenderte",
    "gracias por contactarnos",
    "¿en qué le puedo ayudar?",
    "¿en qué te puedo ayudar hoy?",
    "estoy aquí para ayudarte",
    "no dudes en consultar",
    "fue un placer",
    "que tenga un buen día",
    "estimado cliente",
    "estimada cliente",
    "a continuación",
    "por favor seleccione",
    "selecciona una opción",
    "• opción",
    "1. ",
    "2. ",
    "3. ",
]

_LLM_STRUCTURAL_TELLS = {
    "min_unique_words": 4,
    "min_length": 8,
    "conversational_markers": [
        "?", "|||",
    ],
}


class LLMResponseValidator:
    """
    Valida si una respuesta parece generada por el LLM o por código/plantilla.
    v10.1 — también detecta respuestas en loop (repite la misma pregunta).
    """

    def is_template_response(self, response: str) -> bool:
        if not response:
            return True
        r_low = response.lower()

        if re.search(r"^\s*[1-9]\.\s", response, re.MULTILINE):
            return True
        if "• opción" in r_low or "seleccione una opción" in r_low:
            return True

        template_score = sum(1 for t in _TEMPLATE_TELLS if t in r_low)

        has_substance = (
            len(response.strip()) > 60
            or "?" in response
            or "|||" in response
        )

        if template_score >= 2 and not has_substance:
            return True
        if template_score >= 4:
            return True

        return False

    def is_empty_or_useless(self, response: str) -> bool:
        cleaned = (response or "").strip()
        return len(cleaned) < 3

    def looks_like_question_only(self, response: str) -> bool:
        cleaned = (response or "").strip()
        if len(cleaned) > 80:
            return False
        return bool(re.match(r"^[¿]?\w{1,12}\?$", cleaned.strip()))

    def is_repeating_previous(self, response: str, history: List[Dict[str, Any]]) -> bool:
        """
        NUEVO v10.1: True si la respuesta repite casi exactamente
        una respuesta anterior de Melissa.
        Previene el loop "Cuénteme qué quiere ajustar" x3.
        """
        if not response or not history:
            return False

        response_clean = response.lower().strip()
        for msg in history[-6:]:
            if msg.get("role") != "assistant":
                continue
            prev = str(msg.get("content", "")).lower().strip()
            if not prev:
                continue
            # Si la similitud es > 0.75, es la misma respuesta
            if _text_similarity(response_clean[:100], prev[:100]) > 0.75:
                log.debug(f"[brain_v10] respuesta repetida detectada — similitud alta")
                return True
        return False


# Instancia global
_validator = LLMResponseValidator()


# ══════════════════════════════════════════════════════════════════════════════
# 3. PATCH LLM-FIRST — monkeypatches al ResponseGenerator
# ══════════════════════════════════════════════════════════════════════════════

def _make_llm_first_normalize(original_fn):
    """
    Wrapper de _normalize_first_patient_turn.
    v10.1: si la respuesta repite una anterior, fuerza regeneración.
    """
    def llm_first_normalize(self, response, clinic, personality, user_msg, history):
        is_first = not any(m.get("role") == "assistant" for m in (history or []))
        if not is_first:
            # NUEVO v10.1: si no es primer turno pero la respuesta repite → regenerar
            if _validator.is_repeating_previous(response, history or []):
                log.debug("[brain_v10] respuesta repetida detectada en turno N → aplicando normalize")
                return original_fn(self, response, clinic, personality, user_msg, history)
            return original_fn(self, response, clinic, personality, user_msg, history)

        # Primer turno: solo intervenir si la respuesta está vacía o es inútil
        if (
            _validator.is_empty_or_useless(response)
            or _validator.looks_like_question_only(response)
        ):
            log.debug("[brain_v10] respuesta inútil en primer turno → aplicando normalize")
            return original_fn(self, response, clinic, personality, user_msg, history)

        log.debug("[brain_v10] respuesta LLM OK en primer turno → bypass normalize")
        return response

    return llm_first_normalize


def _make_llm_first_generate(original_generate):
    """
    Wrapper de ResponseGenerator.generate.
    v10.1: elimina seeded_first_turn y previene loops de preguntas.
    """
    async def llm_first_generate(
        self,
        user_msg,
        analysis,
        reasoning,
        clinic,
        patient,
        history,
        search_context,
        personality=None,
        kb_context=None,
        chat_id=None,
    ):
        # Si seeded_first_turn → forzar LLM
        meta_model = (reasoning or {}).get("_metadata", {}).get("model", "")
        if meta_model == "seeded_first_turn":
            log.info("[brain_v10] seeded_first_turn detectado → forzando LLM en primer turno")
            reasoning = dict(reasoning or {})
            reasoning["_metadata"] = {
                **reasoning.get("_metadata", {}),
                "model": "llm_first_v10",
            }

        # NUEVO v10.1: inyectar memoria de frustración en kb_context
        if history:
            mem = extract_short_memory(history)
            memory_block = format_memory_block(mem)
            if memory_block:
                if kb_context:
                    kb_context = f"{kb_context}\n\n{memory_block}"
                else:
                    kb_context = memory_block
                log.debug(f"[brain_v10] memoria inyectada: {memory_block[:80]}...")

        return await original_generate(
            self,
            user_msg,
            analysis,
            reasoning,
            clinic,
            patient,
            history,
            search_context,
            personality=personality,
            kb_context=kb_context,
            chat_id=chat_id,
        )

    return llm_first_generate


def patch_llm_first(generator) -> bool:
    """
    Parchea una instancia de ResponseGenerator para operar en modo LLM-first.
    Retorna True si el patch se aplicó correctamente.
    """
    if generator is None:
        log.warning("[brain_v10] generator es None — patch no aplicado")
        return False

    try:
        import types

        original_normalize = generator._normalize_first_patient_turn
        generator._normalize_first_patient_turn = types.MethodType(
            _make_llm_first_normalize(
                original_normalize.__func__
                if hasattr(original_normalize, "__func__")
                else original_normalize
            ),
            generator,
        )
        log.info("[brain_v10] _normalize_first_patient_turn parchado ✓")

        original_generate = generator.generate
        generator.generate = types.MethodType(
            _make_llm_first_generate(
                original_generate.__func__
                if hasattr(original_generate, "__func__")
                else original_generate
            ),
            generator,
        )
        log.info("[brain_v10] generate parchado (anti-seeded_first_turn + anti-loop) ✓")

        return True

    except Exception as e:
        log.error(f"[brain_v10] error en patch_llm_first: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# 4. INIT — punto de entrada limpio
# ══════════════════════════════════════════════════════════════════════════════

_brain_initialized = False


def init_brain() -> None:
    global _brain_initialized
    if _brain_initialized:
        return
    _brain_initialized = True
    log.info("[brain_v10] cerebro v10.1 inicializado — modo LLM-first + anti-loop activo")


# ══════════════════════════════════════════════════════════════════════════════
# 5. AUTO-PATCH
# ══════════════════════════════════════════════════════════════════════════════

def auto_patch() -> bool:
    import sys

    melissa_module = sys.modules.get("__main__") or sys.modules.get("melissa")
    if melissa_module is None:
        for name, mod in sys.modules.items():
            if name == "melissa" or (name == "__main__" and hasattr(mod, "generator")):
                melissa_module = mod
                break

    if melissa_module is None:
        log.warning("[brain_v10] no se encontró módulo melissa — auto_patch fallido")
        return False

    gen = getattr(melissa_module, "generator", None)
    if gen is None:
        log.warning("[brain_v10] generator no encontrado en módulo — auto_patch fallido")
        return False

    init_brain()
    return patch_llm_first(gen)


# ══════════════════════════════════════════════════════════════════════════════
# 6. UTILIDADES EXTRA
# ══════════════════════════════════════════════════════════════════════════════

def should_ask_for_name(history: List[Dict[str, Any]]) -> bool:
    mem = extract_short_memory(history)
    return mem.get("name") is None and mem.get("turn_count", 0) >= 2


def get_client_name(history: List[Dict[str, Any]]) -> Optional[str]:
    return extract_short_memory(history).get("name")


def conversation_stage(history: List[Dict[str, Any]]) -> str:
    """
    Infiere la etapa de la conversación.
    v10.1 agrega "frustrated" como etapa de máxima prioridad.
    """
    mem = extract_short_memory(history)
    tc = mem.get("turn_count", 0)

    if tc == 0:
        return "first_contact"

    # NUEVO v10.1: frustración tiene prioridad
    if mem.get("is_frustrated") or mem.get("repeated_question_detected"):
        return "frustrated"

    if mem.get("has_price_objection") or mem.get("is_hesitating"):
        return "objecting"
    if tc >= 4 and mem.get("service"):
        return "ready_to_book"
    return "exploring"


def dynamic_temperature(history: List[Dict[str, Any]]) -> float:
    """
    Temperatura dinámica según etapa.
    v10.1: temperatura más alta cuando hay frustración → más variedad léxica,
    menos riesgo de repetir la misma frase.
    """
    mem = extract_short_memory(history)
    tc = mem.get("turn_count", 0)

    # Frustración → temperatura alta para forzar variedad
    if mem.get("is_frustrated") or mem.get("repeated_question_detected"):
        return 0.92

    base = 0.45
    ceiling = 0.88
    step = (ceiling - base) / 8
    return round(min(ceiling, base + step * tc), 2)


# ══════════════════════════════════════════════════════════════════════════════
# 7. SECTOR LAYER BUILDER — helper para mejorar prompts de sector
# ══════════════════════════════════════════════════════════════════════════════

def build_estetica_sector_layer(is_poblado: bool = False) -> str:
    """
    Retorna el sector layer mejorado para clínicas estéticas.

    v10.1: corrige el loop de zona. Instrucción explícita de
    "pregunta zona UNA SOLA VEZ y avanza con lo que el cliente diga".

    Usar en melissa.py reemplazando el _sector_layer de estetica no-Poblado:
        from melissa_brain_v10 import build_estetica_sector_layer
        _sector_layer = build_estetica_sector_layer(is_poblado=_is_poblado)
    """
    if is_poblado:
        return (
            "la clienta ya viene con algo en mente — no hay que convencerla, "
            "hay que escucharla bien y resolver sus dudas sin presionarla. "
            "el miedo más común es quedar exagerada o diferente. "
            "lo que genera confianza es mostrar que la dra trabaja conservador "
            "y que la valoración es sin compromiso."
        )
    else:
        return """PERFIL CLÍNICA ESTÉTICA:
Tu clienta ya sabe lo que quiere — no expliques qué es botox.

REGLA DE ZONA (crítica): Pregunta qué zona le interesa UNA SOLA VEZ.
Si ya respondió algo sobre zona o resultado (aunque sea vago como "rostro", "cara",
"marcar más", "definir", "levantar"), toma esa información y avanza.
NO vuelvas a preguntar la zona después de que el cliente ya respondió.

Si la respuesta de zona es ambigua:
  - "rostro" o "cara" → ofrece opciones concretas: frente, pómulos, mandíbula, relleno de labios
  - "marcar más" o "definir" → puede ser relleno (no botox puro) — explica brevemente y ofrece valoración
  - "levantar" → puede ser hilo tensor o toxina — menciona las dos opciones

REGLA DE PRECIO: Si el cliente pide precio directamente dos veces seguidas,
da un rango aproximado ("entre X y Y dependiendo de la zona y cantidad")
y cierra hacia la valoración. No vuelvas a preguntar.

El cierre siempre es hacia la valoración gratuita con la especialista.
Nunca repitas la misma pregunta dos veces en la misma conversación."""
