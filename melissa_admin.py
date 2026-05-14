from __future__ import annotations
import logging
import asyncio
import re
import json
import time
import hashlib
import secrets
import httpx
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

log = logging.getLogger("melissa.admin")

class MelissaAdmin:
    """
    Componente especializado para la Administración de Melissa.
    Maneja Setup, Auth, Comandos de Control y Simulaciones.
    """
    
    def __init__(self, melissa):
        self.melissa = melissa

    async def handle(self, chat_id: str, text: str, clinic: Dict) -> List[str]:
        """Maneja modo admin o setup. Nunca lanza excepcion al exterior."""
        from melissa import (
            db, auth_engine, llm_engine, calendar_bridge, 
            generate_activation_token, notify_omni, _KB_AVAILABLE, SECTORS
        )
        from melissa_utils import _parse_admin_ids, extract_model_request_from_text
        
        learning_engine = self.melissa.admin_learning
        simulation_engine = self.melissa.simulator

        try:
            # Setup inicial — SOLO si el chat_id ya fue autenticado como admin
            if not clinic.get("setup_done"):
                admin_ids = _parse_admin_ids(clinic.get("admin_chat_ids", []))
                is_authenticated_admin = (chat_id in admin_ids or db.get_admin(chat_id) is not None)

                if is_authenticated_admin:
                    return await self._handle_setup(chat_id, text, clinic)
                else:
                    clinic_name = clinic.get("name") or ""
                    if clinic_name:
                        return [f"Hola. En este momento estamos terminando de configurar el sistema. Vuelve pronto."]
                    else:
                        if db.list_admins():
                            return ["Hola. En este momento no estamos disponibles. Vuelve pronto."]
                        else:
                            sector = clinic.get("sector", "otro")
                            sector_name = "negocio"
                            try:
                                sector_name = SECTORS.get(sector, SECTORS["otro"]).name if sector else "negocio"
                            except Exception: pass
                            clinic_name = clinic.get("name") or f"{sector_name} en proceso"
                            return [
                                f"¡Hola! 👋 Bienvenido a {clinic_name}.",
                                "Soy Melissa, la recepcionista virtual.",
                                "Todavía estoy aprendiendo cómo funciona tu negocio. Escribe /configurar y empezamos.",
                            ]

            # Comandos slash
            cmd = text.lower().strip()
            
            if learning_engine and any(s in cmd for s in ["no digas", "usa emojis", "dile que"]):
                return [learning_engine.add_instruction(chat_id, text)]
            
            if simulation_engine and any(s in cmd for s in ["simula", "como cliente"]):
                return simulation_engine.start(chat_id)

            if cmd == "/citas": return await self.melissa._admin_show_appointments()
            if cmd == "/config": return await self.melissa._admin_show_config(clinic)
            if cmd == "/metricas": return await self.melissa._admin_show_metrics()
            if cmd == "/setup": return await self.melissa._restart_setup(chat_id)
            if cmd == "/login":
                db.set_auth_session(chat_id, flow="login", step="email", temp_data={})
                return ["Tu correo electronico de admin?"]
            if cmd == "/logout":
                if auth_engine: return await auth_engine._logout(chat_id)
                return ["Sesion cerrada."]
            if cmd == "/simular":
                if simulation_engine: return simulation_engine.start(chat_id)
                return ["Motor de simulación no disponible."]
            if cmd == "/reporte": return await self.melissa._admin_trigger_report()

            return await self.melissa._admin_natural_command(chat_id, text, clinic)

        except Exception as e:
            log.error(f"Admin handler error: {e}", exc_info=True)
            return ["algo salió mal, intenta de nuevo"]

    async def _handle_setup(self, chat_id: str, text: str, clinic: Dict) -> List[str]:
        from melissa import db
        setup_step   = clinic.get("setup_step", "idle")
        setup_buffer = clinic.get("setup_buffer", {})
        if isinstance(setup_buffer, str):
            setup_buffer = json.loads(setup_buffer) if setup_buffer else {}

        step_names = ["name", "tagline", "services", "schedule", "phone", "pricing"]

        if setup_step == "idle":
            db.update_clinic(setup_step="name")
            return ["¡Hola! Vamos a dejarme lista para tu negocio.", "¿Cómo se llama tu clínica o negocio?"]

        if setup_step == "confirm_discovered":
            if text.lower().strip() in ["si", "ok", "claro"]:
                discovered = setup_buffer.get("discovered", {})
                db.update_clinic(name=discovered.get("name", setup_buffer.get("name")), 
                                tagline=discovered.get("tagline", ""), services=discovered.get("services", []),
                                schedule=discovered.get("schedule", {}), phone=discovered.get("phone", ""),
                                setup_done=1, setup_step="idle", setup_buffer={})
                return [f"Listo. Quede configurada para {discovered.get('name')}."]
            db.update_clinic(setup_step="tagline", setup_buffer=setup_buffer)
            return ["Entendido, vamos manualmente. ¿Tienes un slogan?"]

        if setup_step not in step_names: return ["Escribe /setup para empezar."]
        idx = step_names.index(setup_step)

        if setup_step == "services":
            setup_buffer["services"] = [s.strip().title() for s in text.split(",") if s.strip()]
        else:
            setup_buffer[setup_step] = text.strip()

        if setup_step == "name":
            clinic_name = text.strip()
            discovered  = await self._discover_clinic_from_web(clinic_name)
            if discovered and discovered.get("confidence", 0) >= 0.5:
                setup_buffer["discovered"] = discovered
                setup_buffer["name"] = clinic_name
                db.update_clinic(setup_step="confirm_discovered", setup_buffer=setup_buffer)
                return [f"Encontré info de {clinic_name} en internet.", f"Confirmas estos datos? (si / no)"]
            db.update_clinic(setup_step="tagline", setup_buffer=setup_buffer)
            return self.melissa._setup_next_bubbles("name", text.strip(), "tagline", setup_buffer)

        if idx + 1 < len(step_names):
            next_step = step_names[idx + 1]
            db.update_clinic(setup_step=next_step, setup_buffer=setup_buffer)
            return self.melissa._setup_next_bubbles(setup_step, text.strip(), next_step, setup_buffer)

        db.update_clinic(name=setup_buffer.get("name"), tagline=setup_buffer.get("tagline"),
                        services=setup_buffer.get("services"), schedule=setup_buffer.get("schedule"),
                        phone=setup_buffer.get("phone"), pricing=setup_buffer.get("pricing"),
                        setup_done=1, setup_step="idle", setup_buffer={})
        return ["¡Listo! Ya puedo atender pacientes."]

    async def _discover_clinic_from_web(self, clinic_name: str, city: str = "Medellin") -> Dict:
        from melissa import llm_engine
        try:
            search_query = f"{clinic_name} {city} servicios precios horario telefono"
            snippets = await asyncio.wait_for(self.melissa.search.search(search_query, context=""), timeout=15.0)
            if not snippets: return {}
            prompt = f"Extrae info de {clinic_name} en {city} de estos snippets: {snippets[:1200]}. Retorna SOLO un JSON."
            response, _ = await asyncio.wait_for(llm_engine.complete([{"role": "user", "content": prompt}], model_tier="fast"), timeout=20.0)
            clean = re.sub(r'^```json\s*|\s*```$', '', response.strip())
            return json.loads(clean)
        except Exception: return {}

class AuthEngine:
    """Maneja toda la logica de autenticacion y activacion."""
    MAX_LOGIN_ATTEMPTS = 5

    def is_auth_message(self, chat_id: str, text: str) -> bool:
        from melissa import db
        from melissa_utils import is_activation_token, is_invite_token
        t = text.strip(); t_low = t.lower()
        if ":" in t and "@" in t_low:
            parts = t.split(":")
            if len(parts) >= 2:
                potential_creds = parts[1].strip().split()
                if len(potential_creds) >= 2 and "@" in potential_creds[0]: return True
        session = db.get_auth_session(chat_id)
        if session and session.get("flow") in ("activate", "login", "invite", "register"): return True
        if is_activation_token(t): return db.get_activation_token(t.upper()) is not None
        if is_invite_token(t): return db.get_auth_session(f"invite:{t.upper()}") is not None
        if db.get_admin(chat_id):
            if t_low.startswith("/") or t_low in ("logout", "salir"): return True
        return False

    async def process(self, chat_id: str, text: str) -> List[str]:
        from melissa import db
        from melissa_utils import is_activation_token, is_invite_token
        t = text.strip()
        if ":" in t and "@" in t.lower():
            parts = t.split(":", 1); creds = parts[1].strip().split()
            if len(creds) >= 2 and "@" in creds[0]: return await self._handle_stealth_login(chat_id, creds[0].lower(), creds[1])
        if is_activation_token(t): return await self._start_activation(chat_id, t)
        if is_invite_token(t): return await self._start_invite_registration(chat_id, t)
        session = db.get_auth_session(chat_id)
        if session:
            flow = session.get("flow", "")
            if flow == "activate": return await self._handle_activation_flow(chat_id, t, session)
            if flow == "invite": return await self._handle_invite_flow(chat_id, t, session)
            if flow == "login": return await self._handle_login_flow(chat_id, t, session)
        if db.get_admin(chat_id):
            if t.lower() in ("logout", "salir"): return self._logout(chat_id)
        return []

    async def _handle_stealth_login(self, chat_id: str, email: str, password: str) -> List[str]:
        from melissa import db
        from melissa_utils import verify_password, _parse_admin_ids
        admin = db.get_admin_by_email(email)
        if admin and verify_password(password, admin["password_hash"]):
            db.create_admin(chat_id=chat_id, email=admin["email"], password_hash=admin["password_hash"], name=admin["name"], role=admin["role"])
            db.update_admin_login(chat_id)
            clinic = db.get_clinic(); admin_ids = _parse_admin_ids(clinic.get("admin_chat_ids", []))
            if chat_id not in admin_ids: admin_ids.append(chat_id); db.update_clinic(admin_chat_ids=admin_ids)
            return [f"Hola {admin['name']}. Acceso concedido discretamente."]
        return []

    def _logout(self, chat_id: str) -> List[str]:
        from melissa import db
        from melissa_utils import _parse_admin_ids
        clinic = db.get_clinic(); admin_ids = _parse_admin_ids(clinic.get("admin_chat_ids", []))
        if chat_id in admin_ids: admin_ids.remove(chat_id); db.update_clinic(admin_chat_ids=admin_ids)
        return ["Sesion cerrada."]

    async def _start_activation(self, chat_id: str, token_raw: str) -> List[str]:
        from melissa import db
        token = token_raw.strip().upper(); td = db.get_activation_token(token)
        if not td: return ["Token no válido."]
        db.set_auth_session(chat_id, flow="activate", step="name", temp_data={"token": token})
        return ["Código válido. ¿Cómo te llamas?"]

    async def _handle_activation_flow(self, chat_id: str, text: str, session: Dict) -> List[str]:
        from melissa import db
        from melissa_utils import hash_password
        step, tmp = session["step"], session.get("temp_data", {})
        if step == "name":
            tmp["name"] = text.strip(); db.set_auth_session(chat_id, "activate", "email", tmp)
            return [f"Hola {text}. ¿Tu email?"]
        if step == "email":
            tmp["email"] = text.strip().lower(); db.set_auth_session(chat_id, "activate", "password", tmp)
            return ["Contraseña segura?"]
        if step == "password":
            tmp["password_hash"] = hash_password(text.strip()); db.set_auth_session(chat_id, "activate", "confirm", tmp)
            return ["Confirma registro? (si/no)"]
        if step == "confirm" and text.lower().strip() == "si":
            db.create_admin(chat_id=chat_id, email=tmp["email"], password_hash=tmp["password_hash"], name=tmp["name"], role="owner")
            db.clear_auth_session(chat_id); return ["¡Cuenta creada!"]
        return ["Cancelado."]

    async def _handle_login_flow(self, chat_id: str, text: str, session: Dict) -> List[str]:
        from melissa import db
        from melissa_utils import verify_password, _parse_admin_ids
        step, tmp, attempts = session["step"], session.get("temp_data", {}), session.get("attempts", 0)
        if step == "email":
            email = text.strip().lower(); admin = db.get_admin_by_email(email)
            if not admin: return ["No encontré esa cuenta."]
            tmp["email"] = email; db.set_auth_session(chat_id, "login", "password", tmp, attempts)
            return ["Entendido. ¿Cuál es tu contraseña?"]
        if step == "password":
            email = tmp.get("email", ""); admin = db.get_admin_by_email(email)
            if verify_password(text.strip(), admin["password_hash"]):
                db.create_admin(chat_id=chat_id, email=admin["email"], password_hash=admin["password_hash"], name=admin["name"], role=admin["role"])
                db.update_admin_login(chat_id); db.clear_auth_session(chat_id)
                clinic = db.get_clinic(); admin_ids = _parse_admin_ids(clinic.get("admin_chat_ids", []))
                if chat_id not in admin_ids: admin_ids.append(chat_id); db.update_clinic(admin_chat_ids=admin_ids)
                return [f"Bienvenido de nuevo, {admin['name']}."]
            return ["Contraseña incorrecta."]
        return []

class AdminLearningEngine:
    """Motor de aprendizaje directo por instrucciones del dueño."""
    def __init__(self, database): self.db = database; self._cached_instructions = None
    def add_instruction(self, chat_id: str, text: str) -> str:
        self.db.add_admin_instruction(chat_id, text); self._cached_instructions = None
        return f"Instrucción guardada: '{text}'."
    def get_prompt_injection(self) -> str:
        ins = self.db.get_active_admin_instructions()
        if not ins: return ""
        return "\n## INSTRUCCIONES DEL DUEÑO:\n" + "\n".join([f"- {i}" for i in ins])
    def clear(self) -> str: self.db.clear_admin_instructions(); return "Instrucciones borradas."

class SimulationEngine:
    """Motor de simulaciones interactivas para entrenamiento del admin."""
    def __init__(self, melissa): self.melissa = melissa; self._active_simulations = {}
    def start(self, chat_id: str, scenario: str = "default") -> List[str]:
        self._active_simulations[chat_id] = {"ts": time.time()}; return ["🎮 Simulación activa. Dime algo."]
    def stop(self, chat_id: str) -> List[str]:
        self._active_simulations.pop(chat_id, None); return ["🎮 Simulación finalizada."]
    def is_simulating(self, chat_id: str) -> bool: return chat_id in self._active_simulations
    async def handle_step(self, chat_id: str, text: str) -> List[str]:
        if "salir" in text.lower(): return self.stop(chat_id)
        return await self.melissa.process_message(chat_id, text, is_simulation=True)

class SelfImprovementEngine:
    def __init__(self, llm): self.llm = llm
    async def analyze_performance(self) -> Dict: return {"ok": True}

class TaskManager:
    def __init__(self): self._tasks = {}
    def add_task(self, chat_id: str, kind: str, data: Dict, delay: int = 0): return secrets.token_hex(4)
