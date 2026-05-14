#!/usr/bin/env python3
"""melissa init — First-run onboarding with arrow-key navigation."""
from __future__ import annotations

import os
import sys
import json
import re
import secrets
import shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from melissa_tui_select import select_menu, confirm, text_input

VERSION = "9.3.4"
try: VERSION = json.loads((Path(__file__).parent / "package.json").read_text()).get("version", VERSION)
except: pass

PURPLE = "\033[38;5;141m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
R = "\033[0m"

INSTANCES_DIR = Path("/home/ubuntu/melissa-instances")
MELISSA_DIR = Path("/home/ubuntu/melissa")

SECTORS = [
    ("clinica", "Clínica / Centro médico"),
    ("estetica", "Estética / Belleza"),
    ("restaurante", "Restaurante / Bar"),
    ("salon", "Salón / Peluquería / Barbería"),
    ("inmobiliaria", "Inmobiliaria / Finca raíz"),
    ("gym", "Gimnasio / Fitness"),
    ("ecommerce", "E-commerce / Tienda online"),
    ("hotel", "Hotel / Hospedaje"),
    ("veterinaria", "Veterinaria"),
    ("educacion", "Educación / Academia"),
    ("otro", "Otro"),
]

CHANNELS = [
    ("whatsapp", "WhatsApp (Baileys bridge)"),
    ("whatsapp_cloud", "WhatsApp Cloud API (Meta)"),
    ("telegram", "Telegram"),
    ("both", "WhatsApp + Telegram"),
]

PROVIDERS = [
    ("gemini", "Gemini 2.5 Flash — rápido y barato"),
    ("claude", "Claude — mejor calidad"),
    ("openrouter", "OpenRouter — múltiples modelos"),
    ("groq", "Groq — ultra rápido"),
]

TONES = [
    ("colombian_warm", "Cálida — cercana pero profesional"),
    ("casual", "Casual — como amiga, relajada"),
    ("formal", "Formal — usted, sin jerga"),
    ("luxury", "Luxury — sofisticada y exclusiva"),
]


def clear():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def step_header(n, total, title):
    print(f"\n  {PURPLE}{BOLD}[{n}/{total}]{R} {title}")
    print(f"  {'─' * 40}\n")


def run_wizard():
    clear()
    print(f"""
  {PURPLE}{BOLD}███╗   ███╗███████╗██╗     ██╗███████╗███████╗ █████╗{R}
  {PURPLE}{BOLD}████╗ ████║██╔════╝██║     ██║██╔════╝██╔════╝██╔══██╗{R}
  {PURPLE}{BOLD}██╔████╔██║█████╗  ██║     ██║███████╗███████╗███████║{R}
  {PURPLE}{BOLD}██║╚██╔╝██║██╔══╝  ██║     ██║╚════██║╚════██║██╔══██║{R}
  {PURPLE}{BOLD}██║ ╚═╝ ██║███████╗███████╗██║███████║███████║██║  ██║{R}
  {PURPLE}{BOLD}╚═╝     ╚═╝╚══════╝╚══════╝╚═╝╚══════╝╚══════╝╚═╝  ╚═╝{R}

  {DIM}Multi-sector. Multi-channel. Always on.{R}
  {PURPLE}✦{R} Melissa v{VERSION}
  {'─' * 54}

  {BOLD}Setup{R} — new instance in 2 minutes.
  {DIM}Use ↑/↓ to navigate, Enter to confirm.{R}
""")

    if not confirm("Ready?"):
        print(f"\n  {DIM}Ok. Run: melissa new{R}\n")
        return

    step_header(1, 6, "Negocio")
    name = text_input("Nombre del negocio")
    instance_id = _slug(name)

    step_header(2, 6, "Sector")
    i = select_menu([s[1] for s in SECTORS], title="Tipo de negocio")
    sector = SECTORS[i][0]

    step_header(3, 6, "Canal")
    i = select_menu([c[1] for c in CHANNELS], title="Canal de atención")
    channel = CHANNELS[i][0]

    step_header(4, 6, "IA")
    i = select_menu([p[1] for p in PROVIDERS], title="Motor de IA")
    provider = PROVIDERS[i][0]

    step_header(5, 6, "Personalidad")
    i = select_menu([t[1] for t in TONES], title="Tono de Melissa")
    tone = TONES[i][0]

    step_header(6, 6, "Confirmar")
    print(f"    Negocio:   {PURPLE}{name}{R}")
    print(f"    Sector:    {sector}")
    print(f"    Canal:     {channel}")
    print(f"    IA:        {provider}")
    print(f"    Tono:      {tone}")
    print()

    if not confirm("Create instance?"):
        print(f"\n  {DIM}Cancelled.{R}\n")
        return

    print(f"\n  {DIM}Creando...{R}")
    _create(name, instance_id, sector, channel, provider, tone)
    print(f"""
  {GREEN}{BOLD}✓ Instancia lista{R}

    Dir:     {INSTANCES_DIR / instance_id}
    Start:   {PURPLE}pm2 start {INSTANCES_DIR / instance_id}/run.sh --name melissa-{instance_id}{R}
    Health:  {PURPLE}melissa doctor {instance_id}{R}
""")


def _create(name, iid, sector, channel, provider, tone):
    idir = INSTANCES_DIR / iid
    idir.mkdir(parents=True, exist_ok=True)
    port = 8004 + sum(1 for d in INSTANCES_DIR.iterdir() if d.is_dir()) if INSTANCES_DIR.exists() else 8004
    secret = f"melissa_{iid}_{secrets.token_hex(8)}"

    (idir / ".env").write_text(f"""INSTANCE_ID={iid}
PORT={port}
DEMO_MODE=false
PLATFORM={channel}
SECTOR={sector}
BUSINESS_NAME={name}
WEBHOOK_SECRET={secret}
LLM_PROVIDER={provider}
""")
    (idir / "personas").mkdir(exist_ok=True)
    (idir / "personas" / "persona.yaml").write_text(f"""identity:
  name: Melissa
  business: "{name}"
  sector: {sector}
voice:
  tone: {tone}
  language: es_CO
llm:
  provider: {provider}
""")
    core = ["melissa.py","melissa_admin.py","melissa_production.py","melissa_config.py",
            "melissa_utils.py","melissa_commands.py","melissa_learning.py","melissa_voice.py",
            "melissa_uncertainty.py","melissa_memory_engine.py","melissa_admin_api.py",
            "melissa_cron.py","melissa_nova_proxy.py","melissa_smart_features.py",
            "melissa_web_search.py","melissa_google_auth.py","run.sh","requirements.txt"]
    for f in core:
        src = MELISSA_DIR / f
        if src.exists(): shutil.copy2(src, idir / f)
    for d in ["soul","teachings","memory_store","knowledge_gaps","integrations/vault"]:
        (idir / d).mkdir(parents=True, exist_ok=True)
    (idir / "run.sh").write_text(f"#!/bin/bash\ncd {idir}\nexec /home/ubuntu/melissa/.venv/bin/python melissa.py\n")
    os.chmod(idir / "run.sh", 0o755)


def _slug(name):
    s = name.lower().strip()
    for a, b in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")]:
        s = s.replace(a, b)
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:40]


def main():
    try:
        run_wizard()
    except KeyboardInterrupt:
        print(f"\n\n  {DIM}Cancelado.{R}\n")

if __name__ == "__main__":
    main()
