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
        instance_id = getattr(self.melissa, "_instance_id", "default")
        clinic_name = clinic.get("name", "el negocio")
        services = clinic.get("services", [])
        if isinstance(services, str):
            services = [s.strip() for s in services.split(",") if s.strip()]
        services_str = ", ".join(services[:10]) if services else "consulta general"
        schedule = clinic.get("schedule", "")
        if isinstance(schedule, dict):
            schedule = " | ".join(f"{k}: {v}" for k, v in schedule.items())

        # Load persona override (tone changes from admin)
        persona_tone = "colombian_warm"
        try:
            from pathlib import Path
            import json as _json
            override_path = Path(f"personas/{instance_id}/runtime_override.json")
            if override_path.exists():
                override = _json.loads(override_path.read_text())
                persona_tone = override.get("tone", persona_tone)
        except Exception:
            pass

        # Load soul knowledge
        soul_context = ""
        try:
            soul_file = Path(f"soul/{instance_id}/knowledge.md")
            if soul_file.exists():
                soul_context = soul_file.read_text()[-2000:]
        except Exception:
            pass

        tone_instructions = {
            "luxury": "Tono LUXURY: sofisticada, elegante, exclusiva. Usa lenguaje premium. Nunca suenes informal ni uses jerga. Transmite exclusividad en cada palabra.",
            "formal": "Tono FORMAL: profesional, respetuosa, precisa. Sin jerga. Usted en vez de tú.",
            "casual": "Tono CASUAL: cercana, relajada, como amiga. Tutea. Usa expresiones naturales.",
            "colombian_warm": "Tono COLOMBIANO CÁLIDO: cercana pero profesional, calidez natural, expresiones colombianas sutiles.",
            "warm_energetic": "Tono ALEGRE: energética, positiva, con chispa. Emojis permitidos.",
        }
        tone_instruction = tone_instructions.get(persona_tone, tone_instructions["colombian_warm"])

        sys_prompt = f"""Eres Melissa, recepcionista virtual de {clinic_name}.
Servicios: {services_str}
Horario: {schedule or 'consultar'}

TONO: {tone_instruction}

{f"CONOCIMIENTO DEL NEGOCIO:{chr(10)}{soul_context}" if soul_context else ""}

REGLA #1 — RESPONDE CON LO QUE SABES:
- Si la respuesta está en la sección "RESPUESTAS QUE YA SABES" → DALA DIRECTAMENTE sin dudar
- Si NO encuentras la respuesta en ninguna sección → "me confirmo y te aviso"
- Las RESPUESTAS QUE YA SABES son información VERIFICADA por el dueño. Úsalas con total confianza.

REGLAS GENERALES:
- {tone_instruction.split(':')[0]} — aplica este tono en CADA respuesta
- Una sola pregunta por turno, enfocada en avanzar la conversación
- Si el paciente quiere cita: pide nombre, servicio, fecha preferida
- NUNCA digas "como IA", "no tengo capacidad", "asistente virtual"
- NUNCA uses formato markdown (**, *, _, #, `)
- Usa máximo 2-3 burbujas separadas por |||
- Sé concisa (máx 40 palabras por burbuja)
- Escribe como escribe una persona en WhatsApp: natural, sin puntuación perfecta
- Puedes usar 1-2 emojis si el tono lo permite (nunca más de 2)
- Si ya saluaste, no vuelvas a saludar en la misma conversación"""

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

        # Teachings injection — THIS IS YOUR KNOWLEDGE, USE IT
        try:
            from melissa_learning import learning_engine
            teachings = await learning_engine.get_teachings(instance_id, limit=20)
            if teachings:
                qa_lines = []
                for t in teachings:
                    q = t.get("question", "").replace("[admin enseñó] ", "")
                    a = t.get("answer", "")
                    if a and not q.startswith("["):
                        qa_lines.append(f"Si preguntan: \"{q}\" → Responde: \"{a}\"")
                    elif a:
                        qa_lines.append(f"Regla: {a[:150]}")
                if qa_lines:
                    # Inject ABOVE the rules, as part of the clinic facts
                    messages[0]["content"] = messages[0]["content"].replace(
                        "REGLA #1",
                        "DATOS CONFIRMADOS POR EL DUEÑO (responde con estos sin dudar):\n" + "\n".join(qa_lines) + "\n\nREGLA #1"
                    )
        except Exception:
            pass

        # Admin rules injection (things admin said to ask first)
        try:
            from pathlib import Path
            rules_file = Path(f"soul/{instance_id}/admin_rules.json")
            if rules_file.exists():
                import json as _j
                rules = _j.loads(rules_file.read_text())
                if rules:
                    rules_text = "\n".join(f"- Si preguntan sobre '{r['topic']}': {r['action']}" for r in rules[-10:])
                    messages[0]["content"] += f"\n\nINSTRUCCIONES DEL DUEÑO:\n{rules_text}"
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

        # Strip ALL markdown — patients must get pure human text (no *, **, `, #)
        import re as _re
        response = _re.sub(r'\*\*(.+?)\*\*', r'\1', response)
        response = _re.sub(r'\*(.+?)\*', r'\1', response)
        response = _re.sub(r'`(.+?)`', r'\1', response)
        response = _re.sub(r'^#+\s*', '', response, flags=_re.MULTILINE)
        response = _re.sub(r'_(.+?)_', r'\1', response)  # no italics either

        response = v8_process_response(response, chat_id=chat_id)

        # Uncertainty check + admin escalation
        try:
            from melissa_uncertainty import uncertainty_detector
            confidence = uncertainty_detector.confidence_score(response, text, history)

            # If response contains data from teachings, trust it (don't override)
            try:
                from melissa_learning import learning_engine as _le
                _teachings = await _le.get_teachings(instance_id, limit=30)
                for t in _teachings:
                    if t.get("answer", "")[:20].lower() in response.lower():
                        confidence = max(confidence, 0.8)
                        break
            except Exception:
                pass

            # Get admin JID for alerts
            admin_ids = clinic.get("admin_chat_ids", [])
            if isinstance(admin_ids, str):
                import json as _j
                admin_ids = _j.loads(admin_ids) if admin_ids else []
            admin_jid = str(admin_ids[0]) if admin_ids else ""

            # Skip alert if we have teachings that match the question
            has_relevant_teaching = False
            try:
                from melissa_learning import learning_engine as _le
                _t = await _le.get_teachings(instance_id, limit=30)
                user_low = text.lower()
                resp_low = response.lower()
                for t in _t:
                    q = t.get("question", "").lower().replace("[admin enseñó] ", "")
                    a = t.get("answer", "").lower()
                    # Fuzzy: check if root words overlap (horario/hora, atencion/atienden)
                    q_stems = set(w[:4] for w in q.split() if len(w) > 3)
                    user_stems = set(w[:4] for w in user_low.split() if len(w) > 3)
                    if q_stems & user_stems:
                        has_relevant_teaching = True
                        break
                    if a and a[:12] in resp_low:
                        has_relevant_teaching = True
                        break
            except Exception:
                pass

            if confidence < 0.5 and admin_jid and not has_relevant_teaching:
                await uncertainty_detector.log_gap(instance_id, text, response, confidence, chat_id)
                alert_msg = (
                    f"oye, me acaba de escribir un paciente preguntando: \"{text[:150]}\"\n\n"
                    f"no tengo esa info todavía, qué le digo?"
                )
                try:
                    await self.melissa._send_message(admin_jid, alert_msg)
                    log.info(f"[production] admin alerted: confidence={confidence:.2f} question='{text[:50]}'")
                except Exception as e:
                    log.warning(f"[production] failed to alert admin: {e}")

                # Override response: tell patient we're checking (only if no teaching matches)
                response = "dame un momento que verifico eso ||| ya te confirmo"
            elif has_relevant_teaching and confidence < 0.5:
                # We have the answer in teachings but LLM still deflected — don't override
                pass

        except Exception as e:
            log.error(f"[production] uncertainty check FAILED: {e}", exc_info=True)

        # Save to DB
        try:
            db.save_message(chat_id, "user", text)
            db.save_message(chat_id, "assistant", response.replace("|||", " "),
                           model=model_used,
                           latency=int((time.time() - start_time) * 1000))
        except Exception:
            pass

        # Real-time learning from turn
        try:
            from melissa_learning import learning_engine
            await learning_engine.learn_from_turn(instance_id, text, response)
        except Exception:
            pass

        return self.melissa._split_bubbles(response, chat_id=chat_id)
