#!/usr/bin/env python3
"""melissa — AI receptionist platform."""
from __future__ import annotations

import os
import sys
import time
import json
import subprocess
import signal
import random
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.theme import Theme
from rich.padding import Padding
from rich.rule import Rule

# ─── Theme ───────────────────────────────────────────────────────────────────

THEME = Theme({
    "m": "bold #b48ead",
    "m.dim": "#8b7498",
    "m.bright": "bold #c9a0dc",
    "ok": "#a3be8c",
    "warn": "#ebcb8b",
    "err": "#bf616a",
    "dim": "#4c566a",
    "info": "#88c0d0",
    "text": "#d8dee9",
})

con = Console(theme=THEME)

VERSION = "9.3.3"
try:
    _p = Path(__file__).parent / "package.json"
    if _p.exists(): VERSION = json.loads(_p.read_text()).get("version", VERSION)
except Exception: pass

# ─── ASCII Brand ─────────────────────────────────────────────────────────────

LOGO = """[m]
    ╔╦╗╔═╗╦  ╦╔═╗╔═╗╔═╗
    ║║║║╣ ║  ║╚═╗╚═╗╠═╣
    ╩ ╩╚═╝╩═╝╩╚═╝╚═╝╩ ╩[/m]"""

TAGLINES = [
    "your AI receptionist",
    "omni-channel AI receptionist",
    "the receptionist that never sleeps",
    "AI that sounds human",
    "WhatsApp AI for business",
    "recepcionista con IA",
]

def _tagline():
    return random.choice(TAGLINES)


# ─── Banner ──────────────────────────────────────────────────────────────────

def banner():
    con.print()
    con.print(LOGO)
    con.print(f"    [dim]v{VERSION}[/dim]  [m.dim]— {_tagline()}[/m.dim]")
    con.print()

    # Status bar
    procs = _pm2()
    online = [p for p in procs if "melissa" in p.get("name","") and p.get("pm2_env",{}).get("status") == "online"]
    if online:
        names = " ".join(f"[m]{p['name'].replace('melissa-','').replace('melissa','main')}[/m]" for p in online)
        con.print(f"    [ok]●[/ok] {names}")
    else:
        con.print(f"    [warn]○[/warn] [dim]no instances running[/dim]")
    con.print()


# ─── Help ────────────────────────────────────────────────────────────────────

def help():
    banner()

    sections = [
        ("CORE", [
            ("new",     "create instance"),
            ("list",    "show instances"),
            ("status",  "services health"),
            ("doctor",  "full diagnostic"),
            ("chat",    "talk to melissa"),
            ("logs",    "live logs"),
        ]),
        ("CONTROL", [
            ("persona", "personality config"),
            ("demo",    "demo mode toggle"),
            ("modelo",  "switch LLM model"),
            ("sync",    "deploy to instances"),
            ("config",  "edit settings"),
        ]),
        ("INTELLIGENCE", [
            ("aprender","teach a response"),
            ("gaps",    "unanswered questions"),
            ("reporte", "weekly brain report"),
            ("studio",  "live monitor"),
        ]),
        ("OPS", [
            ("restart", "restart instance"),
            ("stop",    "stop instance"),
            ("backup",  "create snapshot"),
            ("bridge",  "whatsapp bridge"),
            ("pair",    "telegram routing"),
        ]),
    ]

    for title, cmds in sections:
        con.print(f"    [m]{title}[/m]")
        for cmd, desc in cmds:
            con.print(f"      [m.bright]{cmd:10s}[/m.bright] [dim]{desc}[/dim]")
        con.print()

    con.print(f"    [dim]shortcuts:[/dim] [m]l[/m] list  [m]s[/m] status  [m]d[/m] doctor  [m]c[/m] chat  [m]r[/m] restart")
    con.print()


# ─── Commands ────────────────────────────────────────────────────────────────

def do_status(args=""):
    t = Table(box=box.SIMPLE, border_style="#b48ead", show_edge=False, pad_edge=False, padding=(0,1))
    t.add_column("", width=3)
    t.add_column("instance", style="bold")
    t.add_column("status")
    t.add_column("mem", justify="right", style="dim")
    t.add_column("up", justify="right", style="dim")

    for p in _pm2():
        name = p.get("name","")
        if "melissa" not in name: continue
        st = p.get("pm2_env",{}).get("status","?")
        mem = p.get("monit",{}).get("memory",0) / 1024 / 1024
        up = _uptime(p.get("pm2_env",{}).get("pm_uptime",0))
        icon = "[ok]●[/ok]" if st == "online" else "[err]●[/err]"
        st_s = f"[ok]{st}[/ok]" if st == "online" else f"[err]{st}[/err]"
        t.add_row(icon, name, st_s, f"{mem:.0f}M", up)

    con.print()
    con.print(Padding(t, (0,4)))
    con.print()


def do_list(args=""):
    idir = Path("/home/ubuntu/melissa-instances")
    if not idir.exists():
        con.print("    [dim]no instances[/dim]"); return

    t = Table(box=box.SIMPLE, border_style="#b48ead", show_edge=False, pad_edge=False, padding=(0,1))
    t.add_column("", width=3)
    t.add_column("name", style="bold")
    t.add_column("port", style="dim")
    t.add_column("sector", style="m.dim")

    for d in sorted(idir.iterdir()):
        if not d.is_dir() or not (d / ".env").exists(): continue
        port = sector = ""
        for line in (d / ".env").read_text().splitlines():
            if line.startswith("PORT="): port = line.split("=",1)[1]
            if line.startswith("SECTOR="): sector = line.split("=",1)[1]
        t.add_row("[m]⬡[/m]", d.name, f":{port}" if port else "-", sector or "-")

    con.print()
    con.print(Padding(t, (0,4)))
    con.print()


def do_doctor(args=""): _py("melissa_doctor.py", args or "melissa")
def do_chat(args=""): _py("melissa_studio.py", "--instance", args or "default")
def do_new(args=""): _py("melissa_init.py")
def do_persona(args=""): _py("melissa_persona_cli.py", *(args.split() if args else ["list"]))
def do_logs(args=""): _sh("pm2", "logs", args or "melissa", "--lines", "30", "--nostream")
def do_sync(args=""): _py("melissa_cli.py", "sync")
def do_demo(args=""): _py("melissa_cli.py", "demo", args or "")
def do_modelo(args=""): _py("melissa_cli.py", "modelo", args or "")
def do_restart(args=""): _sh("pm2", "restart", args or "melissa")
def do_stop(args=""): _sh("pm2", "stop", args or "melissa")
def do_backup(args=""): _py("melissa_cli.py", "backup", args or "")
def do_bridge(args=""): _py("melissa_cli.py", "bridge", args or "")
def do_pair(args=""): _py("melissa_cli.py", "pair", args or "")
def do_reporte(args=""): _py("melissa_weekly_report.py", args or "default")

def do_config(args=""):
    env = Path("/home/ubuntu/melissa/.env")
    if not env.exists(): con.print("    [dim]no .env found[/dim]"); return
    lines = [l for l in env.read_text().splitlines()
             if l and not l.startswith("#") and "KEY" not in l.upper() and "SECRET" not in l.upper()]
    con.print()
    con.print(Padding(Panel("\n".join(lines[:20]), border_style="dim", box=box.ROUNDED, title="[m].env[/m]"), (0,4)))
    con.print(f"    [dim]edit: nano {env}[/dim]")
    con.print()

def do_gaps(args=""):
    from datetime import datetime
    gd = Path("knowledge_gaps")
    today = datetime.now().strftime("%Y-%m-%d")
    f = gd / f"{today}.jsonl"
    if not f.exists():
        con.print("    [ok]●[/ok] [dim]no gaps today[/dim]"); return
    con.print()
    for line in open(f):
        g = json.loads(line)
        con.print(f"    [warn]?[/warn] {g.get('user_msg','')[:55]} [dim]({g.get('confidence',0):.0%})[/dim]")
    con.print()

def do_aprender(args=""):
    if not args or ("→" not in args and "->" not in args):
        con.print('    [dim]uso: melissa aprender "pregunta" → "respuesta"[/dim]'); return
    sep = "→" if "→" in args else "->"
    q, a = args.split(sep, 1)
    q, a = q.strip().strip('"'), a.strip().strip('"')
    Path("teachings").mkdir(exist_ok=True)
    with open("teachings/default.jsonl", "a") as f:
        f.write(json.dumps({"ts": time.time(), "question": q, "answer": a}) + "\n")
    con.print(f"    [ok]✓[/ok] learned: [m]{q[:35]}[/m] → {a[:35]}")


# ─── Router ──────────────────────────────────────────────────────────────────

CMDS = {
    "help": help, "--help": help, "-h": help, "?": help, "h": help,
    "status": do_status, "s": do_status,
    "list": do_list, "l": do_list,
    "new": do_new, "doctor": do_doctor, "d": do_doctor, "doc": do_doctor,
    "chat": do_chat, "c": do_chat, "studio": do_chat,
    "persona": do_persona, "logs": do_logs, "demo": do_demo,
    "modelo": do_modelo, "sync": do_sync, "sincronizar": do_sync,
    "config": do_config, "gaps": do_gaps, "aprender": do_aprender,
    "reporte": do_reporte, "restart": do_restart, "r": do_restart,
    "stop": do_stop, "backup": do_backup, "bridge": do_bridge, "pair": do_pair,
}

def route(cmd, args=""):
    if cmd in ("--version", "-v"):
        con.print(f"    melissa v{VERSION}"); return
    fn = CMDS.get(cmd.lower())
    if fn: fn(args)
    else: _py("melissa_cli.py", cmd, args)


# ─── Onboarding ──────────────────────────────────────────────────────────────

def first_run():
    return not Path(os.path.expanduser("~/.melissa/initialized")).exists()

def onboard():
    con.print()
    con.print(LOGO)
    con.print(f"    [dim]v{VERSION}[/dim]  [m.dim]— {_tagline()}[/m.dim]")
    con.print()
    con.print("    [bold]First time? Let's set up your instance.[/bold]")
    con.print("    [dim]This takes about 2 minutes.[/dim]")
    con.print()
    r = con.input("    [m]⬡[/m] ready? [dim](y/n)[/dim] ")
    if r.lower() in ("y", "yes", "s", "si", "sí", ""):
        con.print()
        do_new()
    Path(os.path.expanduser("~/.melissa")).mkdir(parents=True, exist_ok=True)
    Path(os.path.expanduser("~/.melissa/initialized")).write_text(time.strftime("%Y-%m-%d"))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _pm2():
    try:
        r = subprocess.run(["pm2","jlist"], capture_output=True, text=True, timeout=5)
        return json.loads(r.stdout)
    except: return []

def _uptime(ms):
    if not ms: return "-"
    s = (time.time()*1000 - ms) / 1000
    if s < 60: return f"{int(s)}s"
    if s < 3600: return f"{int(s/60)}m"
    if s < 86400: return f"{int(s/3600)}h"
    return f"{int(s/86400)}d"

def _py(*a):
    try: subprocess.run([sys.executable]+[str(x) for x in a], cwd="/home/ubuntu/melissa")
    except Exception as e: con.print(f"    [err]{e}[/err]")

def _sh(*a):
    try: subprocess.run(list(a))
    except Exception as e: con.print(f"    [err]{e}[/err]")


# ─── Entry ───────────────────────────────────────────────────────────────────

def main():
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    if first_run() and not (len(sys.argv)>1 and sys.argv[1] in ("help","--help","-h","-v","--version")):
        onboard()
    if len(sys.argv) <= 1:
        help()
    else:
        route(sys.argv[1], " ".join(sys.argv[2:]))

if __name__ == "__main__":
    main()
