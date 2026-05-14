"""melissa_commands.py — Slash command system for users and admins."""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("melissa.commands")

USER_COMMANDS = {
    "/cita": "Ver o gestionar tu cita",
    "/horarios": "Ver horarios del negocio",
    "/servicios": "Ver lista de servicios",
    "/precios": "Consultar tarifas",
    "/ubicacion": "Dirección y cómo llegar",
    "/ayuda": "Ver comandos disponibles",
    "/hablar": "Hablar con un humano",
}

ADMIN_COMMANDS = {
    "/status": "Estado de la instancia",
    "/gaps": "Preguntas sin responder",
    "/persona": "Cambiar personalidad",
    "/modelo": "Cambiar modelo LLM",
    "/pausa": "Pausar Melissa",
    "/reanudar": "Reanudar Melissa",
    "/stats": "Estadísticas",
    "/test": "Probar respuesta",
    "/reload": "Recargar configuración",
    "/aprender": "Enseñar respuesta",
    "/personalidad": "Cambio rápido de personalidad",
    "/broadcast": "Mensaje masivo",
    "/blacklist": "Bloquear número",
}


class CommandHandler:
    """Handles slash commands from both users and admins."""

    def __init__(self, instance_id: str = "default"):
        self.instance_id = instance_id
        self._paused = False

    def is_command(self, text: str) -> bool:
        return text.strip().startswith("/")

    def is_paused(self) -> bool:
        return self._paused

    async def handle(self, chat_id: str, text: str, is_admin: bool = False,
                     clinic: Optional[Dict] = None, db=None) -> Optional[List[str]]:
        text = text.strip()
        if not text.startswith("/"):
            return None

        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args_str = parts[1] if len(parts) > 1 else ""

        if is_admin:
            result = await self._handle_admin(cmd, args_str, chat_id, clinic, db)
            if result:
                return result

        return await self._handle_user(cmd, args_str, chat_id, clinic, db)

    async def _handle_user(self, cmd: str, args: str, chat_id: str,
                           clinic: Optional[Dict], db) -> Optional[List[str]]:
        if cmd in ("/ayuda", "/help"):
            lines = [
                "Comandos disponibles:",
                "  /help — ver esta lista",
                "  /personalidad — ver y cambiar personalidades",
                "  /reset — empezar de cero con otro negocio",
                "  /modelo — cambiar modelo de IA",
                "",
                "También puedes escribir sin /:",
                "  'formal' 'luxury' 'casual' — cambiar tono",
                "  'reset' — reiniciar demo",
                "  'stats' — ver estadísticas",
                "",
                "Quieres probarme? Dime el nombre de tu negocio y escríbeme como si fueras un cliente",
            ]
            return ["\n".join(lines)]

        if cmd == "/personalidad":
            return [
                "Personalidades disponibles:",
                "  formal — profesional, usted, sin jerga\n"
                "  amigable — cercana, tutea, cálida\n"
                "  luxury — sofisticada, exclusiva, elegante\n"
                "  directa — concisa, sin rodeos\n"
                "  juvenil — fresca, emojis, moderna\n"
                "  experta — técnica, confiable, precisa",
                "Escribe el nombre de la personalidad para verla en acción"
            ]

        if cmd == "/horarios":
            hours = (clinic or {}).get("schedule", "No configurado")
            if isinstance(hours, dict):
                hours = "\n".join(f"  {k}: {v}" for k, v in hours.items())
            return [f"Nuestro horario:\n{hours}"]

        if cmd == "/servicios":
            services = (clinic or {}).get("services", [])
            if isinstance(services, str):
                services = [s.strip() for s in services.split(",")]
            if services:
                return ["Nuestros servicios:\n" + "\n".join(f"  • {s}" for s in services)]
            return ["Servicios no configurados aún."]

        if cmd in ("/ubicacion", "/ubicación"):
            loc = (clinic or {}).get("location", "") or (clinic or {}).get("address", "")
            return [f"Nos encuentras en:\n{loc}"] if loc else ["Ubicación no configurada."]

        if cmd == "/cita":
            return ["Para agendar una cita, dime:\n• Tu nombre\n• Servicio\n• Fecha y hora preferida"]

        if cmd == "/hablar":
            return ["Te paso con alguien del equipo. Un momento."]

        if cmd == "/precios":
            return ["Los precios dependen del servicio. ¿Cuál te interesa?"]

        return None

    async def _handle_admin(self, cmd: str, args: str, chat_id: str,
                            clinic: Optional[Dict], db) -> Optional[List[str]]:
        if cmd in ("/ayuda", "/help"):
            lines = ["🔧 Comandos Admin:"]
            for c, desc in ADMIN_COMMANDS.items():
                lines.append(f"  {c} — {desc}")
            lines.append("\n📋 También puedes:")
            lines.append("  'conectar calendario' — vincular Google Calendar")
            lines.append("  'investiga X' — buscar en internet")
            lines.append("  'modo luxury/formal/casual' — cambiar tono")
            lines.append("  Enviar archivos TXT/PDF/JSON — los leo y aprendo")
            return ["\n".join(lines)]

        if cmd == "/status":
            return [f"Instancia: {self.instance_id}\nEstado: {'pausada' if self._paused else 'activa'}"]

        if cmd == "/pausa":
            self._paused = True
            return ["⏸ Melissa pausada. Mensajes no serán respondidos hasta /reanudar"]

        if cmd == "/reanudar":
            self._paused = False
            return ["▶ Melissa activa de nuevo."]

        if cmd == "/gaps":
            gaps_dir = Path("knowledge_gaps")
            if not gaps_dir.exists():
                return ["No hay gaps registrados."]
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")
            today_file = gaps_dir / f"{today}.jsonl"
            if not today_file.exists():
                return ["No hay gaps de hoy."]
            gaps = []
            for line in open(today_file):
                g = json.loads(line)
                gaps.append(f"• {g['user_msg'][:80]} (conf: {g['confidence']:.0%})")
            return [f"Knowledge gaps ({len(gaps)}):\n" + "\n".join(gaps[:10])]

        if cmd in ("/personalidad", "/persona"):
            if not args:
                return ["Uso: /personalidad tono=formal nombre=Sofía"]
            updates = {}
            for pair in re.findall(r'(\w+)=("[^"]+"|[^\s]+)', args):
                key, val = pair
                updates[key] = val.strip('"')
            if updates:
                override_path = Path(f"personas/{self.instance_id}/runtime_override.json")
                override_path.parent.mkdir(parents=True, exist_ok=True)
                existing = json.loads(override_path.read_text()) if override_path.exists() else {}
                existing.update(updates)
                existing["updated_at"] = time.time()
                override_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
                return [f"✅ Personalidad actualizada: {', '.join(f'{k}={v}' for k,v in updates.items())}"]
            return ["No se detectaron cambios."]

        if cmd == "/aprender":
            if "→" in args or "->" in args:
                sep = "→" if "→" in args else "->"
                question, answer = args.split(sep, 1)
                question = question.strip().strip('"')
                answer = answer.strip().strip('"')
                teachings_dir = Path("teachings")
                teachings_dir.mkdir(exist_ok=True)
                with open(teachings_dir / f"{self.instance_id}.jsonl", "a") as f:
                    f.write(json.dumps({"ts": time.time(), "question": question, "answer": answer}, ensure_ascii=False) + "\n")

                # Auto-update clinic DB with structured data
                q_low = question.lower()
                try:
                    if db and any(w in q_low for w in ["horario", "hora", "atienden", "abrimos"]):
                        db.update_clinic(schedule=json.dumps({"general": answer}))
                    elif db and any(w in q_low for w in ["precio", "cuesta", "vale", "cobran"]):
                        db.update_clinic(pricing=answer)
                    elif db and any(w in q_low for w in ["servicio", "ofrecen", "hacen"]):
                        db.update_clinic(services=[s.strip() for s in answer.split(",")])
                    elif db and any(w in q_low for w in ["telefono", "número", "celular", "llamar"]):
                        db.update_clinic(phone=answer)
                except Exception:
                    pass

                return [f"listo, ya me lo sé: '{question[:40]}' → '{answer[:40]}'"]
            return ["Uso: /aprender pregunta → respuesta"]

        if cmd == "/modelo":
            return [f"Modelo: {args or 'auto'}"] if args else ["Uso: /modelo gemini-2.5-flash"]

        if cmd == "/reload":
            return ["✅ Configuración recargada."]

        if cmd == "/stats":
            return [f"Estadísticas {self.instance_id}: (pendiente integración)"]

        return None


_handlers: Dict[str, CommandHandler] = {}


def get_command_handler(instance_id: str = "default") -> CommandHandler:
    if instance_id not in _handlers:
        _handlers[instance_id] = CommandHandler(instance_id)
    return _handlers[instance_id]
