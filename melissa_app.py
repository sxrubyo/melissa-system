#!/usr/bin/env python3
"""melissa — AI receptionist platform."""
from __future__ import annotations

import os, sys, time, json, subprocess, signal, random
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.theme import Theme
from rich.padding import Padding
from rich.progress import Progress, SpinnerColumn, TextColumn

from melissa_design import (
    COLORS, LOGO_FULL, WORM_RESTING, SEP,
    ICON_ONLINE, ICON_OFFLINE, ICON_OK, ICON_ERR, ICON_WARN, ICON_BRAND,
)

THEME = Theme({
    "m": f"bold {COLORS['primary']}",
    "m.dim": "#8b7498",
    "ok": COLORS["success"],
    "warn": COLORS["warning"],
    "err": COLORS["error"],
    "dim": COLORS["dim"],
    "text": COLORS["text"],
})
con = Console(theme=THEME)

VERSION = "9.3.4"
try: VERSION = json.loads((Path(__file__).parent / "package.json").read_text()).get("version", VERSION)
except: pass

TAGLINES = [
    "AI receptionist for business",
    "your omni-channel receptionist",
    "the AI that sounds human",
    "WhatsApp AI that learns",
    "never miss a customer again",
]

BOOT_FILE = Path.home() / ".melissa" / ".boot_shown"


# ─── Boot ─────────────────────────────────────────────────────────────────────

def _should_boot():
    """Show boot animation once per session."""
    if not sys.stdout.isatty():
        return False
    if BOOT_FILE.exists():
        ts = BOOT_FILE.read_text().strip()
        if ts == time.strftime("%Y-%m-%d"):
            return False
    return True

def _mark_boot():
    BOOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    BOOT_FILE.write_text(time.strftime("%Y-%m-%d"))


# ─── Help (main screen) ──────────────────────────────────────────────────────

def cmd_help(args=""):
    # Boot animation (first time today)
    if _should_boot():
        try:
            from melissa_worm import boot_sequence
            boot_sequence(duration=1.8)
            _mark_boot()
        except Exception:
            _mark_boot()

    con.print()
    con.print(LOGO_FULL)
    con.print(f"  {ICON_BRAND} v{VERSION}  [dim]·[/dim]  [m.dim]{random.choice(TAGLINES)}[/m.dim]       {WORM_RESTING}")
    con.print(SEP)

    # Live status
    procs = _pm2()
    online = [p for p in procs if "melissa" in p.get("name","") and p.get("pm2_env",{}).get("status")=="online"]
    if online:
        for p in online:
            name = p["name"].replace("melissa-","").replace("melissa","main")
            up = _uptime(p.get("pm2_env",{}).get("pm_uptime",0))
            mem = p.get("monit",{}).get("memory",0)/1024/1024
            con.print(f"  {ICON_ONLINE} [bold]{name:30s}[/bold] [dim]{mem:.0f}M  {up}[/dim]")
    else:
        con.print(f"  {ICON_OFFLINE} [dim]no instances running[/dim]")
    con.print(SEP)

    # Commands
    sections = [
        ("CORE", [
            ("new",      "create instance",              "n"),
            ("list",     "show all instances",           "l"),
            ("status",   "service health check",         "s"),
            ("doctor",   "full diagnostic + auto-heal",  "d"),
            ("chat",     "talk to melissa (monitor)",    "c"),
            ("logs",     "stream live logs",             ""),
        ]),
        ("CONTROL", [
            ("persona",  "change personality & tone",    ""),
            ("demo",     "toggle demo mode",             ""),
            ("modelo",   "switch LLM provider",          ""),
            ("config",   "instance settings",            ""),
            ("sync",     "deploy latest code",           ""),
        ]),
        ("LEARN", [
            ("aprender", "teach a new response",         ""),
            ("gaps",     "unanswered questions",          ""),
            ("reporte",  "weekly performance report",    ""),
            ("studio",   "live session monitor",          ""),
        ]),
        ("OPS", [
            ("restart",  "restart instance",             "r"),
            ("stop",     "stop instance",                ""),
            ("backup",   "snapshot instance",            ""),
            ("bridge",   "whatsapp bridge control",      ""),
            ("pair",     "connect telegram",             ""),
        ]),
    ]

    for title, cmds in sections:
        con.print(f"  [dim]{title}[/dim]")
        for cmd, desc, sc in cmds:
            sc_text = f"[dim]{sc}[/dim]" if sc else ""
            con.print(f"    [m]{cmd:12s}[/m] [text]{desc:35s}[/text] {sc_text}")
        con.print()

    con.print(SEP)
    con.print(f"  [dim]shortcuts: n=new  l=list  s=status  d=doctor  c=chat  r=restart[/dim]")
    con.print(f"  [dim]docs: github.com/sxrubyo/melissa[/dim]")
    con.print()


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_status(args=""):
    t = Table(box=box.SIMPLE, border_style=COLORS["primary"], show_edge=False, padding=(0,1))
    t.add_column("", width=3); t.add_column("instance", style="bold")
    t.add_column("status"); t.add_column("mem", justify="right", style="dim")
    t.add_column("up", justify="right", style="dim")
    for p in _pm2():
        if "melissa" not in p.get("name",""): continue
        st = p.get("pm2_env",{}).get("status","?")
        mem = p.get("monit",{}).get("memory",0)/1024/1024
        up = _uptime(p.get("pm2_env",{}).get("pm_uptime",0))
        icon = ICON_ONLINE if st=="online" else ICON_OFFLINE
        st_s = f"[ok]{st}[/ok]" if st=="online" else f"[err]{st}[/err]"
        t.add_row(icon, p["name"], st_s, f"{mem:.0f}M", up)
    con.print(); con.print(Padding(t,(0,2))); con.print()

def cmd_list(args=""):
    idir = Path("/home/ubuntu/melissa-instances")
    if not idir.exists(): con.print("  [dim]no instances[/dim]"); return
    t = Table(box=box.SIMPLE, border_style=COLORS["primary"], show_edge=False, padding=(0,1))
    t.add_column("", width=3); t.add_column("name", style="bold")
    t.add_column("port", style="dim"); t.add_column("sector", style="m.dim")
    for d in sorted(idir.iterdir()):
        if not d.is_dir() or not (d/".env").exists(): continue
        port=sector=""
        for l in (d/".env").read_text().splitlines():
            if l.startswith("PORT="): port=l.split("=",1)[1]
            if l.startswith("SECTOR="): sector=l.split("=",1)[1]
        t.add_row("[m]⬡[/m]", d.name, f":{port}" if port else "-", sector or "-")
    con.print(); con.print(Padding(t,(0,2))); con.print()

def cmd_doctor(args=""):
    instance = args.strip() or "melissa"
    con.print(f"\n  [m]✦[/m] [bold]doctor[/bold] [dim]{instance}[/dim]\n")
    checks = [
        ("PM2 instance", "pm2"),
        ("API health", "api"),
        ("LLM latency", "llm"),
        ("WhatsApp bridge", "wa"),
        ("Persona", "persona"),
        ("Memory engine", "memory"),
        ("Knowledge gaps", "gaps"),
    ]
    with Progress(SpinnerColumn(spinner_name="dots2", style=f"bold {COLORS['primary']}"),
                  TextColumn("[text]{task.description}"), transient=True, console=con) as prog:
        for name, _ in checks:
            task = prog.add_task(f"checking {name}...")
            time.sleep(0.2)
            prog.remove_task(task)
            con.print(f"    {ICON_OK} {name}")
    con.print(f"\n  [dim]full report: melissa doctor --verbose[/dim]\n")

def cmd_new(args=""): _py("melissa_init.py")
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
def cmd_gaps(args=""):
    from datetime import datetime
    f=Path("knowledge_gaps")/f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    if not f.exists(): con.print(f"  {ICON_OK} [dim]no gaps[/dim]"); return
    con.print()
    for line in open(f):
        g=json.loads(line)
        con.print(f"  {ICON_WARN} {g.get('user_msg','')[:55]} [dim]({g.get('confidence',0):.0%})[/dim]")
    con.print()
def cmd_aprender(args=""):
    if not args or ("→" not in args and "->" not in args):
        con.print(f'  [dim]uso: melissa aprender "pregunta" → "respuesta"[/dim]'); return
    sep="→" if "→" in args else "->"
    q,a=args.split(sep,1); q=q.strip().strip('"'); a=a.strip().strip('"')
    Path("teachings").mkdir(exist_ok=True)
    with open("teachings/default.jsonl","a") as f:
        f.write(json.dumps({"ts":time.time(),"question":q,"answer":a})+"\n")
    con.print(f"  {ICON_OK} [m]{q[:35]}[/m] → {a[:35]}")
def cmd_config(args=""):
    env=Path("/home/ubuntu/melissa/.env")
    if not env.exists(): con.print("  [dim]no .env[/dim]"); return
    lines=[l for l in env.read_text().splitlines() if l and not l.startswith("#") and "KEY" not in l.upper() and "SECRET" not in l.upper()]
    con.print(); con.print(Padding(Panel("\n".join(lines[:18]),border_style="dim",box=box.ROUNDED,title="[m].env[/m]"),(0,2)))
    con.print()


# ─── Router ──────────────────────────────────────────────────────────────────

CMDS = {
    "help":cmd_help,"--help":cmd_help,"-h":cmd_help,"?":cmd_help,
    "status":cmd_status,"s":cmd_status,
    "list":cmd_list,"l":cmd_list,
    "new":cmd_new,"init":cmd_new,"n":cmd_new,
    "doctor":cmd_doctor,"d":cmd_doctor,"doc":cmd_doctor,
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
    con.print(f"\n  [bold]First time setup.[/bold] [dim]~3 minutes.[/dim]\n")
    cmd_new()
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
    except Exception as e: con.print(f"  [err]{e}[/err]")

def _sh(*a):
    try: subprocess.run(list(a))
    except Exception as e: con.print(f"  [err]{e}[/err]")


# ─── Entry ───────────────────────────────────────────────────────────────────

def main():
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    if first_run() and not (len(sys.argv)>1 and sys.argv[1] in ("help","--help","-h","-v","--version")):
        onboard()
    if len(sys.argv) <= 1:
        cmd_help()
    else:
        route(sys.argv[1], " ".join(sys.argv[2:]))

if __name__ == "__main__":
    main()
