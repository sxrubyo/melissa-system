#!/usr/bin/env python3
"""melissa_init.py — Interactive wizard for creating new Melissa instances."""
import os, sys, json, secrets, shutil
from pathlib import Path
from datetime import datetime

INSTANCES_DIR = Path("/home/ubuntu/melissa-instances")
MELISSA_DIR = Path("/home/ubuntu/melissa")

SECTOR_DEFAULTS = {
    "clinica": {"services": ["Consulta general", "Especialidades", "Exámenes"], "tone": "warm_professional", "hours": "L-V 7am-6pm, S 8am-1pm"},
    "restaurante": {"services": ["Reservas", "Menú del día", "Domicilios"], "tone": "casual", "hours": "L-D 11am-10pm"},
    "salon": {"services": ["Corte", "Color", "Manicure", "Pedicure"], "tone": "colombian_warm", "hours": "L-S 8am-7pm"},
    "inmobiliaria": {"services": ["Arriendos", "Ventas", "Avalúos"], "tone": "formal", "hours": "L-V 8am-6pm, S 9am-1pm"},
    "gym": {"services": ["Membresías", "Clases grupales", "Personal trainer"], "tone": "casual", "hours": "L-S 5am-10pm, D 7am-2pm"},
    "ecommerce": {"services": ["Pedidos", "Devoluciones", "Estado de envío"], "tone": "casual", "hours": "L-D 24h"},
}

def color(text, code): return f"\033[{code}m{text}\033[0m"
def bold(text): return color(text, "1")
def cyan(text): return color(text, "1;36")
def green(text): return color(text, "32")
def yellow(text): return color(text, "33")
def dim(text): return color(text, "90")

def ask(prompt, default="", required=True):
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"  {prompt}{suffix}: ").strip()
        if not val and default:
            return default
        if val or not required:
            return val
        print(f"  {color('Required field', '31')}")

def ask_choice(prompt, choices):
    print(f"  {prompt}")
    for i, c in enumerate(choices, 1):
        print(f"    {i}. {c}")
    while True:
        val = input(f"  Choice [1-{len(choices)}]: ").strip()
        if val.isdigit() and 1 <= int(val) <= len(choices):
            return choices[int(val)-1]
        print(f"  {color('Invalid choice', '31')}")

def run_wizard():
    print()
    print(cyan("╔══════════════════════════════════════════════════════════╗"))
    print(cyan("║           MELISSA AI — NUEVA INSTANCIA                   ║"))
    print(cyan("║     Recepcionista virtual para tu negocio                ║"))
    print(cyan("╚══════════════════════════════════════════════════════════╝"))
    print()
    print("Vamos a configurar tu instancia de Melissa en 5 minutos.")
    print(dim("Presiona Enter para usar valores por defecto. Ctrl+C para cancelar."))
    print()

    # Step 1: Business info
    print(bold("PASO 1/7 — INFORMACIÓN DEL NEGOCIO"))
    print("─" * 40)
    name = ask("Nombre del negocio")
    instance_id = name.lower().replace(" ", "-").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")
    instance_id = "".join(c for c in instance_id if c.isalnum() or c == "-")[:40]
    print(f"  {dim(f'Instance ID: {instance_id}')}")
    sector = ask_choice("Sector:", list(SECTOR_DEFAULTS.keys()) + ["otro"])
    location = ask("Ubicación (ciudad/dirección)", required=False)
    phone = ask("Teléfono del negocio", required=False)
    hours = ask("Horario", default=SECTOR_DEFAULTS.get(sector, {}).get("hours", "L-V 8am-6pm"))
    print()

    # Step 2: Channels
    print(bold("PASO 2/7 — CANALES"))
    print("─" * 40)
    channel = ask_choice("¿Por dónde atiende?", ["WhatsApp", "Telegram", "Ambos"])
    print()

    # Step 3: LLM
    print(bold("PASO 3/7 — MOTOR DE IA"))
    print("─" * 40)
    provider = ask_choice("Proveedor LLM:", ["Gemini (recomendado)", "Claude", "GPT", "Groq"])
    provider_map = {"Gemini (recomendado)": "gemini", "Claude": "claude", "GPT": "openai", "Groq": "groq"}
    provider_key = provider_map.get(provider, "gemini")
    print()

    # Step 4: Persona
    print(bold("PASO 4/7 — PERSONALIDAD"))
    print("─" * 40)
    defaults = SECTOR_DEFAULTS.get(sector, {})
    tone = ask("Tono", default=defaults.get("tone", "warm_professional"))
    greeting = ask("Saludo preferido", default="Con mucho gusto")
    agent_name = ask("Nombre del agente", default="Melissa")
    print()

    # Step 5: Services
    print(bold("PASO 5/7 — SERVICIOS"))
    print("─" * 40)
    default_services = defaults.get("services", ["Consulta", "Información"])
    print(f"  {dim(f'Servicios sugeridos para {sector}: {', '.join(default_services)}')}")
    services_raw = ask("Servicios (separados por coma)", default=", ".join(default_services))
    services = [s.strip() for s in services_raw.split(",") if s.strip()]
    print()

    # Step 6: Appointments
    print(bold("PASO 6/7 — CITAS"))
    print("─" * 40)
    can_book = ask_choice("¿Melissa puede agendar citas?", ["Sí, agenda directamente", "No, solo informa"])
    print()

    # Step 7: Admin
    print(bold("PASO 7/7 — ADMINISTRADOR"))
    print("─" * 40)
    admin_phone = ask("WhatsApp del admin (para alertas)", required=False)
    print()

    # Generate instance
    print(bold("═══ GENERANDO INSTANCIA ═══"))
    instance_dir = INSTANCES_DIR / instance_id
    instance_dir.mkdir(parents=True, exist_ok=True)

    # Generate .env
    port = 8004 + len(list(INSTANCES_DIR.iterdir()))
    webhook_secret = f"melissa_{instance_id}_{secrets.token_hex(8)}"
    env_content = f"""# Melissa Instance: {name}
# Generated: {datetime.now().isoformat()}
INSTANCE_ID={instance_id}
PORT={port}
DEMO_MODE=false
PLATFORM={channel.lower().replace("ambos", "whatsapp")}
SECTOR={sector}
BUSINESS_NAME={name}
WEBHOOK_SECRET={webhook_secret}
ADMIN_PHONE={admin_phone}
LLM_PROVIDER={provider_key}
"""
    (instance_dir / ".env").write_text(env_content)
    print(f"  {green('✓')} .env generado (port {port})")

    # Generate persona.yaml
    persona_dir = instance_dir / "personas"
    persona_dir.mkdir(exist_ok=True)
    persona_content = f"""identity:
  name: "{agent_name}"
  role: "recepcionista virtual"
  business: "{name}"
  sector: {sector}

voice:
  tone: {tone}
  verbosity: balanced
  language: es_CO
  greeting: "{greeting}"

knowledge:
  services: {json.dumps(services, ensure_ascii=False)}
  hours: "{hours}"
  location: "{location}"
  phone: "{phone}"

restrictions:
  forbidden_topics: ["diagnósticos médicos", "precios de competencia"]
  escalation_triggers: ["urgencia", "emergencia", "queja"]

appointments:
  can_book: {str(can_book.startswith("Sí")).lower()}

llm:
  provider: {provider_key}
  temperature: 0.7
"""
    (persona_dir / "persona.yaml").write_text(persona_content)
    print(f"  {green('✓')} persona.yaml generado")

    # Copy core files
    core_files = ["melissa.py", "melissa_admin.py", "melissa_production.py", "melissa_demo.py",
                  "melissa_utils.py", "melissa_config.py", "melissa_router.py", "melissa_voice.py",
                  "melissa_uncertainty.py", "melissa_memory_engine.py", "melissa_admin_api.py",
                  "melissa_cron.py", "melissa_nova_proxy.py", "run.sh", "requirements.txt"]
    copied = 0
    for f in core_files:
        src = MELISSA_DIR / f
        if src.exists():
            shutil.copy2(src, instance_dir / f)
            copied += 1
    print(f"  {green('✓')} {copied} core files copied")

    # Create run.sh
    run_sh = f"""#!/bin/bash
cd {instance_dir}
exec /home/ubuntu/melissa/.venv/bin/python melissa.py
"""
    (instance_dir / "run.sh").write_text(run_sh)
    os.chmod(instance_dir / "run.sh", 0o755)
    print(f"  {green('✓')} run.sh generado")

    print()
    print(green("═══ INSTANCIA CREADA EXITOSAMENTE ═══"))
    print(f"  Directorio: {instance_dir}")
    print(f"  Puerto: {port}")
    print(f"  Webhook: {webhook_secret}")
    print()
    print(dim("Para iniciar:"))
    print(f"  pm2 start {instance_dir}/run.sh --name melissa-{instance_id}")
    print(f"  curl http://localhost:{port}/health")
    print()

def main():
    try:
        run_wizard()
    except KeyboardInterrupt:
        print("\n\nCancelado.")
        sys.exit(0)

if __name__ == "__main__":
    main()
