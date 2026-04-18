"""
Melissa V7.0 — Agente de Agenda
==================================
Gestiona la valoración/cita. Propone UN día concreto.
Nunca inventa disponibilidad. Cierra hacia el micro-compromiso.
Prompt: ~320 tokens.
"""

from __future__ import annotations
import re
from v7.agents.base import AgentBase, AgentContext, AgentResponse


class AgenteAgenda(AgentBase):

    agent_id     = "agenda"
    context_keys = ["patient_name", "funnel_state", "ultima_cita",
                    "calendar_available", "clinic_tone"]

    def _build_prompt(self, ctx: AgentContext) -> str:
        calendar = ctx.calendar_info or ""
        tiene_calendar = bool(calendar and "disponible" in calendar.lower())
        usted = ctx.usted

        if tiene_calendar:
            disponibilidad_bloque = f"DISPONIBILIDAD REAL:\n{calendar}"
        else:
            disponibilidad_bloque = (
                "No tienes acceso al calendario real. "
                "Propón el próximo jueves como día concreto. "
                "Si el paciente no puede, negocia. "
                "Nunca digas 'cuando puedas' ni 'el día que prefieras'."
            )

        return f"""Eres la persona que contesta el WhatsApp de {ctx.clinic_name or "la clínica"}.
{self._tone_header(ctx)}

MISIÓN: agendar la valoración. La valoración es el producto, no el procedimiento.

LA VALORACIÓN ES:
  Gratis. 20 minutos. Con la doctora directamente.
  Sin compromiso — la doctora evalúa y te dice con honestidad qué aplica.

CÓMO CERRAR:
1. Propón UN día concreto — "esta semana tienes el jueves, te queda bien"
2. NUNCA dos opciones: "jueves o viernes" suena a indecisión
3. Si rechaza ese día → negocia hacia otro día, no listes toda la semana
4. Si acepta → pide nombre y confirma: "perfecto, {ctx.patient_name or 'te anoto'} para el jueves"
5. Si ya tiene cita → confirmar o reagendar con calidez

NUNCA INVENTAR DISPONIBILIDAD:
Si no tienes el calendario real, di "te confirmo" en vez de inventar horarios.
  "esta semana tenemos espacio, déjame confirmarte el jueves a qué hora puedes"

{disponibilidad_bloque}

TONO DE CIERRE:
  {"Le agendamos la valoración. ¿Le queda bien este jueves?" if usted else "te agendo la valoración, esta semana tienes el jueves, te queda bien"}

{self._writing_rules()}
{self._patient_block(ctx)}"""

    def _parse_response(self, raw: str, ctx: AgentContext) -> AgentResponse:
        from v7.postprocess import postprocess, split_bubbles
        clean   = postprocess(raw, is_premium=ctx.is_premium)
        bubbles = split_bubbles(clean)

        # Detectar si se confirmó una cita en la respuesta
        cita_confirmada = bool(re.search(
            r"\b(agend[oé]|confirm[oé]|anot[oé]|queda para|quedaste para)\b",
            raw, re.IGNORECASE
        ))

        return AgentResponse(
            bubbles=bubbles or [clean],
            funnel_update="cita_agendada" if cita_confirmada else None,
        )
