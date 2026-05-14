from __future__ import annotations
import logging
import asyncio
import re
import json
import time
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("melissa.production")

class MelissaProduction:
    """
    Componente especializado para la Producción (Atención a Pacientes).
    Maneja el flujo principal de conversación, razonamiento y respuesta.
    """
    
    def __init__(self, melissa):
        self.melissa = melissa

    async def handle(self, chat_id: str, text: str, clinic: Dict, 
                    history: List[Dict], conv_state: Dict) -> List[str]:
        """Procesa un mensaje de paciente real."""
        from melissa import (
            db, UrgencyLevel, kb, _analysis_to_dict, v8_process_response
        )
        
        analyzer = self.melissa.analyzer
        reasoning_engine = self.melissa.reasoning
        generator = self.melissa.generator

        start_time = time.time()
        patient = db.get_patient(chat_id)
        
        # 1. Análisis del mensaje
        analysis = analyzer.analyze(text, history)

        # 2. Contextos de búsqueda y KB
        search_context = ""
        kb_context = ""
        if kb and kb.has_content():
            kb_context = kb.query(text)
        
        # 3. Razonamiento (Brain)
        reasoning = await reasoning_engine.reason(text, analysis, clinic, history, conv_state)

        # 4. Generación de respuesta
        response = await generator.generate(
            text, analysis, reasoning, clinic, patient, history, 
            search_context=search_context, kb_context=kb_context, chat_id=chat_id
        )

        # 5. Normalización para primer turno si está vacío
        if not any(msg.get("role") == "assistant" for msg in history) and not str(response or "").strip():
            response = generator._normalize_first_patient_turn(
                response="", clinic=clinic, personality=generator._get_default_personality(clinic),
                user_msg=text, history=history
            )

        # 6. Post-procesamiento humano
        bubbles = self.melissa._split_bubbles(response, chat_id=chat_id)
        
        # 7. Guardado y métricas
        await self._save_and_record(chat_id, text, response, analysis, conv_state, start_time, getattr(generator.llm, "last_model", "llm"))
        
        return bubbles

    async def _save_and_record(self, chat_id, text, response, analysis, conv_state, start_time, model):
        from melissa import db, _analysis_to_dict
        db.save_message(chat_id, "user", text, analysis=self.melissa._analysis_to_dict(analysis))
        db.save_message(chat_id, "assistant", response, model=model, latency=int((time.time() - start_time) * 1000))
        conv_state.turn_count += 1
        db.save_conversation_state(conv_state)
        db.record_metric("conversation", "response_time", (time.time() - start_time) * 1000)
        db.record_metric("conversation", "intent", 1, {"intent": analysis.intent.name})
