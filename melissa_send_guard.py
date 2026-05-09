"""
melissa_send_guard.py
════════════════════════════════════════════════════════════════════════════════
GUARDIA DEL PIPELINE DE ENVÍO — v1.0
════════════════════════════════════════════════════════════════════════════════

SOLUCIONA:
  1. Respuestas cortadas ("Listo, ahora soy más", "Entendido, vol...")
     → Detecta el corte y repara antes de enviar al cliente
  2. Robot phrases que borran la última burbuja dejando la respuesta incompleta
     → Agrega burbuja de cierre segura cuando la respuesta queda sin invitación
  3. Smart Handoff subutilizado en demo
     → Intercepta señales de confusión en el dueño/prospecto ANTES del LLM
  4. "Cambia personalidad a X" sin reconocimiento explícito
     → Genera confirmación + continuación en vez de respuesta genérica

CÓMO USAR en melissa.py:

  # Al inicio con los demás imports opcionales:
  try:
      from melissa_send_guard import (
          SendGuard,
          guard_response,
          patch_demo_send,
          DEMO_PERSONALITY_COMMANDS,
      )
      _SEND_GUARD = True
  except ImportError:
      _SEND_GUARD = False

  # En _handle_demo_message, justo ANTES de "return _send(r)":
  if _SEND_GUARD:
      r = guard_response(r, context="demo")

  # Para parchear la función _send completa del demo (más robusto):
  # Llamar una vez después de definir _send, dentro de _handle_demo_message:
  if _SEND_GUARD:
      _send = patch_demo_send(_send, business_name=business_name)

════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("melissa.send_guard")


# ════════════════════════════════════════════════════════════════════════════════
# 1. DETECTOR DE CORTES
#    Identifica respuestas que el pipeline cortó o dejó incompletas.
# ════════════════════════════════════════════════════════════════════════════════

# Palabras que aparecen al FINAL de la respuesta y claramente son incompletas
_DANGLING_WORDS = {
    # Artículos + preposiciones como última palabra → se cortó antes de terminar
    "el", "la", "los", "las", "un", "una", "de", "del", "en", "con",
    "por", "para", "que", "y", "o", "si", "me", "te", "le", "se", "su",
    "al", "a",
    # Comienzos de palabra que nunca terminan solos
    "vol",   # → volvemos, volveré
    "per",   # → pero, permíteme
    "más",   # puede ser válido, pero raro al final sin contexto
    "tam",   # → también
    "sol",   # → solo, solución
    "sig",   # → siguiente, sigue
}

# Patrones de respuesta claramente incompleta
_CUT_PATTERNS = [
    # Termina en preposición o conector
    r'\b(el|la|los|las|un|una|de|del|en|con|por|para|que|y|o|si)\s*$',
    # Termina en comienzo de palabra (3-4 chars, no es una palabra real completa)
    r'\b(vol|per|tam|sol|sig|par|ten|man|pro)\s*$',
    # Termina con coma o punto y coma (siempre cortado)
    r'[,;]\s*$',
    # Última burbuja es un solo token corto sin puntuación ni pregunta
    r'^\s*\w{1,4}\s*$',
]


def _split_response_bubbles(response: str) -> List[str]:
    return [p.strip() for p in re.split(r'\s*\|\|\|\s*', response) if p.strip()]


def _extract_last_token(text: str) -> str:
    stripped = (text or "").rstrip().rstrip(".,!?;:")
    match = re.search(r'\b(\w+)\s*$', stripped.lower())
    return match.group(1) if match else ""


def _has_dangling_last_token(text: str) -> Tuple[bool, str]:
    token = _extract_last_token(text)
    if not token or token not in _DANGLING_WORDS:
        return False, ""
    return True, token


def is_cut_response(response: str) -> Tuple[bool, str]:
    """
    Detecta si una respuesta está cortada.
    Retorna (es_cortado, razón).
    """
    if not response:
        return True, "respuesta vacía"

    # Tomar la última burbuja
    parts = _split_response_bubbles(response)
    if not parts:
        return True, "sin burbujas válidas"

    last = parts[-1]
    last_lower = last.lower()

    # Verificar si termina en palabra colgante
    has_dangling_word, dangling_word = _has_dangling_last_token(last)
    if has_dangling_word:
        return True, f"termina en palabra incompleta: '{dangling_word}'"

    # Verificar patrones de corte
    for pattern in _CUT_PATTERNS:
        if re.search(pattern, last_lower):
            return True, f"patrón de corte detectado: {pattern[:40]}"

    # Respuesta completa que no tiene invitación ni pregunta al final
    # (no es un error crítico, pero sí una señal de que el robot phrase filter borró algo)
    has_question = '?' in last
    has_invitation = any(inv in last_lower for inv in [
        "cuéntame", "cuentame", "dime", "escríbeme", "escribeme",
        "cuál es", "cual es", "cómo se llama", "como se llama",
        "escríbeme", "probame", "pruébame", "qué quieres", "que quieres",
        "seguimos", "dale", "listo",
    ])
    has_terminal_punctuation = last.rstrip().endswith((".", "!", "?", "…"))

    if len(parts) == 1 and not has_question and not has_invitation and not has_terminal_punctuation and len(last) < 24:
        return True, "respuesta de 1 sola burbuja muy corta sin invitación"

    return False, ""


# ════════════════════════════════════════════════════════════════════════════════
# 2. REPARADOR DE RESPUESTAS CORTADAS
#    Agrega burbujas de cierre seguras sin inventar contenido.
# ════════════════════════════════════════════════════════════════════════════════

_SAFE_CLOSINGS_DEMO = [
    "¿qué tipo de negocio tienes?",
    "cuéntame de tu negocio",
    "¿quieres que te muestre cómo respondería a un cliente tuyo?",
    "¿de qué negocio eres?",
    "escríbeme como si fueras un cliente a ver qué pasa",
]

_SAFE_CLOSINGS_PATIENT = [
    "cuéntame más",
    "¿en qué te puedo ayudar?",
    "¿qué necesitas?",
    "dime",
]

import random as _random

def repair_response(
    response: str,
    context: str = "demo",
    business_name: str = "",
) -> str:
    """
    Repara una respuesta cortada agregando una burbuja de cierre segura.

    Args:
        response: La respuesta potencialmente cortada.
        context: "demo" (con dueño de negocio) o "patient" (con cliente final).
        business_name: Nombre del negocio si está disponible.

    Returns:
        Respuesta reparada lista para enviar.
    """
    if not response or not response.strip():
        if context == "demo":
            return f"un momentico ||| ¿cómo se llama tu negocio?"
        return "un momentico ||| cuéntame"

    parts = _split_response_bubbles(response)

    # Limpiar la última burbuja si está claramente cortada
    if parts:
        last = parts[-1]
        has_dangling_word, _ = _has_dangling_last_token(last)
        if has_dangling_word:
            parts = parts[:-1]
            log.info(f"[send_guard] burbuja cortada removida: '{last[:40]}'")

    # Si no quedaron burbujas, recuperar con fallback
    if not parts:
        if context == "demo":
            return f"cuéntame, ¿cómo se llama tu negocio?"
        return "cuéntame"

    # Agregar invitación al final si no hay
    last = parts[-1]
    has_close = '?' in last or any(
        inv in last.lower() for inv in [
            "cuéntame", "cuentame", "dime", "escríbeme", "escribeme",
            "dale", "listo", "cuál es", "cual es", "seguimos",
        ]
    )

    if not has_close:
        if context == "demo":
            closing = _random.choice(_SAFE_CLOSINGS_DEMO)
        else:
            closing = _random.choice(_SAFE_CLOSINGS_PATIENT)
        parts.append(closing)
        log.info(f"[send_guard] invitación agregada: '{closing}'")

    return " ||| ".join(parts)


def guard_response(
    response: str,
    context: str = "demo",
    business_name: str = "",
) -> str:
    """
    Punto de entrada principal del guard.
    Verifica si la respuesta está cortada y la repara si es necesario.

    Usar antes de llamar a _send():
        r = guard_response(r, context="demo", business_name=business_name)
        return _send(r)
    """
    cut, reason = is_cut_response(response)
    if cut:
        log.warning(f"[send_guard] respuesta cortada ({reason}): '{(response or '')[:60]}'")
        repaired = repair_response(response, context=context, business_name=business_name)
        log.info(f"[send_guard] reparada → '{repaired[:80]}'")
        return repaired
    return response


def check_message(
    message: str,
    context: str = "patient",
    business_name: str = "",
) -> str:
    """
    Wrapper liviano para validaciones e integraciones externas.
    Retorna el mensaje limpio y falla si quedó vacío.
    """
    cleaned = guard_response(message, context=context, business_name=business_name).strip()
    if not cleaned:
        raise ValueError("mensaje vacío después del guard")
    return cleaned


# ════════════════════════════════════════════════════════════════════════════════
# 3. DETECTOR DE CAMBIOS DE PERSONALIDAD EN TEXTO LIBRE
#    "cambia personalidad a amigable" → respuesta explícita y apropiada
# ════════════════════════════════════════════════════════════════════════════════

DEMO_PERSONALITY_COMMANDS = {
    "amigable":    "listo, modo amigable ||| escríbeme como si fueras un cliente y lo notas",
    "formal":      "listo, activé modo formal ||| cuéntame qué quieres revisar",
    "luxury":      "listo, modo premium activado ||| en qué le puedo asistir",
    "directa":     "listo, al grano ||| qué necesitas",
    "energica":    "listo, energía al máximo ||| qué andas buscando",
    "empatica":    "listo, modo escucha ||| cuéntame",
    "experta":     "listo, modo técnico ||| en qué le puedo ayudar",
    "juvenil":     "dale, modo casual ||| qué buscas",
    "profesional": "listo, modo profesional ||| cuéntame qué quieres revisar",
}

_PERSONALITY_CHANGE_SIGNALS = [
    r"cambia(?:r)?\s+(?:la\s+)?personalidad\s+(?:a\s+)?(\w+)",
    r"mode\s+(\w+)",
    r"activa(?:r)?\s+(?:modo\s+)?(\w+)",
    r"pon(?:(?:me|te|lo)\s+)?(?:en\s+)?modo\s+(\w+)",
    r"sé\s+más\s+(\w+)",
    r"se\s+mas\s+(\w+)",
    r"quiero\s+(?:que\s+seas\s+más\s+)?(\w+)",
]


def detect_personality_change(user_msg: str) -> Optional[str]:
    """
    Detecta si el usuario está pidiendo cambiar la personalidad de Melissa.
    Retorna el nombre del arquetipo si se detecta, None si no.
    """
    msg_low = (user_msg or "").lower().strip()

    for pattern in _PERSONALITY_CHANGE_SIGNALS:
        m = re.search(pattern, msg_low)
        if m:
            requested = m.group(1).strip()
            # Buscar coincidencia exacta o parcial con arquetipos conocidos
            if requested in DEMO_PERSONALITY_COMMANDS:
                return requested
            # Fuzzy match básico
            for arch in DEMO_PERSONALITY_COMMANDS:
                if requested in arch or arch in requested:
                    return arch
    return None


def get_personality_change_response(archetype: str, business_name: str = "") -> str:
    """
    Retorna la respuesta de confirmación del cambio de personalidad.
    """
    base = DEMO_PERSONALITY_COMMANDS.get(archetype, f"listo, modo {archetype} activado")
    return base


# ════════════════════════════════════════════════════════════════════════════════
# 4. WRAPPER DEL DEMO _send
#    Parchea _send en el contexto del demo para interceptar respuestas antes
#    de que lleguen al cliente.
# ════════════════════════════════════════════════════════════════════════════════

def patch_demo_send(
    original_send: Callable[[str], Any],
    business_name: str = "",
    context: str = "demo",
) -> Callable[[str], Any]:
    """
    Retorna un wrapper de _send que aplica:
      1. guard_response (fix de cortes)
      2. fix_creator_in_response (Black One, no BlackBoss)

    Usar en _handle_demo_message así:
        def _send(r): ...  # definición original

        # Aplicar el guard
        if _SEND_GUARD:
            _send = patch_demo_send(_send, business_name=business_name)

        # Ahora todos los return _send(r) pasan por el guard automáticamente
    """
    try:
        from melissa_pitch_upgrade import fix_creator_in_response
        _has_pitch_upgrade = True
    except ImportError:
        _has_pitch_upgrade = False
        def fix_creator_in_response(r): return r  # type: ignore

    def guarded_send(r: str) -> Any:
        # 1. Fix Black One / BlackBoss
        if _has_pitch_upgrade:
            r = fix_creator_in_response(r)

        # 2. Detect and repair cuts
        r = guard_response(r, context=context, business_name=business_name)

        return original_send(r)

    return guarded_send


# ════════════════════════════════════════════════════════════════════════════════
# 5. SMART HANDOFF PROACTIVO — señales en el flujo demo
#    Para usar ANTES de llamar al LLM — si detecta que el prospecto necesita
#    un humano, no gasta tokens en generar una respuesta que no sirve.
# ════════════════════════════════════════════════════════════════════════════════

_IMMEDIATE_HANDOFF_SIGNALS = [
    # El prospecto quiere hablar con Santiago / con un humano directamente
    "hablar con santiago", "hablar con alguien", "necesito hablar con",
    "dame el número", "dame un número", "cuál es el número",
    "quiero llamar", "me pueden llamar", "puedo llamar",
    "me pueden contactar", "pueden contactarme",
    "quiero una reunión", "quiero una llamada", "agendar una llamada",
    "quiero contratar", "cómo contrato", "como contrato",
    "quiero empezar", "cómo empiezo", "como empiezo",
    "cuándo empezamos", "cuando empezamos",
    # Despedida con interés (se va pero quiere seguimiento)
    "gracias me comunico", "gracias los llamo", "gracias les escribo",
    "gracias más tarde", "gracias después", "gracias luego",
]

_COOLDOWN_HANDOFF_SIGNALS = [
    # Se va frustrado — handoff para salvar la conversación
    "gracias me voy", "hasta luego", "adiós", "adios", "chao", "bye",
    "no era lo que buscaba", "no me interesa", "gracias no",
    "me equivoqué", "me equivoque", "número equivocado",
]


def check_proactive_handoff(user_msg: str, history: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """
    Verifica si se debe escalar a humano ANTES de llamar al LLM.

    Retorna un dict con:
        {"reason": "...", "urgency": "high" | "medium", "suggested_reply": "..."}
    O None si no aplica.

    Usar en _handle_demo_message:
        handoff_check = check_proactive_handoff(text, history)
        if handoff_check and _SMART_HANDOFF and handoff_manager:
            return await handoff_manager.trigger_handoff(...)
    """
    msg_low = (user_msg or "").lower().strip()

    for signal in _IMMEDIATE_HANDOFF_SIGNALS:
        if signal in msg_low:
            return {
                "reason": f"prospecto solicita contacto directo: '{signal}'",
                "urgency": "high",
                "suggested_reply": (
                    "claro, te paso con Santiago directamente ||| "
                    "su contacto es 3124348669 — él te da la propuesta según tu negocio"
                ),
            }

    for signal in _COOLDOWN_HANDOFF_SIGNALS:
        if signal in msg_low:
            # Solo escalar si hay historial (no en primera interacción)
            if len(history) >= 4:
                return {
                    "reason": f"prospecto se va: '{signal}'",
                    "urgency": "medium",
                    "suggested_reply": (
                        "entendido, sin problema ||| "
                        "si en algún momento quieres verme en acción, "
                        "el contacto de Black One es 3124348669"
                    ),
                }

    return None


# ════════════════════════════════════════════════════════════════════════════════
# 6. CLASE PRINCIPAL — SendGuard
#    Encapsula todo el pipeline de guardería en un objeto reutilizable.
# ════════════════════════════════════════════════════════════════════════════════

class SendGuard:
    """
    Guardia completa del pipeline de envío.

    Uso típico:
        guard = SendGuard(context="demo", business_name=business_name)

        # Antes de llamar al LLM:
        handoff = guard.check_handoff(text, history)
        if handoff:
            # ... triggear smart handoff
            pass

        # También detectar cambio de personalidad:
        arch = guard.detect_personality_change(text)
        if arch:
            response = guard.personality_response(arch)
            return _send(response)

        # Después de generar respuesta LLM:
        clean_response = guard.clean(llm_response)
        return _send(clean_response)
    """

    def __init__(self, context: str = "demo", business_name: str = ""):
        self.context = context
        self.business_name = business_name
        self._pitch_fix_available = False
        try:
            from melissa_pitch_upgrade import fix_creator_in_response
            self._fix_creator = fix_creator_in_response
            self._pitch_fix_available = True
        except ImportError:
            self._fix_creator = lambda r: r

    def check_handoff(
        self, user_msg: str, history: List[Dict[str, Any]]
    ) -> Optional[Dict[str, str]]:
        """Verifica si se debe escalar antes del LLM."""
        return check_proactive_handoff(user_msg, history)

    def detect_personality_change(self, user_msg: str) -> Optional[str]:
        """Detecta si el usuario pide cambiar la personalidad."""
        return detect_personality_change(user_msg)

    def personality_response(self, archetype: str) -> str:
        """Retorna la respuesta de confirmación del cambio de personalidad."""
        return get_personality_change_response(archetype, self.business_name)

    def clean(self, response: str) -> str:
        """Limpia y repara una respuesta antes de enviarla."""
        r = self._fix_creator(response)
        r = guard_response(r, context=self.context, business_name=self.business_name)
        return r

    def wrap_send(self, send_fn: Callable) -> Callable:
        """Retorna send_fn envuelta con el guard."""
        return patch_demo_send(send_fn, business_name=self.business_name, context=self.context)


# ════════════════════════════════════════════════════════════════════════════════
# 7. INTEGRACIÓN COMPLETA — snippet listo para pegar
# ════════════════════════════════════════════════════════════════════════════════

INTEGRATION_SNIPPET = '''
# ═══════════════════════════════════════════════════════════════════════
# MELISSA_SEND_GUARD — Pegar al inicio de _handle_demo_message
# ═══════════════════════════════════════════════════════════════════════
try:
    from melissa_send_guard import SendGuard
    from melissa_pitch_upgrade import is_prospect_confused, build_prospect_pitch_system_prompt
    _guard = SendGuard(context="demo", business_name=business_name)
    _GUARD_ACTIVE = True
except ImportError:
    _GUARD_ACTIVE = False
    _guard = None

# ── 1. Antes del bloque de comandos: check handoff proactivo ─────────
if _GUARD_ACTIVE and _guard:
    _handoff_check = _guard.check_handoff(text, history)
    if _handoff_check and _SMART_HANDOFF and handoff_manager:
        _save("user", text)
        _save("assistant", _handoff_check["suggested_reply"])
        return _send(_handoff_check["suggested_reply"])

# ── 2. Cambio de personalidad en texto libre (antes del LLM) ────────
if _GUARD_ACTIVE and _guard:
    _arch = _guard.detect_personality_change(text)
    if _arch:
        _pers_resp = _guard.personality_response(_arch)
        _save("user", text)
        return _send(_pers_resp)

# ── 3. Pitch inteligente si es prospecto confundido ──────────────────
if _GUARD_ACTIVE:
    try:
        if is_prospect_confused(text, history):
            system_prompt = build_prospect_pitch_system_prompt(business_name)
            # system_prompt listo para usar en lugar del genérico
    except Exception:
        pass

# ── 4. Después de definir _send, envolver con el guard ───────────────
if _GUARD_ACTIVE and _guard:
    _send = _guard.wrap_send(_send)

# ═══════════════════════════════════════════════════════════════════════
# FIN DE LA INTEGRACIÓN — el resto del código de _handle_demo_message
# queda igual. Todo return _send(r) pasa ahora por el guard.
# ═══════════════════════════════════════════════════════════════════════
'''
