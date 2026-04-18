#!/usr/bin/env python3
"""
melissa-omni.py — El Ojo que Todo lo Ve v2.0

Centro de comando y control para todas las instancias Melissa.
Solo habla con Santiago. Vigila, analiza, predice y actúa.

CAPACIDADES:
  • Monitoreo en tiempo real de todas las instancias
  • Métricas históricas con tendencias y predicciones
  • Auto-healing: reinicia instancias caídas automáticamente
  • Alertas inteligentes con prioridades y agrupación
  • Analytics profundo: conversión, sentimiento, anomalías
  • Multi-canal: Telegram, Slack, Discord, Email, Webhooks
  • Dashboard web embebido
  • Gestión completa desde chat natural
  • Audit log de todas las acciones
  • Reportes automáticos: diarios, semanales, mensuales
  • Workflows automatizados

MODOS:
  python3 melissa-omni.py server    →  servidor completo (puerto 9001)
  python3 melissa-omni.py chat      →  chat terminal con Omni
  python3 melissa-omni.py status    →  estado rápido
  python3 melissa-omni.py watch     →  monitor live
  python3 melissa-omni.py dashboard →  dashboard en terminal
  python3 melissa-omni.py report    →  generar reporte
  python3 melissa-omni.py analyze   →  análisis profundo
  python3 melissa-omni.py alerts    →  gestionar alertas
  python3 melissa-omni.py logs      →  ver audit log
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import re
import time
import threading
import shutil
import sqlite3
import hashlib
import smtplib
import signal
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import statistics

try:
    import httpx
    _HTTPX = True
except ImportError:
    _HTTPX = False

try:
    from fastapi import FastAPI, Request, Response, BackgroundTasks, WebSocket
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse
    from contextlib import asynccontextmanager
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

try:
    import readline
    HIST_FILE = Path.home() / ".melissa" / "omni_history"
    HIST_FILE.parent.mkdir(exist_ok=True)
    if HIST_FILE.exists():
        readline.read_history_file(str(HIST_FILE))
    readline.set_history_length(500)
    import atexit
    atexit.register(readline.write_history_file, str(HIST_FILE))
except ImportError:
    pass

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════
OMNI_VERSION = "2.0.0"
TEMPLATE_DIR = os.getenv("MELISSA_DIR", "/home/ubuntu/melissa")
INSTANCES_DIR = os.getenv("INSTANCES_DIR", "/home/ubuntu/melissa-instances")

# ── Cargar .env maestro antes de leer variables ───────────────────────────────
# PM2 no carga el .env automáticamente — lo hacemos aquí manualmente
def _load_master_env():
    """Lee el .env maestro y exporta sus variables al entorno del proceso."""
    env_path = os.path.join(TEMPLATE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                # Solo setear si no está ya en el entorno (no pisar vars de PM2)
                if key and val and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass

_load_master_env()
# ─────────────────────────────────────────────────────────────────────────────

OMNI_PORT = int(os.getenv("OMNI_PORT", "9001"))
OMNI_KEY = os.getenv("OMNI_KEY", "omni_secret_change_me")
SANTIAGO_CHAT = os.getenv("SANTIAGO_CHAT_ID", "")
OMNI_TOKEN = os.getenv("OMNI_TELEGRAM_TOKEN", "")
NOVA_PORT = int(os.getenv("NOVA_PORT", "9002"))

# Intervalos
HEALTH_INTERVAL = int(os.getenv("OMNI_HEALTH_INTERVAL", "30"))
METRICS_INTERVAL = int(os.getenv("OMNI_METRICS_INTERVAL", "300"))  # 5 min
AUTO_HEAL_ENABLED = os.getenv("OMNI_AUTO_HEAL", "true").lower() == "true"
AUTO_HEAL_DELAY = int(os.getenv("OMNI_AUTO_HEAL_DELAY", "120"))  # esperar 2 min antes de reiniciar

# Notificaciones
SLACK_WEBHOOK = os.getenv("OMNI_SLACK_WEBHOOK", "")
DISCORD_WEBHOOK = os.getenv("OMNI_DISCORD_WEBHOOK", "")
PAGERDUTY_KEY = os.getenv("OMNI_PAGERDUTY_KEY", "")
SMTP_HOST = os.getenv("OMNI_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("OMNI_SMTP_PORT", "587"))
SMTP_USER = os.getenv("OMNI_SMTP_USER", "")
SMTP_PASS = os.getenv("OMNI_SMTP_PASS", "")
ALERT_EMAIL = os.getenv("OMNI_ALERT_EMAIL", "")
CUSTOM_WEBHOOK = os.getenv("OMNI_CUSTOM_WEBHOOK", "")

# Base de datos
OMNI_DB = Path.home() / ".melissa" / "omni.db"
OMNI_DB.parent.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# COLORES
# ══════════════════════════════════════════════════════════════════════════════
def _tty(): return sys.stdout.isatty() or bool(os.getenv("FORCE_COLOR"))
def _e(c): return f"\033[{c}m" if _tty() else ""

class C:
    R = _e("0"); BOLD = _e("1"); DIM = _e("2"); ITALIC = _e("3")
    P1 = _e("38;5;183"); P2 = _e("38;5;141"); P3 = _e("38;5;135")
    P4 = _e("38;5;99"); P5 = _e("38;5;57")
    W = _e("38;5;15"); G0 = _e("38;5;252"); G1 = _e("38;5;248")
    G2 = _e("38;5;244"); G3 = _e("38;5;240"); G4 = _e("38;5;236")
    GRN = _e("38;5;114"); RED = _e("38;5;203")
    YLW = _e("38;5;221"); CYN = _e("38;5;117"); AMB = _e("38;5;179")
    BLU = _e("38;5;75"); MAG = _e("38;5;177"); ORG = _e("38;5;208")

def q(color, text, bold=False):
    return f"{C.BOLD if bold else ''}{color}{text}{C.R}"

# ══════════════════════════════════════════════════════════════════════════════
# SECTORES (sincronizado con CLI)
# ══════════════════════════════════════════════════════════════════════════════
SECTORS = {
    "estetica": ("💉", "Clínica Estética", "183"),
    "dental": ("🦷", "Clínica Dental", "117"),
    "veterinaria": ("🐾", "Veterinaria", "114"),
    "restaurante": ("🍽️", "Restaurante", "221"),
    "hotel": ("🏨", "Hotel", "179"),
    "gimnasio": ("💪", "Gimnasio", "203"),
    "belleza": ("💇", "Salón de Belleza", "177"),
    "spa": ("🧖", "Spa", "141"),
    "medico": ("🩺", "Consultorio Médico", "117"),
    "psicologo": ("🧠", "Psicología", "135"),
    "abogado": ("⚖️", "Legal", "99"),
    "inmobiliaria": ("🏠", "Inmobiliaria", "179"),
    "taller": ("🔧", "Taller", "208"),
    "academia": ("📚", "Academia", "221"),
    "nutricion": ("🥗", "Nutrición", "114"),
    "fisioterapia": ("🦴", "Fisioterapia", "117"),
    "fotografia": ("📸", "Fotografía", "183"),
    "coworking": ("🏢", "Coworking", "141"),
    "tattoo": ("🎨", "Tattoo", "99"),
    "otro": ("⚙️", "Otro", "248"),
}

def get_sector_info(sector_id: str) -> Tuple[str, str, str]:
    return SECTORS.get(sector_id, SECTORS["otro"])

# ══════════════════════════════════════════════════════════════════════════════
# UI PRIMITIVES
# ══════════════════════════════════════════════════════════════════════════════
def ok(m): print(f"  {q(C.GRN, '✓')}  {q(C.W, m)}")
def fail(m): print(f"  {q(C.RED, '✗')}  {q(C.W, m)}")
def warn(m): print(f"  {q(C.YLW, '!')}  {q(C.G1, m)}")
def info(m): print(f"  {q(C.P2, '·')}  {q(C.G1, m)}")
def dim(m): print(f"       {q(C.G3, m)}")
def nl(): print()
def hr(): print("  " + q(C.G3, "─" * 58))

def section(title, sub="", icon="✦"):
    print()
    print(f"  {q(C.P1, icon, bold=True)}  {q(C.W, title, bold=True)}")
    if sub:
        print(f"       {q(C.G2, sub)}")
    print()

def kv(key, val, color=None):
    c = color or C.P2
    print(f"  {q(C.G2, f'{key:<22}')}  {q(c, str(val))}")

def table(headers, rows, colors=None):
    if not rows:
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                clean = re.sub(r'\033\[[0-9;]*m', '', str(cell))
                widths[i] = max(widths[i], len(clean))
    
    header_line = "  "
    for i, h in enumerate(headers):
        header_line += f"{q(C.G3, h.ljust(widths[i]))}  "
    print(header_line)
    print(f"  {q(C.G4, '─' * (sum(widths) + len(widths) * 2))}")
    
    for row in rows:
        line = "  "
        for i, cell in enumerate(row):
            clean = re.sub(r'\033\[[0-9;]*m', '', str(cell))
            padding = widths[i] - len(clean)
            line += f"{cell}{' ' * padding}  "
        print(line)

def progress_bar(current, total, width=30, label=""):
    pct = current / total if total > 0 else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"{q(C.P2, bar)} {q(C.W, f'{pct*100:.0f}%')} {q(C.G3, label)}"

def spark_line(values: List[float], width: int = 20) -> str:
    """Mini gráfico de línea con caracteres."""
    if not values:
        return "─" * width
    
    blocks = "▁▂▃▄▅▆▇█"
    min_v, max_v = min(values), max(values)
    range_v = max_v - min_v if max_v != min_v else 1
    
    # Resample to width
    step = len(values) / width
    result = ""
    for i in range(width):
        idx = int(i * step)
        v = values[min(idx, len(values) - 1)]
        normalized = (v - min_v) / range_v
        block_idx = int(normalized * (len(blocks) - 1))
        result += blocks[block_idx]
    
    return result

def ascii_chart(data: Dict[str, float], width: int = 40) -> List[str]:
    """Gráfico de barras horizontal ASCII."""
    if not data:
        return []
    
    max_val = max(data.values()) if data.values() else 1
    max_label = max(len(str(k)) for k in data.keys())
    lines = []
    
    for label, value in data.items():
        bar_width = int((value / max_val) * width) if max_val > 0 else 0
        bar = "█" * bar_width
        lines.append(f"  {label:>{max_label}}  {q(C.P2, bar)} {q(C.W, str(int(value)))}")
    
    return lines

class Spinner:
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    def __init__(self, msg):
        self.msg = msg
        self._stop = threading.Event()
        self._thread = None
        self._finished = False
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, *a):
        self.finish()
    
    def start(self):
        def _run():
            i = 0
            while not self._stop.is_set():
                sys.stdout.write(f"\r  {q(C.P2, self.FRAMES[i % len(self.FRAMES)])}  {q(C.G1, self.msg)}")
                sys.stdout.flush()
                time.sleep(0.08)
                i += 1
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
    
    def update(self, msg):
        self.msg = msg
    
    def finish(self, msg=None, ok_=True):
        if self._finished:
            return
        self._finished = True
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.2)
        icon = q(C.GRN, "✓") if ok_ else q(C.RED, "✗")
        sys.stdout.write(f"\r  {icon}  {q(C.W, msg or self.msg)}\n")
        sys.stdout.flush()

def print_logo(compact=False):
    print()
    if compact:
        print(f"  {q(C.AMB, '◉', bold=True)}  {q(C.W, 'melissa omni', bold=True)}  "
              f"{q(C.G3, f'v{OMNI_VERSION}')}")
        print()
        return
    
    rows = [
        ("38;5;208", "   ██████╗ ███╗   ███╗███╗   ██╗██╗"),
        ("38;5;179", "  ██╔═══██╗████╗ ████║████╗  ██║██║"),
        ("38;5;221", "  ██║   ██║██╔████╔██║██╔██╗ ██║██║"),
        ("38;5;214", "  ██║   ██║██║╚██╔╝██║██║╚██╗██║██║"),
        ("38;5;208", "  ╚██████╔╝██║ ╚═╝ ██║██║ ╚████║██║"),
        ("38;5;202", "   ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝"),
    ]
    for col, row in rows:
        print(f"{C.BOLD}{_e(col)}{row}{C.R}")
    print()
    print(f"  {q(C.AMB, '◉')} {q(C.W, 'OMNI', bold=True)}  {q(C.G3, '·')}  "
          f"{q(C.G2, 'El Ojo que Todo lo Ve')}  "
          f"{q(C.G3, f'v{OMNI_VERSION}')}")
    print(f"  {q(C.G4, '─' * 40)}")
    print()

# ══════════════════════════════════════════════════════════════════════════════
# BASE DE DATOS - Métricas históricas, eventos, audit log
# ══════════════════════════════════════════════════════════════════════════════
def init_db():
    """Inicializar base de datos SQLite."""
    conn = sqlite3.connect(str(OMNI_DB))
    cursor = conn.cursor()
    
    # Métricas históricas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT,
            latency_ms REAL,
            memory_mb REAL,
            cpu_percent REAL,
            conversations INTEGER,
            appointments INTEGER,
            messages INTEGER,
            error_rate REAL
        )
    """)
    
    # Eventos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            instance TEXT,
            event_type TEXT NOT NULL,
            severity TEXT DEFAULT 'info',
            details TEXT,
            acknowledged INTEGER DEFAULT 0,
            acknowledged_at DATETIME,
            acknowledged_by TEXT
        )
    """)
    
    # Audit log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            actor TEXT,
            action TEXT NOT NULL,
            target TEXT,
            details TEXT,
            ip_address TEXT
        )
    """)
    
    # Alertas configuradas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            instance TEXT,
            metric TEXT NOT NULL,
            operator TEXT NOT NULL,
            threshold REAL NOT NULL,
            severity TEXT DEFAULT 'warning',
            channels TEXT DEFAULT 'telegram',
            cooldown_minutes INTEGER DEFAULT 30,
            enabled INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_triggered DATETIME
        )
    """)
    
    # Workflows automáticos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            trigger_event TEXT NOT NULL,
            trigger_filter TEXT,
            actions TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_run DATETIME,
            run_count INTEGER DEFAULT 0
        )
    """)
    
    # Conversaciones con Santiago
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS santiago_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            role TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """)
    
    # Preferencias aprendidas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Índices para búsquedas rápidas
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_instance ON metrics(instance)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
    
    conn.commit()
    conn.close()

def db_execute(query: str, params: tuple = (), fetch: bool = False):
    """Ejecutar query en la base de datos."""
    conn = sqlite3.connect(str(OMNI_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    
    if fetch:
        result = cursor.fetchall()
        conn.close()
        return [dict(row) for row in result]
    
    conn.commit()
    conn.close()
    return cursor.lastrowid

def log_event(instance: str, event_type: str, details: str = "", severity: str = "info"):
    """Registrar un evento."""
    db_execute(
        "INSERT INTO events (instance, event_type, severity, details) VALUES (?, ?, ?, ?)",
        (instance, event_type, severity, details)
    )

def log_audit(actor: str, action: str, target: str = "", details: str = "", ip: str = ""):
    """Registrar en audit log."""
    db_execute(
        "INSERT INTO audit_log (actor, action, target, details, ip_address) VALUES (?, ?, ?, ?, ?)",
        (actor, action, target, details, ip)
    )

def record_metrics(instance: str, status: str, latency_ms: float, 
                   conversations: int = 0, appointments: int = 0, messages: int = 0):
    """Registrar métricas de una instancia."""
    db_execute("""
        INSERT INTO metrics (instance, status, latency_ms, conversations, appointments, messages)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (instance, status, latency_ms, conversations, appointments, messages))

def get_metrics_history(instance: str, hours: int = 24) -> List[Dict]:
    """Obtener historial de métricas."""
    return db_execute("""
        SELECT * FROM metrics 
        WHERE instance = ? AND timestamp > datetime('now', ?)
        ORDER BY timestamp ASC
    """, (instance, f'-{hours} hours'), fetch=True)

def get_recent_events(limit: int = 50, severity: str = None) -> List[Dict]:
    """Obtener eventos recientes."""
    if severity:
        return db_execute("""
            SELECT * FROM events WHERE severity = ? 
            ORDER BY timestamp DESC LIMIT ?
        """, (severity, limit), fetch=True)
    return db_execute("""
        SELECT * FROM events ORDER BY timestamp DESC LIMIT ?
    """, (limit,), fetch=True)

def get_unacknowledged_events() -> List[Dict]:
    """Obtener eventos sin reconocer."""
    return db_execute("""
        SELECT * FROM events 
        WHERE acknowledged = 0 AND severity IN ('warning', 'critical', 'error')
        ORDER BY timestamp DESC
    """, fetch=True)

def acknowledge_event(event_id: int, by: str = "Santiago"):
    """Reconocer un evento."""
    db_execute("""
        UPDATE events 
        SET acknowledged = 1, acknowledged_at = datetime('now'), acknowledged_by = ?
        WHERE id = ?
    """, (by, event_id))

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def load_env(path: str) -> dict:
    env = {}
    try:
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env

def update_env_key(path: str, key: str, value: str) -> None:
    env_path = Path(path)
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    rendered = []
    found = False
    for raw in lines:
        if "=" in raw and raw.split("=", 1)[0].strip() == key:
            rendered.append(f"{key}={value}")
            found = True
        else:
            rendered.append(raw)
    if not found:
        rendered.append(f"{key}={value}")
    env_path.write_text("\n".join(rendered) + "\n")

def resolve_instance(instances: List["Instance"], name: str) -> Optional["Instance"]:
    if not name:
        return None
    q = name.strip().lower()
    for inst in instances:
        candidates = {
            inst.name.lower(),
            inst.label.lower(),
            inst.label.lower().replace(" ", "-"),
            inst.name.lower().replace("-", " "),
        }
        if any(q == c for c in candidates):
            return inst
    for inst in instances:
        haystack = " | ".join([
            inst.name.lower(),
            inst.label.lower(),
            inst.label.lower().replace(" ", "-"),
            inst.name.lower().replace("-", " "),
        ])
        if q in haystack:
            return inst
    return None

@dataclass
class Instance:
    name: str
    label: str
    port: int
    dir: str
    env: dict
    is_base: bool = False
    sector: str = "otro"
    
    @property
    def sector_info(self) -> Tuple[str, str, str]:
        return get_sector_info(self.sector)
    
    @property
    def pm2_name(self) -> str:
        return "melissa" if self.is_base else f"melissa-{self.name}"

def get_all_instances() -> List[Instance]:
    instances = []
    
    be = load_env(f"{TEMPLATE_DIR}/.env")
    if be:
        instances.append(Instance(
            name="base",
            label=be.get("CLINIC_NAME", "Instancia base"),
            port=int(be.get("PORT", 8001)),
            dir=TEMPLATE_DIR,
            env=dict(be),
            is_base=True,
            sector=be.get("SECTOR", "estetica")
        ))
    
    if os.path.isdir(INSTANCES_DIR):
        for name in sorted(os.listdir(INSTANCES_DIR)):
            d = f"{INSTANCES_DIR}/{name}"
            ep = f"{d}/.env"
            if not os.path.isdir(d) or not os.path.exists(ep):
                continue
            
            ev = load_env(ep)
            meta_path = f"{d}/instance.json"
            meta = {}
            if os.path.exists(meta_path):
                try:
                    meta = json.loads(Path(meta_path).read_text())
                except Exception:
                    pass
            
            instances.append(Instance(
                name=name,
                label=meta.get("label", name.replace("-", " ").title()),
                port=int(ev.get("PORT", 8002)),
                dir=d,
                env=dict(ev),
                is_base=False,
                sector=ev.get("SECTOR", meta.get("sector", "otro"))
            ))
    
    return instances

async def http_get(url: str, timeout: float = 5.0, headers: dict = None) -> Optional[Dict]:
    try:
        if _HTTPX:
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.get(url, headers=headers or {})
                return r.json() if r.status_code == 200 else None
        else:
            req = urllib.request.urlopen(url, timeout=int(timeout))
            return json.loads(req.read())
    except Exception:
        return None

async def http_post(url: str, data: dict, headers: dict = None, timeout: float = 10.0) -> Optional[Dict]:
    try:
        if _HTTPX:
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.post(url, json=data, headers=headers or {})
                return r.json() if r.status_code in (200, 201) else None
    except Exception:
        return None

async def health_check(port: int) -> Tuple[Dict, float]:
    """Health check con latencia."""
    start = time.time()
    h = await http_get(f"http://localhost:{port}/health")
    latency = (time.time() - start) * 1000
    return h or {}, latency

async def set_instance_demo(
    inst: Instance,
    active: bool,
    business_name: str = "",
    sector: str = "",
    session_ttl: int = 1800,
) -> Dict[str, Any]:
    """Activa o desactiva demo mode en una instancia y lo deja persistido."""
    env_path = Path(inst.dir) / ".env"
    current_env = load_env(str(env_path))

    if active:
        business_name = business_name or current_env.get("DEMO_BUSINESS_NAME") or current_env.get("CLINIC_NAME") or inst.label
        sector = sector or current_env.get("DEMO_SECTOR") or current_env.get("SECTOR") or inst.sector or "otro"
        update_env_key(str(env_path), "DEMO_MODE", "true")
        update_env_key(str(env_path), "DEMO_BUSINESS_NAME", business_name)
        update_env_key(str(env_path), "DEMO_SECTOR", sector)
        update_env_key(str(env_path), "DEMO_SESSION_TTL", str(session_ttl))
    else:
        business_name = business_name or current_env.get("DEMO_BUSINESS_NAME") or inst.label
        sector = sector or current_env.get("DEMO_SECTOR") or current_env.get("SECTOR") or inst.sector or "otro"
        update_env_key(str(env_path), "DEMO_MODE", "false")

    pm2_restart(inst.pm2_name)
    await asyncio.sleep(4)
    status = await http_get(f"http://localhost:{inst.port}/demo/status") or {}
    health, latency = await health_check(inst.port)

    return {
        "instance": inst.name,
        "label": inst.label,
        "active": bool(status.get("demo_mode", active)),
        "business_name": status.get("business_name", business_name),
        "sector": status.get("sector", sector),
        "session_ttl": status.get("session_ttl", session_ttl),
        "health": health.get("status", "offline"),
        "latency_ms": round(latency, 1),
    }

async def get_instance_stats(port: int, master_key: str) -> Dict:
    if not _HTTPX:
        return {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(
                f"http://localhost:{port}/analytics/summary?days=7",
                headers={"X-Master-Key": master_key}
            )
            return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

async def get_recent_conversations(port: int, master_key: str, limit: int = 10) -> List[Dict]:
    if not _HTTPX:
        return []
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(
                f"http://localhost:{port}/conversations/patients?limit={limit}",
                headers={"X-Master-Key": master_key}
            )
            return r.json().get("conversations", []) if r.status_code == 200 else []
    except Exception:
        return []

async def send_to_instance(port: int, master_key: str, chat_id: str, msg: str) -> bool:
    result = await http_post(
        f"http://localhost:{port}/send-message",
        {"chat_id": chat_id, "message": msg},
        {"X-Master-Key": master_key}
    )
    return result is not None

def pm2_command(action: str, name: str) -> bool:
    import subprocess
    result = subprocess.run(["pm2", action, name], capture_output=True)
    return result.returncode == 0

def pm2_restart(name: str) -> bool:
    return pm2_command("restart", name)

def pm2_stop(name: str) -> bool:
    return pm2_command("stop", name)

def pm2_list() -> List[Dict]:
    import subprocess
    try:
        result = subprocess.run(["pm2", "jlist"], capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return []

# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICACIONES MULTI-CANAL
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class Notification:
    title: str
    message: str
    severity: str = "info"  # info, warning, error, critical
    instance: str = ""
    channels: List[str] = field(default_factory=lambda: ["telegram"])

async def send_telegram(text: str, chat_id: str = None, token: str = None, parse_mode: str = "Markdown"):
    # Refrescar desde environ por si fue cargado por _load_master_env post-import
    cid = chat_id or os.environ.get("SANTIAGO_CHAT_ID", "") or SANTIAGO_CHAT
    tok = token or os.environ.get("OMNI_TELEGRAM_TOKEN", "") or OMNI_TOKEN
    if not cid or not tok:
        print(f"  [omni] send_telegram: sin token ({bool(tok)}) o chat_id ({bool(cid)})")
        return False
    
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    try:
        if _HTTPX:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.post(url, json={
                    "chat_id": cid,
                    "text": text,
                    "parse_mode": parse_mode
                })
                return r.status_code == 200
    except Exception as e:
        print(f"  [omni] telegram error: {e}")
    return False

async def send_slack(text: str, webhook: str = None):
    wh = webhook or SLACK_WEBHOOK
    if not wh:
        return False
    
    try:
        if _HTTPX:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.post(wh, json={"text": text})
                return r.status_code == 200
    except Exception:
        pass
    return False

async def send_discord(text: str, webhook: str = None):
    wh = webhook or DISCORD_WEBHOOK
    if not wh:
        return False
    
    try:
        if _HTTPX:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.post(wh, json={"content": text})
                return r.status_code in (200, 204)
    except Exception:
        pass
    return False

async def send_email(subject: str, body: str, to: str = None):
    recipient = to or ALERT_EMAIL
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, recipient]):
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = recipient
        msg['Subject'] = f"[Melissa Omni] {subject}"
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception:
        pass
    return False

async def send_custom_webhook(data: dict, url: str = None):
    wh = url or CUSTOM_WEBHOOK
    if not wh:
        return False
    
    try:
        if _HTTPX:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.post(wh, json=data)
                return r.status_code in (200, 201, 204)
    except Exception:
        pass
    return False

async def send_notification(notif: Notification):
    """Enviar notificación a todos los canales configurados."""
    severity_emoji = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "🔥",
        "critical": "🚨"
    }
    emoji = severity_emoji.get(notif.severity, "📌")
    
    # Texto formateado
    text = f"{emoji} *{notif.title}*"
    if notif.instance:
        text += f"\n📍 {notif.instance}"
    text += f"\n\n{notif.message}"
    
    tasks = []
    
    if "telegram" in notif.channels:
        tasks.append(send_telegram(text))
    
    if "slack" in notif.channels and SLACK_WEBHOOK:
        tasks.append(send_slack(text))
    
    if "discord" in notif.channels and DISCORD_WEBHOOK:
        tasks.append(send_discord(text))
    
    if "email" in notif.channels and SMTP_HOST:
        tasks.append(send_email(notif.title, notif.message))
    
    if "webhook" in notif.channels and CUSTOM_WEBHOOK:
        tasks.append(send_custom_webhook({
            "title": notif.title,
            "message": notif.message,
            "severity": notif.severity,
            "instance": notif.instance,
            "timestamp": datetime.utcnow().isoformat()
        }))
    
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    
    # Log event
    log_event(notif.instance, f"notification_{notif.severity}", notif.message, notif.severity)

# ══════════════════════════════════════════════════════════════════════════════
# ALERTAS INTELIGENTES
# ══════════════════════════════════════════════════════════════════════════════
_alert_cooldowns: Dict[str, datetime] = {}

async def check_alert_rules(instance: str, metrics: Dict):
    """Verificar reglas de alerta para una instancia."""
    rules = db_execute("""
        SELECT * FROM alert_rules WHERE enabled = 1 AND (instance = ? OR instance = '*')
    """, (instance,), fetch=True)
    
    for rule in rules:
        rule_id = f"{rule['id']}_{instance}"
        
        # Verificar cooldown
        if rule_id in _alert_cooldowns:
            if datetime.now() - _alert_cooldowns[rule_id] < timedelta(minutes=rule['cooldown_minutes']):
                continue
        
        # Obtener valor de métrica
        metric_value = metrics.get(rule['metric'])
        if metric_value is None:
            continue
        
        # Evaluar condición
        triggered = False
        op = rule['operator']
        threshold = rule['threshold']
        
        if op == '>' and metric_value > threshold:
            triggered = True
        elif op == '<' and metric_value < threshold:
            triggered = True
        elif op == '>=' and metric_value >= threshold:
            triggered = True
        elif op == '<=' and metric_value <= threshold:
            triggered = True
        elif op == '==' and metric_value == threshold:
            triggered = True
        elif op == '!=' and metric_value != threshold:
            triggered = True
        
        if triggered:
            _alert_cooldowns[rule_id] = datetime.now()
            
            # Actualizar last_triggered
            db_execute(
                "UPDATE alert_rules SET last_triggered = datetime('now') WHERE id = ?",
                (rule['id'],)
            )
            
            # Enviar notificación
            channels = rule.get('channels', 'telegram').split(',')
            await send_notification(Notification(
                title=rule['name'],
                message=f"{rule['metric']} = {metric_value} ({op} {threshold})",
                severity=rule['severity'],
                instance=instance,
                channels=channels
            ))

def create_alert_rule(name: str, instance: str, metric: str, operator: str, 
                      threshold: float, severity: str = "warning", 
                      channels: str = "telegram", cooldown: int = 30):
    """Crear nueva regla de alerta."""
    return db_execute("""
        INSERT INTO alert_rules (name, instance, metric, operator, threshold, severity, channels, cooldown_minutes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, instance, metric, operator, threshold, severity, channels, cooldown))

def get_alert_rules() -> List[Dict]:
    return db_execute("SELECT * FROM alert_rules ORDER BY id", fetch=True)

def delete_alert_rule(rule_id: int):
    db_execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))

def toggle_alert_rule(rule_id: int, enabled: bool):
    db_execute("UPDATE alert_rules SET enabled = ? WHERE id = ?", (1 if enabled else 0, rule_id))

# ══════════════════════════════════════════════════════════════════════════════
# WORKFLOWS AUTOMÁTICOS
# ══════════════════════════════════════════════════════════════════════════════
async def execute_workflow_action(action: Dict, context: Dict):
    """Ejecutar una acción de workflow."""
    action_type = action.get("type")
    
    if action_type == "notify":
        await send_notification(Notification(
            title=action.get("title", "Workflow Alert"),
            message=action.get("message", "").format(**context),
            severity=action.get("severity", "info"),
            instance=context.get("instance", ""),
            channels=action.get("channels", ["telegram"])
        ))
    
    elif action_type == "restart":
        instance_name = action.get("instance") or context.get("instance")
        if instance_name:
            pm2_name = "melissa" if instance_name == "base" else f"melissa-{instance_name}"
            success = pm2_restart(pm2_name)
            log_audit("workflow", "restart", instance_name, f"success={success}")
    
    elif action_type == "webhook":
        await send_custom_webhook({
            **context,
            "workflow_action": action
        }, action.get("url"))
    
    elif action_type == "log":
        log_event(
            context.get("instance", ""),
            "workflow_log",
            action.get("message", "").format(**context),
            action.get("severity", "info")
        )

async def process_event_for_workflows(event_type: str, event_data: Dict):
    """Procesar un evento y ejecutar workflows si aplican."""
    workflows = db_execute("""
        SELECT * FROM workflows WHERE enabled = 1 AND trigger_event = ?
    """, (event_type,), fetch=True)
    
    for wf in workflows:
        # Verificar filtro si existe
        trigger_filter = wf.get("trigger_filter")
        if trigger_filter:
            try:
                filter_dict = json.loads(trigger_filter)
                match = all(event_data.get(k) == v for k, v in filter_dict.items())
                if not match:
                    continue
            except Exception:
                pass
        
        # Ejecutar acciones
        try:
            actions = json.loads(wf.get("actions", "[]"))
            for action in actions:
                await execute_workflow_action(action, event_data)
            
            # Actualizar stats
            db_execute("""
                UPDATE workflows 
                SET last_run = datetime('now'), run_count = run_count + 1 
                WHERE id = ?
            """, (wf['id'],))
        except Exception as e:
            log_event("omni", "workflow_error", f"Workflow {wf['name']}: {e}", "error")

def create_workflow(name: str, trigger_event: str, actions: List[Dict], 
                    trigger_filter: Dict = None) -> int:
    """Crear nuevo workflow."""
    return db_execute("""
        INSERT INTO workflows (name, trigger_event, trigger_filter, actions)
        VALUES (?, ?, ?, ?)
    """, (name, trigger_event, json.dumps(trigger_filter) if trigger_filter else None, json.dumps(actions)))

def get_workflows() -> List[Dict]:
    return db_execute("SELECT * FROM workflows ORDER BY id", fetch=True)

# ══════════════════════════════════════════════════════════════════════════════
# AUTO-HEALING
# ══════════════════════════════════════════════════════════════════════════════
_down_since: Dict[str, datetime] = {}
_restart_attempts: Dict[str, int] = {}

async def auto_heal_instance(instance: Instance):
    """Intentar recuperar una instancia caída."""
    if not AUTO_HEAL_ENABLED:
        return
    
    name = instance.name
    now = datetime.now()
    
    # Verificar si ya pasó el delay
    if name in _down_since:
        down_time = now - _down_since[name]
        if down_time.total_seconds() < AUTO_HEAL_DELAY:
            return  # Esperar más
    else:
        _down_since[name] = now
        return  # Primera vez, empezar a contar
    
    # Verificar intentos
    attempts = _restart_attempts.get(name, 0)
    if attempts >= 3:
        # Demasiados intentos, escalar
        if attempts == 3:
            await send_notification(Notification(
                title="Auto-heal fallido",
                message=f"3 intentos de reinicio sin éxito. Requiere intervención manual.",
                severity="critical",
                instance=name,
                channels=["telegram", "email"]
            ))
            _restart_attempts[name] = 4  # Evitar spam
        return
    
    # Intentar reiniciar
    log_audit("omni_auto_heal", "restart_attempt", name, f"attempt={attempts + 1}")
    success = pm2_restart(instance.pm2_name)
    
    if success:
        _restart_attempts[name] = attempts + 1
        await send_notification(Notification(
            title="Auto-heal: Reiniciando",
            message=f"Intento {attempts + 1}/3",
            severity="warning",
            instance=name
        ))
        
        # Esperar y verificar
        await asyncio.sleep(15)
        h, _ = await health_check(instance.port)
        
        if h.get("status") == "online":
            del _down_since[name]
            _restart_attempts[name] = 0
            await send_notification(Notification(
                title="Auto-heal: Recuperado",
                message="Instancia online nuevamente",
                severity="info",
                instance=name
            ))
            log_event(name, "auto_healed", f"Recuperado después de {attempts + 1} intentos", "info")
    else:
        _restart_attempts[name] = attempts + 1
        log_event(name, "auto_heal_failed", f"pm2 restart falló", "error")

# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISIS Y PREDICCIÓN
# ══════════════════════════════════════════════════════════════════════════════
def analyze_trends(instance: str, hours: int = 24) -> Dict:
    """Analizar tendencias de una instancia."""
    metrics = get_metrics_history(instance, hours)
    
    if len(metrics) < 2:
        return {"status": "insufficient_data"}
    
    latencies = [m['latency_ms'] for m in metrics if m.get('latency_ms')]
    conversations = [m['conversations'] for m in metrics if m.get('conversations') is not None]
    
    analysis = {
        "instance": instance,
        "period_hours": hours,
        "data_points": len(metrics),
        "latency": {},
        "availability": {},
        "trends": {}
    }
    
    # Latencia
    if latencies:
        analysis["latency"] = {
            "avg": statistics.mean(latencies),
            "min": min(latencies),
            "max": max(latencies),
            "stddev": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "p95": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 20 else max(latencies),
            "current": latencies[-1],
            "trend": "up" if len(latencies) >= 10 and statistics.mean(latencies[-5:]) > statistics.mean(latencies[-10:-5]) * 1.1 else "stable"
        }
    
    # Disponibilidad
    total = len(metrics)
    online = sum(1 for m in metrics if m.get('status') == 'online')
    analysis["availability"] = {
        "percentage": (online / total * 100) if total > 0 else 0,
        "total_checks": total,
        "online_checks": online,
        "outages": total - online
    }
    
    # Tendencias
    if conversations and len(conversations) >= 2:
        first_half = statistics.mean(conversations[:len(conversations)//2])
        second_half = statistics.mean(conversations[len(conversations)//2:])
        
        if second_half > first_half * 1.1:
            analysis["trends"]["conversations"] = "increasing"
        elif second_half < first_half * 0.9:
            analysis["trends"]["conversations"] = "decreasing"
        else:
            analysis["trends"]["conversations"] = "stable"
    
    return analysis

def detect_anomalies(instance: str, hours: int = 6) -> List[Dict]:
    """Detectar anomalías en las métricas."""
    metrics = get_metrics_history(instance, hours)
    
    if len(metrics) < 10:
        return []
    
    anomalies = []
    latencies = [m['latency_ms'] for m in metrics if m.get('latency_ms')]
    
    if len(latencies) >= 10:
        mean = statistics.mean(latencies)
        stddev = statistics.stdev(latencies)
        
        for i, m in enumerate(metrics):
            lat = m.get('latency_ms')
            if lat and abs(lat - mean) > 3 * stddev:
                anomalies.append({
                    "type": "latency_spike",
                    "timestamp": m['timestamp'],
                    "value": lat,
                    "expected_range": f"{mean - 2*stddev:.0f} - {mean + 2*stddev:.0f}",
                    "severity": "warning" if lat < mean + 5 * stddev else "error"
                })
    
    # Caídas repentinas
    prev_status = None
    for m in metrics:
        status = m.get('status')
        if prev_status == 'online' and status == 'offline':
            anomalies.append({
                "type": "sudden_offline",
                "timestamp": m['timestamp'],
                "severity": "error"
            })
        prev_status = status
    
    return anomalies

def predict_issues(instance: str) -> List[Dict]:
    """Predecir posibles problemas basado en tendencias."""
    analysis = analyze_trends(instance, 24)
    predictions = []
    
    if analysis.get("status") == "insufficient_data":
        return predictions
    
    # Latencia en aumento
    lat = analysis.get("latency", {})
    if lat.get("trend") == "up" and lat.get("current", 0) > lat.get("avg", 0) * 1.5:
        predictions.append({
            "type": "latency_degradation",
            "probability": "high",
            "message": "Latencia en aumento. Posible sobrecarga inminente.",
            "recommendation": "Considerar escalar o revisar recursos."
        })
    
    # Disponibilidad baja
    avail = analysis.get("availability", {})
    if avail.get("percentage", 100) < 95:
        predictions.append({
            "type": "stability_issues",
            "probability": "medium",
            "message": f"Disponibilidad del {avail.get('percentage', 0):.1f}% en las últimas 24h.",
            "recommendation": "Revisar logs y configuración."
        })
    
    return predictions

# ══════════════════════════════════════════════════════════════════════════════
# REPORTES
# ══════════════════════════════════════════════════════════════════════════════
async def generate_daily_report() -> str:
    """Generar reporte diario completo."""
    instances = get_all_instances()
    
    # Health checks en paralelo
    health_results = await asyncio.gather(*[health_check(i.port) for i in instances])
    
    # Stats de cada instancia
    stats_results = await asyncio.gather(*[
        get_instance_stats(i.port, i.env.get("MASTER_API_KEY", ""))
        for i in instances
    ])
    
    lines = [
        f"📊 *Reporte Diario — {datetime.now().strftime('%d/%m/%Y')}*",
        ""
    ]
    
    # Resumen general
    online = sum(1 for h, _ in health_results if h.get("status") == "online")
    total_conversations = 0
    total_appointments = 0
    
    lines.append(f"*Resumen General*")
    lines.append(f"• Instancias: {online}/{len(instances)} online")
    
    # Por instancia
    lines.append("")
    lines.append("*Por Instancia:*")
    
    for inst, (health, latency), stats in zip(instances, health_results, stats_results):
        emoji, sector_name, _ = inst.sector_info
        is_up = health.get("status") == "online"
        status_icon = "🟢" if is_up else "🔴"
        
        convs = stats.get("total_conversations", 0)
        apts = stats.get("total_appointments", 0)
        total_conversations += convs
        total_appointments += apts
        
        wa = health.get("whatsapp", {})
        plat = "WA" if wa.get("connected") else "TG"
        
        lines.append(f"{status_icon} {emoji} *{inst.label}* ({plat})")
        if is_up:
            lines.append(f"   └ {convs} convs | {apts} citas | {latency:.0f}ms")
        else:
            lines.append(f"   └ OFFLINE")
    
    lines.append("")
    lines.append(f"*Totales:*")
    lines.append(f"• {total_conversations} conversaciones")
    lines.append(f"• {total_appointments} citas agendadas")
    
    # Eventos importantes
    events = get_recent_events(20)
    critical_events = [e for e in events if e['severity'] in ('warning', 'error', 'critical')]
    
    if critical_events:
        lines.append("")
        lines.append(f"*⚠️ Eventos ({len(critical_events)}):*")
        for e in critical_events[:5]:
            ts = e['timestamp'][:16] if e.get('timestamp') else ''
            lines.append(f"• [{ts}] {e.get('event_type', '')} - {e.get('instance', '')}")
    
    # Predicciones
    all_predictions = []
    for inst in instances:
        preds = predict_issues(inst.name)
        for p in preds:
            p['instance'] = inst.name
            all_predictions.append(p)
    
    if all_predictions:
        lines.append("")
        lines.append("*🔮 Predicciones:*")
        for p in all_predictions[:3]:
            lines.append(f"• {p['instance']}: {p['message']}")
    
    return "\n".join(lines)

async def generate_weekly_report() -> str:
    """Generar reporte semanal."""
    instances = get_all_instances()
    
    lines = [
        f"📈 *Reporte Semanal — Semana {datetime.now().strftime('%V/%Y')}*",
        ""
    ]
    
    # Análisis por instancia
    for inst in instances:
        analysis = analyze_trends(inst.name, 168)  # 7 días
        
        if analysis.get("status") == "insufficient_data":
            continue
        
        emoji, sector_name, _ = inst.sector_info
        lines.append(f"{emoji} *{inst.label}*")
        
        avail = analysis.get("availability", {})
        lines.append(f"   Disponibilidad: {avail.get('percentage', 0):.1f}%")
        
        lat = analysis.get("latency", {})
        if lat:
            lines.append(f"   Latencia: {lat.get('avg', 0):.0f}ms avg (p95: {lat.get('p95', 0):.0f}ms)")
        
        trends = analysis.get("trends", {})
        if trends.get("conversations"):
            lines.append(f"   Tendencia: {trends['conversations']}")
        
        lines.append("")
    
    # Top eventos
    events = db_execute("""
        SELECT event_type, COUNT(*) as count 
        FROM events 
        WHERE timestamp > datetime('now', '-7 days')
        GROUP BY event_type 
        ORDER BY count DESC 
        LIMIT 5
    """, fetch=True)
    
    if events:
        lines.append("*Eventos más frecuentes:*")
        for e in events:
            lines.append(f"• {e['event_type']}: {e['count']}")
    
    return "\n".join(lines)

async def send_daily_summary():
    """Enviar resumen diario."""
    report = await generate_daily_report()
    await send_telegram(report)
    log_audit("omni", "send_daily_report", "", "")

async def send_weekly_summary():
    """Enviar resumen semanal."""
    report = await generate_weekly_report()
    await send_telegram(report)
    log_audit("omni", "send_weekly_report", "", "")

# ══════════════════════════════════════════════════════════════════════════════
# LLM - Cerebro de Omni
# ══════════════════════════════════════════════════════════════════════════════
def get_conversation_history(limit: int = 20) -> List[Dict]:
    """Obtener historial de conversaciones con Santiago."""
    rows = db_execute("""
        SELECT role, content FROM santiago_conversations 
        ORDER BY id DESC LIMIT ?
    """, (limit,), fetch=True)
    return list(reversed(rows))

def save_conversation(role: str, content: str):
    """Guardar mensaje en historial."""
    db_execute(
        "INSERT INTO santiago_conversations (role, content) VALUES (?, ?)",
        (role, content)
    )

def get_preference(key: str, default: str = None) -> str:
    """Obtener preferencia guardada."""
    rows = db_execute("SELECT value FROM preferences WHERE key = ?", (key,), fetch=True)
    return rows[0]['value'] if rows else default

def set_preference(key: str, value: str):
    """Guardar preferencia."""
    db_execute("""
        INSERT OR REPLACE INTO preferences (key, value, updated_at) 
        VALUES (?, ?, datetime('now'))
    """, (key, value))

async def omni_brain(user_input: str, all_status: List[Dict], base_env: dict) -> str:
    """LLM que sabe todo sobre las instancias y puede tomar acciones."""
    
    # Construir contexto de instancias
    instance_lines = []
    for s in all_status:
        h = s.get("health", {})
        stats = s.get("stats", {})
        is_up = h.get("status") == "online"
        
        emoji, sector_name, _ = get_sector_info(s.get("sector", "otro"))
        wa = h.get("whatsapp", {})
        plat = f"WA {wa.get('phone', '')}" if wa.get("connected") else "Telegram"
        
        convs = stats.get("total_conversations", "?")
        apts = stats.get("total_appointments", "?")
        nova = "Nova ON" if s.get("env", {}).get("NOVA_ENABLED") == "true" else ""
        latency = s.get("latency", 0)
        
        instance_lines.append(
            f"  {emoji} {s['name']}: {'ONLINE' if is_up else 'OFFLINE'} | {plat} | "
            f"{sector_name} | {convs} convs | {apts} citas | {latency:.0f}ms"
            + (f" | {nova}" if nova else "")
        )
    
    instances_ctx = "\n".join(instance_lines) if instance_lines else "  (sin instancias)"
    
    # Eventos recientes
    events = get_recent_events(10)
    events_ctx = ""
    if events:
        events_ctx = "\n\nEVENTOS RECIENTES:\n" + "\n".join(
            f"  [{e.get('timestamp', '')[:16]}] {e.get('severity', '').upper()}: "
            f"{e.get('event_type', '')} — {e.get('instance', '')}"
            for e in events[:5]
        )
    
    # Alertas sin reconocer
    unack = get_unacknowledged_events()
    alerts_ctx = ""
    if unack:
        alerts_ctx = f"\n\n🔔 ALERTAS SIN RECONOCER: {len(unack)}\n" + "\n".join(
            f"  • [{e.get('timestamp', '')[:16]}] {e.get('event_type', '')} - {e.get('instance', '')}"
            for e in unack[:3]
        )
    
    # Predicciones
    predictions_ctx = ""
    for s in all_status[:3]:  # Solo las primeras para no sobrecargar
        preds = predict_issues(s['name'])
        if preds:
            predictions_ctx += f"\n\n🔮 PREDICCIONES PARA {s['name']}:\n"
            for p in preds:
                predictions_ctx += f"  • {p['message']}"
    
    # Historial de conversación
    history = get_conversation_history(10)
    hist_text = "\n".join(
        f"{'Santiago' if h['role'] == 'user' else 'Omni'}: {h['content'][:200]}"
        for h in history
    )
    
    # Preferencias de Santiago
    preferences = get_preference("communication_style", "profesional pero cercano")
    
    system = f"""Eres Melissa Omni — el centro de comando de Santiago para toda la plataforma Melissa.
Santiago es el dueño y tú eres su asistente ejecutiva de confianza.

═══════════════════════════════════════════════════════════════
ESTADO ACTUAL DE INSTANCIAS:
{instances_ctx}
{events_ctx}
{alerts_ctx}
{predictions_ctx}
═══════════════════════════════════════════════════════════════

HISTORIAL DE CONVERSACIÓN:
{hist_text or "(inicio de conversación)"}

═══════════════════════════════════════════════════════════════
CÓMO ERES:
- Estilo: {preferences}
- Directa y ejecutiva. Máximo 4 oraciones a menos que te pidan detalle.
- Cuando Santiago pregunta por una instancia, das estado completo con números.
- Si hay algo offline, en warning o predicciones, lo mencionas primero.
- Puedes ver tendencias, predecir problemas y sugerir acciones.
- Conoces los sectores: clínicas, restaurantes, hoteles, gimnasios, etc.

ACCIONES QUE PUEDES EJECUTAR (incluye al FINAL si necesitas):
ACTION:{{"type":"detail","instance":"nombre"}}
ACTION:{{"type":"summary_all"}}
ACTION:{{"type":"restart","instance":"nombre"}}
ACTION:{{"type":"send_message","instance":"nombre","chat_id":"...","message":"..."}}
ACTION:{{"type":"create_alert","name":"...","instance":"*","metric":"latency_ms","operator":">","threshold":500}}
ACTION:{{"type":"analyze","instance":"nombre"}}
ACTION:{{"type":"predict","instance":"nombre"}}
ACTION:{{"type":"acknowledge_alerts"}}
ACTION:{{"type":"backup","instance":"nombre"}}
ACTION:{{"type":"scale","instance":"nombre","workers":4}}
ACTION:{{"type":"set_demo","instance":"nombre","active":true,"business_name":"...","sector":"estetica","session_ttl":1800}}
ACTION:{{"type":"demo_status","instance":"nombre"}}

Responde en español, informal con Santiago pero preciso con los datos.

IMPORTANTE — Solo incluye una ACTION si Santiago te lo pide explícitamente o si detectas un problema real que requiere acción inmediata. NO incluyas ACTION:summary_all ni ninguna otra acción por defecto en cada respuesta. Si Santiago solo pregunta o saluda, responde con texto únicamente."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_input}
    ]
    
    # Proveedores LLM
    providers = []
    if base_env.get("GROQ_API_KEY"):
        providers.append(("groq", "https://api.groq.com/openai/v1",
                         base_env["GROQ_API_KEY"], "llama-3.3-70b-versatile"))
    
    gemini_keys = ["GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(2, 8)]
    for k in gemini_keys:
        if base_env.get(k):
            providers.append(("gemini", "native", base_env[k], "gemini-2.0-flash"))
    
    if base_env.get("OPENROUTER_API_KEY"):
        providers.append(("openrouter", "https://openrouter.ai/api/v1",
                         base_env["OPENROUTER_API_KEY"], "google/gemini-2.0-flash-001"))
    
    if not providers:
        return "No hay LLMs configurados en el .env de Melissa."
    
    for name, base_url, api_key, model in providers:
        try:
            if not _HTTPX:
                break
            
            if name == "gemini":
                contents = [
                    {"role": "user" if m["role"] == "user" else "model",
                     "parts": [{"text": m["content"]}]}
                    for m in messages if m["role"] != "system"
                ]
                sys_parts = [m for m in messages if m["role"] == "system"]
                payload = {
                    "contents": contents,
                    "generationConfig": {"temperature": 0.3, "maxOutputTokens": 600}
                }
                if sys_parts:
                    payload["systemInstruction"] = {"parts": [{"text": sys_parts[0]["content"]}]}
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                async with httpx.AsyncClient(timeout=25.0) as c:
                    r = await c.post(url, json=payload)
                    r.raise_for_status()
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            else:
                async with httpx.AsyncClient(timeout=25.0) as c:
                    r = await c.post(
                        f"{base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "temperature": 0.3,
                            "max_tokens": 600
                        }
                    )
                    r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
        
        except Exception as e:
            continue
    
    return "Sin respuesta de LLM — verifica las API keys."

def extract_action(text: str) -> Optional[Dict]:
    """Extraer acción del texto de respuesta."""
    m = re.search(r'ACTION:\s*(\{[^\n]+\})', text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None

def clean_response(text: str) -> str:
    """Limpiar respuesta quitando acciones."""
    return re.sub(r'\n?ACTION:\s*\{[^\n]+\}', '', text).strip()

async def execute_action(action: Dict, instances: List[Instance], base_env: dict) -> str:
    """Ejecutar acción solicitada por Omni."""
    action_type = action.get("type", "")
    
    if action_type == "detail":
        name = action.get("instance", "")
        inst = resolve_instance(instances, name)
        if not inst:
            return f"No encontré instancia '{name}'"
        
        h, latency = await health_check(inst.port)
        mk = inst.env.get("MASTER_API_KEY", "")
        stats = await get_instance_stats(inst.port, mk) if h else {}
        convs = await get_recent_conversations(inst.port, mk, 3) if h else []
        analysis = analyze_trends(inst.name, 24)
        
        emoji, sector_name, _ = inst.sector_info
        wa = h.get("whatsapp", {})
        plat = f"WA {wa.get('phone', '')}" if wa.get("connected") else "Telegram"
        status = "ONLINE" if h.get("status") == "online" else "OFFLINE"
        
        lines = [
            f"*{emoji} {h.get('clinic', inst.label)}* — {status}",
            f"Plataforma: {plat} | Sector: {sector_name}",
            f"Puerto: {inst.port} | Latencia: {latency:.0f}ms",
        ]
        
        if stats:
            lines.append(f"\n📊 *Esta semana:*")
            lines.append(f"• {stats.get('total_conversations', 0)} conversaciones")
            lines.append(f"• {stats.get('total_appointments', 0)} citas")
            cr = stats.get("conversion_rate")
            if cr:
                lines.append(f"• Conversión: {cr}%")
        
        if analysis.get("availability"):
            avail = analysis["availability"]
            lines.append(f"\n📈 *Últimas 24h:*")
            lines.append(f"• Disponibilidad: {avail.get('percentage', 0):.1f}%")
            if analysis.get("latency"):
                lat = analysis["latency"]
                lines.append(f"• Latencia avg: {lat.get('avg', 0):.0f}ms (p95: {lat.get('p95', 0):.0f}ms)")
        
        if convs:
            lines.append(f"\n💬 *Últimas conversaciones:*")
            for c in convs[:3]:
                name = c.get("name") or "Desconocido"
                last = (c.get("last_user_msg") or "")[:60]
                lines.append(f"• {name}: \"{last}\"")
        
        return "\n".join(lines)
    
    elif action_type == "summary_all":
        return await generate_daily_report()
    
    elif action_type == "restart":
        name = action.get("instance", "")
        inst = resolve_instance(instances, name)
        if not inst:
            return f"No encontré instancia '{name}'"
        
        log_audit("santiago", "restart", inst.name, "via omni chat")
        success = pm2_restart(inst.pm2_name)
        
        if success:
            await asyncio.sleep(5)
            h, _ = await health_check(inst.port)
            if h.get("status") == "online":
                return f"✅ {inst.label} reiniciada y online"
            return f"⏳ {inst.label} reiniciada, verificando..."
        return f"❌ Error reiniciando {inst.label}"
    
    elif action_type == "send_message":
        name = action.get("instance", "")
        chat_id = action.get("chat_id", "")
        message = action.get("message", "")
        
        inst = resolve_instance(instances, name)
        if not inst:
            return f"No encontré instancia '{name}'"
        
        mk = inst.env.get("MASTER_API_KEY", "")
        success = await send_to_instance(inst.port, mk, chat_id, message)
        log_audit("santiago", "send_message", inst.name, f"chat_id={chat_id}")
        
        return "✅ Mensaje enviado" if success else "❌ Error enviando mensaje"
    
    elif action_type == "analyze":
        name = action.get("instance", "")
        inst = resolve_instance(instances, name)
        if not inst:
            return f"No encontré instancia '{name}'"
        
        analysis = analyze_trends(inst.name, 24)
        anomalies = detect_anomalies(inst.name, 6)
        
        lines = [f"📊 *Análisis de {inst.label}*"]
        
        if analysis.get("status") == "insufficient_data":
            lines.append("Datos insuficientes para análisis completo")
        else:
            if analysis.get("availability"):
                avail = analysis["availability"]
                lines.append(f"\n*Disponibilidad (24h):* {avail.get('percentage', 0):.1f}%")
            
            if analysis.get("latency"):
                lat = analysis["latency"]
                lines.append(f"\n*Latencia:*")
                lines.append(f"• Promedio: {lat.get('avg', 0):.0f}ms")
                lines.append(f"• P95: {lat.get('p95', 0):.0f}ms")
                lines.append(f"• Tendencia: {lat.get('trend', 'stable')}")
        
        if anomalies:
            lines.append(f"\n⚠️ *Anomalías detectadas:* {len(anomalies)}")
            for a in anomalies[:3]:
                lines.append(f"• {a.get('type', '')}: {a.get('timestamp', '')[:16]}")
        
        return "\n".join(lines)
    
    elif action_type == "predict":
        name = action.get("instance", "")
        inst = resolve_instance(instances, name)
        if not inst:
            return f"No encontré instancia '{name}'"
        
        predictions = predict_issues(inst.name)
        
        if not predictions:
            return f"🔮 Sin predicciones de problemas para {inst.label}"
        
        lines = [f"🔮 *Predicciones para {inst.label}:*"]
        for p in predictions:
            lines.append(f"\n• *{p.get('type', '')}* ({p.get('probability', '')} probabilidad)")
            lines.append(f"  {p.get('message', '')}")
            lines.append(f"  💡 {p.get('recommendation', '')}")
        
        return "\n".join(lines)
    
    elif action_type == "acknowledge_alerts":
        unack = get_unacknowledged_events()
        for e in unack:
            acknowledge_event(e['id'], "Santiago")
        return f"✅ {len(unack)} alertas reconocidas"
    
    elif action_type == "create_alert":
        rule_id = create_alert_rule(
            name=action.get("name", "Nueva alerta"),
            instance=action.get("instance", "*"),
            metric=action.get("metric", "latency_ms"),
            operator=action.get("operator", ">"),
            threshold=float(action.get("threshold", 500)),
            severity=action.get("severity", "warning"),
            channels=action.get("channels", "telegram")
        )
        return f"✅ Alerta creada (ID: {rule_id})"
    
    elif action_type == "backup":
        name = action.get("instance", "")
        inst = resolve_instance(instances, name)
        if not inst:
            return f"No encontré instancia '{name}'"
        
        import subprocess
        result = subprocess.run(
            ["melissa", "backup", inst.name],
            capture_output=True,
            text=True
        )
        log_audit("santiago", "backup", inst.name, "via omni")
        return "✅ Backup iniciado" if result.returncode == 0 else f"❌ Error: {result.stderr[:100]}"
    
    elif action_type == "scale":
        name = action.get("instance", "")
        workers = action.get("workers", 2)
        
        inst = resolve_instance(instances, name)
        if not inst:
            return f"No encontré instancia '{name}'"
        
        import subprocess
        result = subprocess.run(
            ["pm2", "scale", inst.pm2_name, str(workers)],
            capture_output=True
        )
        log_audit("santiago", "scale", inst.name, f"workers={workers}")
        return f"✅ Escalado a {workers} workers" if result.returncode == 0 else "❌ Error escalando"

    elif action_type == "demo_status":
        name = action.get("instance", "")
        inst = resolve_instance(instances, name)
        if not inst:
            return f"No encontré instancia '{name}'"
        status = await http_get(f"http://localhost:{inst.port}/demo/status") or {}
        health, latency = await health_check(inst.port)
        demo_mode = "ACTIVO" if status.get("demo_mode") else "apagado"
        return "\n".join([
            f"🎭 *Demo mode — {inst.label}*",
            f"Estado: {demo_mode}",
            f"Negocio: {status.get('business_name', inst.label)}",
            f"Sector: {status.get('sector', inst.sector)}",
            f"TTL sesión: {status.get('session_ttl', 0)}s",
            f"Instancia: {health.get('status', 'offline')} | {latency:.0f}ms",
        ])

    elif action_type == "set_demo":
        name = action.get("instance", "")
        inst = resolve_instance(instances, name)
        if not inst:
            return f"No encontré instancia '{name}'"
        active = bool(action.get("active", True))
        session_ttl = int(action.get("session_ttl", 1800) or 1800)
        result = await set_instance_demo(
            inst,
            active=active,
            business_name=action.get("business_name", "") or "",
            sector=action.get("sector", "") or "",
            session_ttl=session_ttl,
        )
        log_audit(
            "santiago",
            "set_demo",
            inst.name,
            f"active={result['active']} business={result['business_name']}",
        )
        state = "activado" if result["active"] else "desactivado"
        return "\n".join([
            f"✅ Demo {state} en {result['label']}",
            f"Negocio: {result['business_name']}",
            f"Sector: {result['sector']}",
            f"TTL: {result['session_ttl']}s",
            f"Estado: {result['health']} | {result['latency_ms']:.0f}ms",
        ])
    
    return ""

# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND TASKS
# ══════════════════════════════════════════════════════════════════════════════
async def health_monitor():
    """Monitor de salud que corre cada HEALTH_INTERVAL segundos."""
    while True:
        try:
            instances = get_all_instances()
            
            for inst in instances:
                h, latency = await health_check(inst.port)
                status = h.get("status", "offline")
                
                # Registrar métricas
                mk = inst.env.get("MASTER_API_KEY", "")
                stats = await get_instance_stats(inst.port, mk) if h else {}
                
                record_metrics(
                    inst.name,
                    status,
                    latency,
                    stats.get("total_conversations", 0),
                    stats.get("total_appointments", 0),
                    stats.get("total_messages", 0)
                )
                
                # Verificar alertas
                metrics_dict = {
                    "status": 1 if status == "online" else 0,
                    "latency_ms": latency,
                    "conversations": stats.get("total_conversations", 0),
                    "appointments": stats.get("total_appointments", 0)
                }
                await check_alert_rules(inst.name, metrics_dict)
                
                # Auto-heal si está offline
                if status != "online":
                    log_event(inst.name, "offline_detected", f"Port {inst.port}", "warning")
                    await auto_heal_instance(inst)
                else:
                    # Limpiar estado de down si estaba caído
                    if inst.name in _down_since:
                        del _down_since[inst.name]
                    if inst.name in _restart_attempts:
                        del _restart_attempts[inst.name]
        
        except Exception as e:
            log_event("omni", "health_monitor_error", str(e), "error")
        
        await asyncio.sleep(HEALTH_INTERVAL)

async def metrics_collector():
    """Recolector de métricas detalladas cada METRICS_INTERVAL segundos."""
    while True:
        try:
            instances = get_all_instances()
            
            for inst in instances:
                mk = inst.env.get("MASTER_API_KEY", "")
                stats = await get_instance_stats(inst.port, mk)
                
                if stats:
                    # Guardar métricas adicionales si las hay
                    pass
        
        except Exception as e:
            log_event("omni", "metrics_collector_error", str(e), "error")
        
        await asyncio.sleep(METRICS_INTERVAL)

async def scheduled_reports():
    """Programador de reportes automáticos."""
    while True:
        now = datetime.now()
        
        # Reporte diario a las 8am
        if now.hour == 8 and now.minute == 0:
            await send_daily_summary()
            log_audit("omni", "scheduled_daily_report", "", "")
        
        # Reporte semanal los lunes a las 9am
        if now.weekday() == 0 and now.hour == 9 and now.minute == 0:
            await send_weekly_summary()
            log_audit("omni", "scheduled_weekly_report", "", "")
        
        await asyncio.sleep(60)  # Verificar cada minuto

async def cleanup_old_data():
    """Limpiar datos antiguos periódicamente."""
    while True:
        try:
            # Métricas > 30 días
            db_execute("""
                DELETE FROM metrics WHERE timestamp < datetime('now', '-30 days')
            """)
            
            # Eventos > 90 días
            db_execute("""
                DELETE FROM events WHERE timestamp < datetime('now', '-90 days')
            """)
            
            # Audit log > 180 días
            db_execute("""
                DELETE FROM audit_log WHERE timestamp < datetime('now', '-180 days')
            """)
            
            # Conversaciones > 60 días
            db_execute("""
                DELETE FROM santiago_conversations WHERE timestamp < datetime('now', '-60 days')
            """)
            
        except Exception as e:
            log_event("omni", "cleanup_error", str(e), "error")
        
        await asyncio.sleep(86400)  # Una vez al día

# ══════════════════════════════════════════════════════════════════════════════
# EVENTO QUEUE (en memoria para acceso rápido)
# ══════════════════════════════════════════════════════════════════════════════
_event_queue: List[Dict] = []

async def process_incoming_event(event: Dict):
    """Procesar evento entrante."""
    event["received_at"] = datetime.now().isoformat()
    
    # Guardar en memoria
    _event_queue.append(event)
    if len(_event_queue) > 500:
        _event_queue[:] = _event_queue[-500:]
    
    # Guardar en DB
    log_event(
        event.get("clinic", event.get("instance", "")),
        event.get("event", "unknown"),
        event.get("details", ""),
        event.get("severity", "info")
    )
    
    # Procesar workflows
    await process_event_for_workflows(event.get("event", ""), event)
    
    # Alertas críticas inmediatas
    CRITICAL_EVENTS = {
        "new_whatsapp_number_requested",
        "instance_error",
        "client_complaint",
        "payment_failed",
        "security_alert",
        "data_breach"
    }
    
    if event.get("event") in CRITICAL_EVENTS:
        emoji_map = {
            "new_whatsapp_number_requested": "📱",
            "instance_error": "🔥",
            "client_complaint": "⚠️",
            "payment_failed": "💳",
            "security_alert": "🔐",
            "data_breach": "🚨"
        }
        emoji = emoji_map.get(event.get("event"), "📌")
        
        await send_notification(Notification(
            title=event.get("event", "Evento"),
            message=event.get("details", ""),
            severity="critical",
            instance=event.get("clinic", ""),
            channels=["telegram", "email"] if event.get("event") in {"security_alert", "data_breach"} else ["telegram"]
        ))

# ══════════════════════════════════════════════════════════════════════════════
# FASTAPI SERVER
# ══════════════════════════════════════════════════════════════════════════════
_santiago_ws_connections: List[WebSocket] = []

if HAS_FASTAPI:
    @asynccontextmanager
    async def lifespan(app_: FastAPI):
        init_db()
        
        # Background tasks
        asyncio.create_task(health_monitor())
        asyncio.create_task(metrics_collector())
        asyncio.create_task(scheduled_reports())
        asyncio.create_task(cleanup_old_data())
        
        print_logo(compact=True)
        info(f"Omni server online — puerto {OMNI_PORT}")
        info(f"Dashboard: http://localhost:{OMNI_PORT}/dashboard")
        
        if OMNI_TOKEN:
            ok("Telegram configurado")
        if SLACK_WEBHOOK:
            ok("Slack configurado")
        if DISCORD_WEBHOOK:
            ok("Discord configurado")
        if SMTP_HOST:
            ok("Email configurado")
        if AUTO_HEAL_ENABLED:
            ok(f"Auto-heal activo (delay: {AUTO_HEAL_DELAY}s)")
        
        nl()
        yield
    
    omni_app = FastAPI(title="Melissa Omni", version=OMNI_VERSION, lifespan=lifespan)
    omni_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"]
    )
    
    def auth_required(request: Request) -> bool:
        return request.headers.get("X-Omni-Key", "") == OMNI_KEY
    
    # ──────────────────────────────────────────────────────────────────────────
    # ENDPOINTS PÚBLICOS
    # ──────────────────────────────────────────────────────────────────────────
    
    @omni_app.get("/health")
    async def omni_health():
        instances = get_all_instances()
        health_results = await asyncio.gather(*[health_check(i.port) for i in instances])
        online = sum(1 for h, _ in health_results if h.get("status") == "online")
        
        return {
            "status": "online",
            "version": OMNI_VERSION,
            "instances": len(instances),
            "online": online,
            "events_queue": len(_event_queue),
            "auto_heal": AUTO_HEAL_ENABLED
        }
    
    @omni_app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard_html():
        """Dashboard web embebido."""
        instances = get_all_instances()
        health_results = await asyncio.gather(*[health_check(i.port) for i in instances])
        
        rows_html = ""
        for inst, (h, latency) in zip(instances, health_results):
            is_up = h.get("status") == "online"
            emoji, sector_name, color = inst.sector_info
            status_class = "online" if is_up else "offline"
            wa = h.get("whatsapp", {})
            plat = f"WA {wa.get('phone', '')[-7:]}" if wa.get("connected") else "Telegram"
            
            rows_html += f"""
            <tr class="{status_class}">
                <td>{emoji} {inst.label}</td>
                <td><span class="status-dot {status_class}"></span> {"Online" if is_up else "Offline"}</td>
                <td>{plat}</td>
                <td>{latency:.0f}ms</td>
                <td>{sector_name}</td>
            </tr>
            """
        
        # Eventos recientes
        events = get_recent_events(10)
        events_html = ""
        for e in events:
            severity_class = e.get('severity', 'info')
            events_html += f"""
            <tr class="{severity_class}">
                <td>{e.get('timestamp', '')[:16]}</td>
                <td>{e.get('instance', '')}</td>
                <td>{e.get('event_type', '')}</td>
                <td><span class="severity {severity_class}">{e.get('severity', '').upper()}</span></td>
            </tr>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Melissa Omni Dashboard</title>
            <meta http-equiv="refresh" content="30">
            <style>
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    color: #e0e0e0;
                    min-height: 100vh;
                    padding: 20px;
                }}
                .container {{ max-width: 1400px; margin: 0 auto; }}
                h1 {{
                    color: #f5a623;
                    font-size: 2rem;
                    margin-bottom: 20px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .logo {{ font-size: 2.5rem; }}
                .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }}
                .card {{
                    background: rgba(255,255,255,0.05);
                    border-radius: 12px;
                    padding: 20px;
                    border: 1px solid rgba(255,255,255,0.1);
                }}
                .card h2 {{
                    color: #f5a623;
                    font-size: 1.2rem;
                    margin-bottom: 15px;
                    padding-bottom: 10px;
                    border-bottom: 1px solid rgba(255,255,255,0.1);
                }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{
                    padding: 10px;
                    text-align: left;
                    border-bottom: 1px solid rgba(255,255,255,0.05);
                }}
                th {{ color: #888; font-weight: 500; font-size: 0.85rem; }}
                .status-dot {{
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    display: inline-block;
                    margin-right: 5px;
                }}
                .status-dot.online {{ background: #4caf50; box-shadow: 0 0 10px #4caf50; }}
                .status-dot.offline {{ background: #f44336; box-shadow: 0 0 10px #f44336; }}
                .severity {{
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-size: 0.75rem;
                    font-weight: 600;
                }}
                .severity.info {{ background: #2196f3; }}
                .severity.warning {{ background: #ff9800; }}
                .severity.error {{ background: #f44336; }}
                .severity.critical {{ background: #9c27b0; }}
                tr.offline td {{ opacity: 0.6; }}
                .footer {{
                    text-align: center;
                    margin-top: 20px;
                    color: #666;
                    font-size: 0.85rem;
                }}
                .stats {{
                    display: flex;
                    gap: 30px;
                    margin-bottom: 20px;
                }}
                .stat {{
                    text-align: center;
                }}
                .stat-value {{
                    font-size: 2.5rem;
                    font-weight: 700;
                    color: #f5a623;
                }}
                .stat-label {{
                    color: #888;
                    font-size: 0.9rem;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1><span class="logo">◉</span> Melissa Omni</h1>
                
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">{sum(1 for h, _ in health_results if h.get('status') == 'online')}</div>
                        <div class="stat-label">Online</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{len(instances)}</div>
                        <div class="stat-label">Total</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{len(_event_queue)}</div>
                        <div class="stat-label">Eventos</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{len(get_unacknowledged_events())}</div>
                        <div class="stat-label">Alertas</div>
                    </div>
                </div>
                
                <div class="grid">
                    <div class="card">
                        <h2>📊 Instancias</h2>
                        <table>
                            <tr>
                                <th>Nombre</th>
                                <th>Estado</th>
                                <th>Plataforma</th>
                                <th>Latencia</th>
                                <th>Sector</th>
                            </tr>
                            {rows_html}
                        </table>
                    </div>
                    
                    <div class="card">
                        <h2>📋 Eventos Recientes</h2>
                        <table>
                            <tr>
                                <th>Tiempo</th>
                                <th>Instancia</th>
                                <th>Evento</th>
                                <th>Severidad</th>
                            </tr>
                            {events_html}
                        </table>
                    </div>
                </div>
                
                <div class="footer">
                    Melissa Omni v{OMNI_VERSION} · Auto-refresh cada 30s · {datetime.now().strftime('%H:%M:%S')}
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    # ──────────────────────────────────────────────────────────────────────────
    # ENDPOINTS AUTENTICADOS
    # ──────────────────────────────────────────────────────────────────────────
    
    @omni_app.post("/omni/event")
    async def receive_event(request: Request, bg: BackgroundTasks):
        if not auth_required(request):
            return Response(status_code=403)
        
        data = await request.json()
        bg.add_task(process_incoming_event, data)
        return {"ok": True, "queued": len(_event_queue)}
    
    @omni_app.get("/omni/events")
    async def list_events(request: Request, limit: int = 50, severity: str = None):
        if not auth_required(request):
            return Response(status_code=403)
        return {"events": get_recent_events(limit, severity), "total": len(_event_queue)}
    
    @omni_app.get("/omni/status")
    async def omni_status_endpoint(request: Request):
        if not auth_required(request):
            return Response(status_code=403)
        
        instances = get_all_instances()
        health_results = await asyncio.gather(*[health_check(i.port) for i in instances])
        
        return {
            "timestamp": datetime.now().isoformat(),
            "instances": [
                {
                    "name": i.name,
                    "label": i.label,
                    "port": i.port,
                    "sector": i.sector,
                    "status": h.get("status", "offline"),
                    "latency_ms": lat,
                    "clinic": h.get("clinic", ""),
                    "whatsapp": h.get("whatsapp", {}),
                    "nova_enabled": i.env.get("NOVA_ENABLED", "false")
                }
                for i, (h, lat) in zip(instances, health_results)
            ]
        }
    
    @omni_app.get("/omni/metrics/{instance}")
    async def get_instance_metrics(instance: str, request: Request, hours: int = 24):
        if not auth_required(request):
            return Response(status_code=403)
        
        metrics = get_metrics_history(instance, hours)
        analysis = analyze_trends(instance, hours)
        anomalies = detect_anomalies(instance, min(hours, 6))
        predictions = predict_issues(instance)
        
        return {
            "instance": instance,
            "period_hours": hours,
            "metrics": metrics,
            "analysis": analysis,
            "anomalies": anomalies,
            "predictions": predictions
        }
    
    @omni_app.get("/omni/alerts")
    async def list_alerts(request: Request):
        if not auth_required(request):
            return Response(status_code=403)
        return {"alerts": get_alert_rules()}
    
    @omni_app.post("/omni/alerts")
    async def create_alert(request: Request):
        if not auth_required(request):
            return Response(status_code=403)
        
        data = await request.json()
        rule_id = create_alert_rule(
            name=data.get("name", "Nueva alerta"),
            instance=data.get("instance", "*"),
            metric=data.get("metric"),
            operator=data.get("operator"),
            threshold=data.get("threshold"),
            severity=data.get("severity", "warning"),
            channels=data.get("channels", "telegram"),
            cooldown=data.get("cooldown", 30)
        )
        log_audit("api", "create_alert", str(rule_id), json.dumps(data))
        return {"ok": True, "id": rule_id}
    
    @omni_app.delete("/omni/alerts/{rule_id}")
    async def remove_alert(rule_id: int, request: Request):
        if not auth_required(request):
            return Response(status_code=403)
        
        delete_alert_rule(rule_id)
        log_audit("api", "delete_alert", str(rule_id), "")
        return {"ok": True}
    
    @omni_app.get("/omni/workflows")
    async def list_workflows(request: Request):
        if not auth_required(request):
            return Response(status_code=403)
        return {"workflows": get_workflows()}
    
    @omni_app.post("/omni/workflows")
    async def create_workflow_endpoint(request: Request):
        if not auth_required(request):
            return Response(status_code=403)
        
        data = await request.json()
        wf_id = create_workflow(
            name=data.get("name"),
            trigger_event=data.get("trigger_event"),
            actions=data.get("actions", []),
            trigger_filter=data.get("trigger_filter")
        )
        log_audit("api", "create_workflow", str(wf_id), json.dumps(data))
        return {"ok": True, "id": wf_id}
    
    @omni_app.get("/omni/audit")
    async def get_audit_log(request: Request, limit: int = 100):
        if not auth_required(request):
            return Response(status_code=403)
        
        logs = db_execute("""
            SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?
        """, (limit,), fetch=True)
        return {"logs": logs}
    
    @omni_app.post("/omni/message/{instance}")
    async def send_message_endpoint(instance: str, request: Request):
        if not auth_required(request):
            return Response(status_code=403)
        
        data = await request.json()
        instances = get_all_instances()
        inst = next((i for i in instances if instance.lower() in i.name.lower()), None)
        
        if not inst:
            return JSONResponse({"ok": False, "error": f"No encontré '{instance}'"}, status_code=404)
        
        mk = inst.env.get("MASTER_API_KEY", "")
        success = await send_to_instance(inst.port, mk, data.get("chat_id"), data.get("message"))
        log_audit("api", "send_message", inst.name, f"chat_id={data.get('chat_id')}")
        
        return {"ok": success}
    
    @omni_app.post("/omni/action/{instance}/{action}")
    async def execute_instance_action(instance: str, action: str, request: Request):
        if not auth_required(request):
            return Response(status_code=403)
        
        instances = get_all_instances()
        inst = next((i for i in instances if instance.lower() in i.name.lower()), None)
        
        if not inst:
            return JSONResponse({"ok": False, "error": f"No encontré '{instance}'"}, status_code=404)
        
        if action == "restart":
            success = pm2_restart(inst.pm2_name)
            log_audit("api", "restart", inst.name, "")
            return {"ok": success}
        
        elif action == "stop":
            success = pm2_stop(inst.pm2_name)
            log_audit("api", "stop", inst.name, "")
            return {"ok": success}
        
        elif action == "analyze":
            analysis = analyze_trends(inst.name, 24)
            return {"ok": True, "analysis": analysis}
        
        elif action == "predict":
            predictions = predict_issues(inst.name)
            return {"ok": True, "predictions": predictions}
        
        return JSONResponse({"ok": False, "error": f"Acción desconocida: {action}"}, status_code=400)
    
    # ──────────────────────────────────────────────────────────────────────────
    # TELEGRAM WEBHOOK
    # ──────────────────────────────────────────────────────────────────────────
    
    @omni_app.post("/omni/webhook/{token_suffix}")
    async def telegram_webhook(token_suffix: str, request: Request, bg: BackgroundTasks):
        _tok_check = os.environ.get("OMNI_TELEGRAM_TOKEN", "") or OMNI_TOKEN
        if _tok_check and not _tok_check.split(":")[-1][:10] == token_suffix:
            return Response(status_code=403)
        
        body = await request.json()
        msg = body.get("message", {})
        
        if not msg:
            return {"ok": True}
        
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text", "").strip()
        
        if not text:
            return {"ok": True}
        
        # Solo Santiago puede hablar con Omni
        if SANTIAGO_CHAT and chat_id != str(SANTIAGO_CHAT):
            return {"ok": True}
        
        bg.add_task(handle_telegram_message, chat_id, text)
        return {"ok": True}
    
    @omni_app.websocket("/omni/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket para updates en tiempo real."""
        await websocket.accept()
        _santiago_ws_connections.append(websocket)
        
        try:
            while True:
                data = await websocket.receive_text()
                # Procesar comandos via WebSocket
                if data.startswith("/"):
                    response = await process_ws_command(data)
                    await websocket.send_text(json.dumps(response))
        except Exception:
            pass
        finally:
            if websocket in _santiago_ws_connections:
                _santiago_ws_connections.remove(websocket)

async def process_ws_command(command: str) -> Dict:
    """Procesar comando de WebSocket."""
    cmd = command.strip().lower()
    
    if cmd == "/status":
        instances = get_all_instances()
        health_results = await asyncio.gather(*[health_check(i.port) for i in instances])
        return {
            "type": "status",
            "instances": [
                {"name": i.name, "status": h.get("status", "offline"), "latency": lat}
                for i, (h, lat) in zip(instances, health_results)
            ]
        }
    
    if cmd == "/events":
        return {"type": "events", "events": get_recent_events(20)}
    
    if cmd == "/alerts":
        return {"type": "alerts", "unacknowledged": get_unacknowledged_events()}
    
    return {"type": "error", "message": "Comando no reconocido"}

async def broadcast_to_ws(message: Dict):
    """Broadcast a todas las conexiones WebSocket."""
    if not _santiago_ws_connections:
        return
    
    text = json.dumps(message)
    for ws in _santiago_ws_connections[:]:
        try:
            await ws.send_text(text)
        except Exception:
            if ws in _santiago_ws_connections:
                _santiago_ws_connections.remove(ws)

async def handle_telegram_message(chat_id: str, text: str):
    """Procesar mensaje de Telegram de Santiago."""
    instances = get_all_instances()
    base_env = load_env(f"{TEMPLATE_DIR}/.env")
    
    # Health de todas en paralelo
    health_results = await asyncio.gather(*[health_check(i.port) for i in instances])
    stats_results = await asyncio.gather(*[
        get_instance_stats(i.port, i.env.get("MASTER_API_KEY", ""))
        for i in instances
    ])
    
    all_status = [
        {
            "name": i.name,
            "label": i.label,
            "port": i.port,
            "sector": i.sector,
            "env": i.env,
            "health": h,
            "latency": lat,
            "stats": s
        }
        for i, (h, lat), s in zip(instances, health_results, stats_results)
    ]
    
    # Comandos rápidos
    quick_commands = {
        "/status": lambda: generate_quick_status(all_status),
        "/help": lambda: get_help_text(),
        "/alerts": lambda: format_alerts(),
        "/ack": lambda: acknowledge_all_alerts(),
    }
    
    if text.lower() in quick_commands:
        response = await quick_commands[text.lower()]() if asyncio.iscoroutinefunction(quick_commands[text.lower()]) else quick_commands[text.lower()]()
        await send_telegram(response, chat_id)
        return

    demo_cmd = re.match(r"^/demo(?:\s+(.+?))?(?:\s+(on|off|status))?$", text.strip(), re.IGNORECASE)
    if demo_cmd:
        raw_name = (demo_cmd.group(1) or "").strip()
        raw_mode = (demo_cmd.group(2) or "").strip().lower()
        if raw_mode == "status" or (raw_name.lower() == "status" and not raw_mode):
            name = "" if raw_name.lower() == "status" else raw_name
            if name:
                inst = resolve_instance(instances, name)
                response = await execute_action({"type": "demo_status", "instance": name}, instances, base_env) if inst else f"No encontré instancia '{name}'"
            else:
                lines = ["🎭 *Demo mode por instancia*"]
                for inst in instances:
                    status = await http_get(f"http://localhost:{inst.port}/demo/status") or {}
                    lines.append(f"• {inst.label}: {'ACTIVO' if status.get('demo_mode') else 'apagado'}")
                response = "\n".join(lines)
            await send_telegram(response, chat_id)
            return
        if not raw_name:
            await send_telegram("Uso: /demo <instancia> <on|off|status>", chat_id)
            return
        active = raw_mode != "off"
        response = await execute_action({"type": "set_demo", "instance": raw_name, "active": active}, instances, base_env)
        await send_telegram(response, chat_id)
        return
    
    # LLM
    save_conversation("user", text)
    
    reply = await omni_brain(text, all_status, base_env)
    action = extract_action(reply)
    clean = clean_response(reply)
    
    await send_telegram(clean, chat_id)
    save_conversation("assistant", clean)
    
    if action:
        result = await execute_action(action, instances, base_env)
        if result:
            await send_telegram(result, chat_id)
            save_conversation("assistant", f"[ACTION RESULT]: {result}")
    
    log_audit("santiago", "chat", "", text[:100])

def generate_quick_status(all_status: List[Dict]) -> str:
    """Generar estado rápido."""
    online = sum(1 for s in all_status if s.get("health", {}).get("status") == "online")
    total = len(all_status)
    
    lines = [f"📊 *Estado Rápido* ({datetime.now().strftime('%H:%M')})", ""]
    lines.append(f"Online: {online}/{total}")
    lines.append("")
    
    for s in all_status:
        h = s.get("health", {})
        emoji, _, _ = get_sector_info(s.get("sector", "otro"))
        is_up = h.get("status") == "online"
        icon = "🟢" if is_up else "🔴"
        lat = s.get("latency", 0)
        
        lines.append(f"{icon} {emoji} {s['label'][:20]} ({lat:.0f}ms)")
    
    return "\n".join(lines)

def get_help_text() -> str:
    """Obtener texto de ayuda."""
    return """*Comandos rápidos:*
/status - Estado de todas las instancias
/alerts - Ver alertas pendientes
/ack - Reconocer todas las alertas
/help - Este mensaje

*También puedes preguntarme:*
• "¿Cómo va clinica-bella?"
• "Reinicia el restaurante"
• "Dame un resumen de la semana"
• "¿Hay algo raro?"
• "Crea una alerta de latencia > 500ms"
• "¿Qué predicciones hay?"
"""

def format_alerts() -> str:
    """Formatear alertas pendientes."""
    unack = get_unacknowledged_events()
    
    if not unack:
        return "✅ No hay alertas pendientes"
    
    lines = [f"🔔 *{len(unack)} alertas pendientes:*", ""]
    for e in unack[:10]:
        ts = e.get('timestamp', '')[:16]
        lines.append(f"• [{ts}] {e.get('event_type', '')} - {e.get('instance', '')}")
    
    if len(unack) > 10:
        lines.append(f"... y {len(unack) - 10} más")
    
    lines.append("")
    lines.append("Usa /ack para reconocerlas todas")
    
    return "\n".join(lines)

def acknowledge_all_alerts() -> str:
    """Reconocer todas las alertas."""
    unack = get_unacknowledged_events()
    for e in unack:
        acknowledge_event(e['id'], "Santiago")
    return f"✅ {len(unack)} alertas reconocidas"

# ══════════════════════════════════════════════════════════════════════════════
# CLI COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_status():
    """Estado rápido de todas las instancias."""
    print_logo(compact=True)
    section("Estado de Instancias")
    
    instances = get_all_instances()
    if not instances:
        warn("No hay instancias configuradas")
        return
    
    health_results = await asyncio.gather(*[health_check(i.port) for i in instances])
    online = sum(1 for h, _ in health_results if h.get("status") == "online")
    
    print(f"  {q(C.G2, 'Online:')}  "
          f"{q(C.GRN if online == len(instances) else C.YLW, f'{online}/{len(instances)}')}")
    nl()
    
    headers = ["INSTANCIA", "ESTADO", "SECTOR", "PLATAFORMA", "LATENCIA"]
    rows = []
    
    for inst, (h, latency) in zip(instances, health_results):
        is_up = h.get("status") == "online"
        emoji, sector_name, _ = inst.sector_info
        
        icon = q(C.GRN, "●") if is_up else q(C.RED, "●")
        status = "Online" if is_up else "Offline"
        
        wa = h.get("whatsapp", {})
        plat = f"WA {wa.get('phone', '')[-7:]}" if wa.get("connected") else "Telegram"
        
        rows.append([
            f"{icon} {inst.label[:20]}",
            status,
            f"{emoji} {sector_name[:12]}",
            plat,
            f"{latency:.0f}ms"
        ])
    
    table(headers, rows)
    nl()
    
    # Alertas pendientes
    unack = get_unacknowledged_events()
    if unack:
        warn(f"{len(unack)} alertas sin reconocer")
    
    # Predicciones
    all_predictions = []
    for inst in instances[:5]:
        preds = predict_issues(inst.name)
        all_predictions.extend(preds)
    
    if all_predictions:
        nl()
        info(f"🔮 {len(all_predictions)} predicciones activas")

async def cmd_watch():
    """Monitor live que refresca cada 5 segundos."""
    info("Watch mode — Ctrl+C para salir")
    
    try:
        while True:
            os.system("clear")
            
            instances = get_all_instances()
            health_results = await asyncio.gather(*[health_check(i.port) for i in instances])
            online = sum(1 for h, _ in health_results if h.get("status") == "online")
            now = datetime.now().strftime("%H:%M:%S")
            
            print()
            print(f"  {q(C.AMB, '◉', bold=True)}  {q(C.W, 'Melissa Omni', bold=True)}  "
                  f"{q(C.G3, now)}  "
                  f"{q(C.GRN if online == len(instances) else C.YLW, f'{online}/{len(instances)} online')}")
            print(f"  {q(C.G4, '─' * 70)}")
            
            headers = ["INSTANCIA", "ESTADO", "SECTOR", "PLATAFORMA", "LATENCIA", "TENDENCIA"]
            rows = []
            
            for inst, (h, latency) in zip(instances, health_results):
                is_up = h.get("status") == "online"
                emoji, sector_name, _ = inst.sector_info
                
                icon = q(C.GRN, "●") if is_up else q(C.RED, "●")
                
                wa = h.get("whatsapp", {})
                plat = f"WA" if wa.get("connected") else "TG"
                
                # Tendencia de latencia
                metrics = get_metrics_history(inst.name, 1)
                latencies = [m.get("latency_ms", 0) for m in metrics if m.get("latency_ms")]
                trend = ""
                if len(latencies) >= 5:
                    recent_avg = statistics.mean(latencies[-5:])
                    old_avg = statistics.mean(latencies[:5]) if len(latencies) >= 10 else recent_avg
                    if recent_avg > old_avg * 1.2:
                        trend = q(C.RED, "↑")
                    elif recent_avg < old_avg * 0.8:
                        trend = q(C.GRN, "↓")
                    else:
                        trend = q(C.G3, "→")
                
                rows.append([
                    f"{icon} {inst.label[:18]}",
                    "Online" if is_up else "OFFLINE",
                    f"{emoji}",
                    plat,
                    f"{latency:.0f}ms",
                    trend + " " + spark_line(latencies[-10:], 10) if latencies else ""
                ])
            
            table(headers, rows)
            
            # Eventos recientes
            events = get_recent_events(5)
            if events:
                nl()
                print(f"  {q(C.G2, 'Eventos recientes:')}")
                for e in events:
                    ts = e.get('timestamp', '')[:16]
                    sev = e.get('severity', 'info')
                    sev_color = {"critical": C.RED, "error": C.RED, "warning": C.YLW}.get(sev, C.G3)
                    print(f"  {q(C.G3, ts)}  {q(sev_color, sev.upper()[:4])}  "
                          f"{q(C.G1, e.get('event_type', '')[:20])}  "
                          f"{q(C.P2, e.get('instance', ''))}")
            
            nl()
            print(f"  {q(C.G3, 'Actualiza cada 5s · Ctrl+C para salir')}")
            
            await asyncio.sleep(5)
    
    except asyncio.CancelledError:
        pass

async def cmd_dashboard():
    """Dashboard interactivo en terminal."""
    info("Dashboard mode — Ctrl+C para salir")
    
    try:
        while True:
            os.system("clear")
            print_logo(compact=True)
            
            instances = get_all_instances()
            health_results = await asyncio.gather(*[health_check(i.port) for i in instances])
            stats_results = await asyncio.gather(*[
                get_instance_stats(i.port, i.env.get("MASTER_API_KEY", ""))
                for i in instances
            ])
            
            online = sum(1 for h, _ in health_results if h.get("status") == "online")
            
            # Stats globales
            total_convs = sum(s.get("total_conversations", 0) for s in stats_results)
            total_apts = sum(s.get("total_appointments", 0) for s in stats_results)
            
            print(f"  {q(C.W, 'RESUMEN', bold=True)}")
            print(f"  ┌───────────────┬───────────────┬───────────────┬───────────────┐")
            print(f"  │ {q(C.GRN, f'{online}', bold=True):>12} │ {q(C.W, f'{len(instances)}', bold=True):>12} │ "
                  f"{q(C.P2, f'{total_convs}', bold=True):>12} │ {q(C.AMB, f'{total_apts}', bold=True):>12} │")
            print(f"  │ {'Online':^13} │ {'Total':^13} │ {'Convs':^13} │ {'Citas':^13} │")
            print(f"  └───────────────┴───────────────┴───────────────┴───────────────┘")
            nl()
            
            # Instancias por sector
            by_sector = defaultdict(list)
            for inst, (h, lat), stats in zip(instances, health_results, stats_results):
                by_sector[inst.sector].append((inst, h, lat, stats))
            
            for sector_id, items in sorted(by_sector.items()):
                emoji, sector_name, _ = get_sector_info(sector_id)
                print(f"  {emoji} {q(C.W, sector_name, bold=True)}")
                
                for inst, h, lat, stats in items:
                    is_up = h.get("status") == "online"
                    icon = q(C.GRN, "●") if is_up else q(C.RED, "●")
                    convs = stats.get("total_conversations", 0)
                    apts = stats.get("total_appointments", 0)
                    
                    print(f"     {icon} {inst.label[:25]:<25}  "
                          f"{lat:>4.0f}ms  {convs:>3} conv  {apts:>3} citas")
                
                nl()
            
            # Alertas
            unack = get_unacknowledged_events()
            if unack:
                print(f"  {q(C.YLW, f'⚠️ {len(unack)} alertas pendientes', bold=True)}")
                for e in unack[:3]:
                    print(f"     • {e.get('event_type', '')} - {e.get('instance', '')}")
            
            nl()
            _dashboard_ts = datetime.now().strftime("%H:%M:%S")
            print(f"  {q(C.G3, f'Actualiza cada 10s · {_dashboard_ts}')}")
            
            await asyncio.sleep(10)
    
    except asyncio.CancelledError:
        pass

async def cmd_chat():
    """Chat interactivo con Omni."""
    print_logo()
    
    instances = get_all_instances()
    health_results = await asyncio.gather(*[health_check(i.port) for i in instances])
    stats_results = await asyncio.gather(*[
        get_instance_stats(i.port, i.env.get("MASTER_API_KEY", ""))
        for i in instances
    ])
    
    online = sum(1 for h, _ in health_results if h.get("status") == "online")
    
    all_status = [
        {
            "name": i.name,
            "label": i.label,
            "port": i.port,
            "sector": i.sector,
            "env": i.env,
            "health": h,
            "latency": lat,
            "stats": s
        }
        for i, (h, lat), s in zip(instances, health_results, stats_results)
    ]
    
    base_env = load_env(f"{TEMPLATE_DIR}/.env")
    
    info(f"{online}/{len(instances)} instancias online. Pregúntame lo que necesites.")
    dim("Comandos: /status  /watch  /dashboard  /alerts  /ack  /analyze  /predict  /exit")
    nl()
    
    while True:
        try:
            sys.stdout.write(f"  {q(C.AMB, 'Santiago', bold=True)} {q(C.P3, '›')} ")
            sys.stdout.flush()
            text = input("").strip()
        except (EOFError, KeyboardInterrupt):
            nl()
            info("Hasta luego.")
            break
        
        if not text:
            continue
        
        # Comandos especiales
        if text in ("/exit", "exit", "salir", "q"):
            info("Hasta luego.")
            break
        
        if text == "/status":
            await cmd_status()
            continue
        
        if text == "/watch":
            try:
                await cmd_watch()
            except KeyboardInterrupt:
                pass
            continue
        
        if text == "/dashboard":
            try:
                await cmd_dashboard()
            except KeyboardInterrupt:
                pass
            continue
        
        if text == "/alerts":
            unack = get_unacknowledged_events()
            if not unack:
                ok("Sin alertas pendientes")
            else:
                warn(f"{len(unack)} alertas:")
                for e in unack[:10]:
                    ts = e.get('timestamp', '')[:16]
                    print(f"     [{ts}] {e.get('event_type', '')} - {e.get('instance', '')}")
            continue
        
        if text == "/ack":
            unack = get_unacknowledged_events()
            for e in unack:
                acknowledge_event(e['id'], "Santiago")
            ok(f"{len(unack)} alertas reconocidas")
            continue
        
        if text.startswith("/analyze"):
            parts = text.split()
            if len(parts) > 1:
                name = parts[1]
                analysis = analyze_trends(name, 24)
                if analysis.get("status") == "insufficient_data":
                    warn("Datos insuficientes")
                else:
                    section(f"Análisis de {name}")
                    if analysis.get("availability"):
                        avail = analysis["availability"]
                        kv("Disponibilidad", f"{avail.get('percentage', 0):.1f}%")
                    if analysis.get("latency"):
                        lat = analysis["latency"]
                        kv("Latencia avg", f"{lat.get('avg', 0):.0f}ms")
                        kv("Latencia p95", f"{lat.get('p95', 0):.0f}ms")
                        kv("Tendencia", lat.get("trend", "stable"))
            else:
                info("Uso: /analyze <instancia>")
            continue
        
        if text == "/predict":
            for inst in instances:
                preds = predict_issues(inst.name)
                if preds:
                    print(f"  {q(C.P2, inst.label)}:")
                    for p in preds:
                        print(f"     • {p.get('message', '')}")
            if not any(predict_issues(i.name) for i in instances):
                ok("Sin predicciones de problemas")
            continue

        if text.startswith("/demo"):
            parts = text.split()
            if len(parts) < 2:
                info("Uso: /demo <instancia> <on|off|status>")
                nl()
                continue
            name = parts[1]
            mode = parts[2].lower() if len(parts) > 2 else "status"
            if mode == "status":
                result = await execute_action({"type": "demo_status", "instance": name}, instances, base_env)
            else:
                result = await execute_action({"type": "set_demo", "instance": name, "active": mode != "off"}, instances, base_env)
            for line in result.split('\n'):
                print(f"       {q(C.G1, line)}")
            nl()
            continue
        
        # LLM
        nl()
        sys.stdout.write(f"  {q(C.P2, '·')}  {q(C.G3, 'pensando...')}")
        sys.stdout.flush()
        
        save_conversation("user", text)
        
        reply = await omni_brain(text, all_status, base_env)
        action = extract_action(reply)
        clean = clean_response(reply)
        
        sys.stdout.write(f"\r  {q(C.AMB, '◉')}  {q(C.W, 'Omni', bold=True)}          \n")
        
        # Mostrar respuesta
        for line in clean.split('\n'):
            print(f"       {q(C.G0, line)}")
        
        save_conversation("assistant", clean)
        
        if action:
            result = await execute_action(action, instances, base_env)
            if result:
                nl()
                for line in result.split('\n'):
                    print(f"       {q(C.G1, line)}")
                save_conversation("assistant", f"[ACTION]: {result}")
        
        nl()
        
        # Refrescar estado cada 5 mensajes
        if len(get_conversation_history(100)) % 10 == 0:
            health_results = await asyncio.gather(*[health_check(i.port) for i in instances])
            stats_results = await asyncio.gather(*[
                get_instance_stats(i.port, i.env.get("MASTER_API_KEY", ""))
                for i in instances
            ])
            all_status = [
                {
                    "name": i.name,
                    "label": i.label,
                    "port": i.port,
                    "sector": i.sector,
                    "env": i.env,
                    "health": h,
                    "latency": lat,
                    "stats": s
                }
                for i, (h, lat), s in zip(instances, health_results, stats_results)
            ]

async def cmd_report(report_type: str = "daily"):
    """Generar y mostrar reporte."""
    print_logo(compact=True)
    
    if report_type == "daily":
        with Spinner("Generando reporte diario...") as sp:
            report = await generate_daily_report()
            sp.finish("Reporte generado")
    else:
        with Spinner("Generando reporte semanal...") as sp:
            report = await generate_weekly_report()
            sp.finish("Reporte generado")
    
    nl()
    for line in report.split('\n'):
        clean_line = re.sub(r'\*([^*]+)\*', lambda m: q(C.W, m.group(1), bold=True), line)
        print(f"  {clean_line}")
    nl()
    
    if confirm("¿Enviar por Telegram?"):
        await send_telegram(report)
        ok("Enviado")

def confirm(msg: str) -> bool:
    sys.stdout.write(f"  {q(C.P2, '?')}  {q(C.W, msg)} {q(C.G3, '[S/n]')}  ")
    sys.stdout.flush()
    try:
        v = input("").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return v in ("", "s", "si", "sí", "y", "yes")

async def cmd_alerts_cli():
    """Gestionar alertas desde CLI."""
    print_logo(compact=True)
    section("Gestión de Alertas")
    
    rules = get_alert_rules()
    
    if rules:
        info(f"{len(rules)} reglas configuradas:")
        nl()
        
        headers = ["ID", "NOMBRE", "INSTANCIA", "MÉTRICA", "UMBRAL", "ESTADO"]
        rows = []
        
        for r in rules:
            enabled = q(C.GRN, "ON") if r.get("enabled") else q(C.RED, "OFF")
            rows.append([
                str(r['id']),
                r['name'][:20],
                r['instance'],
                f"{r['metric']} {r['operator']} {r['threshold']}",
                r['severity'],
                enabled
            ])
        
        table(headers, rows)
    else:
        info("No hay reglas de alerta configuradas")
    
    nl()
    
    # Alertas pendientes
    unack = get_unacknowledged_events()
    if unack:
        warn(f"{len(unack)} alertas sin reconocer")
        for e in unack[:5]:
            ts = e.get('timestamp', '')[:16]
            dim(f"  [{ts}] {e.get('event_type', '')} - {e.get('instance', '')}")

async def cmd_logs():
    """Ver audit log."""
    print_logo(compact=True)
    section("Audit Log")
    
    logs = db_execute("""
        SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 30
    """, fetch=True)
    
    if not logs:
        info("Sin entradas en el audit log")
        return
    
    for log in logs:
        ts = log.get('timestamp', '')[:16]
        actor = log.get('actor', '')
        action = log.get('action', '')
        target = log.get('target', '')
        
        print(f"  {q(C.G3, ts)}  {q(C.P2, actor[:12])}  "
              f"{q(C.W, action[:15])}  {q(C.G1, target)}")

async def cmd_analyze_cli(instance: str = None):
    """Análisis profundo."""
    print_logo(compact=True)
    
    if not instance:
        instances = get_all_instances()
        if not instances:
            fail("No hay instancias")
            return
        
        # Análisis global
        section("Análisis Global")
        
        for inst in instances:
            analysis = analyze_trends(inst.name, 24)
            
            if analysis.get("status") == "insufficient_data":
                dim(f"  {inst.label}: datos insuficientes")
                continue
            
            emoji, _, _ = inst.sector_info
            avail = analysis.get("availability", {}).get("percentage", 0)
            lat_avg = analysis.get("latency", {}).get("avg", 0)
            
            avail_color = C.GRN if avail >= 99 else (C.YLW if avail >= 95 else C.RED)
            lat_color = C.GRN if lat_avg < 200 else (C.YLW if lat_avg < 500 else C.RED)
            
            print(f"  {emoji} {q(C.W, inst.label[:25], bold=True)}")
            print(f"     Disponibilidad: {q(avail_color, f'{avail:.1f}%')}  "
                  f"Latencia: {q(lat_color, f'{lat_avg:.0f}ms')}")
            
            # Predicciones
            preds = predict_issues(inst.name)
            if preds:
                for p in preds[:2]:
                    print(f"     {q(C.YLW, '⚠')} {q(C.G2, p.get('message', '')[:50])}")
            
            nl()
    else:
        # Análisis de instancia específica
        section(f"Análisis: {instance}")
        
        analysis = analyze_trends(instance, 48)
        anomalies = detect_anomalies(instance, 12)
        predictions = predict_issues(instance)
        
        if analysis.get("status") == "insufficient_data":
            warn("Datos insuficientes para análisis completo")
            return
        
        # Disponibilidad
        if analysis.get("availability"):
            avail = analysis["availability"]
            kv("Disponibilidad (48h)", f"{avail.get('percentage', 0):.2f}%")
            kv("Checks totales", str(avail.get("total_checks", 0)))
            kv("Outages", str(avail.get("outages", 0)))
        
        nl()
        
        # Latencia
        if analysis.get("latency"):
            lat = analysis["latency"]
            info("Latencia:")
            kv("  Promedio", f"{lat.get('avg', 0):.0f}ms")
            kv("  Mínimo", f"{lat.get('min', 0):.0f}ms")
            kv("  Máximo", f"{lat.get('max', 0):.0f}ms")
            kv("  P95", f"{lat.get('p95', 0):.0f}ms")
            kv("  Desv. estándar", f"{lat.get('stddev', 0):.1f}ms")
            kv("  Tendencia", lat.get("trend", "stable"))
        
        # Gráfico de latencia
        metrics = get_metrics_history(instance, 24)
        latencies = [m.get("latency_ms", 0) for m in metrics if m.get("latency_ms")]
        if latencies:
            nl()
            info("Latencia últimas 24h:")
            print(f"  {q(C.P2, spark_line(latencies, 50))}")
            print(f"  {q(C.G3, f'Min: {min(latencies):.0f}ms')}  "
                  f"{q(C.G3, f'Max: {max(latencies):.0f}ms')}")
        
        # Anomalías
        if anomalies:
            nl()
            warn(f"{len(anomalies)} anomalías detectadas:")
            for a in anomalies[:5]:
                ts = a.get('timestamp', '')[:16]
                dim(f"  [{ts}] {a.get('type', '')} - {a.get('value', '')}")
        
        # Predicciones
        if predictions:
            nl()
            info("🔮 Predicciones:")
            for p in predictions:
                print(f"  {q(C.YLW, '•')} {q(C.W, p.get('type', ''), bold=True)} "
                      f"({p.get('probability', '')})")
                dim(f"    {p.get('message', '')}")
                dim(f"    💡 {p.get('recommendation', '')}")

async def setup_telegram_webhook(base_url: str):
    """Configurar webhook de Telegram."""
    # Refrescar desde environ por si _load_master_env lo cargó después del import
    tok = os.environ.get("OMNI_TELEGRAM_TOKEN", "") or OMNI_TOKEN
    if not tok or not base_url:
        warn("OMNI_TELEGRAM_TOKEN o BASE_URL no configurados — revisa el .env")
        return

    token_suffix = tok.split(":")[-1][:10]
    webhook_url = f"{base_url.rstrip('/')}/omni/webhook/{token_suffix}"

    url = f"https://api.telegram.org/bot{tok}/setWebhook"
    
    try:
        if _HTTPX:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.post(url, json={"url": webhook_url})
                if r.json().get("ok"):
                    ok(f"Webhook configurado: {webhook_url}")
                else:
                    warn(f"Error: {r.text[:100]}")
    except Exception as e:
        warn(f"No pude configurar webhook: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    # Inicializar DB
    init_db()
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else "server"
    
    if cmd == "status":
        asyncio.run(cmd_status())
    
    elif cmd == "watch":
        asyncio.run(cmd_watch())
    
    elif cmd == "dashboard":
        asyncio.run(cmd_dashboard())
    
    elif cmd == "chat":
        asyncio.run(cmd_chat())
    
    elif cmd == "report":
        report_type = sys.argv[2] if len(sys.argv) > 2 else "daily"
        asyncio.run(cmd_report(report_type))
    
    elif cmd == "analyze":
        instance = sys.argv[2] if len(sys.argv) > 2 else None
        asyncio.run(cmd_analyze_cli(instance))

    elif cmd == "demo":
        if len(sys.argv) < 4:
            fail("Uso: melissa-omni.py demo <instancia> <on|off|status>")
            sys.exit(1)
        instance_name = sys.argv[2]
        mode = sys.argv[3].lower()
        instances = get_all_instances()
        inst = resolve_instance(instances, instance_name)
        if not inst:
            fail(f"No encontré instancia '{instance_name}'")
            sys.exit(1)
        if mode == "status":
            result = asyncio.run(execute_action({"type": "demo_status", "instance": instance_name}, instances, {}))
        else:
            result = asyncio.run(execute_action({"type": "set_demo", "instance": instance_name, "active": mode != "off"}, instances, {}))
        print(result)

    elif cmd == "alerts":
        asyncio.run(cmd_alerts_cli())
    
    elif cmd == "logs":
        asyncio.run(cmd_logs())
    
    elif cmd == "summary":
        asyncio.run(send_daily_summary())
        ok("Resumen enviado a Telegram")
    
    elif cmd == "weekly":
        asyncio.run(send_weekly_summary())
        ok("Reporte semanal enviado")
    
    elif cmd == "server":
        if not HAS_FASTAPI:
            fail("Instala dependencias: pip install fastapi uvicorn httpx")
            sys.exit(1)
        
        base_env = load_env(f"{TEMPLATE_DIR}/.env")
        base_url = base_env.get("BASE_URL", "")
        
        print_logo()
        section("Configuración del Servidor")
        
        kv("Puerto", str(OMNI_PORT))
        kv("Instancias", str(len(get_all_instances())))
        kv("Auto-heal", "Activo" if AUTO_HEAL_ENABLED else "Inactivo", 
           C.GRN if AUTO_HEAL_ENABLED else C.G3)
        kv("Health interval", f"{HEALTH_INTERVAL}s")
        kv("Metrics interval", f"{METRICS_INTERVAL}s")
        nl()
        
        info("Canales de notificación:")
        channels = []
        # Re-leer después del _load_master_env por si PM2 no lo tenía al inicio
        _tok = os.environ.get("OMNI_TELEGRAM_TOKEN", "") or OMNI_TOKEN
        _cid = os.environ.get("SANTIAGO_CHAT_ID", "") or SANTIAGO_CHAT
        if _tok:
            channels.append("Telegram")
            ok(f"  Telegram: @admelissabot → chat {_cid or '(sin chat_id)'}")
        else:
            warn("  Telegram: no configurado (revisa OMNI_TELEGRAM_TOKEN en .env)")
        
        if SLACK_WEBHOOK:
            channels.append("Slack")
            ok("  Slack: configurado")
        
        if DISCORD_WEBHOOK:
            channels.append("Discord")
            ok("  Discord: configurado")
        
        if SMTP_HOST:
            channels.append("Email")
            ok(f"  Email: {ALERT_EMAIL or SMTP_USER}")
        
        if CUSTOM_WEBHOOK:
            channels.append("Webhook")
            ok("  Custom webhook: configurado")
        
        if not channels:
            warn("  Sin canales configurados")
        
        nl()
        
        # Configurar webhook de Telegram si está disponible
        _tok_startup = os.environ.get("OMNI_TELEGRAM_TOKEN", "") or OMNI_TOKEN
        if _tok_startup and base_url:
            asyncio.run(setup_telegram_webhook(base_url))
        
        nl()
        info(f"Dashboard: http://localhost:{OMNI_PORT}/dashboard")
        info(f"API: http://localhost:{OMNI_PORT}/omni/status")
        nl()
        
        # Arrancar servidor
        uvicorn.run(
            omni_app,
            host="0.0.0.0",
            port=OMNI_PORT,
            log_level="warning",
            access_log=False
        )
    
    elif cmd == "setup-webhook":
        base_env = load_env(f"{TEMPLATE_DIR}/.env")
        base_url = sys.argv[2] if len(sys.argv) > 2 else base_env.get("BASE_URL", "")
        asyncio.run(setup_telegram_webhook(base_url))
    
    elif cmd == "test-notify":
        # Probar notificaciones
        async def test():
            print_logo(compact=True)
            section("Test de Notificaciones")
            
            notif = Notification(
                title="Test de Omni",
                message=f"Mensaje de prueba enviado a las {datetime.now().strftime('%H:%M:%S')}",
                severity="info",
                instance="test",
                channels=["telegram", "slack", "discord", "email", "webhook"]
            )
            
            with Spinner("Enviando notificaciones...") as sp:
                await send_notification(notif)
                sp.finish("Notificaciones enviadas")
            
            nl()
            info("Verifica que llegaron a todos los canales configurados")
        
        asyncio.run(test())
    
    elif cmd == "create-alert":
        # Crear alerta desde CLI
        print_logo(compact=True)
        section("Crear Alerta")
        
        name = input("  Nombre de la alerta: ").strip()
        if not name:
            fail("Nombre requerido")
            sys.exit(1)
        
        instance = input("  Instancia (* para todas): ").strip() or "*"
        
        metrics = ["latency_ms", "status", "conversations", "appointments", "error_rate"]
        print("  Métricas disponibles:", ", ".join(metrics))
        metric = input("  Métrica: ").strip()
        if metric not in metrics:
            warn(f"Usando métrica personalizada: {metric}")
        
        operators = [">", "<", ">=", "<=", "==", "!="]
        print("  Operadores:", ", ".join(operators))
        operator = input("  Operador: ").strip()
        if operator not in operators:
            fail("Operador inválido")
            sys.exit(1)
        
        try:
            threshold = float(input("  Umbral: ").strip())
        except ValueError:
            fail("Umbral debe ser numérico")
            sys.exit(1)
        
        severities = ["info", "warning", "error", "critical"]
        print("  Severidades:", ", ".join(severities))
        severity = input("  Severidad [warning]: ").strip() or "warning"
        
        channels = input("  Canales (telegram,slack,email) [telegram]: ").strip() or "telegram"
        
        try:
            cooldown = int(input("  Cooldown en minutos [30]: ").strip() or "30")
        except ValueError:
            cooldown = 30
        
        rule_id = create_alert_rule(name, instance, metric, operator, threshold, 
                                     severity, channels, cooldown)
        
        nl()
        ok(f"Alerta creada con ID: {rule_id}")
        log_audit("cli", "create_alert", str(rule_id), name)
    
    elif cmd == "delete-alert":
        if len(sys.argv) < 3:
            fail("Uso: melissa-omni.py delete-alert <id>")
            sys.exit(1)
        
        try:
            rule_id = int(sys.argv[2])
            delete_alert_rule(rule_id)
            ok(f"Alerta {rule_id} eliminada")
            log_audit("cli", "delete_alert", str(rule_id), "")
        except ValueError:
            fail("ID debe ser numérico")
    
    elif cmd == "create-workflow":
        # Crear workflow desde CLI
        print_logo(compact=True)
        section("Crear Workflow")
        
        name = input("  Nombre del workflow: ").strip()
        if not name:
            fail("Nombre requerido")
            sys.exit(1)
        
        events = [
            "instance_offline", "instance_online", "high_latency",
            "new_conversation", "new_appointment", "error",
            "whatsapp_connected", "whatsapp_disconnected"
        ]
        print("  Eventos disponibles:")
        for e in events:
            print(f"    - {e}")
        
        trigger_event = input("  Evento trigger: ").strip()
        
        print("  Acciones disponibles: notify, restart, webhook, log")
        
        actions = []
        while True:
            action_type = input("  Tipo de acción (vacío para terminar): ").strip()
            if not action_type:
                break
            
            action = {"type": action_type}
            
            if action_type == "notify":
                action["title"] = input("    Título: ").strip()
                action["message"] = input("    Mensaje: ").strip()
                action["severity"] = input("    Severidad [warning]: ").strip() or "warning"
                action["channels"] = input("    Canales [telegram]: ").strip().split(",") or ["telegram"]
            
            elif action_type == "restart":
                action["instance"] = input("    Instancia (vacío = del evento): ").strip()
            
            elif action_type == "webhook":
                action["url"] = input("    URL del webhook: ").strip()
            
            elif action_type == "log":
                action["message"] = input("    Mensaje: ").strip()
                action["severity"] = input("    Severidad [info]: ").strip() or "info"
            
            actions.append(action)
            ok(f"  Acción {action_type} añadida")
        
        if not actions:
            fail("Se requiere al menos una acción")
            sys.exit(1)
        
        wf_id = create_workflow(name, trigger_event, actions)
        nl()
        ok(f"Workflow creado con ID: {wf_id}")
        log_audit("cli", "create_workflow", str(wf_id), name)
    
    elif cmd == "workflows":
        print_logo(compact=True)
        section("Workflows")
        
        workflows = get_workflows()
        
        if not workflows:
            info("No hay workflows configurados")
        else:
            for wf in workflows:
                enabled = q(C.GRN, "ON") if wf.get("enabled") else q(C.RED, "OFF")
                runs = wf.get("run_count", 0)
                wf_id = wf.get("id", "?")
                
                print(f"  {q(C.P2, f'[{wf_id}]')} {q(C.W, wf['name'], bold=True)} {enabled}")
                print(f"       Trigger: {wf.get('trigger_event', '')}")
                print(f"       Ejecutado: {runs} veces")
                
                try:
                    actions = json.loads(wf.get("actions", "[]"))
                    print(f"       Acciones: {', '.join(a.get('type', '') for a in actions)}")
                except:
                    pass
                
                nl()
    
    elif cmd == "metrics":
        # Ver métricas de una instancia
        if len(sys.argv) < 3:
            fail("Uso: melissa-omni.py metrics <instancia> [horas]")
            sys.exit(1)
        
        instance = sys.argv[2]
        hours = int(sys.argv[3]) if len(sys.argv) > 3 else 24
        
        print_logo(compact=True)
        section(f"Métricas: {instance}", f"Últimas {hours} horas")
        
        metrics = get_metrics_history(instance, hours)
        
        if not metrics:
            warn("Sin métricas disponibles")
            sys.exit(0)
        
        # Estadísticas
        latencies = [m.get("latency_ms", 0) for m in metrics if m.get("latency_ms")]
        online_count = sum(1 for m in metrics if m.get("status") == "online")
        
        kv("Data points", str(len(metrics)))
        kv("Disponibilidad", f"{(online_count/len(metrics)*100):.1f}%")
        
        if latencies:
            nl()
            info("Latencia:")
            kv("  Promedio", f"{statistics.mean(latencies):.0f}ms")
            kv("  Mínimo", f"{min(latencies):.0f}ms")
            kv("  Máximo", f"{max(latencies):.0f}ms")
            if len(latencies) > 1:
                kv("  Desv. est.", f"{statistics.stdev(latencies):.1f}ms")
            
            nl()
            info("Gráfico:")
            print(f"  {q(C.P2, spark_line(latencies, 50))}")
        
        # Conversaciones
        convs = [m.get("conversations", 0) for m in metrics if m.get("conversations") is not None]
        if convs and any(c > 0 for c in convs):
            nl()
            info("Conversaciones:")
            kv("  Total", str(max(convs)))
            print(f"  {q(C.GRN, spark_line(convs, 50))}")
    
    elif cmd == "export":
        # Exportar datos
        output_file = sys.argv[2] if len(sys.argv) > 2 else f"omni_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        print_logo(compact=True)
        
        with Spinner("Exportando datos...") as sp:
            data = {
                "exported_at": datetime.now().isoformat(),
                "version": OMNI_VERSION,
                "events": get_recent_events(1000),
                "alert_rules": get_alert_rules(),
                "workflows": get_workflows(),
                "audit_log": db_execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 500", fetch=True),
            }
            
            # Métricas de las últimas 24h por instancia
            instances = get_all_instances()
            data["metrics"] = {}
            for inst in instances:
                data["metrics"][inst.name] = get_metrics_history(inst.name, 24)
            
            Path(output_file).write_text(json.dumps(data, indent=2, default=str))
            sp.finish(f"Exportado: {output_file}")
        
        kv("Eventos", str(len(data["events"])))
        kv("Alertas", str(len(data["alert_rules"])))
        kv("Workflows", str(len(data["workflows"])))
    
    elif cmd == "cleanup":
        # Limpiar datos antiguos
        print_logo(compact=True)
        section("Limpieza de datos")
        
        with Spinner("Limpiando métricas antiguas (>30 días)...") as sp:
            db_execute("DELETE FROM metrics WHERE timestamp < datetime('now', '-30 days')")
            sp.finish("Métricas limpiadas")
        
        with Spinner("Limpiando eventos antiguos (>90 días)...") as sp:
            db_execute("DELETE FROM events WHERE timestamp < datetime('now', '-90 days')")
            sp.finish("Eventos limpiados")
        
        with Spinner("Limpiando audit log antiguo (>180 días)...") as sp:
            db_execute("DELETE FROM audit_log WHERE timestamp < datetime('now', '-180 days')")
            sp.finish("Audit log limpiado")
        
        with Spinner("Limpiando conversaciones antiguas (>60 días)...") as sp:
            db_execute("DELETE FROM santiago_conversations WHERE timestamp < datetime('now', '-60 days')")
            sp.finish("Conversaciones limpiadas")
        
        with Spinner("Optimizando base de datos...") as sp:
            conn = sqlite3.connect(str(OMNI_DB))
            conn.execute("VACUUM")
            conn.close()
            sp.finish("Base de datos optimizada")
        
        nl()
        ok("Limpieza completada")
    
    elif cmd == "reset-db":
        # Resetear base de datos (peligroso)
        print_logo(compact=True)
        warn("¡PELIGRO! Esto eliminará TODOS los datos de Omni.")
        
        confirmation = input("  Escribe 'CONFIRMAR' para continuar: ").strip()
        if confirmation != "CONFIRMAR":
            info("Cancelado")
            sys.exit(0)
        
        with Spinner("Eliminando base de datos...") as sp:
            if OMNI_DB.exists():
                OMNI_DB.unlink()
            init_db()
            sp.finish("Base de datos reiniciada")
        
        log_audit("cli", "reset_db", "", "")
    
    elif cmd in ("help", "--help", "-h"):
        print_logo()
        
        cmds = [
            ("server", "Arrancar servidor completo (puerto 9001)"),
            ("chat", "Chat interactivo con Omni"),
            ("status", "Estado rápido de todas las instancias"),
            ("watch", "Monitor live (refresca cada 5s)"),
            ("dashboard", "Dashboard interactivo en terminal"),
            ("report [daily|weekly]", "Generar y mostrar reporte"),
            ("summary", "Enviar resumen diario a Telegram"),
            ("weekly", "Enviar reporte semanal a Telegram"),
            ("analyze [instancia]", "Análisis profundo"),
            ("alerts", "Ver reglas de alerta"),
            ("create-alert", "Crear nueva alerta"),
            ("delete-alert <id>", "Eliminar alerta"),
            ("workflows", "Ver workflows configurados"),
            ("create-workflow", "Crear nuevo workflow"),
            ("logs", "Ver audit log"),
            ("metrics <inst> [horas]", "Ver métricas históricas"),
            ("export [archivo]", "Exportar datos a JSON"),
            ("cleanup", "Limpiar datos antiguos"),
            ("test-notify", "Probar notificaciones"),
            ("setup-webhook [url]", "Configurar webhook Telegram"),
        ]
        
        section("Comandos")
        for c, d in cmds:
            print(f"    {q(C.P2, f'melissa-omni.py {c:<24}', bold=True)}{q(C.G2, d)}")
        
        nl()
        hr()
        nl()
        
        section("Variables de Entorno", "Configura en .env o exporta")
        
        env_vars = [
            ("OMNI_PORT", "9001", "Puerto del servidor"),
            ("OMNI_KEY", "secreto", "Clave de autenticación API"),
            ("OMNI_TELEGRAM_TOKEN", "", "Token del bot personal"),
            ("SANTIAGO_CHAT_ID", "", "Chat ID de Santiago"),
            ("OMNI_HEALTH_INTERVAL", "30", "Segundos entre health checks"),
            ("OMNI_METRICS_INTERVAL", "300", "Segundos entre recolección de métricas"),
            ("OMNI_AUTO_HEAL", "true", "Auto-reiniciar instancias caídas"),
            ("OMNI_AUTO_HEAL_DELAY", "120", "Segundos antes de auto-heal"),
            ("OMNI_SLACK_WEBHOOK", "", "Webhook de Slack"),
            ("OMNI_DISCORD_WEBHOOK", "", "Webhook de Discord"),
            ("OMNI_SMTP_HOST", "", "Servidor SMTP para emails"),
            ("OMNI_SMTP_USER", "", "Usuario SMTP"),
            ("OMNI_SMTP_PASS", "", "Contraseña SMTP"),
            ("OMNI_ALERT_EMAIL", "", "Email para alertas"),
            ("OMNI_CUSTOM_WEBHOOK", "", "Webhook personalizado"),
        ]
        
        for var, default, desc in env_vars:
            d = f"[{default}]" if default else ""
            print(f"    {q(C.CYN, var):<30} {q(C.G3, d):<12} {q(C.G2, desc)}")
        
        nl()
        
        section("Ejemplos de Uso")
        examples = [
            "melissa-omni.py server",
            "melissa-omni.py chat",
            "melissa-omni.py analyze clinica-bella",
            "melissa-omni.py metrics base 48",
            "melissa-omni.py create-alert",
        ]
        for ex in examples:
            print(f"    {q(C.G1, ex)}")
        
        nl()
    
    elif cmd == "version":
        print(f"melissa-omni {OMNI_VERSION}")
    
    else:
        fail(f"Comando desconocido: '{cmd}'")
        info("Usa 'melissa-omni.py help' para ver comandos")
        sys.exit(1)


if __name__ == "__main__":
    # Manejar Ctrl+C
    def signal_handler(sig, frame):
        print()
        info("Interrumpido")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    main()
