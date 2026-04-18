#!/usr/bin/env python3
"""
melissa-chat — Interfaz de lenguaje natural para administrar Melissa.

Uso:
    python3 melissa-chat.py                  → conecta a instancia base (puerto 8001)
    python3 melissa-chat.py clinica-bella    → conecta a instancia específica
    python3 melissa-chat.py --port 8005      → puerto específico

Ejemplo de conversación:
    Tu:     "Melissa tenemos nuevo cliente, la clínica se llama Estética Sofía,
             búscala en Google. El admin se llama Carolina, su número es 3124567890.
             Dame el token y me lo envío."
    Melissa: "Listo Santiago. Busqué Estética Sofía...
             [resumen de lo encontrado]
             Token de activación: ACTV-SOFIA-2025-XXXXXX
             Envíaselo a Carolina al 3124567890. Expira en 72h."
"""

import asyncio
import json
import os
import re
import sys
import time
import readline  # historial de comandos con flecha arriba
from pathlib import Path
from typing import Optional

import httpx

# ── Colores ANSI ───────────────────────────────────────────────────────────────
R  = "\033[0;31m"   # rojo
G  = "\033[0;32m"   # verde
Y  = "\033[1;33m"   # amarillo
B  = "\033[0;34m"   # azul
P  = "\033[0;35m"   # morado
C  = "\033[0;36m"   # cyan
W  = "\033[1;37m"   # blanco brillante
DIM= "\033[2m"      # dimmed
NC = "\033[0m"      # reset

def clear_line():
    sys.stdout.write("\033[2K\033[1G")
    sys.stdout.flush()

def print_typing(name: str = "Melissa"):
    """Muestra animación de 'escribiendo...'"""
    chars = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    for i in range(12):
        clear_line()
        sys.stdout.write(f"  {P}{name}{NC} {DIM}{chars[i % len(chars)]} escribiendo...{NC}")
        sys.stdout.flush()
        time.sleep(0.08)
    clear_line()

# ── Config ─────────────────────────────────────────────────────────────────────
INSTANCES_DIR = "/home/ubuntu/melissa-instances"
TEMPLATE_DIR  = "/home/ubuntu/melissa"
SERP_API_KEY  = ""  # se lee del .env


def load_env(env_path: str) -> dict:
    """Lee un archivo .env y retorna dict."""
    env = {}
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


def resolve_instance(arg: Optional[str]) -> dict:
    """
    Dado un nombre de instancia (o None para la base), retorna su config.
    Retorna: {port, base_url, master_key, name, env_path}
    """
    if not arg:
        env = load_env(f"{TEMPLATE_DIR}/.env")
        return {
            "name": "base",
            "port": int(env.get("PORT", 8001)),
            "base_url": f"http://localhost:{env.get('PORT', 8001)}",
            "master_key": env.get("MASTER_API_KEY", ""),
            "env_path": f"{TEMPLATE_DIR}/.env",
            "env": env,
        }

    # Slugify
    slug = arg.lower().strip()
    inst_dir = f"{INSTANCES_DIR}/{slug}"
    env_path = f"{inst_dir}/.env"

    if not os.path.exists(env_path):
        # Buscar por aproximación
        for d in os.listdir(INSTANCES_DIR) if os.path.exists(INSTANCES_DIR) else []:
            if slug in d:
                inst_dir = f"{INSTANCES_DIR}/{d}"
                env_path = f"{inst_dir}/.env"
                slug = d
                break
        else:
            return None

    env = load_env(env_path)
    port = int(env.get("PORT", 8002))
    return {
        "name": slug,
        "port": port,
        "base_url": f"http://localhost:{port}",
        "master_key": env.get("MASTER_API_KEY", ""),
        "env_path": env_path,
        "env": env,
    }


# ── API Client ─────────────────────────────────────────────────────────────────

async def api_get(base_url: str, path: str, master_key: str = "") -> dict:
    headers = {}
    if master_key:
        headers["X-Master-Key"] = master_key
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{base_url}{path}", headers=headers)
        r.raise_for_status()
        return r.json()

async def api_post(base_url: str, path: str, data: dict, master_key: str = "") -> dict:
    headers = {"Content-Type": "application/json"}
    if master_key:
        headers["X-Master-Key"] = master_key
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(f"{base_url}{path}", json=data, headers=headers)
        r.raise_for_status()
        return r.json()

async def get_health(base_url: str) -> dict:
    try:
        return await api_get(base_url, "/health")
    except Exception:
        return {"status": "offline"}

async def search_clinic_web(clinic_name: str, serp_key: str, city: str = "Medellin") -> str:
    """Busca la clínica en Google vía SerpAPI."""
    if not serp_key:
        return ""
    try:
        async with httpx.AsyncClient(timeout=12.0) as c:
            r = await c.get("https://serpapi.com/search", params={
                "engine": "google",
                "q": f"{clinic_name} {city} clinica estetica servicios precios horario",
                "api_key": serp_key,
                "hl": "es", "gl": "co", "num": 5
            })
            r.raise_for_status()
            data = r.json()

        parts = []
        ab = data.get("answer_box", {})
        if ab.get("snippet"):
            parts.append(ab["snippet"][:400])
        for res in data.get("organic_results", [])[:4]:
            if res.get("snippet"):
                parts.append(f"{res.get('title','')}: {res['snippet'][:200]}")
        return "\n".join(parts)[:1000]
    except Exception as e:
        return f"[búsqueda fallida: {e}]"


async def create_activation_token(base_url: str, master_key: str, clinic_label: str) -> dict:
    """Crea un token de activación para una nueva clínica."""
    return await api_post(base_url, "/api/tokens/create",
                          {"clinic_label": clinic_label}, master_key)

async def get_recent_chats(base_url: str, master_key: str) -> list:
    try:
        r = await api_get(base_url, "/conversations/patients?limit=5", master_key)
        return r.get("conversations", [])
    except Exception:
        return []

async def get_stats(base_url: str, master_key: str) -> dict:
    try:
        h = await api_get(base_url, "/health")
        a = await api_get(base_url, "/analytics/summary?days=7", master_key)
        return {**h, **a}
    except Exception as e:
        return {"error": str(e)}


# ── LLM Brain para el CLI ──────────────────────────────────────────────────────

async def llm_interpret(
    user_input: str,
    history: list,
    instance: dict,
    health: dict,
    serp_key: str,
) -> str:
    """
    Usa el LLM de la instancia activa para interpretar el mensaje del usuario
    y decidir qué acciones tomar. Retorna la respuesta final.
    """

    # Intentar todos los LLMs disponibles
    env = instance.get("env", {})

    providers = []
    if env.get("GROQ_API_KEY"):
        providers.append(("groq", "https://api.groq.com/openai/v1", env["GROQ_API_KEY"], "llama-3.3-70b-versatile"))
    for k in ["GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"]:
        if env.get(k):
            providers.append(("gemini", "native", env[k], "gemini-2.0-flash"))
    if env.get("OPENROUTER_API_KEY"):
        providers.append(("openrouter", "https://openrouter.ai/api/v1", env["OPENROUTER_API_KEY"], "google/gemini-2.0-flash-001"))
    if env.get("OPENAI_API_KEY"):
        providers.append(("openai", "https://api.openai.com/v1", env["OPENAI_API_KEY"], "gpt-4o-mini"))

    if not providers:
        return "No hay LLMs configurados en el .env. Revisa las claves de API."

    # Contexto de la instancia
    clinic_name = health.get("clinic", "desconocida")
    status = health.get("status", "offline")

    hist_text = ""
    for h in history[-6:]:
        role = "Santiago" if h["role"] == "user" else "Melissa"
        hist_text += f"{role}: {h['content']}\n"

    system = f"""Eres Melissa, asistente virtual de administración de clínicas estéticas.
Santiago (el dueño del sistema) te está hablando desde la terminal de su servidor.

INSTANCIA ACTIVA:
- Nombre: {instance['name']}
- Puerto: {instance['port']}
- Clínica: {clinic_name}
- Estado: {status}
- Master Key: {instance['master_key'][:20]}...

ACCIONES QUE PUEDES HACER (cuando las detectes en el mensaje):
1. Crear token de activación para nueva clínica
2. Buscar clínica en Google
3. Ver conversaciones recientes de pacientes
4. Ver estadísticas
5. Dar información sobre configuración
6. Responder preguntas sobre el sistema

FORMATO DE RESPUESTA:
Responde en español natural, directo, como una asistente que conoce el sistema.
Si necesitas ejecutar una acción, incluye al FINAL del mensaje UNA línea con el JSON:
ACTION:{{"type": "create_token", "clinic_label": "...", "admin_name": "...", "admin_phone": "..."}}
ACTION:{{"type": "search_clinic", "clinic_name": "...", "city": "Medellin"}}
ACTION:{{"type": "show_chats"}}
ACTION:{{"type": "show_stats"}}

Si no hay acción, no incluyas ninguna línea ACTION.

REGLAS:
- Si te piden crear un nuevo cliente/clínica: extrae el nombre de la clínica y crea el token
- Si mencionan buscar en Google: extrae el nombre y busca
- Si preguntan por mensajes/pacientes: muestra los chats recientes
- Respuestas cortas y directas — máximo 4 oraciones antes de la acción

CONVERSACIÓN RECIENTE:
{hist_text or "(inicio)"}"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_input}
    ]

    for provider_name, base_url, api_key, model in providers:
        try:
            if provider_name == "gemini":
                # API nativa de Gemini
                system_parts = [m for m in messages if m["role"] == "system"]
                contents = []
                for m in messages:
                    if m["role"] == "user":
                        contents.append({"role": "user", "parts": [{"text": m["content"]}]})
                    elif m["role"] == "assistant":
                        contents.append({"role": "model", "parts": [{"text": m["content"]}]})
                payload = {
                    "contents": contents,
                    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 600}
                }
                if system_parts:
                    payload["systemInstruction"] = {"parts": [{"text": system_parts[0]["content"]}]}
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                async with httpx.AsyncClient(timeout=20.0) as c:
                    r = await c.post(url, json=payload)
                    r.raise_for_status()
                    data = r.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                # OpenAI-compatible
                async with httpx.AsyncClient(timeout=20.0) as c:
                    r = await c.post(
                        f"{base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://melissa.ai",
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "temperature": 0.4,
                            "max_tokens": 600
                        }
                    )
                    r.raise_for_status()
                    data = r.json()
                return data["choices"][0]["message"]["content"].strip()

        except Exception as e:
            continue  # siguiente proveedor

    return "No pude conectarme al LLM. Revisa las claves de API en el .env."


def extract_action(response: str) -> Optional[dict]:
    """Extrae el JSON de acción del final de la respuesta."""
    m = re.search(r'ACTION:\s*(\{[^\n]+\})', response)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None


def clean_response(response: str) -> str:
    """Quita la línea ACTION del texto mostrado al usuario."""
    return re.sub(r'\nACTION:\s*\{[^\n]+\}', '', response).strip()


# ── Ejecutor de acciones ───────────────────────────────────────────────────────

async def execute_action(action: dict, instance: dict, serp_key: str) -> str:
    """Ejecuta la acción y retorna texto adicional para mostrar."""
    base_url   = instance["base_url"]
    master_key = instance["master_key"]
    action_type = action.get("type", "")

    if action_type == "create_token":
        clinic_label = action.get("clinic_label", "Nueva Clínica")
        admin_name   = action.get("admin_name", "")
        admin_phone  = action.get("admin_phone", "")

        try:
            result = await create_activation_token(base_url, master_key, clinic_label)
            token = result.get("token", "")
            expires = result.get("expires_at", "")[:16] if result.get("expires_at") else ""

            lines = [
                f"\n  {G}Token creado:{NC}",
                f"  {W}{token}{NC}",
            ]
            if expires:
                lines.append(f"  {DIM}Expira: {expires}{NC}")
            if admin_name and admin_phone:
                lines.append(f"\n  {Y}Envíaselo a {admin_name} al {admin_phone}:{NC}")
                lines.append(f"  Mensaje sugerido:")
                lines.append(f"  {DIM}\"Hola {admin_name}! Para activar tu asistente virtual")
                lines.append(f"   envía este código al bot de Telegram: {token}\"{NC}")
            lines.append(f"\n  {DIM}Instrucciones de activación:{NC}")
            lines.append(f"  {DIM}1. El admin escribe el token al bot{NC}")
            lines.append(f"  {DIM}2. El bot le pide nombre, correo y contraseña{NC}")
            lines.append(f"  {DIM}3. Queda activado como owner de la clínica{NC}")
            lines.append(f"  {DIM}4. Puede invitar a su equipo con /addadmin{NC}")
            return "\n".join(lines)

        except Exception as e:
            return f"\n  {R}Error creando token: {e}{NC}"

    elif action_type == "search_clinic":
        clinic_name = action.get("clinic_name", "")
        city        = action.get("city", "Medellin")

        if not clinic_name:
            return f"\n  {Y}No especificaste el nombre de la clínica a buscar.{NC}"

        sys.stdout.write(f"\n  {DIM}Buscando '{clinic_name}' en Google...{NC}")
        sys.stdout.flush()
        result = await search_clinic_web(clinic_name, serp_key, city)
        clear_line()

        if not result:
            return f"\n  {Y}No encontré información de '{clinic_name}' en Google.{NC}"

        lines = [f"\n  {C}Lo que encontré de {clinic_name}:{NC}", ""]
        for line in result.split("\n")[:8]:
            if line.strip():
                lines.append(f"  {line[:100]}")
        return "\n".join(lines)

    elif action_type == "show_chats":
        try:
            chats = await get_recent_chats(base_url, master_key)
            if not chats:
                return f"\n  {DIM}No hay conversaciones de pacientes todavía.{NC}"

            lines = [f"\n  {C}Últimas conversaciones:{NC}", ""]
            for c in chats[:5]:
                name = c.get("name") or "Desconocido"
                cid  = c.get("chat_id", "")[-6:]
                n    = c.get("message_count", 0)
                last = (c.get("last_user_msg") or "")[:50]
                lines.append(f"  • {W}{name}{NC} (...{cid}) — {n} msgs")
                if last:
                    lines.append(f"    {DIM}\"{last}\"{NC}")
            return "\n".join(lines)
        except Exception as e:
            return f"\n  {R}Error: {e}{NC}"

    elif action_type == "show_stats":
        try:
            stats = await get_stats(base_url, master_key)
            lines = [f"\n  {C}Estadísticas (últimos 7 días):{NC}", ""]
            if "total_conversations" in stats:
                lines.append(f"  Conversaciones:  {stats['total_conversations']}")
            if "total_appointments" in stats:
                lines.append(f"  Citas agendadas: {stats['total_appointments']}")
            if "conversion_rate" in stats:
                lines.append(f"  Conversión:      {stats['conversion_rate']}%")
            if "clinic" in stats:
                lines.append(f"  Clínica:         {stats['clinic']}")
            return "\n".join(lines)
        except Exception as e:
            return f"\n  {R}Error: {e}{NC}"

    return ""


# ── REPL Principal ─────────────────────────────────────────────────────────────

async def repl(instance: dict):
    """Loop principal de chat."""
    base_url   = instance["base_url"]
    master_key = instance["master_key"]
    name       = instance["name"]
    env        = instance.get("env", {})
    serp_key   = env.get("SERP_API_KEY", "")

    # Verificar conexión
    health = await get_health(base_url)
    status = health.get("status", "offline")
    clinic = health.get("clinic", "sin configurar")

    # Header
    print(f"\n{P}{'═'*54}{NC}")
    print(f"{P}  MELISSA CHAT{NC} — {W}{name}{NC}")
    print(f"  Puerto: {C}{instance['port']}{NC}  Clínica: {W}{clinic}{NC}")
    status_color = G if status == "online" else R
    print(f"  Estado: {status_color}{status}{NC}")
    print(f"{P}{'═'*54}{NC}")
    print(f"\n  {DIM}Escríbeme en lenguaje natural.")
    print(f"  Ej: 'nuevo cliente, clínica La Bella, admin Juan 3124567890'")
    print(f"  Comandos rápidos: /chats /stats /exit{NC}\n")

    history = []
    readline.set_history_length(100)

    while True:
        try:
            user_input = input(f"{W}  Tú:{NC} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n  {DIM}Hasta luego.{NC}\n")
            break

        if not user_input:
            continue

        # Comandos rápidos
        if user_input.lower() in ("/exit", "/quit", "salir", "exit", "quit"):
            print(f"\n  {DIM}Hasta luego.{NC}\n")
            break

        if user_input.lower() in ("/chats", "chats"):
            user_input = "muéstrame las conversaciones recientes de pacientes"
        elif user_input.lower() in ("/stats", "stats", "estadísticas"):
            user_input = "dame las estadísticas"
        elif user_input.lower() in ("/help", "help", "ayuda"):
            print(f"""
  {C}Lo que puedo hacer:{NC}
  • Crear token para nuevo cliente:
    "nuevo cliente, la clínica se llama X, el admin es Juan, número 3124567890"
  • Buscar clínica en Google:
    "busca la clínica X en Google"
  • Ver conversaciones:
    "quién me ha escrito?" o /chats
  • Ver estadísticas:
    "cómo vamos?" o /stats
  • Cualquier pregunta sobre el sistema
""")
            continue

        # Procesar con LLM
        print()
        print_typing("Melissa")

        response = await llm_interpret(user_input, history, instance, health, serp_key)

        # Extraer y ejecutar acción si hay
        action = extract_action(response)
        reply  = clean_response(response)

        # Mostrar respuesta
        print(f"{P}  Melissa:{NC} {reply}")

        # Ejecutar acción y mostrar resultado
        if action:
            action_output = await execute_action(action, instance, serp_key)
            if action_output:
                print(action_output)

        print()

        # Guardar en historial
        history.append({"role": "user",      "content": user_input})
        history.append({"role": "assistant",  "content": reply})
        if len(history) > 20:
            history = history[-20:]


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    # Parsear argumentos
    instance_name = None
    port_override = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            port_override = int(args[i + 1])
            i += 2
        elif not args[i].startswith("--"):
            instance_name = args[i]
            i += 1
        else:
            i += 1

    # Resolver instancia
    instance = resolve_instance(instance_name)

    if instance is None:
        print(f"\n{R}  Instancia '{instance_name}' no encontrada.{NC}")
        if os.path.exists(INSTANCES_DIR):
            available = os.listdir(INSTANCES_DIR)
            if available:
                print(f"  Instancias disponibles: {', '.join(available)}")
        print(f"  Crea una con: ./melissa-cli nuevo-cliente\n")
        sys.exit(1)

    if port_override:
        instance["port"] = port_override
        instance["base_url"] = f"http://localhost:{port_override}"

    try:
        asyncio.run(repl(instance))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass

if __name__ == "__main__":
    main()

# Alias directo: también se puede llamar como script standalone
# python3 melissa-chat.py          → instancia base
# python3 melissa-chat.py nombre   → instancia específica
