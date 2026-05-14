from __future__ import annotations
import logging
import json
import time
import hashlib
import secrets
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

log = logging.getLogger("melissa.admin")

SOUL_DIR = Path("soul")


class MelissaAdmin:
    """
    Melissa como empleada nueva hablando con su jefe.
    Aprende activamente: pregunta sobre el negocio, pide practicar,
    investiga por su cuenta, y recuerda TODO.
    """

    def __init__(self, melissa):
        self.melissa = melissa

    async def handle(self, chat_id: str, text: str, clinic: Dict,
                    attachments: Optional[List[Dict]] = None) -> List[str]:
        """Conversación inteligente con el admin via LLM."""
        from melissa import db, llm_engine
        from melissa_utils import _parse_admin_ids
        from melissa_commands import get_command_handler
        attachments = attachments or []

        try:
            # Process attachments (docs, credentials, knowledge files)
            doc_content = await self._process_admin_attachments(
                attachments, chat_id, getattr(self.melissa, "_instance_id", "default")
            )
            if doc_content:
                text = f"{text}\n\n[CONTENIDO DE ARCHIVOS ADJUNTOS]\n{doc_content}" if text.strip() else doc_content

            # Comandos slash primero
            if text.strip().startswith("/"):
                cmd_handler = get_command_handler(getattr(self.melissa, "_instance_id", "default"))
                result = await cmd_handler.handle(chat_id, text, is_admin=True, clinic=clinic, db=db)
                if result:
                    return result

            # Google OAuth code detection
            try:
                from melissa_google_auth import is_oauth_code, exchange_code_for_tokens, get_oauth_url
                instance_id_auth = getattr(self.melissa, "_instance_id", "default")
                # Admin sends OAuth code
                if is_oauth_code(text.strip()):
                    tokens = await exchange_code_for_tokens(text.strip(), instance_id_auth)
                    if tokens:
                        return ["✅ Calendario de Google conectado exitosamente!", "Ya puedo ver disponibilidad y agendar citas directamente."]
                    else:
                        return ["❌ El código no funcionó. Puede que haya expirado.", "Escribe 'conectar calendario' y te genero uno nuevo."]
                # Admin asks to connect calendar
                cal_triggers = ["conectar calendario", "google calendar", "vincular calendario", "enlace oauth", "conectar google"]
                if any(t in text.lower() for t in cal_triggers):
                    url = get_oauth_url(instance_id_auth)
                    if url:
                        return [
                            "Listo! Abre este enlace en tu navegador:",
                            url,
                            "Inicia sesión con la cuenta de Google del negocio, acepta los permisos, y pégame aquí el código que te aparece."
                        ]
                    else:
                        return ["Para conectar Google Calendar necesito que configures GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET en el .env"]
            except ImportError:
                pass

            # Setup pendiente
            if not clinic.get("setup_done"):
                return await self._handle_setup(chat_id, text, clinic)

            # Conversación natural con el admin via LLM
            return await self._admin_conversation(chat_id, text, clinic, db, llm_engine)

        except Exception as e:
            log.error(f"Admin handler error: {e}", exc_info=True)
            # Fallback LLM directo
            try:
                from melissa import llm_engine as _llm
                if _llm:
                    r, _ = await _llm.complete(
                        [{"role": "system", "content": "Eres Melissa, recepcionista nueva. Responde brevemente al dueño."},
                         {"role": "user", "content": text}],
                        model_tier="fast", temperature=0.8, max_tokens=200, use_cache=False)
                    if r and r.strip():
                        return self.melissa._split_bubbles(r, chat_id=chat_id)
            except Exception:
                pass
            return ["perdona, me trabé un momento ||| qué me decías?"]

    async def _admin_conversation(self, chat_id: str, text: str, clinic: Dict, db, llm_engine) -> List[str]:
        """Conversación real con el dueño como empleada nueva inteligente."""
        if not llm_engine:
            return ["cuéntame más sobre el negocio, estoy aprendiendo"]

        instance_id = getattr(self.melissa, "_instance_id", "default")
        clinic_name = clinic.get("name", "tu negocio")
        history = db.get_history(chat_id) if db else []

        # Cargar historial de pacientes recientes (para que admin sepa quién escribió)
        recent_patients_summary = self._get_recent_patients_summary(db, chat_id)

        # Cargar alma/memoria del negocio
        soul_context = self._load_soul(instance_id)
        teachings_context = self._load_teachings(instance_id)

        # Auto-investigar si el admin pide o si Melissa necesita info
        web_research = ""
        research_triggers = ["investiga", "busca", "google", "averigua", "informate", "infórmate", "buscar"]
        if any(t in text.lower() for t in research_triggers) or (
            not soul_context and clinic_name and clinic_name != "tu negocio"
        ):
            try:
                from melissa_web_search import search_business
                web_research = await search_business(clinic_name)
                if web_research:
                    self._append_soul(instance_id, f"[investigación web] {web_research[:500]}")
                    soul_context = self._load_soul(instance_id)
            except Exception as e:
                log.debug(f"[admin] web search failed: {e}")

        # Determinar nivel de conocimiento
        knowledge_level = self._assess_knowledge_level(soul_context, teachings_context, clinic)

        sys_prompt = f"""Eres Melissa, una empleada NUEVA que acaba de ser contratada como recepcionista virtual de {clinic_name}.

SITUACIÓN ACTUAL:
- Estás hablando con tu JEFE (el dueño del negocio)
- Llevas poco tiempo y estás aprendiendo cómo funciona todo
- Tu actitud es: proactiva, curiosa, respetuosa pero cercana, con ganas de aprender
- NO eres un bot, eres una persona nueva en el equipo

{"NIVEL: Ya sé bastante del negocio. Puedo operar con confianza." if knowledge_level == "ready" else "NIVEL: Todavía estoy aprendiendo. Necesito que me enseñes más." if knowledge_level == "learning" else "NIVEL: Soy nueva. Necesito conocer TODO sobre el negocio."}

ACTIVIDAD RECIENTE (pacientes que me han escrito):
{recent_patients_summary if recent_patients_summary else "Nadie me ha escrito todavía."}

{"INVESTIGACIÓN WEB RECIENTE:" + chr(10) + web_research if web_research else ""}

LO QUE YA SÉ DEL NEGOCIO:
{soul_context if soul_context else "Casi nada todavía. Necesito que me cuentes."}

{f"LO QUE ME HAN ENSEÑADO:{chr(10)}{teachings_context}" if teachings_context else ""}

COMPORTAMIENTO OBLIGATORIO:
1. Si el dueño te saluda → responde cálida y pregunta algo útil sobre el negocio que NO sepas
2. Si te enseña algo nuevo → confirma que entendiste, repite con tus palabras, y pide más detalles
3. Si no sabes algo → ADMÍTELO y pregunta: "eso no lo tengo claro, me explicas?"
4. SIEMPRE termina con una pregunta o propuesta proactiva:
   - "¿quieres que practiquemos cómo respondo a un paciente?"
   - "¿me cuentas los precios así los tengo listos?"
   - "¿hay algo que NUNCA deba decirle a un paciente?"
5. Si ya tienes suficiente info → ofrece simular: "¿hacemos una prueba? Escríbeme como si fueras un paciente"
6. NUNCA respondas como si fueras un bot de servicio al cliente
7. NUNCA digas "como IA", "no tengo capacidad", "asistente virtual"
8. Usa máximo 2-3 burbujas (separadas por |||)
9. Tono: colombiana, directa, con chispa pero profesional

COSAS QUE DEBES PREGUNTAR PROACTIVAMENTE (si no las sabes):
- Servicios y precios
- Horarios de atención
- Cómo manejar urgencias
- Qué palabras NUNCA usar con pacientes
- Especialidades o doctores
- Cómo agendar citas (manual o calendario)
- Datos de contacto para escalar
- Políticas de cancelación
- Qué hace a este negocio diferente de la competencia

EJEMPLO DE BUENA RESPUESTA:
Dueño: "Hola"
Melissa: "Hola! Qué bueno verte ||| oye, todavía no tengo claros los precios de las consultas — me los pasas? así no me quedo en blanco si un paciente pregunta"

EJEMPLO MALO:
"Hola, bienvenido a Clínica X, en qué te puedo ayudar?" ← NUNCA responder así al DUEÑO"""

        messages = [{"role": "system", "content": sys_prompt}]
        for m in history[-15:]:
            messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        messages.append({"role": "user", "content": text})

        try:
            response, meta = await llm_engine.complete(
                messages, model_tier="fast", temperature=0.82,
                max_tokens=2048, use_cache=False,
            )
            log.info(f"[admin] {meta.get('provider','?')} latency={meta.get('latency_ms',0)}ms")
        except Exception as e:
            log.error(f"[admin] LLM error: {e}")
            response = "perdona, se me fue la señal un momento ||| qué me decías?"

        if not response or not response.strip():
            response = "cuéntame más, estoy tomando nota de todo"

        # Guardar en historial
        try:
            db.save_message(chat_id, "user", text)
            db.save_message(chat_id, "assistant", response.replace("|||", " "))
        except Exception:
            pass

        # Auto-aprender de lo que el admin dice
        await self._auto_learn(instance_id, text, response, chat_id)

        from melissa import v8_process_response
        # Strip ** (WhatsApp uses single * for bold, not **)
        import re as _re
        response = _re.sub(r'\*\*(.+?)\*\*', r'*\1*', response)
        response = _re.sub(r'`(.+?)`', r'\1', response)
        response = _re.sub(r'^#+\s*', '', response, flags=_re.MULTILINE)
        response = v8_process_response(response, chat_id=chat_id)
        return self.melissa._split_bubbles(response, chat_id=chat_id)

    async def _auto_learn(self, instance_id: str, admin_text: str, bot_response: str, chat_id: str):
        """Extraer conocimiento y APLICAR cambios de personalidad en tiempo real."""
        text_low = admin_text.lower()

        # ── Detectar URLs y scrapear contenido ──
        import re as _re
        urls = _re.findall(r'https?://[^\s<>"\']+', admin_text)
        if urls:
            try:
                import httpx
                for url in urls[:2]:
                    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                        if r.status_code == 200:
                            # Extract text from HTML
                            html = r.text[:10000]
                            # Simple HTML text extraction
                            text_only = _re.sub(r'<script[^>]*>.*?</script>', '', html, flags=_re.S)
                            text_only = _re.sub(r'<style[^>]*>.*?</style>', '', text_only, flags=_re.S)
                            text_only = _re.sub(r'<[^>]+>', ' ', text_only)
                            text_only = _re.sub(r'\s+', ' ', text_only).strip()[:3000]
                            if text_only:
                                self._append_soul(instance_id, f"[web: {url}]\n{text_only[:1500]}")
                                log.info(f"[admin] scraped URL: {url} ({len(text_only)} chars)")
            except Exception as e:
                log.debug(f"[admin] URL scrape failed: {e}")

        # ── Detectar REGLAS del admin ("si preguntan X, pregúntame") ──
        rule_signals = [
            "si preguntan", "si alguien pregunta", "cuando pregunten",
            "si te preguntan", "me mandas mensaje", "me avisas",
            "pregúntame primero", "consultame primero", "no respondas sin",
            "a partir de ahora", "desde ahora", "de ahora en adelante",
        ]
        if any(signal in text_low for signal in rule_signals):
            try:
                rules_file = Path(f"soul/{instance_id}/admin_rules.json")
                rules_file.parent.mkdir(parents=True, exist_ok=True)
                rules = json.loads(rules_file.read_text()) if rules_file.exists() else []
                rules.append({
                    "topic": admin_text[:200],
                    "action": "consultar al admin antes de responder",
                    "created": datetime.now().isoformat(),
                    "admin_id": chat_id,
                })
                rules_file.write_text(json.dumps(rules, ensure_ascii=False, indent=2))
                self._append_soul(instance_id, f"[REGLA ADMIN] {admin_text[:200]}")
                log.info(f"[admin] new rule saved: {admin_text[:60]}")
            except Exception as e:
                log.debug(f"[admin] rule save error: {e}")

        # ── Detectar cambios de PERSONALIDAD y aplicarlos persistentemente ──
        personality_signals = [
            "modo luxury", "modo formal", "modo informal", "modo casual",
            "modo profesional", "modo alegre", "modo serio", "modo cálido",
            "personalidad", "cambia tu tono", "habla más", "sé más",
            "no seas tan", "quiero que seas", "actúa como", "tono",
            "luxury", "elegante", "sofisticada", "exclusiva",
        ]
        if any(signal in text_low for signal in personality_signals):
            try:
                detected_tone = self._detect_tone_from_text(text_low)
                if detected_tone:
                    override_path = Path(f"personas/{instance_id}/runtime_override.json")
                    override_path.parent.mkdir(parents=True, exist_ok=True)
                    existing = json.loads(override_path.read_text()) if override_path.exists() else {}
                    existing["tone"] = detected_tone
                    existing["updated_at"] = datetime.now().isoformat()
                    existing["set_by"] = "admin_conversation"
                    override_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
                    self._append_soul(instance_id, f"[PERSONALIDAD CAMBIADA] Tono: {detected_tone}. El admin pidió: {admin_text[:100]}")
                    log.info(f"[admin] personality changed to: {detected_tone}")
            except Exception as e:
                log.debug(f"[admin] personality change error: {e}")

        # ── Detectar enseñanzas (precios, servicios, reglas) ──
        teaching_signals = [
            "cuesta", "vale", "precio", "cobra", "$",
            "horario", "abrimos", "cerramos", "atendemos",
            "servicio", "ofrecemos", "hacemos", "tenemos",
            "nunca digas", "no le digas", "no menciones",
            "doctor", "especialista", "profesional",
            "dirección", "ubicación", "estamos en",
            "teléfono", "número", "celular", "llamar",
        ]

        if any(signal in text_low for signal in teaching_signals):
            try:
                from melissa_learning import learning_engine
                await learning_engine.learn_from_admin(
                    instance_id,
                    question=f"[admin enseñó] {admin_text[:200]}",
                    answer=admin_text[:500],
                    admin_id=chat_id,
                )
                self._append_soul(instance_id, admin_text)
            except Exception as e:
                log.debug(f"[admin] auto_learn error: {e}")

    def _detect_tone_from_text(self, text_low: str) -> Optional[str]:
        """Detect requested tone from admin message."""
        # Order matters: check longer/specific keywords FIRST
        checks = [
            ("informal", "casual"),
            ("casual", "casual"),
            ("relajada", "casual"),
            ("parche", "casual"),
            ("luxury", "luxury"),
            ("elegante", "luxury"),
            ("sofisticada", "luxury"),
            ("exclusiva", "luxury"),
            ("profesional", "formal"),
            ("formal", "formal"),
            ("serio", "formal"),
            ("alegre", "warm_energetic"),
            ("cálida", "colombian_warm"),
            ("calida", "colombian_warm"),
            ("colombiana", "colombian_warm"),
        ]
        for keyword, tone in checks:
            if keyword in text_low:
                return tone
        return None

    async def _process_admin_attachments(self, attachments: List[Dict], chat_id: str, instance_id: str) -> str:
        """Process files sent by admin — extract text and learn from them."""
        if not attachments:
            return ""
        import base64 as _b64
        extracted_parts = []
        for att in attachments:
            kind = att.get("kind", "")
            mime = att.get("mime_type", "")
            filename = att.get("filename", "file")

            # Get binary content
            raw = att.get("bytes") or b""
            if not raw and att.get("base64"):
                raw = _b64.b64decode(att["base64"])
            if not raw and att.get("file_id") and att.get("platform") == "telegram":
                try:
                    raw, _ = await self.melissa._download_telegram_binary(att["file_id"])
                except Exception:
                    pass
            if not raw and att.get("media_id") and att.get("platform") == "whatsapp_cloud":
                try:
                    raw, _, _ = await self.melissa._download_whatsapp_cloud_binary(att["media_id"])
                except Exception:
                    pass

            if not raw:
                continue

            # Extract text based on file type
            text_content = ""
            if "pdf" in mime or filename.endswith(".pdf"):
                try:
                    import pdfplumber, io
                    with pdfplumber.open(io.BytesIO(raw)) as pdf:
                        pages = [p.extract_text() or "" for p in pdf.pages[:20]]
                        text_content = "\n".join(filter(None, pages))[:5000]
                except Exception:
                    text_content = raw.decode("utf-8", errors="ignore")[:5000]
            elif "json" in mime or filename.endswith(".json"):
                text_content = raw.decode("utf-8", errors="ignore")[:5000]
            elif "text" in mime or filename.endswith((".txt", ".md", ".csv")):
                text_content = raw.decode("utf-8", errors="ignore")[:5000]
            else:
                try:
                    text_content = raw.decode("utf-8", errors="ignore")[:3000]
                except Exception:
                    continue

            if text_content.strip():
                extracted_parts.append(f"[{filename}]\n{text_content.strip()}")
                log.info(f"[admin] processed attachment: {filename} ({len(text_content)} chars)")

                # Auto-configure Google credentials if detected
                is_credential_file = "client_id" in text_content and "client_secret" in text_content
                is_secret = "private_key" in text_content or "api_key" in text_content.lower()

                if is_credential_file:
                    await self._auto_configure_google(text_content, instance_id)
                    self._append_soul(instance_id, f"[archivo: {filename}] Credenciales de Google recibidas y configuradas.")
                elif is_secret:
                    # NEVER save secrets/keys to soul — only to vault
                    creds_dir = Path(f"integrations/vault/{instance_id}")
                    creds_dir.mkdir(parents=True, exist_ok=True)
                    (creds_dir / filename).write_text(text_content)
                    self._append_soul(instance_id, f"[archivo: {filename}] API key/credencial guardada en vault (no expuesta).")
                else:
                    # Normal knowledge file — safe to save to soul
                    self._append_soul(instance_id, f"[archivo: {filename}]\n{text_content[:1000]}")

        return "\n\n".join(extracted_parts) if extracted_parts else ""

    async def _auto_configure_google(self, json_text: str, instance_id: str):
        """Auto-extract Google OAuth creds from JSON and configure .env + generate OAuth URL."""
        try:
            data = json.loads(json_text)
            # Handle both "installed" and "web" credential formats
            creds = data.get("installed") or data.get("web") or data
            client_id = creds.get("client_id", "")
            client_secret = creds.get("client_secret", "")
            if not client_id or not client_secret:
                return

            # Save credentials file
            creds_dir = Path(f"integrations/vault/{instance_id}")
            creds_dir.mkdir(parents=True, exist_ok=True)
            (creds_dir / "google_credentials.json").write_text(json_text)

            # Update .env
            env_path = Path(f"/home/ubuntu/melissa-instances/{instance_id}/.env")
            if not env_path.exists():
                env_path = Path(".env")
            if env_path.exists():
                env_content = env_path.read_text()
                if "GOOGLE_CLIENT_ID" not in env_content:
                    env_content += f"\n\n# Google Calendar (auto-configured)\nGOOGLE_CLIENT_ID={client_id}\nGOOGLE_CLIENT_SECRET={client_secret}\nGOOGLE_REDIRECT_URI=urn:ietf:wg:oauth:2.0:oob\n"
                    env_path.write_text(env_content)

            # Set env vars for current process
            import os
            os.environ["GOOGLE_CLIENT_ID"] = client_id
            os.environ["GOOGLE_CLIENT_SECRET"] = client_secret
            log.info(f"[admin] Google credentials auto-configured for {instance_id}")
        except Exception as e:
            log.warning(f"[admin] auto-configure Google failed: {e}")

    def _get_recent_patients_summary(self, db, admin_chat_id: str) -> str:
        """Get summary of recent patient conversations (excluding admin)."""
        try:
            import sqlite3
            with db._conn() as c:
                rows = c.execute("""
                    SELECT chat_id, content, role
                    FROM conversations
                    WHERE chat_id != ? AND role = 'user'
                    ORDER BY id DESC LIMIT 20
                """, (admin_chat_id,)).fetchall()
            if not rows:
                return ""
            # Group by chat_id
            patients = {}
            for row in rows:
                cid = row[0] if isinstance(row, tuple) else row["chat_id"]
                content = row[1] if isinstance(row, tuple) else row["content"]
                if cid not in patients:
                    patients[cid] = []
                patients[cid].append(content[:100])

            lines = []
            for cid, msgs in list(patients.items())[:5]:
                short_id = cid.split("@")[0][-4:] if "@" in cid else cid[-4:]
                first_msg = msgs[0] if msgs else "?"
                lines.append(f"- Paciente ...{short_id}: \"{first_msg[:80]}\" ({len(msgs)} msgs)")
            return "\n".join(lines)
        except Exception:
            return ""

    def _load_soul(self, instance_id: str) -> str:
        """Cargar el 'alma' — todo lo que Melissa sabe del negocio."""
        soul_file = SOUL_DIR / instance_id / "knowledge.md"
        if soul_file.exists():
            content = soul_file.read_text()
            return content[-3000:] if len(content) > 3000 else content

        # Fallback: cargar de teachings
        teachings_file = Path("teachings") / f"{instance_id}.jsonl"
        if teachings_file.exists():
            lines = teachings_file.read_text().splitlines()[-20:]
            teachings = []
            for line in lines:
                try:
                    t = json.loads(line)
                    teachings.append(f"- {t.get('answer', t.get('question', ''))[:150]}")
                except Exception:
                    continue
            return "\n".join(teachings) if teachings else ""
        return ""

    def _append_soul(self, instance_id: str, new_knowledge: str):
        """Agregar nuevo conocimiento al alma."""
        soul_dir = SOUL_DIR / instance_id
        soul_dir.mkdir(parents=True, exist_ok=True)
        soul_file = soul_dir / "knowledge.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(soul_file, "a") as f:
            f.write(f"\n[{timestamp}] {new_knowledge[:500]}\n")

    def _load_teachings(self, instance_id: str) -> str:
        """Cargar enseñanzas del admin."""
        teachings_file = Path("teachings") / f"{instance_id}.jsonl"
        if not teachings_file.exists():
            return ""
        lines = teachings_file.read_text().splitlines()[-10:]
        result = []
        for line in lines:
            try:
                t = json.loads(line)
                q = t.get("question", "")
                a = t.get("answer", "")
                if a and not q.startswith("[admin"):
                    result.append(f"- P: {q[:80]} → R: {a[:100]}")
                elif a:
                    result.append(f"- {a[:150]}")
            except Exception:
                continue
        return "\n".join(result)

    def _assess_knowledge_level(self, soul: str, teachings: str, clinic: Dict) -> str:
        """Evaluar cuánto sabe Melissa del negocio."""
        total_knowledge = len(soul) + len(teachings)
        has_services = bool(clinic.get("services"))
        has_schedule = bool(clinic.get("schedule"))
        has_phone = bool(clinic.get("phone"))

        if total_knowledge > 2000 and has_services and has_schedule:
            return "ready"
        elif total_knowledge > 500 or has_services:
            return "learning"
        return "new"

    async def _handle_setup(self, chat_id: str, text: str, clinic: Dict) -> List[str]:
        from melissa import db
        setup_step = clinic.get("setup_step", "idle")
        setup_buffer = clinic.get("setup_buffer", {})
        if isinstance(setup_buffer, str):
            setup_buffer = json.loads(setup_buffer) if setup_buffer else {}

        step_names = ["name", "tagline", "services", "schedule", "phone", "pricing"]

        if setup_step == "idle":
            db.update_clinic(setup_step="name")
            return ["Hola! Soy Melissa, tu recepcionista nueva", "Cuéntame, cómo se llama tu negocio?"]

        if setup_step == "confirm_discovered":
            if text.lower().strip() in ["si", "ok", "claro"]:
                discovered = setup_buffer.get("discovered", {})
                db.update_clinic(name=discovered.get("name", setup_buffer.get("name")),
                                tagline=discovered.get("tagline", ""), services=discovered.get("services", []),
                                schedule=discovered.get("schedule", {}), phone=discovered.get("phone", ""),
                                setup_done=1, setup_step="idle", setup_buffer={})
                return [f"Listo, ya tengo la info de {discovered.get('name')}.", "Ahora cuéntame más — qué servicios son los más importantes?"]
            db.update_clinic(setup_step="tagline", setup_buffer=setup_buffer)
            return ["Ok vamos manual. Tienes algún slogan o frase de marca?"]

        if setup_step not in step_names:
            return ["Escribe /setup para empezar de nuevo."]
        idx = step_names.index(setup_step)

        if setup_step == "services":
            setup_buffer["services"] = [s.strip().title() for s in text.split(",") if s.strip()]
        else:
            setup_buffer[setup_step] = text.strip()

        if setup_step == "name":
            setup_buffer["name"] = text.strip()
            db.update_clinic(setup_step="services", setup_buffer=setup_buffer, name=text.strip())
            return [f"Anotado: {text.strip()}", "Qué servicios ofrecen? (ponlos separados por coma)"]

        if idx + 1 < len(step_names):
            next_step = step_names[idx + 1]
            prompts = {
                "tagline": "Tienes slogan?",
                "services": "Servicios (separados por coma)?",
                "schedule": "Horario de atención?",
                "phone": "Teléfono de contacto?",
                "pricing": "Rango de precios? (puede ser aproximado)",
            }
            db.update_clinic(setup_step=next_step, setup_buffer=setup_buffer)
            return [f"Perfecto, anotado", prompts.get(next_step, "Siguiente?")]

        db.update_clinic(name=setup_buffer.get("name"), tagline=setup_buffer.get("tagline"),
                        services=setup_buffer.get("services"), schedule=setup_buffer.get("schedule"),
                        phone=setup_buffer.get("phone"), pricing=setup_buffer.get("pricing"),
                        setup_done=1, setup_step="idle", setup_buffer={})
        return ["Listo! Ya tengo lo básico para arrancar", "Ahora cuéntame más libremente — precios, cosas que no deba decir, etc. Todo me sirve"]


class AuthEngine:
    """Autenticacion y activacion."""
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
            if flow == "login": return await self._handle_login_flow(chat_id, t, session)
        return []

    async def _handle_stealth_login(self, chat_id: str, email: str, password: str) -> List[str]:
        from melissa import db
        from melissa_utils import verify_password, _parse_admin_ids
        admin = db.get_admin_by_email(email)
        if admin and verify_password(password, admin["password_hash"]):
            db.create_admin(chat_id=chat_id, email=admin["email"], password_hash=admin["password_hash"], name=admin["name"], role=admin["role"])
            clinic = db.get_clinic(); admin_ids = _parse_admin_ids(clinic.get("admin_chat_ids", []))
            if chat_id not in admin_ids: admin_ids.append(chat_id); db.update_clinic(admin_chat_ids=admin_ids)
            return [f"Hola {admin['name']}. Ya te reconozco."]
        return []

    async def _start_activation(self, chat_id: str, token_raw: str) -> List[str]:
        from melissa import db
        token = token_raw.strip().upper(); td = db.get_activation_token(token)
        if not td: return ["Token no válido."]
        db.set_auth_session(chat_id, flow="activate", step="name", temp_data={"token": token})
        return ["Código válido. Cómo te llamas?"]

    async def _handle_activation_flow(self, chat_id: str, text: str, session: Dict) -> List[str]:
        from melissa import db
        from melissa_utils import hash_password
        step, tmp = session["step"], session.get("temp_data", {})
        if step == "name":
            tmp["name"] = text.strip(); db.set_auth_session(chat_id, "activate", "email", tmp)
            return [f"Hola {text}. Tu email?"]
        if step == "email":
            tmp["email"] = text.strip().lower(); db.set_auth_session(chat_id, "activate", "password", tmp)
            return ["Elige una contraseña segura"]
        if step == "password":
            tmp["password_hash"] = hash_password(text.strip()); db.set_auth_session(chat_id, "activate", "confirm", tmp)
            return ["Confirmas? (si/no)"]
        if step == "confirm" and text.lower().strip() == "si":
            db.create_admin(chat_id=chat_id, email=tmp["email"], password_hash=tmp["password_hash"], name=tmp["name"], role="owner")
            db.clear_auth_session(chat_id); return ["Listo, cuenta creada. Ahora cuéntame del negocio"]
        return ["Cancelado."]

    async def _handle_login_flow(self, chat_id: str, text: str, session: Dict) -> List[str]:
        from melissa import db
        from melissa_utils import verify_password, _parse_admin_ids
        step, tmp = session["step"], session.get("temp_data", {})
        if step == "email":
            email = text.strip().lower(); admin = db.get_admin_by_email(email)
            if not admin: return ["No encontré esa cuenta."]
            tmp["email"] = email; db.set_auth_session(chat_id, "login", "password", tmp)
            return ["Tu contraseña?"]
        if step == "password":
            email = tmp.get("email", ""); admin = db.get_admin_by_email(email)
            if admin and verify_password(text.strip(), admin["password_hash"]):
                db.create_admin(chat_id=chat_id, email=admin["email"], password_hash=admin["password_hash"], name=admin["name"], role=admin["role"])
                db.clear_auth_session(chat_id)
                clinic = db.get_clinic(); admin_ids = _parse_admin_ids(clinic.get("admin_chat_ids", []))
                if chat_id not in admin_ids: admin_ids.append(chat_id); db.update_clinic(admin_chat_ids=admin_ids)
                return [f"Bienvenido de nuevo, {admin['name']}."]
            return ["Contraseña incorrecta."]
        return []


class AdminLearningEngine:
    def __init__(self, database): self.db = database; self._cached_instructions = None
    def add_instruction(self, chat_id: str, text: str) -> str:
        self.db.add_admin_instruction(chat_id, text); self._cached_instructions = None
        return f"Anotado: '{text}'."
    def get_prompt_injection(self) -> str:
        ins = self.db.get_active_admin_instructions()
        if not ins: return ""
        return "\n## INSTRUCCIONES DEL DUEÑO:\n" + "\n".join([f"- {i}" for i in ins])
    def clear(self) -> str: self.db.clear_admin_instructions(); return "Instrucciones borradas."


class SimulationEngine:
    def __init__(self, melissa): self.melissa = melissa; self._active_simulations = {}
    def start(self, chat_id: str, scenario: str = "default") -> List[str]:
        self._active_simulations[chat_id] = {"ts": time.time()}
        return ["Dale, escríbeme como si fueras un paciente y te respondo en personaje"]
    def stop(self, chat_id: str) -> List[str]:
        self._active_simulations.pop(chat_id, None); return ["Listo, salí del modo simulación"]
    def is_simulating(self, chat_id: str) -> bool: return chat_id in self._active_simulations
    async def handle_step(self, chat_id: str, text: str) -> List[str]:
        if "salir" in text.lower() or "/salir" in text.lower(): return self.stop(chat_id)
        return await self.melissa.process_message(chat_id, text, is_simulation=True)


class SelfImprovementEngine:
    def __init__(self, llm): self.llm = llm
    async def analyze_performance(self) -> Dict: return {"ok": True}


class TaskManager:
    def __init__(self): self._tasks = {}
    def add_task(self, chat_id: str, kind: str, data: Dict, delay: int = 0): return secrets.token_hex(4)
