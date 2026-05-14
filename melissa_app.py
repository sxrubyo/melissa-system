#!/usr/bin/env python3
"""melissa — CLI potente para Melissa AI."""
from __future__ import annotations

import os
import sys
import time
import json
import subprocess
import signal
from pathlib import Path

# ─── Rich imports (mega output) ───────────────────────────────────────────────
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.markdown import Markdown
from rich import box
from rich.style import Style
from rich.theme import Theme

# ─── Branding ────────────────────────────────────────────────────────────────

MELISSA_THEME = Theme({
    "melissa": "bold #b48ead",       # soft purple
    "accent": "#d08770",             # warm coral
    "success": "#a3be8c",            # green
    "warning": "#ebcb8b",            # gold
    "error": "#bf616a",              # soft red
    "dim": "#4c566a",                # muted
    "info": "#88c0d0",               # blue
})

console = Console(theme=MELISSA_THEME)

VERSION = "9.3.3"
try:
    _p = Path(__file__).parent / "package.json"
    if _p.exists(): VERSION = json.loads(_p.read_text()).get("version", VERSION)
except Exception: pass

WORM_ART = """[melissa]
     ╭──╮
    ╭┤  ├─╮
    │╰──╯ │  melissa
    ╰─────╯[/melissa]"""

WORM_MINI = "[melissa]⬡[/melissa]"


# ─── Header ──────────────────────────────────────────────────────────────────

def print_banner():
    banner = Text()
    banner.append("  ⬡ ", style="bold #b48ead")
    banner.append("melissa", style="bold #b48ead")
    banner.append(f"  v{VERSION}", style="dim")

    console.print()
    console.print(Panel(
        banner,
        border_style="#b48ead",
        box=box.ROUNDED,
        subtitle="[dim]recepcionista virtual con superpoderes[/dim]",
        subtitle_align="left",
        padding=(0, 1),
    ))


def print_status():
    """Quick status line."""
    procs = _get_pm2()
    online = [p for p in procs if "melissa" in p.get("name", "") and p.get("pm2_env", {}).get("status") == "online"]
    if online:
        console.print(f"  [success]●[/success] {len(online)} instancias online", highlight=False)
    else:
        console.print(f"  [warning]○[/warning] sin instancias corriendo", highlight=False)
    console.print()


# ─── Help ────────────────────────────────────────────────────────────────────

def print_help():
    print_banner()
    print_status()

    t = Table(show_header=False, box=None, padding=(0, 2, 0, 0), show_edge=False)
    t.add_column(style="bold #b48ead", width=14)
    t.add_column(style="")

    t.add_row("", "[bold]Esencial[/bold]")
    t.add_row("  new", "Crear instancia")
    t.add_row("  list", "Ver instancias")
    t.add_row("  status", "Estado de servicios")
    t.add_row("  doctor", "Diagnóstico de salud")
    t.add_row("  chat", "Hablar con Melissa")
    t.add_row("  logs", "Ver logs")
    t.add_row()
    t.add_row("", "[bold]Control[/bold]")
    t.add_row("  persona", "Personalidad")
    t.add_row("  demo", "Demo on/off")
    t.add_row("  modelo", "Cambiar LLM")
    t.add_row("  sync", "Sincronizar instancias")
    t.add_row("  config", "Configuración")
    t.add_row()
    t.add_row("", "[bold]Inteligencia[/bold]")
    t.add_row("  aprender", "Enseñar respuesta")
    t.add_row("  gaps", "Preguntas sin resolver")
    t.add_row("  reporte", "Reporte semanal")
    t.add_row("  studio", "Monitor en tiempo real")
    t.add_row()
    t.add_row("", "[bold]Operaciones[/bold]")
    t.add_row("  restart", "Reiniciar")
    t.add_row("  stop", "Detener")
    t.add_row("  backup", "Snapshot")
    t.add_row("  bridge", "WhatsApp Bridge")
    t.add_row("  pair", "Telegram router")

    console.print(t)
    console.print()
    console.print("  [dim]Shortcuts:[/dim] [melissa]l[/melissa]=list  [melissa]s[/melissa]=status  [melissa]d[/melissa]=doctor  [melissa]c[/melissa]=chat")
    console.print("  [dim]Lenguaje natural:[/dim] [melissa]melissa[/melissa] 'crear instancia para gym'")
    console.print()


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_status(args=""):
    procs = _get_pm2()
    t = Table(title="Instancias", box=box.SIMPLE_HEAD, border_style="#b48ead", show_edge=False)
    t.add_column("", width=2)
    t.add_column("Nombre", style="bold")
    t.add_column("Estado")
    t.add_column("Memoria", justify="right", style="dim")
    t.add_column("Uptime", justify="right", style="dim")

    for p in procs:
        name = p.get("name", "")
        if "melissa" not in name:
            continue
        st = p.get("pm2_env", {}).get("status", "?")
        mem = p.get("monit", {}).get("memory", 0) / 1024 / 1024
        uptime_ms = p.get("pm2_env", {}).get("pm_uptime", 0)
        uptime = _fmt_uptime(uptime_ms) if uptime_ms else "-"
        icon = "[success]●[/success]" if st == "online" else "[error]●[/error]"
        st_text = f"[success]{st}[/success]" if st == "online" else f"[error]{st}[/error]"
        t.add_row(icon, name, st_text, f"{mem:.0f}MB", uptime)

    console.print()
    console.print(t)
    console.print()


def cmd_list(args=""):
    idir = Path("/home/ubuntu/melissa-instances")
    if not idir.exists():
        console.print("  [dim]Sin instancias[/dim]")
        return

    t = Table(title="Instancias", box=box.SIMPLE_HEAD, border_style="#b48ead", show_edge=False)
    t.add_column("", width=2)
    t.add_column("Nombre", style="bold")
    t.add_column("Puerto", style="dim")
    t.add_column("Sector", style="dim")

    for d in sorted(idir.iterdir()):
        if not d.is_dir() or not (d / ".env").exists():
            continue
        env = (d / ".env").read_text()
        port, sector = "", ""
        for line in env.splitlines():
            if line.startswith("PORT="): port = line.split("=")[1]
            if line.startswith("SECTOR="): sector = line.split("=")[1]
        t.add_row("[melissa]⬡[/melissa]", d.name, f":{port}" if port else "-", sector or "-")

    console.print()
    console.print(t)
    console.print()


def cmd_doctor(args=""):
    instance = args.strip() or "melissa"
    _run_py("melissa_doctor.py", instance)


def cmd_chat(args=""):
    instance = args.strip() or "default"
    _run_py("melissa_studio.py", "--instance", instance)


def cmd_persona(args=""):
    parts = args.split() if args else ["list"]
    _run_py("melissa_persona_cli.py", *parts)


def cmd_logs(args=""):
    instance = args.strip() or "melissa"
    _exec("pm2", "logs", instance, "--lines", "30", "--nostream")


def cmd_new(args=""):
    _run_py("melissa_init.py")


def cmd_sync(args=""):
    _run_py("melissa_cli.py", "sync")


def cmd_demo(args=""):
    _run_py("melissa_cli.py", "demo", args or "")


def cmd_modelo(args=""):
    _run_py("melissa_cli.py", "modelo", args or "")


def cmd_config(args=""):
    console.print()
    env = Path("/home/ubuntu/melissa/.env")
    if env.exists():
        lines = []
        for line in env.read_text().splitlines():
            if line and not line.startswith("#") and "KEY" not in line.upper() and "SECRET" not in line.upper():
                lines.append(line)
        console.print(Panel("\n".join(lines[:20]), title="[melissa].env[/melissa]", border_style="dim", box=box.ROUNDED))
    console.print(f"  [dim]Editar: nano {env}[/dim]")
    console.print()


def cmd_gaps(args=""):
    from datetime import datetime
    gaps_dir = Path("knowledge_gaps")
    if not gaps_dir.exists():
        console.print("  [success]●[/success] Sin gaps")
        return
    today = datetime.now().strftime("%Y-%m-%d")
    f = gaps_dir / f"{today}.jsonl"
    if not f.exists():
        console.print("  [success]●[/success] Sin gaps hoy")
        return
    console.print()
    for line in open(f):
        g = json.loads(line)
        console.print(f"  [warning]?[/warning] {g.get('user_msg', '')[:60]} [dim](conf: {g.get('confidence',0):.0%})[/dim]")
    console.print()


def cmd_aprender(args=""):
    if not args or ("→" not in args and "->" not in args):
        console.print('  [dim]Uso: melissa aprender "pregunta" → "respuesta"[/dim]')
        return
    sep = "→" if "→" in args else "->"
    q, a = args.split(sep, 1)
    q, a = q.strip().strip('"'), a.strip().strip('"')
    Path("teachings").mkdir(exist_ok=True)
    with open("teachings/default.jsonl", "a") as f:
        f.write(json.dumps({"ts": time.time(), "question": q, "answer": a}) + "\n")
    console.print(f"  [success]✓[/success] Aprendido: [melissa]{q[:40]}[/melissa] → {a[:40]}")


def cmd_reporte(args=""):
    _run_py("melissa_weekly_report.py", args or "default")


def cmd_restart(args=""):
    instance = args.strip() or "melissa"
    _exec("pm2", "restart", instance)


def cmd_stop(args=""):
    instance = args.strip() or "melissa"
    _exec("pm2", "stop", instance)


def cmd_backup(args=""):
    _run_py("melissa_cli.py", "backup", args or "")


def cmd_bridge(args=""):
    _run_py("melissa_cli.py", "bridge", args or "")


def cmd_pair(args=""):
    _run_py("melissa_cli.py", "pair", args or "")


# ─── Dispatch ────────────────────────────────────────────────────────────────

DISPATCH = {
    "help": print_help, "--help": print_help, "-h": print_help, "h": print_help, "?": print_help,
    "status": cmd_status, "s": cmd_status,
    "list": cmd_list, "l": cmd_list,
    "new": cmd_new,
    "doctor": cmd_doctor, "doc": cmd_doctor, "d": cmd_doctor,
    "chat": cmd_chat, "c": cmd_chat, "studio": cmd_chat,
    "persona": cmd_persona,
    "logs": cmd_logs,
    "demo": cmd_demo,
    "modelo": cmd_modelo,
    "sync": cmd_sync, "sincronizar": cmd_sync,
    "config": cmd_config,
    "gaps": cmd_gaps,
    "aprender": cmd_aprender,
    "reporte": cmd_reporte,
    "restart": cmd_restart, "r": cmd_restart,
    "stop": cmd_stop,
    "backup": cmd_backup,
    "bridge": cmd_bridge,
    "pair": cmd_pair,
}


def dispatch(cmd: str, args: str = ""):
    cmd = cmd.lower().strip()
    if cmd in ("--version", "-v"):
        console.print(f"  melissa v{VERSION}")
        return
    handler = DISPATCH.get(cmd)
    if handler:
        handler(args)
    else:
        # Delegate to old CLI
        _run_py("melissa_cli.py", cmd, args)


# ─── Onboarding ──────────────────────────────────────────────────────────────

def is_first_run():
    return not Path(os.path.expanduser("~/.melissa/initialized")).exists()

def onboarding():
    console.print()
    console.print(Panel(
        "[bold melissa]Bienvenido a Melissa AI[/bold melissa]\n\n"
        "Tu recepcionista virtual con superpoderes.\n"
        "Responde WhatsApp, aprende tu negocio, agenda citas.",
        border_style="#b48ead",
        box=box.DOUBLE,
        padding=(1, 2),
    ))
    console.print()
    resp = console.input("  [melissa]⬡[/melissa] Configurar primera instancia? [dim](s/n)[/dim] ")
    if resp.lower() in ("s", "si", "sí", "y", "yes", ""):
        console.print()
        cmd_new()
    Path(os.path.expanduser("~/.melissa")).mkdir(parents=True, exist_ok=True)
    Path(os.path.expanduser("~/.melissa/initialized")).write_text(time.strftime("%Y-%m-%d"))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_pm2():
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=5)
        return json.loads(r.stdout)
    except Exception:
        return []

def _fmt_uptime(pm_uptime_ms):
    secs = (time.time() * 1000 - pm_uptime_ms) / 1000
    if secs < 60: return f"{int(secs)}s"
    if secs < 3600: return f"{int(secs/60)}m"
    if secs < 86400: return f"{int(secs/3600)}h"
    return f"{int(secs/86400)}d"

def _run_py(*args):
    try:
        subprocess.run([sys.executable] + [str(a) for a in args], cwd="/home/ubuntu/melissa")
    except Exception as e:
        console.print(f"  [error]Error: {e}[/error]")

def _exec(*args):
    try:
        subprocess.run(list(args))
    except Exception as e:
        console.print(f"  [error]Error: {e}[/error]")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    signal.signal(signal.SIGINT, lambda *_: (console.print("\n"), sys.exit(0)))

    if len(sys.argv) <= 1:
        # No args: show help (like modern CLIs)
        if is_first_run():
            onboarding()
        else:
            print_help()
        return

    cmd = sys.argv[1]
    args = " ".join(sys.argv[2:])

    if is_first_run() and cmd not in ("help", "--help", "-h", "--version", "-v"):
        onboarding()

    dispatch(cmd, args)


if __name__ == "__main__":
    main()
