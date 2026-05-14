from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("melissa.production")


class MelissaProduction:
    """
    Producción: Atención a pacientes reales via LLM directo.
    100% inteligencia artificial, sin templates hardcodeados.
    """

    def __init__(self, melissa):
        self.melissa = melissa

    async def handle(self, chat_id: str, text: str, clinic: Dict,
                    history: List[Dict], conv_state: Dict) -> List[str]:
        """Procesa un mensaje de paciente real via LLM directo."""
        from melissa import db, llm_engine, kb, v8_process_response

        start_time = time.time()
        clinic_name = clinic.get("name", "el negocio")
        services = clinic.get("services", [])
        if isinstance(services, str):
            services = [s.strip() for s in services.split(",") if s.strip()]
        services_str = ", ".join(services[:10]) if services else "consulta general"
        schedule = clinic.get("schedule", "")
        if isinstance(schedule, dict):
            schedule = " | ".join(f"{k}: {v}" for k, v in schedule.items())

        sys_prompt = f"""Eres Melissa, recepcionista virtual de {clinic_name}.
Servicios: {services_str}
Horario: {schedule or 'consultar'}

REGLAS:
- Responde como recepcionista colombiana real: cálida, directa, útil
- Una sola pregunta por turno, enfocada en avanzar la conversación
- Si el paciente quiere cita: pide nombre, servicio, fecha preferida
- Si preguntan precio: "depende del servicio, te ayudo a cotizar"
- Si no sabes algo: "déjame verificar eso y te confirmo"
- NUNCA digas "como IA", "no tengo capacidad", "asistente virtual"
- Usa máximo 2-3 burbujas separadas por |||
- Sé concisa (máx 40 palabras por burbuja)"""

        messages = [{"role": "system", "content": sys_prompt}]
        for m in history[-12:]:
            messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        messages.append({"role": "user", "content": text})

        # KB context
        kb_context = ""
        if kb:
            try:
                if hasattr(kb, "has_content") and kb.has_content():
                    kb_context = kb.query(text)
            except Exception:
                pass
        if kb_context:
            messages[0]["content"] += f"\n\nCONTEXTO DEL NEGOCIO:\n{kb_context[:1000]}"

        # Teachings injection
        try:
            from melissa_learning import learning_engine
            teachings = await learning_engine.get_teachings(
                getattr(self.melissa, "_instance_id", "default"), limit=20
            )
            if teachings:
                teachings_text = learning_engine.build_teachings_prompt(teachings)
                messages[0]["content"] += f"\n\n{teachings_text}"
        except Exception:
            pass

        # LLM call
        response = ""
        model_used = "llm"
        if llm_engine:
            try:
                response, meta = await llm_engine.complete(
                    messages, model_tier="fast", temperature=0.75,
                    max_tokens=2048, use_cache=False,
                )
                model_used = meta.get("model", "llm")
                log.info(f"[production] {meta.get('provider','?')} latency={time.time()-start_time:.1f}s")
            except Exception as e:
                log.error(f"[production] LLM error: {e}")

        if not response or not response.strip():
            response = "cuéntame en qué te puedo ayudar"

        response = v8_process_response(response, chat_id=chat_id)

        # Save to DB
        try:
            db.save_message(chat_id, "user", text)
            db.save_message(chat_id, "assistant", response.replace("|||", " "),
                           model=model_used,
                           latency=int((time.time() - start_time) * 1000))
        except Exception:
            pass

        return self.melissa._split_bubbles(response, chat_id=chat_id)
