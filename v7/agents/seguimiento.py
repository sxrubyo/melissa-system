"""
Melissa V7.0 — Agente de Seguimiento
======================================
Reactivación de pacientes inactivos, no-shows, post-procedimiento.
Se activa por cron O por mensaje del paciente que ya tuvo cita.
Prompt: ~290 tokens.
"""

from __future__ import annotations
from v7.agents.base import AgentBase, AgentContext, AgentResponse


class AgenteSeguimiento(AgentBase):

    agent_id     = "seguimiento"
    context_keys = ["patient_name", "ultima_cita", "procedimiento_realizado",
                    "clinic_tone", "funnel_state"]

    def _build_prompt(self, ctx: AgentContext) -> str:
        razon    = ctx.metadata.get("follow_up_reason", "reactivacion")
        nombre   = ctx.patient_name or ""
        usted    = ctx.usted

        razon_map = {
            "no_show":        f"{"No vino a su cita" if usted else "No fue a la cita"}. Tono: calidez, sin reproche.",
            "post_cita_48h":  f"Tuvo la valoración hace 2 días. Tono: genuino interés.",
            "post_procedimiento": "Ya le hicieron el procedimiento. Revisa cómo le fue.",
            "reactivacion_30d": f"Lleva más de 30 días sin escribir. Tono: suave, sin presión.",
            "reactivacion":   f"{"Había mostrado interés." if not nombre else f"{nombre} había mostrado interés."}. Retomar suave.",
        }
        contexto_razon = razon_map.get(razon, razon_map["reactivacion"])
        nombre_bloque  = f"{"Su nombre es" if usted else "Se llama"} {nombre}." if nombre else ""

        return f"""Eres la persona que contesta el WhatsApp de {ctx.clinic_name or "la clínica"}.
{self._tone_header(ctx)}

SITUACIÓN: {contexto_razon}
{nombre_bloque}

MISIÓN: retomar el contacto de forma natural. Sin presión. Sin drama.

GUÍAS POR SITUACIÓN:
No-show:
  No preguntes por qué no fue. Solo retoma.
  {"¿Tuvo algún imprevisto? Podemos reagendar cuando le quede bien." if usted else "oye, quedaste de venir, ¿te pasó algo? podemos reagendar sin problema"}

Post-valoración (48h):
  Pregunta genuinamente cómo le fue, sin venta.
  {"¿Cómo le quedaron las recomendaciones de la doctora?" if usted else "oye, cómo te fue con lo que te dijo la doctora"}

Post-procedimiento:
  Interés real en el resultado. Abre espacio para que cuente.
  {"¿Cómo se ha sentido?" if usted else "qué tal cómo quedaste, ya se ven los resultados?"}

Reactivación larga (30+ días):
  Suave, sin recordar que desapareció.
  {"Queríamos saber cómo está" if usted else "oye, hace rato no sabemos de ti, ¿cómo has estado?"}

SI HAY APERTURA → reagendar en el mismo mensaje
  "esta semana tienes el jueves, te queda bien"

{self._writing_rules()}"""

    def _parse_response(self, raw: str, ctx: AgentContext) -> AgentResponse:
        from v7.postprocess import postprocess, split_bubbles
        clean   = postprocess(raw, is_premium=ctx.is_premium)
        bubbles = split_bubbles(clean)
        return AgentResponse(
            bubbles=bubbles or [clean],
            funnel_update="reactivacion",
        )
