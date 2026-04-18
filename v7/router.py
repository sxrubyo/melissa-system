"""
Melissa V7.0 — Router de Intención
===================================
Clasifica el mensaje entrante al agente correcto en 3 capas:
  Capa 1: señales exactas (regex)     → 5-15ms, costo 0
  Capa 2: señales semánticas (score)  → 15-30ms, costo 0
  Capa 3: LLM fallback                → 400ms, solo si confianza < THRESHOLD

Nunca llama al LLM para los casos claros (>85% de los mensajes reales).
"""

from __future__ import annotations
import re
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

log = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.65  # bajo esto → LLM fallback


# ── Agentes disponibles ───────────────────────────────────────────────────────

class AgentID(str, Enum):
    CAPTACION    = "captacion"
    OBJECIONES   = "objeciones"
    AGENDA       = "agenda"
    SEGUIMIENTO  = "seguimiento"
    CONOCIMIENTO = "conocimiento"
    ESCALACION   = "escalacion"
    ADMIN        = "admin"
    FALLBACK     = "fallback"   # generator clásico si ningún agente matchea


# ── Resultado del router ──────────────────────────────────────────────────────

@dataclass
class RouterResult:
    agent_id:    AgentID
    confidence:  float
    signals:     List[str]          # qué señales dispararon la decisión
    context_keys: List[str]         # qué campos de memoria necesita el agente
    latency_ms:  float = 0.0

    @property
    def is_confident(self) -> bool:
        return self.confidence >= CONFIDENCE_THRESHOLD


# ── Definición de señales por agente ─────────────────────────────────────────

# Cada señal tiene: patrón regex, peso (0-1), contexto_mínimo
_SIGNALS: Dict[AgentID, List[Tuple[str, float]]] = {

    AgentID.ESCALACION: [
        # Alta prioridad — se evalúa PRIMERO
        (r"\b(emergencia|urgente|me duele mucho|reacción|alergia|complicación|demanda|abogado|denunciar)\b", 0.95),
        (r"\b(hablar con (alguien|una persona|el dueño|el doctor)|quiero quejarme)\b", 0.90),
        (r"\b(me quedó mal|quedé horrible|daño|perjuicio)\b", 0.85),
    ],

    AgentID.OBJECIONES: [
        (r"\b(caro|costoso|muy caro|no tengo plata|presupuesto|precio alto)\b", 0.90),
        (r"\b(pensarlo|lo pienso|déjame pensar|no sé si|lo consulto|mi (pareja|esposo|esposa|mamá))\b", 0.88),
        (r"\b(miedo|da miedo|me asusta|quede (rara|exagerada|tiesa|mal)|se note|natural)\b", 0.90),
        (r"\b(ya fui|fui a otro|otra clínica|otro lugar|en otro lado)\b", 0.88),
        (r"\b(no funciona|no sirve|pura carreta|no creo|esceptic|dudas?)\b", 0.85),
        (r"\b(no tengo tiempo|muy ocupad|trabajo mucho|no puedo ir)\b", 0.82),
        (r"\b(vergüenza|pena|me da pena|qué dirán)\b", 0.85),
        (r"\b(bogotá|exterior|fuera del país|afuera)\b", 0.75),
    ],

    AgentID.AGENDA: [
        (r"\b(agendar|agenda|cita|turno|hora|reservar|apartar)\b", 0.92),
        (r"\b(cuándo (tienen|puedo|hay|están|podría))\b", 0.88),
        (r"\b(disponibilidad|disponible|libre|espacio)\b", 0.85),
        (r"\b(lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)\b", 0.75),
        (r"\b(mañana|esta semana|próxima semana|este mes)\b", 0.70),
        (r"\b(puedo ir|quiero ir|ir a la clínica|ir a consulta)\b", 0.80),
        (r"\b(valoración|valoracion|consulta)\b", 0.72),
    ],

    AgentID.CONOCIMIENTO: [
        (r"\b(qué es|que es|cómo funciona|como funciona|qué hace|explica)\b", 0.88),
        (r"\b(cuánto dura|tiempo de recuperación|recuperación|efectos|riesgos|contraindicaciones)\b", 0.90),
        (r"\b(diferencia entre|diferencia del|cuál es mejor|cuál recomiendas)\b", 0.85),
        (r"\b(botox|relleno|rellenos|láser|laser|hilos|mesoterapia|peeling|facelift|bichectomía|rinoplastia|liposucción)\b", 0.72),
        (r"\b(cuántas sesiones|cuánto tiempo|cuándo veo resultados|resultados)\b", 0.80),
        (r"\b(antes y después|fotos de resultados|casos)\b", 0.78),
    ],

    AgentID.CAPTACION: [
        (r"\b(hola|buenas|buenos días|buenos dias|buenas tardes|buenas noches)\b", 0.70),
        (r"\b(información|informacion|info|quiero saber|me interesa|quisiera)\b", 0.75),
        (r"\b(primera vez|nunca he ido|primer vez)\b", 0.85),
        (r"\b(me recomendaron|me dijeron|escuché de|leí sobre)\b", 0.78),
        (r"\b(qué servicios|qué ofrecen|qué hacen|cuáles (son|tienen))\b", 0.80),
        (r"^(hola|buenas|hi|hey|buen día)[.!?\s]*$", 0.85),  # solo saludo
    ],

    AgentID.SEGUIMIENTO: [
        # Mayormente activado por cron, pero también por texto
        (r"\b(cómo quedé|cómo me veo|cómo salió|resultados?\s*de\s*mi)\b", 0.88),
        (r"\b(ya me lo hice|ya fui|ya vine|me lo hicieron)\b", 0.82),
        (r"\b(seguimiento|control|revisión|revision)\b", 0.85),
    ],
}

# Contexto que necesita cada agente de la memoria
_CONTEXT_KEYS: Dict[AgentID, List[str]] = {
    AgentID.CAPTACION:    ["patient_name", "visits", "funnel_state", "clinic_tone"],
    AgentID.OBJECIONES:   ["patient_name", "objeciones_pasadas", "funnel_state", "clinic_tone", "servicios_relevantes"],
    AgentID.AGENDA:       ["patient_name", "funnel_state", "ultima_cita", "calendar_available"],
    AgentID.CONOCIMIENTO: ["servicios_clinica", "precios", "clinic_kb_excerpt"],
    AgentID.SEGUIMIENTO:  ["patient_name", "ultima_cita", "procedimiento_realizado"],
    AgentID.ESCALACION:   ["patient_name", "admin_chat_ids", "clinic_phone"],
    AgentID.FALLBACK:     ["full_context"],  # fallback recibe todo
}


# ── Router principal ──────────────────────────────────────────────────────────

class IntentRouter:
    """
    Router de tres capas.
    Se instancia una vez al arranque y se reutiliza para todos los mensajes.
    """

    def __init__(self):
        # Precompilar todos los patrones
        self._compiled: Dict[AgentID, List[Tuple[re.Pattern, float]]] = {}
        for agent_id, signals in _SIGNALS.items():
            self._compiled[agent_id] = [
                (re.compile(pat, re.IGNORECASE | re.UNICODE), weight)
                for pat, weight in signals
            ]
        log.info("[router] IntentRouter listo — %d agentes registrados", len(self._compiled))

    def route(
        self,
        text: str,
        funnel_state: str = "primer_contacto",
        history_length: int = 0,
        is_cron: bool = False,
        cron_type: Optional[str] = None,
    ) -> RouterResult:
        """
        Clasifica el mensaje y devuelve el agente más apropiado.
        Esta función NUNCA llama al LLM.
        """
        t0 = time.perf_counter()

        # Cron triggers van directamente a seguimiento
        if is_cron:
            return RouterResult(
                agent_id=AgentID.SEGUIMIENTO,
                confidence=1.0,
                signals=[f"cron:{cron_type}"],
                context_keys=_CONTEXT_KEYS[AgentID.SEGUIMIENTO],
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

        # Capa 1: scoring por señales regex
        scores: Dict[AgentID, Tuple[float, List[str]]] = {}
        for agent_id, patterns in self._compiled.items():
            hits = []
            total_weight = 0.0
            for pattern, weight in patterns:
                if pattern.search(text):
                    hits.append(pattern.pattern[:40])
                    total_weight = max(total_weight, weight)
            if hits:
                scores[agent_id] = (total_weight, hits)

        # Capa 2: ajuste por estado del funnel
        scores = self._adjust_by_funnel(scores, funnel_state, history_length)

        # Elegir ganador
        if scores:
            best_agent = max(scores, key=lambda a: scores[a][0])
            best_score, best_signals = scores[best_agent]
        else:
            best_agent  = AgentID.CAPTACION
            best_score  = 0.40
            best_signals = ["sin_señales_explícitas"]

        latency = (time.perf_counter() - t0) * 1000
        log.debug(
            "[router] %s confianza=%.2f señales=%s latencia=%.1fms",
            best_agent.value, best_score, best_signals[:2], latency
        )

        return RouterResult(
            agent_id=best_agent,
            confidence=best_score,
            signals=best_signals,
            context_keys=_CONTEXT_KEYS.get(best_agent, _CONTEXT_KEYS[AgentID.FALLBACK]),
            latency_ms=latency,
        )

    def _adjust_by_funnel(
        self,
        scores: Dict[AgentID, Tuple[float, List[str]]],
        funnel_state: str,
        history_length: int,
    ) -> Dict[AgentID, Tuple[float, List[str]]]:
        """
        Ajusta los scores según el contexto del funnel.
        El funnel no sobreescribe señales fuertes — solo desempata.
        """
        adjusted = dict(scores)

        # Si es primer contacto y no hay señales claras → captacion gana
        if funnel_state == "primer_contacto" and history_length == 0:
            if AgentID.CAPTACION not in adjusted:
                adjusted[AgentID.CAPTACION] = (0.65, ["funnel:primer_contacto"])
            else:
                sc, sig = adjusted[AgentID.CAPTACION]
                adjusted[AgentID.CAPTACION] = (min(sc + 0.10, 1.0), sig + ["funnel:boost_primer_contacto"])

        # Si tiene intención confirmada y hay señal de agenda → boost agenda
        if funnel_state == "con_intencion" and AgentID.AGENDA in adjusted:
            sc, sig = adjusted[AgentID.AGENDA]
            adjusted[AgentID.AGENDA] = (min(sc + 0.12, 1.0), sig + ["funnel:boost_con_intencion"])

        # Escalacion siempre tiene prioridad — no se reduce
        if AgentID.ESCALACION in adjusted:
            sc, sig = adjusted[AgentID.ESCALACION]
            adjusted[AgentID.ESCALACION] = (max(sc, 0.92), sig)

        return adjusted


# ── Instancia global (singleton) ─────────────────────────────────────────────
# Se importa desde melissa.py:  from router import router
router = IntentRouter()
