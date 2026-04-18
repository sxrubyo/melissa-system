"""
Melissa V7.0 — Agente de Escalación
=====================================
Detecta urgencias reales y deriva al humano correcto.
Nunca diagnostica. Nunca minimiza una queja.
Prompt: ~220 tokens.
"""

from __future__ import annotations
import re
from v7.agents.base import AgentBase, AgentContext, AgentResponse

_URGENCIA_MEDICA_RE = re.compile(
    r"\b(emergencia|reacción|alergia|inflamación grave|no puedo respirar|"
    r"me duele mucho|complicación|infección|sangrado|desmay)\b",
    re.IGNORECASE,
)

_QUEJA_LEGAL_RE = re.compile(
    r"\b(demanda|abogado|denunciar|demandar|tribunal|juridico|legal)\b",
    re.IGNORECASE,
)


class AgenteEscalacion(AgentBase):

    agent_id     = "escalacion"
    context_keys = ["patient_name", "admin_chat_ids", "clinic_phone", "clinic_tone"]

    def _build_prompt(self, ctx: AgentContext) -> str:
        es_medica = bool(_URGENCIA_MEDICA_RE.search(ctx.text))
        es_legal  = bool(_QUEJA_LEGAL_RE.search(ctx.text))
        usted     = ctx.usted

        if es_medica:
            tipo = "URGENCIA MÉDICA"
            instruccion = (
                "Calma al paciente. Deriva inmediatamente a la línea de emergencias de la clínica. "
                f"Número de contacto urgente: {ctx.metadata.get('clinic_emergency', 'el número de la clínica')}. "
                "No diagnostiques. No minimices."
            )
        elif es_legal:
            tipo = "SITUACIÓN LEGAL"
            instruccion = (
                "Sé cordial y profesional. No te pongas a la defensiva. "
                "Conecta con el equipo directivo de inmediato. "
                "No hagas promesas ni admitas responsabilidad."
            )
        else:
            tipo = "SOLICITUD DE HUMANO"
            instruccion = (
                "El paciente quiere hablar con una persona. "
                "Conecta de forma cálida. No lo hagas esperar."
            )

        return f"""Eres la persona que contesta el WhatsApp de {ctx.clinic_name or "la clínica"}.
{self._tone_header(ctx)}

SITUACIÓN: {tipo}
{instruccion}

RESPUESTA EN DOS PASOS:
1. Acusa recibo con calma — una sola frase, sin alarmar
2. Conecta al humano correcto — rápido y concreto

{"Ejemplo: Entiendo, le conecto en este momento con alguien del equipo." if usted else "Ejemplo: entiendo, te conecto ahora mismo con alguien del equipo"}

NUNCA:
  Diagnosticar síntomas médicos
  Prometer resultados o soluciones
  Dar largas ni pedir que espere sin conectar

{self._writing_rules()}"""

    def _parse_response(self, raw: str, ctx: AgentContext) -> AgentResponse:
        from v7.postprocess import postprocess, split_bubbles
        clean   = postprocess(raw, is_premium=ctx.is_premium)
        bubbles = split_bubbles(clean)
        return AgentResponse(
            bubbles=bubbles or [clean],
            next_agent="human",   # señal al orquestador: notificar admin
            funnel_update=None,
        )
