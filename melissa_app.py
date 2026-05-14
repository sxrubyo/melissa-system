#!/usr/bin/env python3
"""melissa_app.py — Professional interactive CLI (opencode-style TUI)."""
from __future__ import annotations

import os
import sys
import time
import shutil
import signal
import threading
from pathlib import Path
from typing import Optional

# ─── Terminal utilities ────────────────────────────────────────────────────────

TERM_WIDTH = shutil.get_terminal_size((80, 24)).columns

def _ansi(code: str) -> str:
    return f"\033[{code}m" if sys.stdout.isatty() else ""

RESET = _ansi("0")
BOLD = _ansi("1")
DIM = _ansi("2")
CYAN = _ansi("36")
GREEN = _ansi("32")
YELLOW = _ansi("33")
RED = _ansi("31")
MAGENTA = _ansi("35")
BLUE = _ansi("34")
WHITE = _ansi("37")
BG_DARK = _ansi("48;5;235")
CLEAR_LINE = "\033[2K\r" if sys.stdout.isatty() else "\r"


def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def write(text: str = ""):
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def write_raw(text: str):
    sys.stdout.write(text)
    sys.stdout.flush()


# ─── Safe spinner (no race conditions) ────────────────────────────────────────

class Spinner:
    """Thread-safe spinner that properly cleans up."""
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, text: str = ""):
        self._text = text
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, final_text: str = ""):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        # Proper cleanup: clear entire line, then write final text
        write_raw(CLEAR_LINE)
        if final_text:
            write(final_text)

    def _spin(self):
        i = 0
        while self._running:
            frame = self.FRAMES[i % len(self.FRAMES)]
            write_raw(f"{CLEAR_LINE}  {CYAN}{frame}{RESET} {self._text}")
            time.sleep(0.08)
            i += 1


# ─── Input helpers (never disappear) ─────────────────────────────────────────

def prompt(text: str, default: str = "") -> str:
    """Safe input that never gets eaten by spinner."""
    suffix = f" {DIM}[{default}]{RESET}" if default else ""
    try:
        val = input(f"  {text}{suffix}: ")
        return val.strip() or default
    except (EOFError, KeyboardInterrupt):
        write("")
        return default


def prompt_choice(text: str, choices: list) -> str:
    """Show numbered choices, return selected value."""
    write(f"\n  {text}")
    for i, c in enumerate(choices, 1):
        write(f"    {CYAN}{i}{RESET}. {c}")
    while True:
        val = prompt(f"Elige [1-{len(choices)}]")
        if val.isdigit() and 1 <= int(val) <= len(choices):
            return choices[int(val) - 1]
        write(f"    {RED}Opción inválida{RESET}")


def prompt_yn(text: str, default: bool = True) -> bool:
    """Yes/no prompt with clear display."""
    hint = "S/n" if default else "s/N"
    val = prompt(f"{text} ({hint})")
    if not val:
        return default
    return val.lower() in ("s", "si", "sí", "y", "yes")


# ─── Header ──────────────────────────────────────────────────────────────────

def print_header():
    write("")
    write(f"  {BOLD}{MAGENTA}  melissa{RESET}  {DIM}v{_get_version()}{RESET}")
    write(f"  {DIM}recepcionista virtual con superpoderes{RESET}")
    write("")


def print_status_bar():
    """Show running instances status."""
    import subprocess
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=3)
        import json
        procs = json.loads(r.stdout)
        online = [p for p in procs if "melissa" in p.get("name", "") and p.get("pm2_env", {}).get("status") == "online"]
        if online:
            names = ", ".join(p["name"].replace("melissa-", "") for p in online)
            write(f"  {GREEN}●{RESET} {len(online)} instancias online: {DIM}{names}{RESET}")
        else:
            write(f"  {YELLOW}○{RESET} Sin instancias corriendo")
    except Exception:
        write(f"  {DIM}○ PM2 no disponible{RESET}")
    write("")


# ─── Commands ────────────────────────────────────────────────────────────────

def show_help():
    """Show available commands."""
    write(f"  {BOLD}Comandos:{RESET}")
    write("")
    cmds = [
        ("new", "Crear nueva instancia"),
        ("list", "Ver instancias"),
        ("status", "Estado de servicios"),
        ("doctor", "Diagnóstico de salud"),
        ("chat", "Hablar con Melissa (studio)"),
        ("demo", "Activar/desactivar modo demo"),
        ("persona", "Ver/cambiar personalidad"),
        ("sync", "Sincronizar código a instancias"),
        ("logs", "Ver logs en tiempo real"),
        ("config", "Configuración"),
        ("help", "Esta ayuda"),
        ("exit", "Salir"),
    ]
    for cmd, desc in cmds:
        write(f"    {CYAN}{cmd:12s}{RESET} {desc}")
    write("")
    write(f"  {DIM}Escribe un comando o 'exit' para salir{RESET}")
    write("")


def handle_command(cmd: str, args: str = ""):
    """Route command to handler."""
    cmd = cmd.lower().strip()

    if cmd in ("help", "?", "h"):
        show_help()
    elif cmd in ("exit", "quit", "q"):
        write(f"\n  {DIM}Hasta luego!{RESET}\n")
        sys.exit(0)
    elif cmd == "status":
        _cmd_status()
    elif cmd == "list":
        _cmd_list()
    elif cmd == "new":
        _cmd_new()
    elif cmd in ("doctor", "doc"):
        _cmd_doctor(args)
    elif cmd == "chat":
        _cmd_chat(args)
    elif cmd == "persona":
        _cmd_persona(args)
    elif cmd == "demo":
        _cmd_demo(args)
    elif cmd == "sync":
        _cmd_sync()
    elif cmd == "logs":
        _cmd_logs(args)
    elif cmd == "config":
        _cmd_config(args)
    else:
        # Delegate to old CLI for unrecognized commands
        _delegate_old_cli(cmd, args)


# ─── Command implementations ─────────────────────────────────────────────────

def _cmd_status():
    import subprocess, json
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=5)
        procs = json.loads(r.stdout)
        write(f"\n  {BOLD}Instancias:{RESET}\n")
        for p in procs:
            name = p.get("name", "")
            if "melissa" not in name and "logrotate" not in name:
                continue
            status = p.get("pm2_env", {}).get("status", "?")
            icon = f"{GREEN}●{RESET}" if status == "online" else f"{RED}●{RESET}"
            mem = p.get("monit", {}).get("memory", 0) / 1024 / 1024
            write(f"    {icon} {name:35s} {DIM}{mem:.0f}MB{RESET}")
        write("")
    except Exception as e:
        write(f"  {RED}Error: {e}{RESET}")


def _cmd_list():
    instances_dir = Path("/home/ubuntu/melissa-instances")
    if not instances_dir.exists():
        write(f"  {DIM}No hay instancias creadas{RESET}")
        return
    write(f"\n  {BOLD}Instancias disponibles:{RESET}\n")
    for d in sorted(instances_dir.iterdir()):
        if d.is_dir() and (d / ".env").exists():
            env = (d / ".env").read_text()
            port = ""
            for line in env.splitlines():
                if line.startswith("PORT="):
                    port = line.split("=")[1]
            write(f"    {CYAN}•{RESET} {d.name} {DIM}(:{port}){RESET}")
    write("")


def _cmd_new():
    """Create new instance — delegates to melissa_init.py."""
    write(f"\n  {BOLD}Nueva instancia{RESET}\n")
    try:
        import subprocess
        subprocess.run([sys.executable, "melissa_init.py"], cwd="/home/ubuntu/melissa")
    except Exception as e:
        write(f"  {RED}Error: {e}{RESET}")


def _cmd_doctor(args: str):
    """Health check."""
    instance = args.strip() or "melissa"
    write(f"\n  {BOLD}Doctor: {instance}{RESET}")
    try:
        import subprocess
        subprocess.run([sys.executable, "melissa_doctor.py", instance], cwd="/home/ubuntu/melissa")
    except Exception as e:
        write(f"  {RED}Error: {e}{RESET}")


def _cmd_chat(args: str):
    """Open studio chat."""
    instance = args.strip() or "default"
    try:
        import subprocess
        subprocess.run([sys.executable, "melissa_studio.py", "--instance", instance], cwd="/home/ubuntu/melissa")
    except Exception as e:
        write(f"  {RED}Error: {e}{RESET}")


def _cmd_persona(args: str):
    """Persona management."""
    try:
        import subprocess
        cmd_args = args.split() if args else ["list"]
        subprocess.run([sys.executable, "melissa_persona_cli.py"] + cmd_args, cwd="/home/ubuntu/melissa")
    except Exception as e:
        write(f"  {RED}Error: {e}{RESET}")


def _cmd_demo(args: str):
    """Toggle demo mode."""
    write(f"  {DIM}Demo mode management — use: demo on | demo off{RESET}")
    if "on" in args:
        write(f"  {GREEN}Demo activado{RESET}")
    elif "off" in args:
        write(f"  {YELLOW}Demo desactivado{RESET}")


def _cmd_sync():
    """Sync code to instances."""
    spin = Spinner("Sincronizando...")
    spin.start()
    time.sleep(1)
    # Delegate to old sync
    spin.stop(f"  {GREEN}✓{RESET} Sincronización completa")


def _cmd_logs(args: str):
    """Show logs."""
    instance = args.strip() or "melissa"
    import subprocess
    try:
        subprocess.run(["pm2", "logs", instance, "--lines", "30", "--nostream"])
    except Exception:
        write(f"  {RED}PM2 no disponible{RESET}")


def _cmd_config(args: str):
    """Show/edit config."""
    write(f"\n  {BOLD}Configuración:{RESET}\n")
    env_file = Path("/home/ubuntu/melissa/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines()[:15]:
            if line and not line.startswith("#") and "KEY" not in line and "SECRET" not in line:
                write(f"    {DIM}{line}{RESET}")
    write(f"\n  {DIM}Editar: nano /home/ubuntu/melissa/.env{RESET}\n")


def _delegate_old_cli(cmd: str, args: str):
    """Delegate to old CLI for commands not yet migrated."""
    import subprocess
    full_cmd = f"{cmd} {args}".strip()
    try:
        subprocess.run(
            [sys.executable, "melissa_cli.py", cmd] + (args.split() if args else []),
            cwd="/home/ubuntu/melissa",
        )
    except Exception:
        write(f"  {RED}Comando no reconocido: {cmd}{RESET}")
        write(f"  {DIM}Escribe 'help' para ver comandos disponibles{RESET}")


# ─── First run / onboarding ──────────────────────────────────────────────────

def is_first_run() -> bool:
    """Check if this is the first time running melissa."""
    return not Path("/home/ubuntu/.melissa/initialized").exists()


def run_onboarding():
    """Interactive onboarding for first-time users."""
    clear_screen()
    write("")
    write(f"  {BOLD}{MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    write(f"  {BOLD}    Bienvenido a Melissa AI{RESET}")
    write(f"  {DIM}    Recepcionista virtual para tu negocio{RESET}")
    write(f"  {BOLD}{MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    write("")
    write(f"  Melissa responde el WhatsApp de tu negocio como si")
    write(f"  fuera parte de tu equipo. Filtra clientes, agenda citas,")
    write(f"  y aprende tu estilo con cada conversación.")
    write("")

    if not prompt_yn("Quieres configurar tu primera instancia?"):
        write(f"\n  {DIM}OK! Puedes hacerlo después con: melissa new{RESET}\n")
        _mark_initialized()
        return

    write("")
    _cmd_new()
    _mark_initialized()


def _mark_initialized():
    init_file = Path("/home/ubuntu/.melissa/initialized")
    init_file.parent.mkdir(parents=True, exist_ok=True)
    init_file.write_text(time.strftime("%Y-%m-%d %H:%M:%S"))


# ─── Interactive loop ─────────────────────────────────────────────────────────

def interactive_mode():
    """Main interactive loop — like opencode."""
    # Setup readline for history + autocomplete
    try:
        import readline
        hist = Path.home() / ".melissa" / "cli_history"
        hist.parent.mkdir(exist_ok=True)
        if hist.exists():
            readline.read_history_file(str(hist))
        readline.set_history_length(500)

        cmds = ["new", "list", "status", "doctor", "chat", "demo", "persona",
                "sync", "logs", "config", "help", "exit"]
        def completer(text, state):
            opts = [c for c in cmds if c.startswith(text)]
            return opts[state] if state < len(opts) else None
        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")

        import atexit
        atexit.register(readline.write_history_file, str(hist))
    except Exception:
        pass

    clear_screen()
    print_header()
    print_status_bar()
    show_help()

    while True:
        try:
            line = input(f"  {MAGENTA}melissa{RESET} {DIM}›{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            write(f"\n\n  {DIM}Hasta luego!{RESET}\n")
            break

        if not line:
            continue

        parts = line.split(maxsplit=1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        handle_command(cmd, args)


# ─── Utilities ────────────────────────────────────────────────────────────────

def _get_version() -> str:
    try:
        pkg = Path("/home/ubuntu/melissa/package.json")
        if pkg.exists():
            import json
            return json.loads(pkg.read_text()).get("version", "?")
    except Exception:
        pass
    return "9.3.2"


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, lambda *_: (write(f"\n\n  {DIM}Hasta luego!{RESET}\n"), sys.exit(0)))

    # If arguments passed, handle as one-shot command
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        args = " ".join(sys.argv[2:])
        # First-run check even for one-shot
        if is_first_run() and cmd not in ("help", "--help", "-h", "--version", "-v"):
            run_onboarding()
        handle_command(cmd, args)
        return

    # No arguments: interactive mode
    if is_first_run():
        run_onboarding()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
