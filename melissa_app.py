#!/usr/bin/env python3
"""melissa — AI receptionist platform CLI."""
from __future__ import annotations

import os, sys, time, json, subprocess, signal, random
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.theme import Theme
from rich.padding import Padding

THEME = Theme({
    "m": "bold #b48ead",
    "m.dim": "#8b7498",
    "ok": "#a3be8c",
    "warn": "#ebcb8b",
    "err": "#bf616a",
    "dim": "#4c566a",
})
con = Console(theme=THEME)

VERSION = "9.3.3"
try: VERSION = json.loads((Path(__file__).parent / "package.json").read_text()).get("version", VERSION)
except: pass

# ─── ASCII Art ────────────────────────────────────────────────────────────────

LOGO_FULL = """\
[m]  ███╗   ███╗███████╗██╗     ██╗███████╗███████╗ █████╗
  ████╗ ████║██╔════╝██║     ██║██╔════╝██╔════╝██╔══██╗
  ██╔████╔██║█████╗  ██║     ██║███████╗███████╗███████║
  ██║╚██╔╝██║██╔══╝  ██║     ██║╚════██║╚════██║██╔══██║
  ██║ ╚═╝ ██║███████╗███████╗██║███████║███████║██║  ██║
  ╚═╝     ╚═╝╚══════╝╚══════╝╚═╝╚══════╝╚══════╝╚═╝  ╚═╝[/m]"""

LOGO_SMALL = """\
[m]    ╔╦╗╔═╗╦  ╦╔═╗╔═╗╔═╗
    ║║║║╣ ║  ║╚═╗╚═╗╠═╣
    ╩ ╩╚═╝╩═╝╩╚═╝╚═╝╩ ╩[/m]"""

TAGLINES = [
    "AI receptionist for business",
    "your omni-channel receptionist",
    "the AI that sounds human",
    "WhatsApp AI that learns",
    "never miss a customer again",
]


# ─── Banner ──────────────────────────────────────────────────────────────────

def banner(big=False):
    con.print()
    con.print(LOGO_FULL if big else LOGO_SMALL)
    con.print(f"    [dim]v{VERSION}[/dim]  [m.dim]— {random.choice(TAGLINES)}[/m.dim]")
    con.print()
    # Status
    procs = _pm2()
    online = [p for p in procs if "melissa" in p.get("name","") and p.get("pm2_env",{}).get("status")=="online"]
    if online:
        names = " ".join(f"[m]{p['name'].replace('melissa-','').replace('melissa','main')}[/m]" for p in online)
        con.print(f"    [ok]●[/ok] {names}")
    else:
        con.print(f"    [warn]○[/warn] [dim]no instances running[/dim]")
    con.print()


# ─── Help ────────────────────────────────────────────────────────────────────

def cmd_help(args="", big=False):
    banner(big=big)
    sections = [
        ("CORE", [
            ("new",      "create instance"),
            ("list",     "show instances"),
            ("status",   "service health"),
            ("doctor",   "full diagnostic"),
            ("chat",     "talk to melissa"),
            ("logs",     "live logs"),
        ]),
        ("CONTROL", [
            ("persona",  "personality"),
            ("demo",     "demo toggle"),
            ("modelo",   "switch LLM"),
            ("sync",     "deploy code"),
            ("config",   "settings"),
        ]),
        ("LEARN", [
            ("aprender", "teach response"),
            ("gaps",     "unanswered Qs"),
            ("reporte",  "weekly report"),
            ("studio",   "live monitor"),
        ]),
        ("OPS", [
            ("restart",  "restart"),
            ("stop",     "stop"),
            ("backup",   "snapshot"),
            ("bridge",   "whatsapp"),
            ("pair",     "telegram"),
        ]),
    ]
    for title, cmds in sections:
        con.print(f"    [m]{title}[/m]")
        for cmd, desc in cmds:
            con.print(f"      [bold #b48ead]{cmd:10s}[/bold #b48ead] [dim]{desc}[/dim]")
        con.print()
    con.print("    [dim]shortcuts: l=list s=status d=doctor c=chat r=restart[/dim]")
    con.print()


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_status(args=""):
    t = Table(box=box.SIMPLE, border_style="#b48ead", show_edge=False, padding=(0,1))
    t.add_column("", width=3); t.add_column("instance", style="bold")
    t.add_column("status"); t.add_column("mem", justify="right", style="dim")
    t.add_column("up", justify="right", style="dim")
    for p in _pm2():
        name = p.get("name","")
        if "melissa" not in name: continue
        st = p.get("pm2_env",{}).get("status","?")
        mem = p.get("monit",{}).get("memory",0)/1024/1024
        up = _uptime(p.get("pm2_env",{}).get("pm_uptime",0))
        icon = "[ok]●[/ok]" if st=="online" else "[err]●[/err]"
        t.add_row(icon, name, f"[ok]{st}[/ok]" if st=="online" else f"[err]{st}[/err]", f"{mem:.0f}M", up)
    con.print(); con.print(Padding(t,(0,4))); con.print()

def cmd_list(args=""):
    idir = Path("/home/ubuntu/melissa-instances")
    if not idir.exists(): con.print("    [dim]no instances[/dim]"); return
    t = Table(box=box.SIMPLE, border_style="#b48ead", show_edge=False, padding=(0,1))
    t.add_column("", width=3); t.add_column("name", style="bold")
    t.add_column("port", style="dim"); t.add_column("sector", style="m.dim")
    for d in sorted(idir.iterdir()):
        if not d.is_dir() or not (d/".env").exists(): continue
        port=sector=""
        for l in (d/".env").read_text().splitlines():
            if l.startswith("PORT="): port=l.split("=",1)[1]
            if l.startswith("SECTOR="): sector=l.split("=",1)[1]
        t.add_row("[m]⬡[/m]", d.name, f":{port}" if port else "-", sector or "-")
    con.print(); con.print(Padding(t,(0,4))); con.print()

def cmd_new(args=""): _py("melissa_init.py")
def cmd_doctor(args=""): _py("melissa_doctor.py", args.strip() or "melissa")
def cmd_chat(args=""): _py("melissa_studio.py", "--instance", args.strip() or "default")
def cmd_persona(args=""): _py("melissa_persona_cli.py", *(args.split() if args else ["list"]))
def cmd_logs(args=""): _sh("pm2","logs",args.strip() or "melissa","--lines","30","--nostream")
def cmd_sync(args=""): _py("melissa_cli.py","sync")
def cmd_demo(args=""): _py("melissa_cli.py","demo",args or "")
def cmd_modelo(args=""): _py("melissa_cli.py","modelo",args or "")
def cmd_restart(args=""): _sh("pm2","restart",args.strip() or "melissa")
def cmd_stop(args=""): _sh("pm2","stop",args.strip() or "melissa")
def cmd_backup(args=""): _py("melissa_cli.py","backup",args or "")
def cmd_bridge(args=""): _py("melissa_cli.py","bridge",args or "")
def cmd_pair(args=""): _py("melissa_cli.py","pair",args or "")
def cmd_reporte(args=""): _py("melissa_weekly_report.py",args or "default")

def cmd_config(args=""):
    env = Path("/home/ubuntu/melissa/.env")
    if not env.exists(): con.print("    [dim]no .env[/dim]"); return
    lines = [l for l in env.read_text().splitlines() if l and not l.startswith("#") and "KEY" not in l.upper() and "SECRET" not in l.upper()]
    con.print()
    con.print(Padding(Panel("\n".join(lines[:20]),border_style="dim",box=box.ROUNDED,title="[m].env[/m]"),(0,4)))
    con.print()

def cmd_gaps(args=""):
    from datetime import datetime
    f = Path("knowledge_gaps")/f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    if not f.exists(): con.print("    [ok]●[/ok] [dim]no gaps[/dim]"); return
    con.print()
    for line in open(f):
        g=json.loads(line)
        con.print(f"    [warn]?[/warn] {g.get('user_msg','')[:55]} [dim]({g.get('confidence',0):.0%})[/dim]")
    con.print()

def cmd_aprender(args=""):
    if not args or ("→" not in args and "->" not in args):
        con.print('    [dim]uso: melissa aprender "pregunta" → "respuesta"[/dim]'); return
    sep="→" if "→" in args else "->"
    q,a=args.split(sep,1); q=q.strip().strip('"'); a=a.strip().strip('"')
    Path("teachings").mkdir(exist_ok=True)
    with open("teachings/default.jsonl","a") as f:
        f.write(json.dumps({"ts":time.time(),"question":q,"answer":a})+"\n")
    con.print(f"    [ok]✓[/ok] [m]{q[:35]}[/m] → {a[:35]}")


# ─── Router ──────────────────────────────────────────────────────────────────

CMDS = {
    "help":cmd_help,"--help":cmd_help,"-h":cmd_help,"?":cmd_help,
    "status":cmd_status,"s":cmd_status,
    "list":cmd_list,"l":cmd_list,
    "new":cmd_new,"doctor":cmd_doctor,"d":cmd_doctor,"doc":cmd_doctor,
    "chat":cmd_chat,"c":cmd_chat,"studio":cmd_chat,
    "persona":cmd_persona,"logs":cmd_logs,"demo":cmd_demo,
    "modelo":cmd_modelo,"sync":cmd_sync,"sincronizar":cmd_sync,
    "config":cmd_config,"gaps":cmd_gaps,"aprender":cmd_aprender,
    "reporte":cmd_reporte,"restart":cmd_restart,"r":cmd_restart,
    "stop":cmd_stop,"backup":cmd_backup,"bridge":cmd_bridge,"pair":cmd_pair,
}

def route(cmd, args=""):
    if cmd in ("--version","-v"): con.print(f"  melissa v{VERSION}"); return
    fn = CMDS.get(cmd.lower())
    if fn: fn(args)
    else: _py("melissa_cli.py", cmd, args)


# ─── Onboarding ──────────────────────────────────────────────────────────────

def first_run():
    return not Path(os.path.expanduser("~/.melissa/initialized")).exists()

def onboard():
    con.print(); con.print(LOGO_FULL)
    con.print(f"\n    [bold]Welcome.[/bold] [dim]Let's set up your first instance.[/dim]\n")
    r = con.input("    [m]⬡[/m] ready? [dim](y/n)[/dim] ")
    if r.lower() in ("y","yes","s","si","sí",""):
        con.print(); cmd_new()
    Path(os.path.expanduser("~/.melissa")).mkdir(parents=True,exist_ok=True)
    Path(os.path.expanduser("~/.melissa/initialized")).write_text(time.strftime("%Y-%m-%d"))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _pm2():
    try:
        r=subprocess.run(["pm2","jlist"],capture_output=True,text=True,timeout=5)
        return json.loads(r.stdout)
    except: return []

def _uptime(ms):
    if not ms: return "-"
    s=(time.time()*1000-ms)/1000
    if s<60: return f"{int(s)}s"
    if s<3600: return f"{int(s/60)}m"
    if s<86400: return f"{int(s/3600)}h"
    return f"{int(s/86400)}d"

def _py(*a):
    try: subprocess.run([sys.executable]+[str(x) for x in a],cwd="/home/ubuntu/melissa")
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
        cmd_help(big=True)
    else:
        route(sys.argv[1], " ".join(sys.argv[2:]))

if __name__ == "__main__":
    main()
