#!/usr/bin/env python3
"""melissa — Professional CLI for Melissa AI."""
from __future__ import annotations

import os
import sys
import time
import shutil
import signal
import threading
import subprocess
import json
from pathlib import Path
from typing import Optional, List

# ─── Terminal ─────────────────────────────────────────────────────────────────

TERM_W = shutil.get_terminal_size((80, 24)).columns
IS_TTY = sys.stdout.isatty()

def _c(code): return f"\033[{code}m" if IS_TTY else ""

R = _c("0")       # reset
B = _c("1")       # bold
D = _c("2")       # dim
PURPLE = _c("38;5;141")  # melissa brand purple
LILAC = _c("38;5;183")   # lighter purple
GREEN = _c("32")
YELLOW = _c("33")
RED = _c("31")
CYAN = _c("36")
WHITE = _c("37")
CL = "\033[2K\r" if IS_TTY else ""

def w(t=""): sys.stdout.write(t + "\n"); sys.stdout.flush()
def wr(t): sys.stdout.write(t); sys.stdout.flush()


# ─── Branding ────────────────────────────────────────────────────────────────

VERSION = "9.3.2"
try:
    _pkg = Path(__file__).parent / "package.json"
    if _pkg.exists():
        VERSION = json.loads(_pkg.read_text()).get("version", VERSION)
except Exception:
    pass

WORM = "🐛"  # Melissa's spirit animal

BANNER = f"""
  {PURPLE}{B}┌─────────────────────────────────────────────┐{R}
  {PURPLE}{B}│{R}  {WORM} {B}{PURPLE}melissa{R} {D}v{VERSION}{R}                           {PURPLE}{B}│{R}
  {PURPLE}{B}│{R}  {LILAC}recepcionista virtual con superpoderes{R}     {PURPLE}{B}│{R}
  {PURPLE}{B}└─────────────────────────────────────────────┘{R}
"""

BANNER_MINI = f"  {WORM} {B}{PURPLE}melissa{R} {D}v{VERSION}{R}"


# ─── Safe I/O ────────────────────────────────────────────────────────────────

class Spinner:
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    def __init__(self, text=""): self._text = text; self._on = False; self._t = None
    def start(self):
        self._on = True
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()
    def stop(self, msg=""):
        self._on = False
        if self._t: self._t.join(timeout=1)
        wr(CL)
        if msg: w(msg)
    def _run(self):
        i = 0
        while self._on:
            wr(f"{CL}  {PURPLE}{self.FRAMES[i % 10]}{R} {self._text}")
            time.sleep(0.08); i += 1


def ask(text, default=""):
    sfx = f" {D}[{default}]{R}" if default else ""
    try:
        v = input(f"  {text}{sfx}: ").strip()
        return v or default
    except (EOFError, KeyboardInterrupt):
        w(""); return default

def ask_yn(text, default=True):
    hint = f"{PURPLE}S{R}/n" if default else f"s/{PURPLE}N{R}"
    v = ask(f"{text} ({hint})")
    if not v: return default
    return v.lower() in ("s", "si", "sí", "y", "yes")


# ─── Status ──────────────────────────────────────────────────────────────────

def get_instances():
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=3)
        return json.loads(r.stdout)
    except Exception:
        return []

def print_status():
    procs = get_instances()
    online = [p for p in procs if "melissa" in p.get("name", "") and p.get("pm2_env", {}).get("status") == "online"]
    if online:
        w(f"  {GREEN}●{R} {len(online)} online{R}")
    else:
        w(f"  {YELLOW}○{R} sin instancias{R}")


# ─── Commands ────────────────────────────────────────────────────────────────

COMMANDS = {
    # Core
    "new":       ("Crear instancia nueva",            "core"),
    "list":      ("Ver instancias",                   "core"),
    "status":    ("Estado de servicios",              "core"),
    "doctor":    ("Diagnóstico completo",             "core"),
    "chat":      ("Hablar con Melissa (studio)",      "core"),
    "logs":      ("Logs en tiempo real",              "core"),
    # Control
    "persona":   ("Ver/cambiar personalidad",         "control"),
    "demo":      ("Demo mode on/off",                 "control"),
    "modelo":    ("Cambiar modelo LLM",               "control"),
    "sync":      ("Sincronizar a instancias",         "control"),
    "config":    ("Configuración",                    "control"),
    # Intelligence
    "studio":    ("Chat interactivo + monitor",       "intel"),
    "aprender":  ("Enseñar info al negocio",          "intel"),
    "gaps":      ("Ver preguntas sin responder",      "intel"),
    "reporte":   ("Reporte semanal",                  "intel"),
    # Operations
    "restart":   ("Reiniciar instancia",              "ops"),
    "stop":      ("Detener instancia",                "ops"),
    "backup":    ("Crear snapshot",                   "ops"),
    "pair":      ("Enlazar Telegram router",          "ops"),
    "bridge":    ("Estado WhatsApp Bridge",           "ops"),
}


def print_help():
    w(BANNER)
    print_status()
    w("")

    groups = {
        "core": f"  {PURPLE}{B}Esencial{R}",
        "control": f"  {PURPLE}{B}Control{R}",
        "intel": f"  {PURPLE}{B}Inteligencia{R}",
        "ops": f"  {PURPLE}{B}Operaciones{R}",
    }

    for group_key, header in groups.items():
        w(header)
        for cmd, (desc, g) in COMMANDS.items():
            if g == group_key:
                w(f"    {PURPLE}{cmd:12s}{R} {desc}")
        w("")

    w(f"  {D}Shortcuts: l=list  s=status  r=restart  d=doctor  c=chat{R}")
    w(f"  {D}Interactivo: melissa (sin args) abre shell{R}")
    w("")


# ─── Command dispatch ────────────────────────────────────────────────────────

def dispatch(cmd: str, args: str = ""):
    cmd = cmd.lower().strip()
    # Shortcuts
    shortcuts = {"l": "list", "s": "status", "d": "doctor", "c": "chat", "r": "restart",
                 "h": "help", "?": "help", "q": "exit", "i": "interactive"}
    cmd = shortcuts.get(cmd, cmd)

    if cmd in ("help", "--help", "-h"):
        print_help()
    elif cmd in ("exit", "quit"):
        w(f"\n  {D}chao! {WORM}{R}\n")
        sys.exit(0)
    elif cmd == "status":
        _status()
    elif cmd == "list":
        _list()
    elif cmd == "new":
        _run_py("melissa_init.py")
    elif cmd in ("doctor", "doc"):
        _run_py("melissa_doctor.py", args or "melissa")
    elif cmd in ("chat", "studio"):
        _run_py("melissa_studio.py", "--instance", args or "default")
    elif cmd == "persona":
        _run_py("melissa_persona_cli.py", *(args.split() if args else ["list"]))
    elif cmd == "logs":
        _exec("pm2", "logs", args or "melissa", "--lines", "30", "--nostream")
    elif cmd == "restart":
        _exec("pm2", "restart", args or "melissa")
    elif cmd == "stop":
        _exec("pm2", "stop", args or "melissa")
    elif cmd in ("sync", "sincronizar"):
        _run_py("melissa_cli.py", "sync")
    elif cmd == "demo":
        _run_py("melissa_cli.py", "demo", args or "")
    elif cmd == "modelo":
        _run_py("melissa_cli.py", "modelo", args or "")
    elif cmd == "config":
        _config(args)
    elif cmd == "bridge":
        _run_py("melissa_cli.py", "bridge", args or "")
    elif cmd == "pair":
        _run_py("melissa_cli.py", "pair", args or "")
    elif cmd == "backup":
        _run_py("melissa_cli.py", "backup", args or "")
    elif cmd == "gaps":
        _gaps(args)
    elif cmd == "aprender":
        _aprender(args)
    elif cmd == "reporte":
        _run_py("melissa_weekly_report.py", args or "default")
    elif cmd == "interactive":
        interactive()
    elif cmd == "--version" or cmd == "-v":
        w(f"  melissa v{VERSION}")
    else:
        # Try old CLI
        _run_py("melissa_cli.py", cmd, args)


# ─── Implementations ─────────────────────────────────────────────────────────

def _status():
    procs = get_instances()
    w(f"\n  {B}Instancias:{R}\n")
    for p in procs:
        name = p.get("name", "")
        if "melissa" not in name:
            continue
        st = p.get("pm2_env", {}).get("status", "?")
        mem = p.get("monit", {}).get("memory", 0) / 1024 / 1024
        icon = f"{GREEN}●{R}" if st == "online" else f"{RED}●{R}"
        w(f"    {icon} {name:35s} {D}{mem:.0f}MB{R}")
    w("")

def _list():
    idir = Path("/home/ubuntu/melissa-instances")
    if not idir.exists():
        w(f"  {D}sin instancias{R}"); return
    w(f"\n  {B}Instancias:{R}\n")
    for d in sorted(idir.iterdir()):
        if d.is_dir() and (d / ".env").exists():
            port = ""
            for line in (d / ".env").read_text().splitlines():
                if line.startswith("PORT="): port = line.split("=")[1]
            w(f"    {PURPLE}●{R} {d.name} {D}(:{port}){R}")
    w("")

def _config(args):
    w(f"\n  {B}Config (.env):{R}\n")
    env = Path("/home/ubuntu/melissa/.env")
    if env.exists():
        for line in env.read_text().splitlines()[:20]:
            if line and not line.startswith("#") and "KEY" not in line.upper() and "SECRET" not in line.upper():
                w(f"    {D}{line}{R}")
    w(f"\n  {D}Editar: nano {env}{R}\n")

def _gaps(args):
    from pathlib import Path
    from datetime import datetime
    gaps_dir = Path("knowledge_gaps")
    if not gaps_dir.exists():
        w(f"  {GREEN}●{R} Sin gaps pendientes"); return
    today = datetime.now().strftime("%Y-%m-%d")
    f = gaps_dir / f"{today}.jsonl"
    if not f.exists():
        w(f"  {GREEN}●{R} Sin gaps hoy"); return
    w(f"\n  {B}Knowledge gaps hoy:{R}\n")
    for line in open(f):
        g = json.loads(line)
        w(f"    {YELLOW}?{R} {g.get('user_msg', '')[:60]} {D}(conf: {g.get('confidence',0):.0%}){R}")
    w("")

def _aprender(args):
    if not args or "→" not in args and "->" not in args:
        w(f"  {D}Uso: melissa aprender \"pregunta\" → \"respuesta\"{R}")
        return
    sep = "→" if "→" in args else "->"
    q, a = args.split(sep, 1)
    q = q.strip().strip('"')
    a = a.strip().strip('"')
    teachings_dir = Path("teachings")
    teachings_dir.mkdir(exist_ok=True)
    with open(teachings_dir / "default.jsonl", "a") as f:
        f.write(json.dumps({"ts": time.time(), "question": q, "answer": a}) + "\n")
    w(f"  {GREEN}✓{R} Aprendido: {q[:40]} → {a[:40]}")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _run_py(*args):
    try:
        subprocess.run([sys.executable] + [str(a) for a in args], cwd="/home/ubuntu/melissa")
    except Exception as e:
        w(f"  {RED}Error: {e}{R}")

def _exec(*args):
    try:
        subprocess.run(list(args))
    except Exception as e:
        w(f"  {RED}Error: {e}{R}")


# ─── Interactive mode ─────────────────────────────────────────────────────────

def interactive():
    try:
        import readline
        hist = Path.home() / ".melissa" / "cli_history"
        hist.parent.mkdir(exist_ok=True)
        if hist.exists(): readline.read_history_file(str(hist))
        readline.set_history_length(500)
        def _comp(text, state):
            opts = [c for c in COMMANDS if c.startswith(text)]
            return opts[state] if state < len(opts) else None
        readline.set_completer(_comp)
        readline.parse_and_bind("tab: complete")
        import atexit
        atexit.register(readline.write_history_file, str(hist))
    except Exception:
        pass

    w(BANNER)
    print_status()
    w(f"  {D}Escribe un comando o 'help'. Tab para autocompletar.{R}\n")

    while True:
        try:
            line = input(f"  {PURPLE}{WORM} melissa{R} {D}›{R} ").strip()
        except (EOFError, KeyboardInterrupt):
            w(f"\n  {D}chao! {WORM}{R}\n"); break
        if not line: continue
        parts = line.split(maxsplit=1)
        dispatch(parts[0], parts[1] if len(parts) > 1 else "")


# ─── Onboarding ──────────────────────────────────────────────────────────────

def is_first_run():
    return not Path(os.path.expanduser("~/.melissa/initialized")).exists()

def onboarding():
    w(f"""
  {PURPLE}{B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{R}

      {WORM} {B}Bienvenido a Melissa AI{R}

      {LILAC}Tu recepcionista virtual con superpoderes.{R}
      {LILAC}Responde WhatsApp, aprende tu negocio, agenda citas.{R}

  {PURPLE}{B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{R}
""")
    if ask_yn("Configurar tu primera instancia?"):
        w("")
        _run_py("melissa_init.py")

    Path(os.path.expanduser("~/.melissa")).mkdir(parents=True, exist_ok=True)
    Path(os.path.expanduser("~/.melissa/initialized")).write_text(time.strftime("%Y-%m-%d"))


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    signal.signal(signal.SIGINT, lambda *_: (w(f"\n  {D}chao! {WORM}{R}\n"), sys.exit(0)))

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        args = " ".join(sys.argv[2:])
        if is_first_run() and cmd not in ("help", "--help", "-h", "--version", "-v"):
            onboarding()
        dispatch(cmd, args)
    else:
        if is_first_run():
            onboarding()
        else:
            interactive()


if __name__ == "__main__":
    main()
