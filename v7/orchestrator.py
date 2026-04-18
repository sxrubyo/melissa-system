"""
Melissa V7.0 — Orquestador
============================
Conecta router, memoria, agentes y postprocessor.
melissa.py llama a orchestrator.process() en lugar de generator.generate().
Si algo falla, cae al generator clásico (backward compat).

"todo debe actuar como uno" — el paciente nunca sabe qué agente respondió.
"""

from __future__ import annotations
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any

from v7.router             import router, AgentID, RouterResult
from v7.agents             import build_registry
from v7.agents.base        import AgentContext, AgentResponse
from v7.memory.patient_profile import ProfileStore, PatientProfile, FunnelStage
from v7.postprocess        import postprocess, split_bubbles

log = logging.getLogger(__name__)


class MelissaOrchestrator:
    """
    Orquestador central de Melissa V7.
    Se instancia una vez al arranque de MelissaUltra.
    """

    def __init__(self, llm_engine, db):
        self._agents       = build_registry(llm_engine)
        self._profile_store = ProfileStore(db)
        self._llm          = llm_engine
        self._db           = db
        log.info(
            "[orchestrator] V7 listo. Agentes: %s",
            list(self._agents.keys())
        )

    async def process(
        self,
        chat_id:   str,
        text:      str,
        clinic:    Dict,
        patient:   Dict,
        history:   List[Dict],
        search_context: str = "",
        kb_context:     str = "",
        calendar_info:  str = "",
        is_cron:   bool = False,
        cron_type: Optional[str] = None,
    ) -> List[str]:
        """
        Punto de entrada principal.
        Devuelve lista de burbujas lista para enviar.
        """
        t0 = time.perf_counter()

        # 1. Cargar perfil del paciente
        profile = self._profile_store.load(chat_id)

        # 2. Routing de intención
        route = router.route(
            text=text,
            funnel_state=profile.funnel_stage.value,
            history_length=len(history),
            is_cron=is_cron,
            cron_type=cron_type,
        )

        log.info(
            "[orchestrator] %s → agente=%s confianza=%.2f señales=%s funnel=%s",
            chat_id[:8],
            route.agent_id.value,
            route.confidence,
            route.signals[:2],
            profile.funnel_stage.value,
        )

        # 3. Resolver agente
        agent = self._agents.get(route.agent_id)
        if not agent:
            log.warning("[orchestrator] agente %s no encontrado, usando fallback", route.agent_id)
            return None  # señal para que melissa.py use el generator clásico

        # 4. Ensamblar contexto mínimo
        ctx = self._build_context(
            chat_id=chat_id,
            text=text,
            clinic=clinic,
            profile=profile,
            history=history,
            context_keys=route.context_keys,
            search_context=search_context,
            kb_context=kb_context,
            calendar_info=calendar_info,
            cron_metadata={"follow_up_reason": cron_type} if is_cron else {},
        )

        # 5. Ejecutar agente
        response: AgentResponse = await agent.run(ctx)

        # 6. Actualizar memoria (async, no bloquea la respuesta)
        asyncio.create_task(
            self._update_memory(profile, response, route)
        )

        # 7. Si el agente detectó escalación a humano → notificar
        if response.next_agent == "human":
            asyncio.create_task(
                self._notify_escalation(chat_id, text, clinic)
            )

        latency = (time.perf_counter() - t0) * 1000
        log.info(
            "[orchestrator] %s completado en %.0fms (agente=%.0fms)",
            chat_id[:8], latency, response.latency_ms
        )

        return response.bubbles

    # ── Ensamblado de contexto ────────────────────────────────────────────────

    def _build_context(
        self,
        chat_id:      str,
        text:         str,
        clinic:       Dict,
        profile:      PatientProfile,
        history:      List[Dict],
        context_keys: List[str],
        search_context: str,
        kb_context:   str,
        calendar_info: str,
        cron_metadata: Dict,
    ) -> AgentContext:
        """
        Ensambla SOLO los campos que el agente declaró necesitar.
        Clave para mantener el prompt corto.
        """
        # Tone detection
        clinic_tone = self._detect_tone(clinic)

        # Servicios en texto compacto
        servicios_raw = clinic.get("services", [])
        if isinstance(servicios_raw, list):
            servicios = ", ".join(
                s.get("name", "") if isinstance(s, dict) else str(s)
                for s in servicios_raw[:8]
            )
        else:
            servicios = str(servicios_raw)[:200]

        return AgentContext(
            chat_id=chat_id,
            text=text,
            platform=str(clinic.get("platform") or "whatsapp"),
            patient_summary=profile.to_context_summary(context_keys),
            funnel_stage=profile.funnel_stage.value,
            patient_name=profile.nombre,
            visits=profile.visitas,
            objeciones_pasadas=profile.objeciones_pasadas,
            clinic_name=clinic.get("name", ""),
            clinic_tone=clinic_tone,
            clinic_kb=kb_context[:500] if kb_context else "",
            servicios=servicios,
            precios=self._extract_pricing(clinic)[:300],
            history=history[-8:],
            search_context=search_context[:400] if search_context else "",
            calendar_info=calendar_info,
            metadata=cron_metadata,
        )

    def _detect_tone(self, clinic: Dict) -> str:
        name = clinic.get("name", "").lower()
        ctx  = clinic.get("description", "").lower()
        combined = name + " " + ctx

        _premium_words = [
            "hospital","las américas","pablo tobón","tobon","country",
            "bocagrande","fundación","fundacion","universitario","cardiovascular",
            "premium","internacional","vip","élite","elite",
        ]
        _health_words = [
            "clínica","clinica","médico","medico","salud","consultorio",
            "odontología","dental","psicología","terapia","estetica","estética",
        ]
        _retail_words = [
            "tienda","almacén","almacen","muebles","ropa","calzado",
            "restaurante","cafetería","ferretería",
        ]

        is_health   = any(w in combined for w in _health_words)
        is_premium  = any(w in combined for w in _premium_words)
        is_retail   = any(w in combined for w in _retail_words)

        if is_health and is_premium:
            return "SALUD PREMIUM"
        elif is_health:
            return "SALUD"
        elif is_premium:
            return "PREMIUM"
        elif is_retail:
            return "RETAIL"
        return "GENERAL"

    def _extract_pricing(self, clinic: Dict) -> str:
        pricing = clinic.get("pricing", {})
        if not pricing:
            return ""
        if isinstance(pricing, dict):
            lines = [f"{k}: {v}" for k, v in list(pricing.items())[:5]]
            return "\n".join(lines)
        return str(pricing)[:300]

    # ── Actualización de memoria ──────────────────────────────────────────────

    async def _update_memory(
        self,
        profile:  PatientProfile,
        response: AgentResponse,
        route:    RouterResult,
    ) -> None:
        """Actualiza el perfil del paciente con lo aprendido en este turno."""
        try:
            changed = False

            if response.funnel_update:
                try:
                    new_stage = FunnelStage(response.funnel_update)
                    if profile.advance_funnel(new_stage):
                        changed = True
                except ValueError:
                    pass

            if response.new_objecion:
                profile.add_objecion(response.new_objecion)
                changed = True

            if response.learned_name:
                profile.nombre = response.learned_name
                changed = True

            if response.learned_zona:
                profile.add_zona(response.learned_zona)
                changed = True

            if changed:
                self._profile_store.save(profile)

        except Exception as e:
            log.warning("[orchestrator] error actualizando memoria: %s", e)

    async def _notify_escalation(
        self, chat_id: str, text: str, clinic: Dict
    ) -> None:
        """Notifica a los admins cuando se detecta escalación."""
        try:
            admin_ids = clinic.get("admin_chat_ids", [])
            if isinstance(admin_ids, str):
                import json
                admin_ids = json.loads(admin_ids) if admin_ids else []
            clinic_name = clinic.get("name", "la clínica")
            msg = (
                f"ESCALACIÓN detectada en {clinic_name}\n"
                f"Paciente: {chat_id}\n"
                f"Mensaje: {text[:150]}"
            )
            log.warning("[escalacion] %s", msg)
            # El envío real lo hace melissa.py con _send_message
            # Aquí solo dejamos el log — el handler de escalación ya respondió al paciente
        except Exception as e:
            log.warning("[orchestrator] error en notify_escalation: %s", e)
