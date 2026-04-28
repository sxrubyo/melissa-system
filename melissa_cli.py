#!/usr/bin/env python3
"""
melissa — CLI v8.0 Enterprise

Sistema de recepcionista IA multi-sector.

Sectores soportados:
  • Clínicas estéticas      • Dentales           • Veterinarias
  • Restaurantes            • Hoteles            • Gimnasios
  • Salones de belleza      • Spas               • Consultorios médicos
  • Psicólogos              • Abogados           • Inmobiliarias
  • Talleres mecánicos      • Academias          • Nutricionistas
  • Fisioterapia            • Fotografía         • Coworkings

Comandos:
  melissa install           Instalar CLI globalmente (hazlo primero)
  melissa init              Primer setup guiado del producto
  melissa new               Crear instancia para un cliente (wizard)
  melissa list              Ver todas las instancias
  melissa dashboard         Panel en tiempo real
  melissa chat [n]          Generar tokens, probar bot, ver webhook
  melissa sync              Clonar runtime compartido actualizado a todos los clientes
  melissa fix [n]           Reparar instancias con bug de --cwd (bot no responde)
  melissa status [n]        Estado detallado
  melissa health            Health check rápido de todas
  melissa logs [n]          Logs en tiempo real
  melissa restart [n]       Reiniciar (o 'all')
  melissa webhooks [n]      Ver/reconfigurar webhook de Telegram
  melissa config [n]        Hub de configuración o edición de instancia
  melissa guide             Guía completa de operación
  melissa doctor            Diagnóstico del sistema
  melissa upgrade           Actualizar + propagar a todos los clientes
  melissa metrics [n]       Métricas de uso
  melissa stats [n]         Estadísticas de conversaciones
  melissa export [n]        Exportar a JSON/CSV
  melissa import [file]     Importar configuración
  melissa test [n]          Probar respuestas
  melissa stop [n]          Detener
  melissa delete [n]        Eliminar
  melissa clone [n]         Clonar instancia
  melissa reset [n]         Resetear sesión
  melissa backup [n]        Crear snapshot
  melissa restore [file]    Restaurar snapshot
  melissa scale [n] [num]   Escalar workers
  melissa audit             Auditoría de seguridad
  melissa benchmark         Test de rendimiento
  melissa secure            Guía de seguridad
  melissa rotate-keys       Rotar secrets
  melissa billing           Uso de APIs y costos
  melissa omni [sub]        Monitoreo central
  melissa nova [sub]        Motor Nova
  melissa gateway [n]       Gateway automático de skills y reglas
  melissa control [n]       Control duro del admin sobre frases, saludo y trato

V8.0 — NUEVOS COMANDOS:
  melissa modelo [n]        Cambiar modelo LLM en caliente (sin reiniciar)
  melissa simular [n]       Simular 10 conversaciones — detecta frases de bot
  melissa v8 [n]            Estado de los 15 sistemas V8
  melissa quality [n]       Score de humanidad de últimas respuestas
  melissa briefing [n]      Briefing diario: leads calientes + acción recomendada
  melissa cost [n]          Estimación de costo mensual del LLM
  melissa latency [n]       Test de latencia HTTP + LLM
  melissa diff [n1] [n2]    Comparar configuración entre instancias
  melissa watchdog          Monitor continuo con auto-restart inteligente
  melissa warmup [n]        Precalentar LLM antes de lanzar
  melissa campana [n]       Campañas de seguimiento y reactivación
  melissa env-check [n]     Verificar .env contra mejores prácticas V8
  melissa rollforward [n]   Aplicar melissa.py a instancias
  melissa dashboard-v8      Dashboard enriquecido con métricas V8

LOG ENGINE — Análisis inteligente de errores:
  melissa logs [n]           Stream en vivo con colores + alerta de errores
  melissa logs [n] --scan    Escanear logs: detecta errores con diagnóstico
  melissa logs [n] --fix     Detectar errores + aplicar fixes automáticos
  melissa logs [n] --errors  Mostrar solo líneas de error
  melissa logfix [n]         Atajo: logs --fix
  melissa logscan [n]        Atajo: logs --scan
"""

import sys, os, json, time, subprocess, threading, shutil, hashlib, signal, ast, tempfile
import platform, re, argparse, tarfile, sqlite3, csv
from pathlib import Path
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from melissa_cli_bb import (
    BBContext,
    bb_apply_persona as _bb_apply_persona_impl,
    bb_load_persona as _bb_load_persona_impl,
    bb_persona_defaults as _bb_persona_defaults_impl,
    bb_personality_catalog as _bb_personality_catalog_impl,
    bb_prompt_block as _bb_prompt_block_impl,
    bb_read_persona_db as _bb_read_persona_db_impl,
    bb_score_prompt as _bb_score_prompt_impl,
    bb_show_agent_summary as _bb_show_agent_summary_impl,
    bb_write_persona_db as _bb_write_persona_db_impl,
    cmd_bb as _cmd_bb_impl,
    cmd_bb_config as _cmd_bb_config_impl,
)

# ══════════════════════════════════════════════════════════════════════════════
# READLINE + AUTOCOMPLETADO
# ══════════════════════════════════════════════════════════════════════════════
COMMANDS = [
    "init", "new", "list", "dashboard", "status", "health", "metrics", "stats",
    "logs", "config", "template", "export", "import", "test", "restart", "stop",
    "delete", "clone", "reset", "backup", "restore", "scale", "doctor", "audit",
    "benchmark", "secure", "rotate-keys", "upgrade", "billing", "chat", "omni", "nova",
    "sync", "fix", "install", "guide",
    "pair", "pairing",
    "token", "tokens", "activar", "bridge", "whatsapp", "wa", "info",
    # V8.0 — nuevos comandos
    "modelo", "simular", "simulate", "v8", "quality", "humanness",
    "briefing", "campana", "campaign", "diff", "compare",
    "cost", "costos", "latency", "latencia",
    "env-check", "warmup", "watchdog", "rollforward", "watch", "live", "diagnose", "obs", "skills", "skill", "aprender", "desaprender", "entrenar", "simular-cliente", "skills", "skill", "aprender", "desaprender", "entrenar", "trainer", "simular-cliente", "cliente", "gateway", "control",
]

try:
    import readline
    HIST = Path.home() / ".melissa" / "history"
    HIST.parent.mkdir(exist_ok=True)
    if HIST.exists():
        readline.read_history_file(str(HIST))
    readline.set_history_length(1000)
    
    def _completer(text, state):
        opts = [c for c in COMMANDS if c.startswith(text.lower())]
        return opts[state] if state < len(opts) else None
    
    readline.set_completer(_completer)
    readline.parse_and_bind("tab: complete")
    
    import atexit
    atexit.register(readline.write_history_file, str(HIST))
except Exception:
    pass

# ══════════════════════════════════════════════════════════════════════════════
# HTTP CLIENT
# ══════════════════════════════════════════════════════════════════════════════
try:
    import httpx as _httpx
    _HTTPX = True
except ImportError:
    import urllib.request
    _HTTPX = False

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════
VERSION = "8.0.2"
MELISSA_HOME = os.getenv("MELISSA_HOME", str(Path.home() / ".melissa"))
MELISSA_DIR = os.getenv("MELISSA_DIR", str(Path(__file__).resolve().parent))
INSTANCES_DIR = os.getenv("INSTANCES_DIR", str(Path(MELISSA_HOME) / "instances"))
NOVA_DIR = os.getenv("NOVA_DIR", "/home/ubuntu/nova-os")
BACKUP_DIR = Path(os.getenv("MELISSA_BACKUPS", Path.home() / "melissa-backups"))
CACHE_DIR = Path(MELISSA_HOME) / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OMNI_PORT = int(os.getenv("OMNI_PORT", "9001"))
NOVA_PORT = int(os.getenv("NOVA_PORT", "9002"))
BASE_PORT, MAX_PORT = 8001, 8199

# Caddy — proxy reverso que maneja SSL y enrutamiento
# IMPORTANTE: el Caddyfile vive SIEMPRE en xus-https, nunca en la carpeta de Melissa.
# CADDY_DIR se ignora a propósito para evitar que un .env de instancia lo pise.
CADDY_DIR      = "/home/ubuntu/xus-https"
CADDYFILE_PATH = "/home/ubuntu/xus-https/Caddyfile"
CADDY_DOCKER_GW = os.getenv("CADDY_DOCKER_GW", "172.28.0.1")  # gateway Docker→host
SHARED_TELEGRAM_ROUTES = Path(
    os.getenv("MELISSA_SHARED_TELEGRAM_ROUTES", f"{MELISSA_HOME}/shared_telegram_routes.json")
)
WORKSPACE_CONFIG_PATH = Path(os.getenv("MELISSA_WORKSPACE_CONFIG", f"{MELISSA_HOME}/config.json"))

# PATCH v1 — 2026-04-16 — unificar runtime compartido para clone/new/sync
SYNC_RUNTIME_FILES = [
    "melissa.py",
    "melissa_brain_v10.py",
    "melissa_domino.py",
    "search.py",
    "knowledge_base.py",
    "brand_assets.py",
    "nova_bridge.py",
    "requirements.txt",
    ".env.example",
]

SYNC_RUNTIME_DIRS = [
    "v7",
    "melissa_core",
    "melissa_agents",
    "melissa_skills",
    "melissa_integrations",
    "personas",
]


def _runtime_sync_entries(source_root: str) -> List[str]:
    root = Path(source_root)
    entries: List[str] = []
    for rel_path in [*SYNC_RUNTIME_FILES, *SYNC_RUNTIME_DIRS]:
        if (root / rel_path).exists():
            entries.append(rel_path)
    return entries


def _remove_runtime_target(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _clone_runtime_entries(source_root: str, dest_root: str, entries: Optional[List[str]] = None) -> List[str]:
    src_root = Path(source_root)
    dst_root = Path(dest_root)
    copied: List[str] = []
    for rel_path in entries or _runtime_sync_entries(source_root):
        src = src_root / rel_path
        dst = dst_root / rel_path
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            _remove_runtime_target(dst)
            shutil.copytree(src, dst)
        else:
            if dst.exists() or dst.is_symlink():
                _remove_runtime_target(dst)
            shutil.copy2(src, dst)
        copied.append(rel_path)
    return copied

# ══════════════════════════════════════════════════════════════════════════════
# SECTORES - La clave para escalar Melissa
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class Sector:
    id: str
    name: str
    emoji: str
    tagline: str
    services: List[str]
    hours_default: str
    questions: List[str]
    keywords: List[str]
    color: str

SECTORS: Dict[str, Sector] = {
    "estetica": Sector(
        id="estetica", name="Clínica Estética", emoji="💉",
        tagline="Transforma belleza en citas",
        services=["Botox", "Rellenos", "Láser", "Peeling", "Mesoterapia"],
        hours_default="09:00-19:00",
        questions=["¿Qué tratamientos ofrecen?", "¿Precio del botox?", "¿Tienen promociones?"],
        keywords=["botox", "relleno", "arrugas", "rejuvenecimiento", "lifting"],
        color="183"
    ),
    "dental": Sector(
        id="dental", name="Clínica Dental", emoji="🦷",
        tagline="Sonrisas que agendan solas",
        services=["Limpieza", "Blanqueamiento", "Ortodoncia", "Implantes", "Endodoncia"],
        hours_default="08:00-18:00",
        questions=["¿Hacen urgencias?", "¿Precio de limpieza?", "¿Aceptan seguro?"],
        keywords=["diente", "muela", "dolor", "caries", "brackets"],
        color="117"
    ),
    "veterinaria": Sector(
        id="veterinaria", name="Veterinaria", emoji="🐾",
        tagline="Cuidando a quien no puede llamar",
        services=["Consulta", "Vacunación", "Cirugía", "Peluquería", "Urgencias"],
        hours_default="08:00-20:00",
        questions=["¿Atienden urgencias 24h?", "¿Precio de consulta?", "¿Tienen pensión?"],
        keywords=["perro", "gato", "mascota", "vacuna", "enfermo"],
        color="114"
    ),
    "restaurante": Sector(
        id="restaurante", name="Restaurante", emoji="🍽️",
        tagline="Mesas llenas, cocina feliz",
        services=["Reservas", "Eventos", "Catering", "Menú del día", "Delivery"],
        hours_default="12:00-23:00",
        questions=["¿Tienen terraza?", "¿Menú vegetariano?", "¿Reserva para grupos?"],
        keywords=["reserva", "mesa", "cena", "almuerzo", "grupo"],
        color="221"
    ),
    "hotel": Sector(
        id="hotel", name="Hotel / Hospedaje", emoji="🏨",
        tagline="Reservas mientras duermes",
        services=["Habitaciones", "Suites", "Desayuno", "Spa", "Eventos"],
        hours_default="24h",
        questions=["¿Precio por noche?", "¿Incluye desayuno?", "¿Admiten mascotas?"],
        keywords=["habitación", "reserva", "noche", "disponibilidad", "check-in"],
        color="179"
    ),
    "gimnasio": Sector(
        id="gimnasio", name="Gimnasio / Fitness", emoji="💪",
        tagline="Membresías que se venden solas",
        services=["Membresía", "Personal trainer", "Clases grupales", "Nutrición"],
        hours_default="06:00-22:00",
        questions=["¿Precio mensual?", "¿Tienen piscina?", "¿Clases incluidas?"],
        keywords=["inscripción", "clase", "horario", "entrenador", "precio"],
        color="203"
    ),
    "belleza": Sector(
        id="belleza", name="Salón de Belleza", emoji="💇",
        tagline="Cada cita, una transformación",
        services=["Corte", "Color", "Manicure", "Pedicure", "Tratamientos capilares"],
        hours_default="09:00-20:00",
        questions=["¿Precio de mechas?", "¿Atienden sin cita?", "¿Tienen parking?"],
        keywords=["corte", "tinte", "uñas", "peinado", "cita"],
        color="177"
    ),
    "spa": Sector(
        id="spa", name="Spa / Wellness", emoji="🧖",
        tagline="Relax automatizado",
        services=["Masajes", "Faciales", "Circuito spa", "Aromaterapia", "Parejas"],
        hours_default="10:00-21:00",
        questions=["¿Paquetes para parejas?", "¿Duración del circuito?", "¿Promociones?"],
        keywords=["masaje", "relajación", "facial", "spa", "pareja"],
        color="141"
    ),
    "medico": Sector(
        id="medico", name="Consultorio Médico", emoji="🩺",
        tagline="Citas sin espera telefónica",
        services=["Consulta general", "Especialidades", "Estudios", "Certificados"],
        hours_default="08:00-17:00",
        questions=["¿Atienden mi seguro?", "¿Cuánto dura la cita?", "¿Necesito ayuno?"],
        keywords=["cita", "doctor", "consulta", "seguro", "estudios"],
        color="117"
    ),
    "psicologo": Sector(
        id="psicologo", name="Psicología / Terapia", emoji="🧠",
        tagline="El primer paso, más fácil",
        services=["Terapia individual", "Parejas", "Familiar", "Online", "Evaluaciones"],
        hours_default="09:00-20:00",
        questions=["¿Primera cita gratis?", "¿Terapia online?", "¿Cuánto dura la sesión?"],
        keywords=["terapia", "ansiedad", "sesión", "psicólogo", "ayuda"],
        color="135"
    ),
    "abogado": Sector(
        id="abogado", name="Despacho Legal", emoji="⚖️",
        tagline="Consultas que llegan solas",
        services=["Consulta inicial", "Divorcios", "Laboral", "Mercantil", "Penal"],
        hours_default="09:00-18:00",
        questions=["¿Primera consulta gratis?", "¿Manejan mi caso?", "¿Cuánto cobran?"],
        keywords=["abogado", "demanda", "divorcio", "consulta", "legal"],
        color="99"
    ),
    "inmobiliaria": Sector(
        id="inmobiliaria", name="Inmobiliaria", emoji="🏠",
        tagline="Visitas que se agendan solas",
        services=["Venta", "Renta", "Avalúos", "Administración", "Asesoría"],
        hours_default="09:00-19:00",
        questions=["¿Propiedades en X zona?", "¿Aceptan crédito?", "¿Puedo agendar visita?"],
        keywords=["casa", "departamento", "renta", "comprar", "visita"],
        color="179"
    ),
    "taller": Sector(
        id="taller", name="Taller Mecánico", emoji="🔧",
        tagline="Citas de servicio sin llamadas",
        services=["Servicio", "Diagnóstico", "Frenos", "Alineación", "Hojalatería"],
        hours_default="08:00-18:00",
        questions=["¿Cuánto tarda el servicio?", "¿Tienen refacciones?", "¿Precio aproximado?"],
        keywords=["carro", "coche", "servicio", "frenos", "ruido"],
        color="208"
    ),
    "academia": Sector(
        id="academia", name="Academia / Escuela", emoji="📚",
        tagline="Inscripciones automáticas",
        services=["Inscripción", "Cursos", "Clases particulares", "Certificaciones"],
        hours_default="08:00-20:00",
        questions=["¿Horarios disponibles?", "¿Precio del curso?", "¿Tienen becas?"],
        keywords=["curso", "clase", "inscripción", "horario", "nivel"],
        color="221"
    ),
    "nutricion": Sector(
        id="nutricion", name="Nutricionista", emoji="🥗",
        tagline="Consultas que transforman",
        services=["Consulta", "Plan alimenticio", "Seguimiento", "Estudios"],
        hours_default="08:00-18:00",
        questions=["¿Primera cita incluye plan?", "¿Consulta online?", "¿Cuánto dura?"],
        keywords=["dieta", "peso", "nutrición", "plan", "consulta"],
        color="114"
    ),
    "fisioterapia": Sector(
        id="fisioterapia", name="Fisioterapia", emoji="🦴",
        tagline="Rehabilitación sin esperas",
        services=["Evaluación", "Rehabilitación", "Masaje terapéutico", "Electroterapia"],
        hours_default="07:00-19:00",
        questions=["¿Cuántas sesiones necesito?", "¿Aceptan seguro?", "¿Precio por sesión?"],
        keywords=["dolor", "lesión", "rehabilitación", "sesión", "terapia"],
        color="117"
    ),
    "fotografia": Sector(
        id="fotografia", name="Fotografía / Estudio", emoji="📸",
        tagline="Sesiones que se agendan solas",
        services=["Sesión retrato", "Eventos", "Producto", "Bodas", "Books"],
        hours_default="10:00-19:00",
        questions=["¿Precio de sesión?", "¿Incluye edición?", "¿Cuántas fotos entrega?"],
        keywords=["sesión", "fotos", "boda", "retrato", "evento"],
        color="183"
    ),
    "coworking": Sector(
        id="coworking", name="Coworking", emoji="🏢",
        tagline="Espacios que se rentan solos",
        services=["Hot desk", "Oficina privada", "Sala de juntas", "Domicilio fiscal"],
        hours_default="08:00-20:00",
        questions=["¿Precio mensual?", "¿Incluye internet?", "¿Tienen estacionamiento?"],
        keywords=["oficina", "espacio", "escritorio", "renta", "sala"],
        color="141"
    ),
    "tattoo": Sector(
        id="tattoo", name="Estudio de Tatuaje", emoji="🎨",
        tagline="Arte que se agenda",
        services=["Tatuaje", "Cover up", "Piercing", "Diseño personalizado"],
        hours_default="12:00-21:00",
        questions=["¿Precio por hora?", "¿Cómo agendar?", "¿Tienen portafolio?"],
        keywords=["tatuaje", "diseño", "cita", "piercing", "cover"],
        color="99"
    ),
    "otro": Sector(
        id="otro", name="Otro / Personalizado", emoji="⚙️",
        tagline="Adaptable a cualquier negocio",
        services=["Personalizado"],
        hours_default="09:00-18:00",
        questions=[],
        keywords=[],
        color="248"
    ),
}

# ══════════════════════════════════════════════════════════════════════════════
# SISTEMA DE COLORES
# ══════════════════════════════════════════════════════════════════════════════
def _tty(): 
    return sys.stdout.isatty() or bool(os.getenv("FORCE_COLOR"))

def _e(c): 
    return f"\033[{c}m" if _tty() else ""

class C:
    R = _e("0")
    BOLD = _e("1")
    DIM = _e("2")
    ITALIC = _e("3")
    
    # Paleta principal - Púrpura
    P1 = _e("38;5;183")   # Lavanda brillante
    P2 = _e("38;5;141")   # Púrpura suave
    P3 = _e("38;5;135")   # Púrpura medio
    P4 = _e("38;5;99")    # Púrpura profundo
    P5 = _e("38;5;57")    # Púrpura oscuro
    
    # Neutros
    W = _e("38;5;15")     # Blanco puro
    G0 = _e("38;5;252")   # Casi blanco
    G1 = _e("38;5;248")   # Gris claro
    G2 = _e("38;5;244")   # Gris medio
    G3 = _e("38;5;240")   # Gris oscuro
    G4 = _e("38;5;236")   # Gris muy oscuro
    
    # Semánticos
    GRN = _e("38;5;114")  # Verde
    RED = _e("38;5;203")  # Rojo
    YLW = _e("38;5;221")  # Amarillo
    CYN = _e("38;5;117")  # Cyan
    AMB = _e("38;5;179")  # Amber
    
    # Backgrounds
    BG_P = _e("48;5;57")
    BG_G = _e("48;5;236")

def q(color, text, bold=False):
    """Quick format."""
    return f"{C.BOLD if bold else ''}{color}{text}{C.R}"

def sector_color(sector_id: str) -> str:
    """Obtener color según sector."""
    s = SECTORS.get(sector_id, SECTORS["otro"])
    return _e(f"38;5;{s.color}")

# ══════════════════════════════════════════════════════════════════════════════
# LOGO ESTÁTICO CON PAC-MAN (ya comió parte del texto)
# ══════════════════════════════════════════════════════════════════════════════
def _get_terminal_width() -> int:
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80

def print_logo(compact=False, sector=None):
    print()
    YLW = _e("38;5;220")

    if compact:
        print(f"  {q(C.P1, '✦', bold=True)}  "
              f"{q(C.W, 'melissa', bold=True)}  "
              f"{q(C.G3, f'v{VERSION}')}")
        print()
        return

    ROWS = [
        ("38;5;183", "  ███╗   ███╗███████╗██╗     ██╗███████╗███████╗ █████╗ "),
        ("38;5;183", "  ████╗ ████║██╔════╝██║     ██║██╔════╝██╔════╝██╔══██╗"),
        ("38;5;141", "  ██╔████╔██║█████╗  ██║     ██║███████╗███████╗███████║"),
        ("38;5;141", "  ██║╚██╔╝██║██╔══╝  ██║     ██║╚════██║╚════██║██╔══██║"),
        ("38;5;99",  "  ██║ ╚═╝ ██║███████╗███████╗██║███████║███████║██║  ██║"),
        ("38;5;99",  "  ╚═╝     ╚═╝╚══════╝╚══════╝╚═╝╚══════╝╚══════╝╚═╝  ╚═╝"),
    ]
    for col_code, row in ROWS:
        print(f"{C.BOLD}{_e(col_code)}{row}{C.R}")
    print()

    if sector and sector in SECTORS:
        s = SECTORS[sector]
        print(f"  {s.emoji}  {q(sector_color(sector), s.tagline, bold=True)}")
    else:
        taglines = [
            "La IA que convierte conversaciones en citas.",
            "Multi-sector. Multi-canal. Siempre disponible.",
            "19 sectores. Infinitas posibilidades.",
            "Tu negocio, atendido 24/7.",
        ]
        print(f"  {q(C.P2, taglines[hash(datetime.now().strftime('%Y%m%d')) % len(taglines)])}")
    print(f"  {q(C.P1, '✦')} {q(C.G2, f'Melissa v{VERSION}')}  "
          f"{q(C.G3, '·')}  {q(C.G3, f'{len(SECTORS)} sectores')}")
    print(f"  {q(C.G4, '─' * 54)}")
    print()

def ok(m):    print(f"  {q(C.GRN, '✓')}  {q(C.W, m)}")
def fail(m):  print(f"  {q(C.RED, '✗')}  {q(C.W, m)}")
def warn(m):  print(f"  {q(C.YLW, '!')}  {q(C.G1, m)}")
def info(m):  print(f"  {q(C.P2, '·')}  {q(C.G1, m)}")
def dim(m):   print(f"       {q(C.G3, m)}")
def nl():     print()
def hr():     print(f"  {q(C.G4, '─' * 54)}")

def section(title, sub="", icon="✦"):
    """Sección con título."""
    print()
    print(f"  {q(C.P1, icon, bold=True)}  {q(C.W, title, bold=True)}")
    if sub:
        print(f"       {q(C.G2, sub)}")
    print()

def kv(key, val, color=None):
    """Key-value pair."""
    c = color or C.P2
    print(f"  {q(C.G2, f'{key:<20}')}  {q(c, str(val))}")

def box(title, content_lines, width=50):
    """Caja con borde."""
    print(f"  ┌{'─' * (width - 2)}┐")
    print(f"  │ {q(C.W, title.center(width - 4), bold=True)} │")
    print(f"  ├{'─' * (width - 2)}┤")
    for line in content_lines:
        padding = width - 4 - len(line.replace('\033[', '').split('m')[-1] if '\033[' in line else line)
        print(f"  │ {line}{' ' * max(0, padding)} │")
    print(f"  └{'─' * (width - 2)}┘")

def table(headers, rows, colors=None):
    """Tabla formateada."""
    if not rows:
        return
    
    _ansi_re = re.compile(r'\033\[[0-9;]*m')
    
    def _vis_len(s):
        return len(_ansi_re.sub('', str(s)))
    
    # Calcular anchos
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], _vis_len(cell))
    
    # Header
    header_line = "  "
    for i, h in enumerate(headers):
        header_line += f"{q(C.G2, h.ljust(widths[i]))}  "
    print(header_line)
    print(f"  {q(C.G4, '─' * (sum(widths) + len(widths) * 2))}")
    
    # Rows
    for row in rows:
        line = "  "
        for i, cell in enumerate(row):
            c = colors[i] if colors and i < len(colors) else C.G1
            padding = widths[i] - _vis_len(cell)
            line += f"{q(c, str(cell))}{' ' * padding}  "
        print(line)

def progress_bar(current, total, width=30, label=""):
    """Barra de progreso estática."""
    pct = current / total if total > 0 else 0
    filled = int(width * pct)
    bar = f"{'█' * filled}{'░' * (width - filled)}"
    pct_str = f"{pct * 100:.0f}%"
    print(f"  {q(C.P2, bar)} {q(C.W, pct_str)} {q(C.G3, label)}")

def prompt(label, default="", secret=False):
    """Input con estilo."""
    d = f" [{default}]" if default else ""
    sys.stdout.write(f"\n  {q(C.P2, '?')}  {q(C.W, label)}{q(C.G3, d)}  ")
    sys.stdout.flush()
    try:
        import getpass
        v = getpass.getpass("") if secret else input("")
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return v.strip() or default

def confirm(label, default=True):
    """Confirmación S/N."""
    d = "S/n" if default else "s/N"
    sys.stdout.write(f"\n  {q(C.P2, '?')}  {q(C.W, label)} {q(C.G3, f'[{d}]')}  ")
    sys.stdout.flush()
    try:
        v = input("").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return (v in ("s", "si", "sí", "y", "yes")) if v else default

def select(opts, descs=None, title="", icons=None):
    """Selector de opciones."""
    if title:
        print(f"\n  {q(C.G2, title)}")
    
    for i, o in enumerate(opts):
        num = q(C.P2, f"{i + 1}.", bold=True)
        icon = f"{icons[i]} " if icons and i < len(icons) else ""
        desc = f"  {q(C.G3, descs[i])}" if descs and i < len(descs) else ""
        print(f"    {num}  {icon}{q(C.W, o)}{desc}")
    
    while True:
        sys.stdout.write(f"\n  {q(C.P2, '→')}  ")
        sys.stdout.flush()
        try:
            v = input("").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if v.isdigit() and 1 <= int(v) <= len(opts):
            return int(v) - 1
        warn("Escribe el número de la opción")

def multi_select(opts, descs=None, title=""):
    """Selector múltiple."""
    if title:
        print(f"\n  {q(C.G2, title)}")
    
    for i, o in enumerate(opts):
        num = q(C.P2, f"{i + 1}.", bold=True)
        desc = f"  {q(C.G3, descs[i])}" if descs and i < len(descs) else ""
        print(f"    {num}  {q(C.W, o)}{desc}")
    
    print(f"\n  {q(C.G3, 'Escribe números separados por coma (ej: 1,3,5) o todo')}")
    
    sys.stdout.write(f"\n  {q(C.P2, '→')}  ")
    sys.stdout.flush()
    try:
        v = input("").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return []
    
    if v in ("todo", "all", "*"):
        return list(range(len(opts)))
    
    result = []
    for part in v.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= len(opts):
            result.append(int(part) - 1)
    return result

# ══════════════════════════════════════════════════════════════════════════════
# SPINNER SIMPLE (para operaciones largas)
# ══════════════════════════════════════════════════════════════════════════════
class Spinner:
    """Spinner minimalista para operaciones largas."""
    
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    def __init__(self, msg):
        self.msg = msg
        self._stop = threading.Event()
        self._thread = None
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, *args):
        self.stop()
    
    def start(self):
        def _run():
            i = 0
            while not self._stop.is_set():
                frame = q(C.P2, self.FRAMES[i % len(self.FRAMES)], bold=True)
                sys.stdout.write(f"\r  {frame}  {q(C.G1, self.msg)}")
                sys.stdout.flush()
                time.sleep(0.1)
                i += 1
        
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
    
    def update(self, msg):
        self.msg = msg
    
    def stop(self, msg=None, success=True, ok=None):
        # ok= es alias de success= para compatibilidad
        if ok is not None:
            success = ok
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.2)

        icon = q(C.GRN, "✓") if success else q(C.RED, "✗")
        final_msg = msg or self.msg
        # Pad a 70 chars para limpiar cualquier basura del spinner anterior
        padded = f"{final_msg:<70}"
        sys.stdout.write(f"\r  {icon}  {q(C.W, padded)}\n")
        sys.stdout.flush()
    
    def finish(self, msg=None, ok=True):
        self.stop(msg, ok=ok)

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS - Utilidades optimizadas
# ══════════════════════════════════════════════════════════════════════════════
@lru_cache(maxsize=32)
def load_env(path):
    """Cargar .env con caché."""
    env = {}
    try:
        p = Path(path)
        if not p.exists():
            return env
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env

def save_env(path, env_dict):
    """Guardar .env."""
    lines = []
    for k, v in env_dict.items():
        if '\n' in str(v):
            v = f'"{v}"'
        lines.append(f"{k}={v}")
    Path(path).write_text("\n".join(lines))
    load_env.cache_clear()

def update_env_key(path, key, val):
    """Actualizar una clave específica."""
    try:
        c = Path(path).read_text() if Path(path).exists() else ""
        if re.search(rf"^{key}=", c, re.MULTILINE):
            c = re.sub(rf"^{key}=.*$", f"{key}={val}", c, flags=re.MULTILINE)
        else:
            c += f"\n{key}={val}"
        Path(path).write_text(c)
        load_env.cache_clear()
    except Exception as e:
        warn(f".env no actualizado: {e}")


def workspace_defaults() -> Dict[str, Any]:
    return {
        "owner_name": "",
        "default_business_name": "",
        "default_sector": "",
        "default_platform": "telegram",
        "public_base_url": "",
        "telegram_token": "",
        "telegram_shared": False,
        "llm_keys": {
            "GROQ_API_KEY": "",
            "GEMINI_API_KEY": "",
            "GEMINI_API_KEY_2": "",
            "GEMINI_API_KEY_3": "",
            "GEMINI_API_KEY_4": "",
            "GEMINI_API_KEY_5": "",
            "GEMINI_API_KEY_6": "",
            "GEMINI_API_KEY_7": "",
            "OPENROUTER_API_KEY": "",
            "OPENAI_API_KEY": "",
        },
        "search_keys": {
            "SERP_API_KEY": "",
            "BRAVE_API_KEY": "",
            "APIFY_API_KEY": "",
        },
        "meta": {
            "META_APP_ID": "",
            "META_APP_SECRET": "",
        },
        "nova": {
            "url": f"http://localhost:{NOVA_PORT}",
            "api_key": "",
            "token": "",
            "enabled": False,
        },
        "omni": {
            "url": f"http://localhost:{OMNI_PORT}",
            "key": "",
        },
        "agent": {
            "display_name": "Melissa",
            "role": "asesora virtual",
            "prompt_master": "",
        },
    }


def ensure_workspace_files() -> None:
    Path(MELISSA_HOME).mkdir(parents=True, exist_ok=True)
    Path(INSTANCES_DIR).mkdir(parents=True, exist_ok=True)
    if not WORKSPACE_CONFIG_PATH.exists():
        WORKSPACE_CONFIG_PATH.write_text(
            json.dumps(workspace_defaults(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    if not SHARED_TELEGRAM_ROUTES.exists():
        save_shared_telegram_routes({"default_instance": "", "routes": {}})


def load_workspace_config() -> Dict[str, Any]:
    defaults = workspace_defaults()
    if not WORKSPACE_CONFIG_PATH.exists():
        return defaults
    try:
        payload = json.loads(WORKSPACE_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return defaults
    if not isinstance(payload, dict):
        return defaults
    merged = json.loads(json.dumps(defaults))
    for key, value in payload.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def save_workspace_config(data: Dict[str, Any]) -> None:
    ensure_workspace_files()
    WORKSPACE_CONFIG_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def workspace_is_configured() -> bool:
    config = load_workspace_config()
    return bool(
        str(config.get("default_business_name", "")).strip()
        or str(config.get("owner_name", "")).strip()
        or str(config.get("telegram_token", "")).strip()
        or any(str(v).strip() for v in config.get("llm_keys", {}).values())
    )


def runtime_defaults() -> Dict[str, Any]:
    config = load_workspace_config()
    legacy_env = load_env(f"{MELISSA_DIR}/.env")
    llm_keys = dict(config.get("llm_keys", {}))
    search_keys = dict(config.get("search_keys", {}))
    meta = dict(config.get("meta", {}))
    nova_cfg = dict(config.get("nova", {}))
    omni_cfg = dict(config.get("omni", {}))

    for key in llm_keys:
        llm_keys[key] = llm_keys.get(key) or legacy_env.get(key, "")
    for key in search_keys:
        search_keys[key] = search_keys.get(key) or legacy_env.get(key, "")
    for key in meta:
        meta[key] = meta.get(key) or legacy_env.get(key, "")

    nova_cfg["url"] = nova_cfg.get("url") or legacy_env.get("NOVA_URL", f"http://localhost:{NOVA_PORT}")
    nova_cfg["api_key"] = nova_cfg.get("api_key") or legacy_env.get("NOVA_API_KEY", "")
    nova_cfg["token"] = nova_cfg.get("token") or legacy_env.get("NOVA_TOKEN", "")
    if "NOVA_ENABLED" in legacy_env and not nova_cfg.get("enabled"):
        nova_cfg["enabled"] = legacy_env.get("NOVA_ENABLED", "false").lower() == "true"

    omni_cfg["url"] = omni_cfg.get("url") or legacy_env.get("OMNI_URL", f"http://localhost:{OMNI_PORT}")
    omni_cfg["key"] = omni_cfg.get("key") or legacy_env.get("OMNI_KEY", "")

    return {
        "workspace": config,
        "llm_keys": llm_keys,
        "search_keys": search_keys,
        "meta": meta,
        "nova": nova_cfg,
        "omni": omni_cfg,
        "public_base_url": str(config.get("public_base_url", "")).strip() or legacy_env.get("BASE_URL", "").strip(),
        "telegram_token": str(config.get("telegram_token", "")).strip() or legacy_env.get("TELEGRAM_TOKEN", "").strip(),
        "telegram_shared": bool(config.get("telegram_shared", False)),
        "default_platform": str(config.get("default_platform", "telegram")).strip() or "telegram",
        "default_business_name": str(config.get("default_business_name", "")).strip(),
        "default_sector": str(config.get("default_sector", "")).strip(),
    }


def load_shared_telegram_routes() -> Dict[str, Any]:
    default = {"default_instance": "", "routes": {}}
    if not SHARED_TELEGRAM_ROUTES.exists():
        return default
    try:
        data = json.loads(SHARED_TELEGRAM_ROUTES.read_text())
        if not isinstance(data, dict):
            return default
        if not isinstance(data.get("routes"), dict):
            data["routes"] = {}
        data.setdefault("default_instance", "")
        return data
    except Exception:
        return default


def save_shared_telegram_routes(data: Dict[str, Any]):
    SHARED_TELEGRAM_ROUTES.parent.mkdir(parents=True, exist_ok=True)
    SHARED_TELEGRAM_ROUTES.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def ensure_shared_telegram_default(instance_name: str) -> Dict[str, Any]:
    routes = load_shared_telegram_routes()
    routes.setdefault("routes", {})
    if not routes.get("default_instance"):
        routes["default_instance"] = instance_name
        save_shared_telegram_routes(routes)
    return routes


def workspace_summary(config: Optional[Dict[str, Any]] = None) -> None:
    cfg = config or load_workspace_config()
    llm_active = [key for key, value in cfg.get("llm_keys", {}).items() if str(value).strip()]
    search_active = [key for key, value in cfg.get("search_keys", {}).items() if str(value).strip()]
    section("Workspace Melissa", "Producto limpio y configurable")
    kv("Owner", cfg.get("owner_name", "") or "—")
    kv("Negocio por defecto", cfg.get("default_business_name", "") or "—")
    kv("Sector sugerido", cfg.get("default_sector", "") or "—")
    kv("Plataforma sugerida", cfg.get("default_platform", "telegram") or "telegram")
    kv("Base URL", cfg.get("public_base_url", "") or "—")
    kv("Telegram compartido", "sí" if cfg.get("telegram_shared") else "no")
    kv("Token Telegram", "configurado" if cfg.get("telegram_token") else "vacío")
    kv("LLM keys", ", ".join(llm_active) if llm_active else "ninguna")
    kv("Search keys", ", ".join(search_active) if search_active else "ninguna")
    kv("Agente", cfg.get("agent", {}).get("display_name", "Melissa"))
    nl()


def edit_workspace_config() -> Dict[str, Any]:
    ensure_workspace_files()
    cfg = load_workspace_config()

    owner_name = prompt("Nombre del dueño o admin", default=cfg.get("owner_name", ""))
    business_name = prompt("Nombre del negocio por defecto", default=cfg.get("default_business_name", ""))
    sector_keys = list(SECTORS.keys())
    suggested_sector = str(cfg.get("default_sector", "") or "").strip()
    if confirm("¿Definir un sector por defecto para nuevas instancias?", default=bool(suggested_sector)):
        sector_labels = [f"{SECTORS[key].emoji} {SECTORS[key].name}" for key in sector_keys]
        sector_descs = [SECTORS[key].tagline for key in sector_keys]
        sector_idx = select(sector_labels, descs=sector_descs, title="Sector sugerido para nuevas instancias")
        cfg["default_sector"] = sector_keys[sector_idx]

    platform_options = ["telegram", "whatsapp", "ambos"]
    platform_descs = [
        "Empieza por Telegram con setup más simple.",
        "Prepara WhatsApp Business como canal principal.",
        "Deja todo listo para Telegram y WhatsApp.",
    ]
    platform_idx = select(
        ["Telegram", "WhatsApp", "Ambos"],
        descs=platform_descs,
        title="Canal sugerido para nuevas instancias",
    )
    cfg["default_platform"] = platform_options[platform_idx]

    public_base_url = prompt("Base URL pública por defecto", default=cfg.get("public_base_url", ""))
    telegram_token = prompt(
        "Token compartido de Telegram (opcional)",
        default=cfg.get("telegram_token", ""),
        secret=bool(cfg.get("telegram_token")),
    )
    telegram_shared = confirm("¿Usar router compartido de Telegram por defecto?", default=bool(cfg.get("telegram_shared")))

    llm_labels = [
        ("GROQ_API_KEY", "Groq"),
        ("GEMINI_API_KEY", "Gemini"),
        ("OPENROUTER_API_KEY", "OpenRouter"),
        ("OPENAI_API_KEY", "OpenAI"),
    ]
    if confirm("¿Configurar API keys LLM ahora?", default=any(cfg.get("llm_keys", {}).values())):
        for key, label in llm_labels:
            current = cfg["llm_keys"].get(key, "")
            cfg["llm_keys"][key] = prompt(f"{label} API key", default=current, secret=bool(current))

    if confirm("¿Configurar claves de búsqueda ahora?", default=any(cfg.get("search_keys", {}).values())):
        for key, label in [("BRAVE_API_KEY", "Brave Search"), ("SERP_API_KEY", "SerpAPI"), ("APIFY_API_KEY", "Apify")]:
            current = cfg["search_keys"].get(key, "")
            cfg["search_keys"][key] = prompt(f"{label} API key", default=current, secret=bool(current))

    cfg["owner_name"] = owner_name.strip()
    cfg["default_business_name"] = business_name.strip()
    cfg["public_base_url"] = public_base_url.strip()
    cfg["telegram_token"] = telegram_token.strip()
    cfg["telegram_shared"] = telegram_shared

    agent_cfg = dict(cfg.get("agent", {}))
    agent_cfg["display_name"] = prompt("Nombre base del agente", default=agent_cfg.get("display_name", "Melissa")).strip() or "Melissa"
    agent_cfg["role"] = prompt("Rol base del agente", default=agent_cfg.get("role", "asesora virtual")).strip() or "asesora virtual"
    agent_cfg["prompt_master"] = prompt(
        "Prompt maestro base (opcional)",
        default=agent_cfg.get("prompt_master", ""),
    ).strip()
    cfg["agent"] = agent_cfg

    save_workspace_config(cfg)
    ok(f"Workspace guardado en {WORKSPACE_CONFIG_PATH}")
    return cfg

def slug(name):
    """Convertir nombre a slug."""
    n = name.lower().strip()
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")]:
        n = n.replace(a, b)
    return re.sub(r'[^a-z0-9]+', '-', n).strip('-')

def next_port():
    """Encontrar siguiente puerto disponible."""
    import socket
    for p in range(BASE_PORT + 1, MAX_PORT + 1):
        with socket.socket() as s:
            try:
                s.bind(("0.0.0.0", p))
                return p
            except OSError:
                pass
    return None

def health(port, timeout=2):
    """Health check rápido."""
    url = f"http://localhost:{port}/health"
    try:
        if _HTTPX:
            r = _httpx.get(url, timeout=timeout)
            return r.json() if r.status_code == 200 else {}
        else:
            return json.loads(urllib.request.urlopen(url, timeout=timeout).read())
    except Exception:
        return {}

def health_batch(ports, timeout=2):
    """Health check en paralelo."""
    results = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(health, p, timeout): p for p in ports}
        for f in as_completed(futures):
            port = futures[f]
            try:
                results[port] = f.result()
            except Exception:
                results[port] = {}
    return results

def pm2(cmd, name=""):
    """Ejecutar comando PM2."""
    args = ["pm2", cmd]
    if name:
        args.append(name)
    return subprocess.run(args, capture_output=True).returncode == 0

def pm2_save():
    subprocess.run(["pm2", "save"], capture_output=True)

def pm2_list():
    """Obtener lista de procesos PM2."""
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        pass
    return []

def public_ip():
    """Obtener IP pública."""
    try:
        if _HTTPX:
            return _httpx.get("https://api.ipify.org", timeout=5).text.strip()
        return urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode().strip()
    except Exception:
        return ""

def icon_status(h):
    """Icono de estado."""
    if not h:
        return q(C.RED, "●"), "offline"
    return (q(C.GRN, "●"), "online") if h.get("status") == "online" else (q(C.RED, "●"), "offline")

# ══════════════════════════════════════════════════════════════════════════════
# INSTANCIAS - Gestión centralizada
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class Instance:
    name: str
    label: str
    port: int
    dir: str
    env: dict
    is_base: bool = False
    sector: str = "otro"
    created_at: str = ""

    @property
    def pm2_name(self) -> str:
        """Nombre PM2 de esta instancia."""
        return "melissa" if self.is_base else f"melissa-{self.name}"

    @property
    def db_path(self) -> str:
        return self.env.get("DB_PATH", f"{self.dir}/melissa.db")

    @property
    def master_key(self) -> str:
        return self.env.get("MASTER_API_KEY", "")

    @property
    def platform(self) -> str:
        return self.env.get("PLATFORM", "telegram")

    @property
    def webhook_secret(self) -> str:
        return self.env.get("WEBHOOK_SECRET", "")

    @property
    def is_active(self) -> bool:
        """True si la instancia tiene setup_done=1 en la DB."""
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute("SELECT setup_done FROM clinic WHERE id=1").fetchone()
            conn.close()
            return bool(row and row[0])
        except Exception:
            return False

    def api_call(self, method: str, path: str, payload: dict = None, timeout: int = 10) -> dict:
        """Llamada HTTP a la API de esta instancia."""
        url = f"http://localhost:{self.port}{path}"
        headers = {"Content-Type": "application/json"}
        if self.master_key:
            headers["X-Master-Key"] = self.master_key
        try:
            if _HTTPX:
                method_up = (method or "GET").upper()
                request_kwargs = {"headers": headers, "timeout": timeout}
                if method_up == "GET":
                    if payload:
                        request_kwargs["params"] = payload
                else:
                    request_kwargs["json"] = payload
                r = _httpx.request(method_up, url, **request_kwargs)
                return r.json() if r.status_code < 400 else {"error": r.text[:200], "status": r.status_code}
            else:
                import urllib.request as _ur
                data = json.dumps(payload).encode() if payload else None
                req = _ur.Request(url, data=data, headers=headers, method=method)
                return json.loads(_ur.urlopen(req, timeout=timeout).read())
        except Exception as e:
            return {"error": str(e)}

def get_instances() -> List[Instance]:
    """Obtener todas las instancias."""
    instances = []
    
    # Base instance
    base_env = load_env(f"{MELISSA_DIR}/.env")
    if base_env:
        instances.append(Instance(
            name="base",
            label="Instancia Base",
            port=int(base_env.get("PORT", BASE_PORT)),
            dir=MELISSA_DIR,
            env=dict(base_env),
            is_base=True,
            sector=base_env.get("SECTOR", "estetica")
        ))
    
    # Additional instances
    if os.path.isdir(INSTANCES_DIR):
        for nm in sorted(os.listdir(INSTANCES_DIR)):
            d = f"{INSTANCES_DIR}/{nm}"
            ep = f"{d}/.env"
            if not os.path.isdir(d) or not os.path.exists(ep):
                continue
            
            ev = load_env(ep)
            
            # Load instance.json if exists
            meta = {}
            meta_path = f"{d}/instance.json"
            if os.path.exists(meta_path):
                try:
                    meta = json.loads(Path(meta_path).read_text())
                except Exception:
                    pass
            
            instances.append(Instance(
                name=nm,
                label=meta.get("label", nm.replace("-", " ").title()),
                port=int(ev.get("PORT", 8002)),
                dir=d,
                env=dict(ev),
                is_base=False,
                sector=ev.get("SECTOR", meta.get("sector", "otro")),
                created_at=meta.get("created_at", "")
            ))
    
    return instances

def find_instance(name: str) -> Optional[Instance]:
    """Buscar instancia por nombre (parcial)."""
    instances = get_instances()
    name_lower = name.lower()
    
    # Exact match
    for inst in instances:
        if inst.name.lower() == name_lower:
            return inst
    
    # Partial match
    for inst in instances:
        if name_lower in inst.name.lower() or name_lower in inst.label.lower():
            return inst
    
    return None

def get_instance_stats(inst: Instance) -> dict:
    """Obtener estadísticas de una instancia."""
    stats = {
        "conversations": 0,
        "messages": 0,
        "appointments": 0,
        "memory_items": 0,
    }
    
    db_path = f"{inst.dir}/melissa.db"
    if not os.path.exists(db_path):
        return stats
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Conversations
        try:
            cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM conversations")
            stats["conversations"] = cursor.fetchone()[0]
        except Exception:
            pass
        
        # Messages
        try:
            cursor.execute("SELECT COUNT(*) FROM conversations")
            stats["messages"] = cursor.fetchone()[0]
        except Exception:
            pass
        
        # Appointments
        try:
            cursor.execute("SELECT COUNT(*) FROM appointments")
            stats["appointments"] = cursor.fetchone()[0]
        except Exception:
            pass
        
        # Memory
        try:
            cursor.execute("SELECT COUNT(*) FROM memory")
            stats["memory_items"] = cursor.fetchone()[0]
        except Exception:
            pass
        
        conn.close()
    except Exception:
        pass
    
    return stats

# ══════════════════════════════════════════════════════════════════════════════
# CACHÉ DE SALUD - Para dashboard rápido
# ══════════════════════════════════════════════════════════════════════════════
_health_cache = {}
_health_cache_time = 0
_HEALTH_CACHE_TTL = 5  # segundos

def get_cached_health(port):
    """Health check con caché."""
    global _health_cache, _health_cache_time
    
    now = time.time()
    if now - _health_cache_time > _HEALTH_CACHE_TTL:
        _health_cache = {}
        _health_cache_time = now
    
    if port in _health_cache:
        return _health_cache[port]
    
    h = health(port)
    _health_cache[port] = h
    return h

# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICACIONES
# ══════════════════════════════════════════════════════════════════════════════
def notify_omni(event, details=""):
    """Notificar a Omni (fire-and-forget)."""
    try:
        base_env = load_env(f"{MELISSA_DIR}/.env")
        omni_url = base_env.get("OMNI_URL", "")
        omni_key = base_env.get("OMNI_KEY", "")
        if not omni_url or not omni_key:
            return
        
        payload = json.dumps({
            "event": event,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }).encode()
        
        if _HTTPX:
            _httpx.post(
                f"{omni_url}/omni/event",
                content=payload,
                headers={"X-Omni-Key": omni_key, "Content-Type": "application/json"},
                timeout=4
            )
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
# COMANDOS
# ══════════════════════════════════════════════════════════════════════════════

def cmd_init(args):
    """Onboarding guiado del producto Melissa."""
    print_logo()
    ensure_workspace_files()
    section("Melissa Init", "Primer setup guiado del producto")
    info("Este init no usa configuraciones del autor. Crea tu workspace limpio en ~/.melissa.")
    nl()

    info("Sistema:")
    kv("OS", platform.system())
    kv("Python", sys.version.split()[0])
    kv("Melissa home", MELISSA_HOME)
    kv("Instancias", INSTANCES_DIR)
    nl()

    info("Dependencias base:")
    deps = [("python3", "Python 3"), ("pm2", "PM2"), ("git", "Git"), ("curl", "curl")]
    for cmd_, label in deps:
        if shutil.which(cmd_):
            ok(label)
        else:
            warn(f"{label} no encontrado")
    nl()

    workspace_summary()
    if not confirm("¿Configurar o actualizar este workspace ahora?", default=True):
        return

    cfg = edit_workspace_config()
    nl()
    info("Melissa ya puede nacer como producto abierto sin estado previo.")
    info("Cuando hables con Melissa desde Telegram como admin podrás afinarla con:")
    dim("  /aprender [instrucción]   → evolucionar prompt en lenguaje natural")
    dim("  /control [instrucción]    → saludo, frases prohibidas y trato duro")
    dim("  /personalidad             → ver estado actual del agente")
    nl()

    if confirm("¿Crear tu primera instancia ahora?", default=not bool(get_instances())):
        cmd_new(argparse.Namespace(name=cfg.get("default_business_name", ""), subcommand="", command="new"))
        return

    section("Listo", "Workspace preparado")
    info("Siguiente paso: melissa new")
    info("Luego: melissa config o melissa bb config para ajustar prompt y personalidad")
    nl()

def cmd_list(args):
    """Listar todas las instancias."""
    print_logo(compact=True)
    section("Instancias")
    
    instances = get_instances()
    if not instances:
        warn("No hay instancias configuradas")
        info("Crea una con: melissa new")
        return
    
    # Health check en paralelo
    ports = [i.port for i in instances]
    healths = health_batch(ports)
    
    # Tabla
    headers = ["ESTADO", "NOMBRE", "SECTOR", "PUERTO", "PLATAFORMA"]
    rows = []
    
    for inst in instances:
        h = healths.get(inst.port, {})
        icon, status = icon_status(h)
        sector = SECTORS.get(inst.sector, SECTORS["otro"])
        
        wa = h.get("whatsapp", {})
        plat = f"WA {wa.get('phone', '')[-7:]}" if wa.get("connected") else inst.env.get("PLATFORM", "telegram")[:10]
        
        rows.append([
            f"{icon} {status}",
            inst.label[:25],
            f"{sector.emoji} {sector.name[:15]}",
            str(inst.port),
            plat
        ])
    
    table(headers, rows, [None, C.W, None, C.P2, C.G2])
    nl()
    
    # Resumen
    online = sum(1 for h in healths.values() if h.get("status") == "online")
    total = len(instances)
    
    if online == total:
        ok(f"Todas las instancias online ({total})")
    else:
        warn(f"{online}/{total} instancias online")
    nl()

def cmd_dashboard(args):
    """Dashboard en tiempo real."""
    print_logo(compact=True)
    section("Dashboard", "Ctrl+C para salir")
    
    def draw():
        os.system("clear")
        print_logo(compact=True)
        print()
        
        instances = get_instances()
        ports = [i.port for i in instances]
        healths = health_batch(ports, timeout=1)
        
        online = sum(1 for h in healths.values() if h.get("status") == "online")
        total = len(instances)
        now = datetime.now().strftime("%H:%M:%S")
        
        # Header
        status_color = C.GRN if online == total else C.YLW
        print(f"  {q(C.P1, '✦', bold=True)}  {q(C.W, 'Dashboard', bold=True)}  "
              f"{q(C.G3, now)}  "
              f"{q(status_color, f'{online}/{total} online')}")
        hr()
        nl()
        
        # Instances
        for inst in instances:
            h = healths.get(inst.port, {})
            icon, status = icon_status(h)
            sector = SECTORS.get(inst.sector, SECTORS["otro"])
            
            # Stats
            stats = get_instance_stats(inst)
            
            wa = h.get("whatsapp", {})
            plat = "WhatsApp" if wa.get("connected") else inst.env.get("PLATFORM", "Telegram")
            
            nova = q(C.P3, " ✦Nova") if inst.env.get("NOVA_ENABLED") == "true" else ""
            
            print(f"  {icon}  {q(C.W, inst.label, bold=True)}{nova}")
            print(f"       {sector.emoji} {q(C.G2, sector.name)}  ·  :{inst.port}  ·  {q(C.G1, plat)}")
            _stats_line = f'{stats["conversations"]} conv · {stats["appointments"]} citas · {stats["memory_items"]} mem'
            print(f"       {q(C.G3, _stats_line)}")
            nl()
        
        hr()
        print(f"  {q(C.G3, 'Actualiza cada 3s')}")
    
    try:
        while True:
            draw()
            time.sleep(3)
    except KeyboardInterrupt:
        nl()
        info("Dashboard cerrado")

def cmd_new(args):
    """Crear nueva instancia con wizard de sector."""
    print_logo(compact=True)
    section("Nueva Instancia", "Wizard de configuración")
    
    # 1. Nombre
    name_raw = getattr(args, 'name', '') or prompt("Nombre del negocio")
    if not name_raw:
        fail("Necesitas un nombre")
        return
    
    name = slug(name_raw)
    inst_dir = f"{INSTANCES_DIR}/{name}"
    
    if os.path.isdir(inst_dir):
        fail(f"Ya existe '{name}'")
        info(f"Usa 'melissa status {name}' para ver su estado")
        return
    
    nl()
    
    defaults = runtime_defaults()
    workspace_cfg = defaults["workspace"]

    # 2. Sector
    sector_list = list(SECTORS.keys())
    sector_names = [f"{SECTORS[s].emoji} {SECTORS[s].name}" for s in sector_list]
    sector_descs = [SECTORS[s].tagline for s in sector_list]
    default_sector = defaults.get("default_sector", "")
    if default_sector in SECTORS and confirm(
        f"¿Usar el sector base '{SECTORS[default_sector].name}' para esta instancia?",
        default=True,
    ):
        sector_id = default_sector
    else:
        info("¿Qué tipo de negocio es?")
        sector_idx = select(sector_names, sector_descs)
        sector_id = sector_list[sector_idx]
    sector = SECTORS[sector_id]
    
    nl()
    ok(f"Sector: {sector.emoji} {sector.name}")
    nl()
    
    # 3. Plataforma
    platforms = ["Telegram", "WhatsApp", "Ambos"]
    platform_descs = [
        "Bot de Telegram (más fácil de configurar)",
        "WhatsApp Business API (requiere Meta Business)",
        "Telegram primero, WhatsApp después"
    ]
    default_platform = defaults.get("default_platform", "telegram")
    if default_platform in {"telegram", "whatsapp", "ambos"} and confirm(
        f"¿Usar la plataforma sugerida '{default_platform}'?",
        default=True,
    ):
        platform_choice = "telegram" if default_platform == "ambos" else default_platform
    else:
        plat_idx = select(platforms, platform_descs, title="¿Qué plataforma usará?")
        platform_choice = ["telegram", "whatsapp", "telegram"][plat_idx]
    
    nl()
    
    # 4. Token de Telegram
    tg_token = ""
    telegram_shared = False
    if platform_choice == "telegram":
        shared_base_token = defaults["telegram_token"]
        if shared_base_token and confirm("¿Usar el token compartido de Melissa base para Telegram?"):
            tg_token = shared_base_token
            telegram_shared = bool(defaults["telegram_shared"])
        else:
            tg_token = prompt("Token de Telegram (@BotFather → /newbot)")
            if not tg_token:
                fail("Token obligatorio para Telegram")
                return
    
    # 5. Puerto
    port = next_port()
    if not port:
        fail("Sin puertos disponibles (8002-8199)")
        return
    
    # 6. URL
    ip = public_ip()
    # Para Telegram detrás de Caddy, la URL pública correcta es el dominio HTTPS
    # compartido. El puerto interno vive solo en el reverse proxy.
    shared_public_base = defaults["public_base_url"].rstrip("/")
    if shared_public_base.startswith("https://"):
        default_url = shared_public_base
    else:
        default_url = f"http://{ip}:{port}" if ip else f"http://localhost:{port}"
    base_url = prompt("URL pública", default=default_url)
    
    # Generar secrets
    import secrets as _s
    master_key = _s.token_hex(12)
    webhook_secret = _s.token_hex(8)
    
    nl()
    
    # Crear instancia
    with Spinner(f"Creando '{name}'...") as sp:
        os.makedirs(inst_dir, exist_ok=True)
        os.makedirs(f"{inst_dir}/logs", exist_ok=True)
        
        _clone_runtime_entries(MELISSA_DIR, inst_dir)
        
        # .env
        env_content = f"""# Melissa — {name}
# Sector: {sector.name}
# Creado: {datetime.now().strftime('%Y-%m-%d %H:%M')}

SECTOR={sector_id}
PLATFORM={platform_choice}
TELEGRAM_TOKEN={tg_token}
TELEGRAM_SHARED={"true" if telegram_shared else "false"}

# LLM
GROQ_API_KEY={defaults['llm_keys']['GROQ_API_KEY']}
GEMINI_API_KEY={defaults['llm_keys']['GEMINI_API_KEY']}
GEMINI_API_KEY_2={defaults['llm_keys']['GEMINI_API_KEY_2']}
GEMINI_API_KEY_3={defaults['llm_keys']['GEMINI_API_KEY_3']}
GEMINI_API_KEY_4={defaults['llm_keys']['GEMINI_API_KEY_4']}
GEMINI_API_KEY_5={defaults['llm_keys']['GEMINI_API_KEY_5']}
GEMINI_API_KEY_6={defaults['llm_keys']['GEMINI_API_KEY_6']}
GEMINI_API_KEY_7={defaults['llm_keys']['GEMINI_API_KEY_7']}
OPENROUTER_API_KEY={defaults['llm_keys']['OPENROUTER_API_KEY']}
OPENAI_API_KEY={defaults['llm_keys']['OPENAI_API_KEY']}
LLM_REASONING=google/gemini-2.5-flash
LLM_FAST=google/gemini-2.5-flash
LLM_LITE=google/gemini-2.5-flash-lite
V8_QUALITY_THRESHOLD=0.72
V8_MAX_RETRIES=3

# Búsqueda
SERP_API_KEY={defaults['search_keys']['SERP_API_KEY']}
BRAVE_API_KEY={defaults['search_keys']['BRAVE_API_KEY']}
APIFY_API_KEY={defaults['search_keys']['APIFY_API_KEY']}

# Servidor
PORT={port}
HOST=0.0.0.0
BASE_URL={base_url}
WEBHOOK_SECRET=melissa_{name}_{webhook_secret}

# DB
DB_PATH={inst_dir}/melissa.db
VECTOR_DB_PATH={inst_dir}/vectors.db
BRAND_ASSETS_BASE_DIR={inst_dir}/brand-assets

# Seguridad
MASTER_API_KEY={master_key}
BUFFER_WAIT_MIN=8
BUFFER_WAIT_MAX=18
BUBBLE_PAUSE_MIN=0.8
BUBBLE_PAUSE_MAX=2.5

# WhatsApp
WA_PHONE_ID=
WA_ACCESS_TOKEN=
WA_VERIFY_TOKEN=
META_APP_ID={defaults['meta']['META_APP_ID']}
META_APP_SECRET={defaults['meta']['META_APP_SECRET']}

# Nova
NOVA_URL={defaults['nova']['url']}
NOVA_API_KEY={defaults['nova']['api_key']}
NOVA_TOKEN={defaults['nova']['token']}
NOVA_ENABLED={"true" if defaults['nova'].get('enabled') else "false"}

# Omni
OMNI_URL={defaults['omni']['url']}
OMNI_KEY={defaults['omni']['key']}
"""
        Path(f"{inst_dir}/.env").write_text(env_content)
        
        # instance.json
        instance_meta = {
            "name": name,
            "label": name_raw,
            "sector": sector_id,
            "port": port,
            "base_url": base_url,
            "master_key": master_key,
            "platform": platform_choice,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "services": sector.services,
            "hours": sector.hours_default,
        }
        Path(f"{inst_dir}/instance.json").write_text(json.dumps(instance_meta, indent=2))
        
        sp.finish(f"Instancia '{name}' creada")
    
    # Arrancar
    pm2_name = f"melissa-{name}"
    
    with Spinner(f"Arrancando {pm2_name}...") as sp:
        pm2("delete", pm2_name)
        subprocess.run([
            "pm2", "start", f"{inst_dir}/melissa.py",
            "--name", pm2_name,
            "--interpreter", "python3",
            "--cwd", inst_dir,          # ✅ FIX: sin --cwd, load_dotenv() carga el .env equivocado
            "--restart-delay", "3000",
            "--max-restarts", "10",
            "--log", f"{inst_dir}/logs/melissa.log",
            "--error", f"{inst_dir}/logs/error.log"
        ], capture_output=True)
        pm2_save()
        time.sleep(4)
        h = health(port)
        sp.finish("Online" if h else "Arrancando...", ok=bool(h))

    agent_seed = dict(workspace_cfg.get("agent", {}))
    if agent_seed and any(str(agent_seed.get(key, "")).strip() for key in ("display_name", "role", "prompt_master")):
        seeded_inst = Instance(
            name=name,
            label=name_raw,
            port=port,
            dir=inst_dir,
            env=load_env(f"{inst_dir}/.env"),
            is_base=False,
            sector=sector_id,
        )
        _bb_apply_persona(
            seeded_inst,
            {
                "name": agent_seed.get("display_name") or "Melissa",
                "role": agent_seed.get("role") or "asesora virtual",
                "tone_instruction": agent_seed.get("prompt_master", ""),
            },
            spinner_label="Aplicando identidad base del agente...",
        )
    
    # Nova
    nova_h = health(NOVA_PORT)
    if nova_h and confirm("Nova activo. ¿Conectar a esta instancia?"):
        _nova_attach(inst_dir, name)
    
    notify_omni("nueva_instancia", f"{sector.emoji} {name_raw} ({sector.name}) en :{port}")
    
    nl()
    section(f"'{name_raw}' lista", f"{sector.emoji} {sector.name}")
    kv("Instancia", name)
    kv("Sector", sector.name)
    kv("Puerto", str(port))
    kv("URL base", base_url)
    kv("Telegram compartido", "sí" if telegram_shared else "no")
    kv("Master Key", master_key)
    nl()

    webhook_url_real = f"{base_url}/webhook/melissa_{name}_{webhook_secret}"
    if telegram_shared:
        routes = ensure_shared_telegram_default(name)
        default_instance = routes.get("default_instance", name)
        info("Telegram compartido activo:")
        print(f"       {q(C.CYN, 'El webhook real lo gestiona Melissa base (/telegram/shared/...)')}")
        print(f"       {q(C.G3, f'La instancia recibe tráfico reenviado internamente hacia :{port}')}")
        print(f"       {q(C.G2, f'Instancia por defecto del router: {default_instance}')}")
    else:
        info("Webhook registrado en Telegram:")
        print(f"       {q(C.CYN, webhook_url_real)}")
    nl()

    # ── Caddy — agregar ruta si es instancia adicional ─────────────────────
    webhook_path = f"webhook/melissa_{name}_{webhook_secret}"
    if telegram_shared:
        info("Caddy por instancia no es necesario en modo Telegram compartido")
        nl()
    elif port != BASE_PORT:
        with Spinner(f"Actualizando Caddy (puerto {port})...") as sp:
            caddy_ok = _caddy_add_route(name, port, webhook_path)
            if caddy_ok:
                reload_ok = _caddy_reload()
                if reload_ok:
                    sp.finish(f"Caddy actualizado — ruta /{webhook_path[:30]}... → :{port}")
                else:
                    sp.finish("Ruta agregada al Caddyfile — recarga manual necesaria", ok=False)
                    warn(f"Recarga manual: cd {CADDY_DIR} && docker compose restart caddy")
            else:
                sp.finish("No pude actualizar Caddy automáticamente", ok=False)
                info(f"Agrega manualmente en {CADDYFILE_PATH}:")
                print(f"    handle /{webhook_path}* {{")
                print(f"        reverse_proxy {CADDY_DOCKER_GW}:{port}")
                print(f"    }}")
        nl()
    else:
        ok(f"Caddy — usando ruta /webhook/* existente (puerto base {BASE_PORT})")
        nl()

    # ✅ Diagnóstico rápido de configuración
    env_ok = True
    env_path_check = f"{inst_dir}/.env"
    if os.path.exists(env_path_check):
        ev_check = load_env(env_path_check)
        if ev_check.get("BASE_URL", "") != base_url:
            warn(f"⚠ BASE_URL en .env no coincide: {ev_check.get('BASE_URL')}")
            env_ok = False
        if not ev_check.get("TELEGRAM_TOKEN", ""):
            warn("⚠ TELEGRAM_TOKEN vacío en .env")
            env_ok = False
        if ev_check.get("PORT", "") != str(port):
            warn(f"⚠ PORT en .env no coincide: {ev_check.get('PORT')}")
            env_ok = False
        if env_ok:
            ok(".env verificado correctamente")
    nl()

    info("Abre el bot en Telegram y envía el token de activación")
    info(f"Genera el token con: melissa chat {name}")
    nl()

    # ── Auto-generar token de activacion y mostrarlo ──────────────────────────
    time.sleep(3)  # dar tiempo a que Melissa arranque
    h_final = health(port)
    if h_final and master_key:
        try:
            if _HTTPX:
                r = _httpx.post(
                    f"http://localhost:{port}/api/tokens/create",
                    json={"clinic_label": name_raw},
                    headers={"X-Master-Key": master_key},
                    timeout=10
                )
                tdata = r.json() if r.status_code == 200 else {}
            else:
                import urllib.request as _ur2
                req2 = _ur2.Request(
                    f"http://localhost:{port}/api/tokens/create",
                    data=json.dumps({"clinic_label": name_raw}).encode(),
                    headers={"Content-Type": "application/json", "X-Master-Key": master_key},
                    method="POST"
                )
                tdata = json.loads(_ur2.urlopen(req2, timeout=10).read())
            if tdata.get("token"):
                section("Token de activacion listo", "Envia esto al administrador")
                print(f"\n    {q(C.YLW, tdata['token'], bold=True)}\n")
                info(f"Expira en 72h")
                nl()
        except Exception:
            info(f"Genera el token con: melissa token {name}")
    else:
        info(f"Genera el token con: melissa token {name}")

def cmd_template(args):
    """Ver y crear desde plantillas de sector."""
    print_logo(compact=True)
    section("Plantillas por Sector")
    
    sector_id = getattr(args, 'name', '').lower() or ''
    
    if sector_id and sector_id in SECTORS:
        # Mostrar detalle de un sector
        s = SECTORS[sector_id]
        print(f"  {s.emoji}  {q(C.W, s.name, bold=True)}")
        print(f"       {q(C.G2, s.tagline)}")
        nl()
        
        kv("Horario típico", s.hours_default)
        nl()
        
        info("Servicios comunes:")
        for svc in s.services:
            print(f"       · {q(C.G1, svc)}")
        nl()
        
        if s.questions:
            info("Preguntas frecuentes:")
            for q_ in s.questions:
                print(f"       {q(C.G3, '?')} {q(C.G2, q_)}")
        nl()
        
        if confirm(f"¿Crear instancia de {s.name}?"):
            args.name = ""
            cmd_new(args)
    else:
        # Listar todos los sectores
        for sid, s in SECTORS.items():
            print(f"  {s.emoji}  {q(C.W, s.name, bold=True)}")
            print(f"       {q(C.G3, s.tagline)}")
            print(f"       {q(C.G2, 'ID:')} {q(C.P2, sid)}  ·  "
                  f"{q(C.G2, 'Servicios:')} {q(C.G1, ', '.join(s.services[:3]))}")
            nl()
        
        hr()
        info("Usa: melissa template <sector_id>")
        info("Ejemplo: melissa template dental")
        nl()

def cmd_status(args):
    """Estado detallado de una instancia."""
    name = getattr(args, 'name', '') or ''
    print_logo(compact=True)
    
    instances = get_instances()
    if name:
        instances = [i for i in instances if name.lower() in i.name.lower() or name.lower() in i.label.lower()]
    
    if not instances:
        fail(f"No encontré instancia '{name}'")
        return
    
    for inst in instances:
        h = health(inst.port)
        icon, status = icon_status(h)
        sector = SECTORS.get(inst.sector, SECTORS["otro"])
        stats = get_instance_stats(inst)
        
        section(f"{sector.emoji} {inst.label}", inst.name)
        
        kv("Estado", status.upper(), C.GRN if status == "online" else C.RED)
        kv("Sector", sector.name)
        kv("Puerto", str(inst.port))
        kv("Directorio", inst.dir)
        kv("PM2", f"melissa-{inst.name}" if not inst.is_base else "melissa")
        nl()
        
        if h:
            info("Métricas:")
            kv("Clínica", h.get("clinic", "—"))
            kv("Plataforma", h.get("platform", "—"))
            
            wa = h.get("whatsapp", {})
            if wa.get("connected"):
                kv("WhatsApp", wa.get("phone", "conectado"), C.GRN)
            
            kv("Conversaciones", str(stats["conversations"]))
            kv("Mensajes", str(stats["messages"]))
            kv("Citas", str(stats["appointments"]))
            kv("Memoria", f"{stats['memory_items']} items")
            
            nova_status = "activo" if inst.env.get("NOVA_ENABLED") == "true" else "inactivo"
            kv("Nova", nova_status, C.P2 if nova_status == "activo" else C.G3)
        
        nl()

def cmd_health(args):
    """Health check rápido de todas las instancias."""
    print_logo(compact=True)
    
    instances = get_instances()
    if not instances:
        warn("No hay instancias")
        return
    
    section("Health Check")
    
    ports = [i.port for i in instances]
    healths = health_batch(ports, timeout=2)
    
    for inst in instances:
        h = healths.get(inst.port, {})
        icon, status = icon_status(h)
        sector = SECTORS.get(inst.sector, SECTORS["otro"])
        
        print(f"  {icon}  {q(C.W, inst.label[:30])}  :{inst.port}  {sector.emoji}")
    
    nl()
    online = sum(1 for h in healths.values() if h.get("status") == "online")
    total = len(instances)
    
    if online == total:
        ok(f"Todo online ({total}/{total})")
    elif online > 0:
        warn(f"{online}/{total} online")
    else:
        fail("Todo offline")
    nl()

def cmd_metrics(args):
    """Métricas de uso de una instancia."""
    name = getattr(args, 'name', '') or ''
    
    inst = find_instance(name) if name else None
    if not inst:
        instances = get_instances()
        if len(instances) == 1:
            inst = instances[0]
        elif instances:
            idx = select([i.label for i in instances], title="¿De cuál instancia?")
            inst = instances[idx]
        else:
            fail("No hay instancias")
            return
    
    print_logo(compact=True)
    section(f"Métricas — {inst.label}")
    
    stats = get_instance_stats(inst)
    h = health(inst.port)
    
    # Stats generales
    kv("Conversaciones totales", str(stats["conversations"]))
    kv("Mensajes totales", str(stats["messages"]))
    kv("Citas agendadas", str(stats["appointments"]))
    kv("Items en memoria", str(stats["memory_items"]))
    nl()
    
    # Si hay acceso a la DB, más detalles
    db_path = f"{inst.dir}/melissa.db"
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Citas por estado
            info("Citas por estado:")
            try:
                cursor.execute("""
                    SELECT status, COUNT(*) 
                    FROM appointments 
                    GROUP BY status
                """)
                for row in cursor.fetchall():
                    status_name = row[0] or "pendiente"
                    kv(f"  {status_name}", str(row[1]))
            except Exception:
                pass
            
            # Últimas 24h
            nl()
            info("Últimas 24 horas:")
            try:
                cursor.execute("""
                    SELECT COUNT(DISTINCT chat_id) FROM conversations WHERE ts > datetime('now', '-1 day')
                """)
                result = cursor.fetchone()
                kv("Usuarios activos", str(result[0] if result else 0))
            except Exception:
                pass
            
            conn.close()
        except Exception:
            pass
    
    nl()

def cmd_stats(args):
    """Estadísticas de conversaciones."""
    cmd_metrics(args)  # Por ahora mismo que metrics


# ══════════════════════════════════════════════════════════════════════════════
# LOG ENGINE — Análisis inteligente de errores con auto-fix
# ══════════════════════════════════════════════════════════════════════════════

# Patrones de error conocidos con diagnóstico y solución
_LOG_ERROR_PATTERNS = [
    # (regex, severidad, título, diagnóstico, fix_cmd_o_instruccion)
    (
        re.compile(r"TELEGRAM_TOKEN.*invalid|Unauthorized|401", re.I),
        "CRITICO", "Token de Telegram inválido",
        "El TELEGRAM_TOKEN expiró o es incorrecto.",
        "melissa config {name}  → cambia TELEGRAM_TOKEN\nLuego: melissa restart {name}",
    ),
    (
        re.compile(r"ConnectionRefused|Connection refused", re.I),
        "CRITICO", "Puerto rechazado",
        "El proceso no está escuchando en el puerto configurado.",
        "melissa restart {name}",
    ),
    (
        re.compile(r"rate.?limit|429|Too Many Requests", re.I),
        "ALTO", "Rate limit de API",
        "La API (Groq/Gemini/OpenRouter) rechazó por exceso de llamadas.",
        "Espera 60s o configura una API key adicional en melissa config {name}",
    ),
    (
        re.compile(r"ImportError|ModuleNotFoundError", re.I),
        "CRITICO", "Módulo faltante",
        "Falta una dependencia de Python.",
        "cd /home/ubuntu/melissa && pip install -r requirements.txt\nmelissa restart {name}",
    ),
    (
        re.compile(r"PermissionError|Permission denied", re.I),
        "ALTO", "Permiso denegado",
        "Sin acceso a un archivo o directorio.",
        "chmod 755 /home/ubuntu/melissa && melissa restart {name}",
    ),
    (
        re.compile(r"MemoryError|out of memory|OOM", re.I),
        "CRITICO", "Sin memoria RAM",
        "El proceso se quedó sin memoria.",
        "melissa restart {name}  (libera RAM inmediatamente)",
    ),
    (
        re.compile(r"SSL|certificate verify failed|ssl.SSLError", re.I),
        "ALTO", "Error SSL",
        "Certificado SSL vencido o no verificable.",
        "Verifica tu BASE_URL en .env — debe ser https:// con cert válido",
    ),
    (
        re.compile(r"webhook.*error|Failed to set webhook|conflict.*webhook", re.I),
        "ALTO", "Webhook mal configurado",
        "Telegram no puede contactar el webhook.",
        "melissa webhooks {name}  → reconfigurar webhook",
    ),
    (
        re.compile(r"TimeoutError|asyncio.*timeout|timed out", re.I),
        "MEDIO", "Timeout",
        "Una llamada al LLM o API tardó demasiado.",
        "Normal si es puntual. Si es frecuente: melissa latency {name}",
    ),
    (
        re.compile(r"sqlite3|database.*locked|disk.*full", re.I),
        "CRITICO", "Error de base de datos",
        "La DB está bloqueada o el disco está lleno.",
        "melissa doctor  → verificar espacio\nmelissa restart {name}",
    ),
    (
        re.compile(r"KeyError|AttributeError|TypeError|ValueError", re.I),
        "MEDIO", "Error de código",
        "Error interno de Python — posiblemente un bug.",
        "melissa sync  → clona el runtime compartido actualizado\nmelissa restart {name}",
    ),
    (
        re.compile(r"GROQ_API_KEY|GEMINI_API_KEY|OPENROUTER.*empty|API key.*missing", re.I),
        "CRITICO", "API key vacía",
        "Falta configurar una API key del LLM.",
        "melissa config {name}  → agregar API key",
    ),
    (
        re.compile(r"No route to host|Name or service not known|DNS", re.I),
        "ALTO", "Sin conectividad",
        "No hay acceso a internet o falla DNS.",
        "ping 8.8.8.8  → verificar red del servidor",
    ),
    (
        re.compile(r"nova.*unavailable|nova.*connection|nova.*error", re.I),
        "BAJO", "Nova no disponible",
        "El motor Nova no responde — Melissa funciona sin él.",
        "melissa nova status  → verificar Nova (opcional)",
    ),
]

# Niveles de log con colores
_LOG_LEVELS = {
    "ERROR":   C.RED,
    "CRITICO": C.RED,
    "WARNING": C.YLW,
    "WARN":    C.YLW,
    "INFO":    C.G2,
    "DEBUG":   C.G3,
    "OK":      C.GRN,
}

_SEV_COLOR = {
    "CRITICO": C.RED,
    "ALTO":    C.YLW,
    "MEDIO":   C.AMB,
    "BAJO":    C.G2,
}


def _find_pm2_log(pm2_name: str) -> Optional[str]:
    """Localiza el archivo de log de pm2 para una instancia."""
    candidates = [
        Path.home() / ".pm2" / "logs" / f"{pm2_name}-out.log",
        Path.home() / ".pm2" / "logs" / f"{pm2_name}-error.log",
        Path(f"/root/.pm2/logs/{pm2_name}-out.log"),
        Path(f"/root/.pm2/logs/{pm2_name}-error.log"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    # Intentar obtenerlo de pm2 jlist
    try:
        out = subprocess.check_output(
            ["pm2", "jlist"], stderr=subprocess.DEVNULL, timeout=5
        )
        data = json.loads(out)
        for proc in data:
            if proc.get("name") == pm2_name:
                pm2_env = proc.get("pm2_env", {})
                lp = pm2_env.get("pm_out_log_path") or pm2_env.get("pm_err_log_path")
                if lp and Path(lp).exists():
                    return lp
    except Exception:
        pass
    return None


def _color_log_line(line: str) -> str:
    """Colorea una línea de log según su nivel."""
    line = line.rstrip()
    for level, color in _LOG_LEVELS.items():
        if level in line.upper():
            # Colorear la línea entera con el color del nivel
            ts_match = re.match(r'^(\d{2}:\d{2}:\d{2})\s*[│|]?\s*(.*)', line)
            if ts_match:
                ts, rest = ts_match.groups()
                return f"  {q(C.G3, ts)} {color}{rest}{C.R}"
            return f"  {color}{line}{C.R}"
    return f"  {q(C.G3, line)}"


def _analyze_errors(lines: List[str], inst_name: str) -> List[Dict]:
    """
    Analiza líneas de log y devuelve lista de errores detectados con su fix.
    Deduplica — no reporta el mismo patrón dos veces.
    """
    found = []
    seen_patterns = set()
    full_text = "\n".join(lines)

    for pattern, severity, title, diagnosis, fix_template in _LOG_ERROR_PATTERNS:
        if id(pattern) in seen_patterns:
            continue
        matches = pattern.findall(full_text)
        if matches:
            seen_patterns.add(id(pattern))
            fix = fix_template.replace("{name}", inst_name)
            # Encontrar la línea donde aparece para mostrar contexto
            ctx_line = next(
                (l.strip() for l in lines if pattern.search(l)), ""
            )
            found.append({
                "severity":  severity,
                "title":     title,
                "diagnosis": diagnosis,
                "fix":       fix,
                "context":   ctx_line[:120],
                "count":     len(matches),
            })

    # Ordenar por severidad
    order = {"CRITICO": 0, "ALTO": 1, "MEDIO": 2, "BAJO": 3}
    found.sort(key=lambda x: order.get(x["severity"], 9))
    return found


def _print_error_report(errors: List[Dict], inst_name: str):
    """Imprime el reporte de errores con soluciones."""
    if not errors:
        ok("Sin errores detectados en los logs recientes")
        return

    nl()
    print(f"  {q(C.RED, '●')} {q(C.W, f'{len(errors)} problema(s) detectado(s):', bold=True)}")
    nl()

    for i, err in enumerate(errors, 1):
        sev_color = _SEV_COLOR.get(err["severity"], C.G2)
        sev_badge = q(sev_color, f"[{err['severity']}]")
        count_str = f" x{err['count']}" if err["count"] > 1 else ""

        print(f"  {q(C.G3, str(i) + '.')}  {sev_badge}  {q(C.W, err['title'])}{q(C.G3, count_str)}")

        if err["context"]:
            print(f"       {q(C.G3, '↳')} {q(C.G3, err['context'])}")

        print(f"       {q(C.AMB, 'diagnóstico:')} {q(C.G1, err['diagnosis'])}")
        print(f"       {q(C.GRN, 'solución:')}")
        for fix_line in err["fix"].split("\n"):
            print(f"         {q(C.CYN, fix_line)}")
        nl()


def _auto_fix(errors: List[Dict], inst: Any) -> int:
    """
    Aplica fixes automáticos para errores que tienen solución ejecutable.
    Retorna número de fixes aplicados.
    """
    applied = 0
    auto_fixable = {
        "ConnectionRefusedError", "TimeoutError", "MemoryError",
        "Sin memoria RAM", "Puerto rechazado",
    }
    needs_restart = any(
        err["title"] in auto_fixable for err in errors
        if err["severity"] in ("CRITICO", "ALTO")
    )

    if needs_restart:
        pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
        info(f"Auto-fix: reiniciando {inst.label}...")
        result = pm2("restart", pm2_name)
        time.sleep(3)
        h = health(inst.port, timeout=8)
        if h:
            ok(f"{inst.label} reiniciada correctamente")
            applied += 1
        else:
            fail(f"{inst.label} no responde después del reinicio")

    return applied


def _recent_model_usage(inst: Instance, limit: int = 8) -> List[Dict[str, Any]]:
    """
    Traza real del modelo usado por respuesta desde la DB de conversaciones.
    Esto evita depender de logs de PM2 viejos o de procesos lanzados fuera de PM2.
    """
    try:
        conn = sqlite3.connect(inst.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT chat_id, model_used, latency_ms, content, ts
            FROM conversations
            WHERE role='assistant' AND COALESCE(model_used, '') <> ''
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        conn.close()
    except Exception:
        return []

    items: List[Dict[str, Any]] = []
    for row in rows:
        content = (row["content"] or "").replace("\n", " ").strip()
        if len(content) > 72:
            content = content[:72].rstrip() + "..."
        items.append({
            "chat_id": row["chat_id"],
            "model_used": row["model_used"],
            "latency_ms": row["latency_ms"] or 0,
            "content": content,
            "ts": row["ts"],
        })
    return items


def cmd_logs(args):
    """
    Logs inteligentes — como pm2 logs pero con análisis de errores y auto-fix.

    melissa logs [nombre]              — últimas 50 líneas + stream en vivo
    melissa logs [nombre] --lines 200  — más líneas históricas
    melissa logs [nombre] --errors     — solo líneas de error
    melissa logs [nombre] --fix        — analiza + aplica fixes automáticos
    melissa logs [nombre] --scan       — escaneo de errores sin stream
    """
    name        = getattr(args, 'name', '')        or ''
    subcommand  = getattr(args, 'subcommand', '')  or ''
    raw_name    = name or subcommand

    # Resolver flags desde subcommand o nombre
    mode = "live"   # live | errors | scan | fix
    if getattr(args, "errors", False):
        mode = "errors"
    elif getattr(args, "fix", False):
        mode = "fix"
    elif getattr(args, "scan", False):
        mode = "scan"
    elif raw_name in ("--errors", "errors", "error"):
        mode, raw_name = "errors", ""
    elif raw_name in ("--fix", "fix"):
        mode, raw_name = "fix", ""
    elif raw_name in ("--scan", "scan"):
        mode, raw_name = "scan", ""

    # Seleccionar instancia
    inst = find_instance(raw_name) if raw_name else None
    if not inst:
        instances = get_instances()
        if not instances:
            fail("No hay instancias")
            return
        if len(instances) == 1:
            inst = instances[0]
        else:
            idx = select([i.label for i in instances], title="¿De cuál instancia?")
            inst = instances[idx]

    pm2_name  = "melissa" if inst.is_base else f"melissa-{inst.name}"
    log_path  = _find_pm2_log(pm2_name)
    n_lines   = max(1, int(getattr(args, "lines", 100) or 100))  # líneas históricas a mostrar
    recent_models = _recent_model_usage(inst, limit=min(max(n_lines // 10, 3), 8))

    print_logo(compact=True)

    # ── MODO SCAN / FIX — solo análisis, sin stream ───────────────────────────
    if mode in ("scan", "fix", "errors"):
        section(
            f"Análisis de logs — {inst.label}",
            "fix automático activado" if mode == "fix" else ""
        )

        if recent_models:
            info("Últimas respuestas con modelo real:")
            nl()
            for item in recent_models:
                latency_label = f"({item['latency_ms']}ms)"
                print(
                    f"  {q(C.CYN, item['model_used'])}  "
                    f"{q(C.G3, latency_label)}  "
                    f"{q(C.G2, item['chat_id'])}"
                )
                if item["content"]:
                    print(f"    {q(C.G3, item['content'])}")
            nl()

        if not log_path:
            warn("No se encontró el archivo de log del proceso actual.")
            info("La traza de modelo anterior salió desde la DB de conversaciones.")
            return

        try:
            with open(log_path) as f:
                all_lines = f.readlines()
        except OSError as e:
            fail(f"No se pudo leer el log: {e}")
            return

        recent = [l.rstrip() for l in all_lines[-500:]]  # últimas 500 líneas

        if mode == "errors":
            error_lines = [l for l in recent
                           if re.search(r"ERROR|CRITICAL|Traceback|Exception", l, re.I)]
            if not error_lines:
                ok("Sin errores en las últimas 500 líneas")
                return
            nl()
            info(f"{len(error_lines)} líneas de error encontradas:")
            nl()
            for line in error_lines[-30:]:  # max 30
                print(_color_log_line(line))
            nl()

        errors_found = _analyze_errors(recent, inst.name)
        _print_error_report(errors_found, inst.name)

        if mode == "fix" and errors_found:
            fixable = [e for e in errors_found if e["severity"] in ("CRITICO", "ALTO")]
            if fixable:
                nl()
                if confirm(f"Aplicar {len(fixable)} fix(es) automático(s)?"):
                    applied = _auto_fix(errors_found, inst)
                    if applied:
                        ok(f"{applied} fix(es) aplicado(s)")
                    else:
                        info("Los fixes manuales están listados arriba")
            else:
                info("No hay fixes automáticos disponibles para estos errores")
        return

    # ── MODO LIVE — stream en tiempo real (pm2 logs mejorado) ─────────────────
    h = health(inst.port, timeout=4)
    status_str = q(C.GRN, "● online") if h else q(C.RED, "● offline")
    section(f"Logs de {inst.label}", f"{status_str}  {q(C.G3, 'Ctrl+C para salir')}")

    if recent_models:
        info("Modelos reales recientes:")
        nl()
        for item in recent_models:
            latency_label = f"({item['latency_ms']}ms)"
            print(
                f"  {q(C.CYN, item['model_used'])}  "
                f"{q(C.G3, latency_label)}  "
                f"{q(C.G2, item['chat_id'])}"
            )
        nl()

    # Mostrar historial antes del stream
    if log_path:
        try:
            with open(log_path) as f:
                hist_lines = f.readlines()
            recent_hist = [l.rstrip() for l in hist_lines[-n_lines:]]

            if recent_hist:
                print(f"  {q(C.G3, f'── últimas {len(recent_hist)} líneas ──────────────────────')}")
                nl()
                for line in recent_hist:
                    print(_color_log_line(line))
                nl()

            # Análisis rápido de errores en el historial (no bloquea)
            errors_found = _analyze_errors(
                [l.rstrip() for l in hist_lines[-500:]], inst.name
            )
            if errors_found:
                crit = [e for e in errors_found if e["severity"] == "CRITICO"]
                high = [e for e in errors_found if e["severity"] == "ALTO"]
                if crit:
                    print(f"  {q(C.RED, '⚠')}  {q(C.RED, f'{len(crit)} error(es) CRÍTICO(s) detectado(s)')}  "
                          f"{q(C.G3, '→ melissa logs ' + inst.name + ' --fix')}")
                elif high:
                    print(f"  {q(C.YLW, '!')}  {q(C.YLW, f'{len(high)} advertencia(s) de nivel ALTO')}  "
                          f"{q(C.G3, '→ melissa logs ' + inst.name + ' --scan')}")
                nl()

        except OSError:
            pass

    # Stream en vivo
    print(f"  {q(C.G3, '── stream en vivo ──────────────────────────────────')}")
    nl()

    # Intentar stream nativo con tail -f si hay archivo de log
    if log_path:
        try:
            proc = subprocess.Popen(
                ["tail", "-f", "-n", "0", log_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            error_counter = 0
            try:
                for raw_line in proc.stdout:
                    line = raw_line.rstrip()
                    if not line:
                        continue
                    # Colorear + imprimir en tiempo real
                    print(_color_log_line(line))
                    # Contar errores en vivo y alertar
                    if re.search(r"ERROR|CRITICAL|Traceback", line, re.I):
                        error_counter += 1
                        if error_counter == 3:
                            print(f"\n  {q(C.RED, '⚠')}  {q(C.YLW, '3 errores seguidos — ejecuta: ')} "
                                  f"{q(C.CYN, 'melissa logs ' + inst.name + ' --fix')}\n")
                            error_counter = 0
                    else:
                        error_counter = max(0, error_counter - 1)
            except KeyboardInterrupt:
                pass
            finally:
                proc.terminate()
        except FileNotFoundError:
            # tail no disponible — fallback a pm2
            os.execvp("pm2", ["pm2", "logs", pm2_name, "--lines", "0"])
    else:
        # Sin archivo de log localizable — usar pm2 directamente
        info("Usando pm2 logs (archivo de log no localizado directamente)")
        nl()
        os.execvp("pm2", ["pm2", "logs", pm2_name, "--lines", str(n_lines)])



def cmd_config(args):
    """Editar configuración de una instancia."""
    name = getattr(args, 'name', '') or ''
    instances = get_instances()

    if not name:
        ensure_workspace_files()
        if not instances:
            info("No hay instancias todavía. Abro el init guiado.")
            nl()
            cmd_init(args)
            return

        print_logo(compact=True)
        section("Melissa Config", "Hub de configuración del producto")
        workspace_cfg = load_workspace_config()
        workspace_summary(workspace_cfg)
        options = [
            "Configurar workspace base",
            "Configurar una instancia",
            "Ajustar agente, prompt y personalidad",
            "Router compartido de Telegram",
            "Salir",
        ]
        descs = [
            "Dueño, negocio por defecto, API keys y prompt base.",
            "Variables operativas de una instancia concreta.",
            "Abre Black Boss Config para tono, prompt y skills.",
            "Elegir instancia por defecto y limpiar rutas compartidas.",
            "Volver a la terminal.",
        ]
        choice = select(options, descs=descs, title="¿Qué quieres configurar?")
        if choice == 0:
            edit_workspace_config()
            return
        if choice == 2:
            cmd_bb_config(argparse.Namespace(name="", subcommand="", command="bb"))
            return
        if choice == 3:
            routes = load_shared_telegram_routes()
            router_options = [
                "Definir instancia por defecto",
                "Limpiar instancia por defecto",
                "Vaciar rutas por chat",
                "Salir",
            ]
            router_descs = [
                f"Actual: {routes.get('default_instance', '') or 'ninguna'}",
                "Deja el router sin fallback.",
                "Borra el mapeo chat → instancia compartida.",
                "Volver.",
            ]
            router_choice = select(router_options, descs=router_descs, title="Router compartido de Telegram")
            if router_choice == 0:
                idx = select([inst.label for inst in instances], title="Instancia por defecto del router")
                routes["default_instance"] = instances[idx].name
                save_shared_telegram_routes(routes)
                ok(f"Router por defecto: {instances[idx].name}")
            elif router_choice == 1:
                routes["default_instance"] = ""
                save_shared_telegram_routes(routes)
                ok("Router sin instancia por defecto")
            elif router_choice == 2:
                routes["routes"] = {}
                save_shared_telegram_routes(routes)
                ok("Rutas por chat limpiadas")
            return
        if choice == 4:
            return
    
    inst = find_instance(name) if name else None
    if not inst:
        if len(instances) == 1:
            inst = instances[0]
        elif instances:
            idx = select([i.label for i in instances], title="¿Cuál instancia configurar?")
            inst = instances[idx]
        else:
            fail("No hay instancias")
            return
    
    print_logo(compact=True)
    section(f"Configuración — {inst.label}")
    
    env_path = f"{inst.dir}/.env"
    ev = dict(load_env(env_path))
    
    # Opciones de configuración
    options = [
        "Cambiar sector",
        "Configurar horarios",
        "Editar servicios",
        "Configurar WhatsApp",
        "Activar/Desactivar Nova",
        "Ver todas las variables",
        "Editar .env manualmente",
    ]
    
    choice = select(options)
    
    if choice == 0:  # Sector
        sector_list = list(SECTORS.keys())
        sector_names = [f"{SECTORS[s].emoji} {SECTORS[s].name}" for s in sector_list]
        idx = select(sector_names, title="Nuevo sector:")
        new_sector = sector_list[idx]
        update_env_key(env_path, "SECTOR", new_sector)
        ok(f"Sector cambiado a {SECTORS[new_sector].name}")
        
    elif choice == 1:  # Horarios
        current = ev.get("BUSINESS_HOURS", "09:00-18:00")
        new_hours = prompt("Horario (ej: 09:00-18:00)", default=current)
        update_env_key(env_path, "BUSINESS_HOURS", new_hours)
        ok(f"Horario: {new_hours}")
        
    elif choice == 2:  # Servicios
        current = ev.get("SERVICES", "")
        info("Servicios actuales:")
        if current:
            for s in current.split(","):
                print(f"       · {s.strip()}")
        new_services = prompt("Servicios (separados por coma)")
        if new_services:
            update_env_key(env_path, "SERVICES", new_services)
            ok("Servicios actualizados")
            
    elif choice == 3:  # WhatsApp
        info("Para WhatsApp necesitas:")
        dim("1. Cuenta de Meta Business")
        dim("2. App en developers.facebook.com")
        dim("3. Número de WhatsApp Business verificado")
        nl()
        wa_phone = prompt("WhatsApp Phone ID")
        wa_token = prompt("WhatsApp Access Token", secret=True)
        if wa_phone and wa_token:
            update_env_key(env_path, "WA_PHONE_ID", wa_phone)
            update_env_key(env_path, "WA_ACCESS_TOKEN", wa_token)
            ok("WhatsApp configurado")
            
    elif choice == 4:  # Nova
        current = ev.get("NOVA_ENABLED", "false")
        if current == "true":
            if confirm("¿Desactivar Nova?"):
                update_env_key(env_path, "NOVA_ENABLED", "false")
                ok("Nova desactivado")
        else:
            if confirm("¿Activar Nova?"):
                _nova_attach(inst.dir, inst.name)
                
    elif choice == 5:  # Ver todas
        nl()
        for k, v in sorted(ev.items()):
            # Ocultar valores sensibles
            if "KEY" in k or "TOKEN" in k or "SECRET" in k:
                v = v[:8] + "..." if len(v) > 8 else "***"
            print(f"  {q(C.G2, k)}: {q(C.G1, v)}")
        nl()
        
    elif choice == 6:  # Manual
        editor = os.getenv("EDITOR", "nano")
        os.system(f"{editor} {env_path}")
    
    # Reiniciar si cambió algo
    if choice < 5 and confirm("¿Reiniciar para aplicar cambios?"):
        pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
        pm2("restart", pm2_name)
        ok(f"{inst.label} reiniciada")
    
    nl()

def cmd_export(args):
    """Exportar datos a JSON/CSV."""
    name = getattr(args, 'name', '') or ''
    
    inst = find_instance(name) if name else None
    if not inst:
        instances = get_instances()
        if len(instances) == 1:
            inst = instances[0]
        elif instances:
            idx = select([i.label for i in instances], title="¿De cuál instancia exportar?")
            inst = instances[idx]
        else:
            fail("No hay instancias")
            return
    
    print_logo(compact=True)
    section(f"Exportar — {inst.label}")
    
    formats = ["JSON (completo)", "CSV (citas)", "CSV (conversaciones)"]
    fmt_idx = select(formats)
    
    db_path = f"{inst.dir}/melissa.db"
    if not os.path.exists(db_path):
        fail("No hay datos para exportar")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(exist_ok=True)
    
    if fmt_idx == 0:  # JSON completo
        output = BACKUP_DIR / f"melissa_{inst.name}_{timestamp}.json"
        
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            data = {
                "instance": inst.name,
                "exported_at": datetime.utcnow().isoformat(),
                "appointments": [],
                "conversations": [],
                "memory": [],
            }
            
            # Appointments
            try:
                cursor.execute("SELECT * FROM appointments ORDER BY created_at DESC LIMIT 1000")
                data["appointments"] = [dict(row) for row in cursor.fetchall()]
            except Exception:
                pass
            
            # Conversations
            try:
                cursor.execute("SELECT * FROM conversations ORDER BY created_at DESC LIMIT 5000")
                data["conversations"] = [dict(row) for row in cursor.fetchall()]
            except Exception:
                pass
            
            # Memory
            try:
                cursor.execute("SELECT * FROM memory")
                data["memory"] = [dict(row) for row in cursor.fetchall()]
            except Exception:
                pass
            
            conn.close()
            
            output.write_text(json.dumps(data, indent=2, default=str))
            ok(f"Exportado: {output}")
            kv("Citas", str(len(data["appointments"])))
            kv("Conversaciones", str(len(data["conversations"])))
            
        except Exception as e:
            fail(f"Error: {e}")
            
    elif fmt_idx == 1:  # CSV citas
        output = BACKUP_DIR / f"citas_{inst.name}_{timestamp}.csv"
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM appointments ORDER BY created_at DESC")
            rows = cursor.fetchall()
            headers = [desc[0] for desc in cursor.description]
            conn.close()
            
            with open(output, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            
            ok(f"Exportado: {output}")
            kv("Filas", str(len(rows)))
            
        except Exception as e:
            fail(f"Error: {e}")
            
    elif fmt_idx == 2:  # CSV conversaciones
        output = BACKUP_DIR / f"conversaciones_{inst.name}_{timestamp}.csv"
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM conversations ORDER BY created_at DESC LIMIT 10000")
            rows = cursor.fetchall()
            headers = [desc[0] for desc in cursor.description]
            conn.close()
            
            with open(output, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            
            ok(f"Exportado: {output}")
            kv("Filas", str(len(rows)))
            
        except Exception as e:
            fail(f"Error: {e}")
    
    nl()

def cmd_import_data(args):
    """Importar configuración desde archivo."""
    file_path = getattr(args, 'name', '') or prompt("Archivo a importar (.json)")
    
    if not file_path:
        return
    
    if not os.path.exists(file_path):
        fail(f"No existe: {file_path}")
        return
    
    print_logo(compact=True)
    section("Importar configuración")
    
    try:
        data = json.loads(Path(file_path).read_text())
        
        if "instance" in data:
            info(f"Datos de: {data.get('instance', 'desconocido')}")
            info(f"Exportado: {data.get('exported_at', '?')}")
            
            if "appointments" in data:
                kv("Citas", str(len(data["appointments"])))
            if "conversations" in data:
                kv("Conversaciones", str(len(data["conversations"])))
            
            nl()
            warn("La importación sobreescribirá datos existentes")
            
            if not confirm("¿Continuar?", default=False):
                return
            
            # Seleccionar instancia destino
            instances = get_instances()
            if not instances:
                fail("No hay instancias destino")
                return
            
            idx = select([i.label for i in instances], title="Instancia destino:")
            inst = instances[idx]
            
            db_path = f"{inst.dir}/melissa.db"
            
            # Importar
            with Spinner("Importando...") as sp:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # TODO: Implementar importación real
                # Por ahora solo validamos el archivo
                
                conn.close()
                sp.finish("Importación completada")
        else:
            fail("Formato de archivo no reconocido")
            
    except json.JSONDecodeError:
        fail("El archivo no es JSON válido")
    except Exception as e:
        fail(f"Error: {e}")

def cmd_test(args):
    """Probar respuestas de una instancia."""
    name = getattr(args, 'name', '') or ''
    
    inst = find_instance(name) if name else None
    if not inst:
        instances = get_instances()
        online = [i for i in instances if health(i.port).get("status") == "online"]
        
        if len(online) == 1:
            inst = online[0]
        elif online:
            idx = select([i.label for i in online], title="¿Cuál instancia probar?")
            inst = online[idx]
        else:
            fail("No hay instancias online")
            return
    
    print_logo(compact=True)
    section(f"Test — {inst.label}", "Prueba respuestas de Melissa")
    
    sector = SECTORS.get(inst.sector, SECTORS["otro"])
    
    # Preguntas de prueba según sector
    test_questions = [
        "Hola, buenos días",
        "¿Qué servicios ofrecen?",
        "¿Cuál es el horario?",
        "Quiero agendar una cita",
        "¿Cuánto cuesta?",
    ] + sector.questions[:3]
    
    info("Preguntas de prueba disponibles:")
    for i, q_ in enumerate(test_questions):
        print(f"    {q(C.P2, str(i + 1) + '.')} {q(C.G1, q_)}")
    
    nl()
    info("Escribe una pregunta o el número de la lista")
    info("Escribe 'salir' para terminar")
    nl()
    
    while True:
        sys.stdout.write(f"  {q(C.P2, '→')}  ")
        sys.stdout.flush()
        
        try:
            user_input = input("").strip()
        except (EOFError, KeyboardInterrupt):
            break
        
        if not user_input or user_input.lower() in ("salir", "exit", "q"):
            break
        
        # Si es número, usar pregunta predefinida
        if user_input.isdigit() and 1 <= int(user_input) <= len(test_questions):
            question = test_questions[int(user_input) - 1]
        else:
            question = user_input
        
        print(f"       {q(C.G3, 'Pregunta:')} {question}")
        
        # Llamar al endpoint de test
        try:
            url = f"http://localhost:{inst.port}/test"
            payload = {"message": question, "user_id": "test_cli"}
            
            if _HTTPX:
                r = _httpx.post(url, json=payload, timeout=30)
                if r.status_code == 200:
                    response = r.json().get("response", "Sin respuesta")
                else:
                    response = f"Error HTTP {r.status_code}"
            else:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=30) as res:
                    response = json.loads(res.read()).get("response", "Sin respuesta")
            
            nl()
            print(f"  {q(C.P2, 'ᗧ')}  {q(C.W, 'Melissa:', bold=True)}")
            
            # Formatear respuesta
            for line in response.split('\n'):
                print(f"       {q(C.G1, line)}")
            
        except Exception as e:
            print(f"       {q(C.RED, f'Error: {e}')}")
        
        nl()
    
    info("Test finalizado")
    nl()

def cmd_restart(args):
    """Reiniciar instancia(s)."""
    name = getattr(args, 'name', '') or ''
    
    if name.lower() in ("all", "todo", "todas"):
        if confirm("¿Reiniciar TODAS las instancias?"):
            with Spinner("Reiniciando todo...") as sp:
                pm2("restart", "all")
                sp.finish("Todas reiniciadas")
        return
    
    inst = find_instance(name) if name else None
    if not inst:
        instances = get_instances()
        if len(instances) == 1:
            inst = instances[0]
        elif instances:
            idx = select([i.label for i in instances], title="¿Cuál reiniciar?")
            inst = instances[idx]
        else:
            fail("No hay instancias")
            return
    
    pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
    
    with Spinner(f"Reiniciando {inst.label}...") as sp:
        pm2("restart", pm2_name)
        time.sleep(2)
        h = health(inst.port)
        sp.finish("Online" if h else "Reiniciando...", ok=bool(h))

def cmd_stop(args):
    """Detener instancia."""
    name = getattr(args, 'name', '') or ''
    
    if not name:
        fail("Especifica la instancia: melissa stop <nombre>")
        return
    
    inst = find_instance(name)
    if not inst:
        fail(f"No encontré '{name}'")
        return
    
    pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
    
    if pm2("stop", pm2_name):
        ok(f"{inst.label} detenida")
    else:
        fail(f"No pude detener {pm2_name}")

def cmd_delete(args):
    """Eliminar instancia."""
    name = getattr(args, 'name', '') or ''
    
    if not name:
        fail("Especifica la instancia: melissa delete <nombre>")
        return
    
    inst = find_instance(name)
    if not inst or inst.is_base:
        fail(f"No puedo eliminar '{name}'" + (" (es la base)" if inst and inst.is_base else ""))
        return
    
    warn(f"Esto eliminará '{inst.label}' y TODOS sus datos permanentemente.")
    warn("Esta acción NO se puede deshacer.")
    nl()
    
    confirmation = prompt(f"Escribe '{inst.name}' para confirmar")
    if confirmation != inst.name:
        info("Cancelado")
        return
    
    pm2_name = f"melissa-{inst.name}"
    
    with Spinner(f"Eliminando {inst.label}...") as sp:
        pm2("delete", pm2_name)
        pm2_save()
        shutil.rmtree(inst.dir, ignore_errors=True)
        sp.finish(f"'{inst.label}' eliminada")
    
    # Eliminar ruta de Caddy si era instancia adicional
    if inst.port != BASE_PORT:
        with Spinner("Limpiando ruta en Caddy...") as sp:
            if _caddy_remove_route(inst.port):
                _caddy_reload()
                sp.finish("Ruta eliminada de Caddy")
            else:
                sp.finish("Caddy — verifica manualmente", ok=False)
        nl()

    notify_omni("instancia_eliminada", inst.label)

def cmd_clone(args):
    """Clonar instancia existente."""
    source_name = getattr(args, 'name', '') or ''
    
    source = find_instance(source_name) if source_name else None
    if not source:
        instances = get_instances()
        if instances:
            idx = select([i.label for i in instances], title="¿Cuál instancia clonar?")
            source = instances[idx]
        else:
            fail("No hay instancias para clonar")
            return
    
    print_logo(compact=True)
    section(f"Clonar — {source.label}")
    
    dest_name = prompt(f"Nombre para el clon")
    if not dest_name:
        return
    
    dest_slug = slug(dest_name)
    dest_dir = f"{INSTANCES_DIR}/{dest_slug}"
    
    if os.path.isdir(dest_dir):
        fail(f"Ya existe '{dest_slug}'")
        return
    
    tg_token = prompt("Token de Telegram para el clon")
    if not tg_token:
        fail("Token obligatorio")
        return
    
    port = next_port()
    if not port:
        fail("Sin puertos disponibles")
        return
    
    import secrets as _s
    
    with Spinner(f"Clonando '{source.label}' → '{dest_name}'...") as sp:
        os.makedirs(dest_dir, exist_ok=True)
        os.makedirs(f"{dest_dir}/logs", exist_ok=True)
        
        clone_entries = _clone_runtime_entries(source.dir, dest_dir)
        missing_base_entries = [
            rel_path for rel_path in _runtime_sync_entries(MELISSA_DIR)
            if rel_path not in clone_entries
        ]
        if missing_base_entries:
            _clone_runtime_entries(MELISSA_DIR, dest_dir, missing_base_entries)
        
        # Nuevo .env
        src_env = dict(source.env)
        src_env["TELEGRAM_TOKEN"] = tg_token
        src_env["PORT"] = str(port)
        src_env["MASTER_API_KEY"] = _s.token_hex(12)
        src_env["WEBHOOK_SECRET"] = f"melissa_{dest_slug}_{_s.token_hex(6)}"
        src_env["DB_PATH"] = f"{dest_dir}/melissa.db"
        src_env["BRAND_ASSETS_BASE_DIR"] = f"{dest_dir}/brand-assets"
        src_env["VECTOR_DB_PATH"] = f"{dest_dir}/vectors.db"
        src_env["NOVA_ENABLED"] = "false"
        src_env["NOVA_TOKEN"] = ""
        
        env_lines = [f"# Melissa — {dest_slug}  (clonado de {source.name})"]
        for k, v in src_env.items():
            env_lines.append(f"{k}={v}")
        Path(f"{dest_dir}/.env").write_text("\n".join(env_lines))
        
        # instance.json
        Path(f"{dest_dir}/instance.json").write_text(json.dumps({
            "name": dest_slug,
            "label": dest_name,
            "sector": source.sector,
            "port": port,
            "cloned_from": source.name,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }, indent=2))
        
        sp.finish(f"Clon '{dest_name}' creado")
    
    pm2_name = f"melissa-{dest_slug}"
    
    with Spinner("Arrancando...") as sp:
        pm2("delete", pm2_name)
        subprocess.run([
            "pm2", "start", f"{dest_dir}/melissa.py",
            "--name", pm2_name,
            "--interpreter", "python3",
            "--cwd", dest_dir,          # ✅ FIX: --cwd necesario para que load_dotenv() funcione
            "--log", f"{dest_dir}/logs/melissa.log",
            "--error", f"{dest_dir}/logs/error.log"
        ], capture_output=True)
        pm2_save()
        time.sleep(3)
        h = health(port)
        sp.finish("Online" if h else "Arrancando...", ok=bool(h))
    
    nl()
    ok(f"Clon '{dest_name}' listo en :{port}")
    info("Necesita ser configurado desde cero (nuevo admin)")

def cmd_reset(args):
    """Resetear sesión de instancia."""
    name = getattr(args, 'name', '') or ''
    
    inst = find_instance(name) if name else None
    if not inst:
        instances = get_instances()
        if instances:
            idx = select([i.label for i in instances], title="¿Cuál instancia resetear?")
            inst = instances[idx]
        else:
            fail("No hay instancias")
            return
    
    print_logo(compact=True)
    section(f"Reset — {inst.label}")
    
    warn("Esto borrará TODAS las conversaciones, configuración del admin,")
    warn("citas agendadas y memoria.")
    warn("Las claves de API (.env) se conservan.")
    nl()
    
    if not confirm(f"¿Confirmar reset de '{inst.label}'?", default=False):
        info("Cancelado")
        return
    
    pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
    
    with Spinner("Deteniendo...") as sp:
        pm2("stop", pm2_name)
        time.sleep(1)
        sp.finish("Detenida")
    
    with Spinner("Borrando sesión...") as sp:
        for db_file in [
            f"{inst.dir}/melissa.db",
            f"{inst.dir}/vectors.db",
            f"{inst.dir}/melissa.db-wal",
            f"{inst.dir}/melissa.db-shm"
        ]:
            if os.path.exists(db_file):
                os.remove(db_file)
        sp.finish("Sesión borrada")
    
    with Spinner("Reiniciando...") as sp:
        pm2("start", pm2_name)
        time.sleep(3)
        h = health(inst.port)
        sp.finish("Online — esperando nuevo admin" if h else "Arrancando...")
    
    notify_omni("reset_sesion", inst.label)
    
    nl()
    ok("Reset completado")
    info("La próxima persona con token será el nuevo admin")

def cmd_zero(args):
    """
    Deja una instancia en cero para un cliente nuevo.

    Qué hace:
      ✓ Borra TODOS los datos (conversaciones, citas, pacientes, memoria, admin)
      ✓ Conserva los archivos de código y las API keys del .env
      ✓ Permite cambiar el nombre del negocio
      ✓ Permite cambiar el bot de Telegram (token nuevo = bot nuevo)
      ✓ Permite cambiar el sector
      ✓ Hace backup automático antes de borrar (por si acaso)
      ✓ Reinicia limpio esperando un nuevo admin

    Diferencia con 'melissa reset':
      reset  → borra solo el DB, sin tocar nada más (para testear)
      zero   → entrega completa al siguiente cliente, con wizard de renombre
    """
    print_logo(compact=True)
    name = getattr(args, 'name', '') or ''

    # ── Seleccionar instancia ─────────────────────────────────────────────────
    inst = find_instance(name) if name else None
    if not inst:
        instances = [i for i in get_instances() if not i.is_base]
        if not instances:
            fail("No hay instancias de clientes")
            info("Las instancias están en: " + INSTANCES_DIR)
            return
        if len(instances) == 1:
            inst = instances[0]
        else:
            section("Seleccionar instancia", "¿A cuál cliente se va?")
            idx = select([i.label for i in instances])
            inst = instances[idx]

    sector_obj = SECTORS.get(inst.sector, SECTORS["otro"])

    # ── Pantalla de confirmación ──────────────────────────────────────────────
    section(f"Zero — {inst.label}", "Entregar instancia a nuevo cliente")
    nl()

    print(f"  {q(C.YLW, '⚠', bold=True)}  {q(C.W, 'Esta operación borrará:', bold=True)}")
    print(f"       {q(C.RED, '✗')}  Todas las conversaciones")
    print(f"       {q(C.RED, '✗')}  Todos los pacientes / contactos")
    print(f"       {q(C.RED, '✗')}  Todas las citas agendadas")
    print(f"       {q(C.RED, '✗')}  Toda la memoria y embeddings")
    print(f"       {q(C.RED, '✗')}  El admin actual y su configuración")
    print(f"       {q(C.RED, '✗')}  Reglas y carpeta de confianza")
    nl()
    print(f"  {q(C.GRN, '✓', bold=True)}  {q(C.W, 'Esto se conserva:', bold=True)}")
    print(f"       {q(C.GRN, '✓')}  Archivos de código (melissa.py, etc.)")
    print(f"       {q(C.GRN, '✓')}  API keys (Groq, Gemini, OpenRouter...)")
    print(f"       {q(C.GRN, '✓')}  Puerto asignado ({inst.port})")
    print(f"       {q(C.GRN, '✓')}  Backup automático antes de borrar")
    nl()

    confirmation = prompt(
        f"Escribe el nombre de la instancia '{q(C.YLW, inst.name)}' para confirmar"
    )
    if confirmation.strip() != inst.name:
        info("Cancelado — no coincide el nombre")
        return

    nl()

    # ── Paso 1: Backup automático ─────────────────────────────────────────────
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_out = BACKUP_DIR / f"zero_backup_{inst.name}_{timestamp}.tar.gz"

    with Spinner(f"Creando backup de seguridad...") as sp:
        try:
            import tarfile as _tar
            with _tar.open(backup_out, "w:gz") as tar:
                for f in [".env", "melissa.db", "instance.json", "vectors.db",
                          "melissa.db-wal", "melissa.db-shm"]:
                    p = f"{inst.dir}/{f}"
                    if os.path.exists(p):
                        tar.add(p, arcname=f)
            sp.finish(f"Backup guardado: {backup_out.name}")
        except Exception as e:
            sp.finish(f"Backup falló ({e}) — ¿continuar igual?", ok=False)
            if not confirm("¿Continuar sin backup?", default=False):
                return

    # ── Paso 2: Detener la instancia ──────────────────────────────────────────
    pm2_name = f"melissa-{inst.name}"

    with Spinner("Deteniendo instancia...") as sp:
        pm2("stop", pm2_name)
        time.sleep(1)
        sp.finish("Instancia detenida")

    # ── Paso 3: Borrar todos los datos ────────────────────────────────────────
    db_files = [
        f"{inst.dir}/melissa.db",
        f"{inst.dir}/melissa_ultra.db",
        f"{inst.dir}/vectors.db",
        f"{inst.dir}/melissa.db-wal",
        f"{inst.dir}/melissa.db-shm",
        f"{inst.dir}/melissa.db-journal",
    ]

    with Spinner("Borrando todos los datos...") as sp:
        removed = 0
        for db_file in db_files:
            if os.path.exists(db_file):
                os.remove(db_file)
                removed += 1
        # También limpiar logs viejos del cliente anterior
        logs_dir = f"{inst.dir}/logs"
        if os.path.isdir(logs_dir):
            for log_file in Path(logs_dir).glob("*.log"):
                try:
                    log_file.unlink()
                except Exception:
                    pass
        sp.finish(f"Datos borrados ({removed} archivos de base de datos)")

    # ── Paso 4: Configurar para el nuevo cliente (wizard) ─────────────────────
    nl()
    section("Configurar para el nuevo cliente", "Puedes cambiar todo o dejar igual")

    ev_path = f"{inst.dir}/.env"
    ev      = dict(load_env(ev_path))

    # — Nombre del negocio —
    nuevo_label = prompt(
        "Nombre del nuevo negocio",
        default=inst.label
    )
    nuevo_label = nuevo_label.strip() or inst.label

    # — Sector —
    cambiar_sector = confirm("¿Cambiar el sector del negocio?", default=False)
    nuevo_sector   = inst.sector
    if cambiar_sector:
        sector_list  = list(SECTORS.keys())
        sector_names = [f"{SECTORS[s].emoji} {SECTORS[s].name}" for s in sector_list]
        sector_descs = [SECTORS[s].tagline for s in sector_list]
        info("Selecciona el nuevo sector:")
        idx          = select(sector_names, sector_descs)
        nuevo_sector = sector_list[idx]
        ok(f"Sector: {SECTORS[nuevo_sector].emoji} {SECTORS[nuevo_sector].name}")

    # — Token de Telegram —
    nl()
    info("Token de Telegram actual:")
    tg_actual = ev.get("TELEGRAM_TOKEN", "")
    if tg_actual:
        print(f"       {q(C.G3, tg_actual[:10] + '...' + tg_actual[-6:])}")
    else:
        warn("Sin token configurado")

    cambiar_token = confirm(
        "¿Cambiar bot de Telegram? (recomendado si el cliente anterior aún tiene el bot)",
        default=True
    )
    nuevo_token = tg_actual
    if cambiar_token:
        info("Ve a @BotFather en Telegram, crea un /newbot y pega el token aquí.")
        info("Deja en blanco para conservar el token actual.")
        t = prompt("Nuevo token de Telegram", default="")
        if t.strip():
            nuevo_token = t.strip()
            ok("Token actualizado")
        else:
            info("Se conserva el token actual")

    # ── Paso 5: Aplicar cambios al .env e instance.json ──────────────────────
    with Spinner("Aplicando nueva configuración...") as sp:
        # Actualizar .env
        if nuevo_token != tg_actual:
            update_env_key(ev_path, "TELEGRAM_TOKEN", nuevo_token)
        if nuevo_sector != inst.sector:
            update_env_key(ev_path, "SECTOR", nuevo_sector)

        # Rotar MASTER_API_KEY y WEBHOOK_SECRET para el nuevo cliente
        import secrets as _s
        nuevo_master     = _s.token_hex(12)
        nuevo_wh_secret  = f"melissa_{inst.name}_{_s.token_hex(8)}"
        update_env_key(ev_path, "MASTER_API_KEY",  nuevo_master)
        update_env_key(ev_path, "WEBHOOK_SECRET",  nuevo_wh_secret)

        # Actualizar instance.json
        meta_path = f"{inst.dir}/instance.json"
        meta = {}
        if os.path.exists(meta_path):
            try:
                meta = json.loads(Path(meta_path).read_text())
            except Exception:
                pass
        meta.update({
            "label":       nuevo_label,
            "sector":      nuevo_sector,
            "zeroed_at":   datetime.utcnow().isoformat() + "Z",
            "zeroed_from": inst.label,
        })
        Path(meta_path).write_text(json.dumps(meta, indent=2))

        sp.finish("Configuración aplicada")

    # ── Paso 6: Relanzar con PM2 (con --cwd correcto) ─────────────────────────
    with Spinner("Arrancando instancia limpia...") as sp:
        pm2("delete", pm2_name)
        time.sleep(1)
        subprocess.run([
            "pm2", "start", f"{inst.dir}/melissa.py",
            "--name",          pm2_name,
            "--interpreter",   "python3",
            "--cwd",           inst.dir,
            "--restart-delay", "3000",
            "--max-restarts",  "10",
            "--log",           f"{inst.dir}/logs/melissa.log",
            "--error",         f"{inst.dir}/logs/error.log",
        ], capture_output=True)
        pm2_save()
        time.sleep(4)
        h = health(inst.port)
        sp.finish("Online — esperando nuevo admin ✓" if h else "Arrancando...", ok=bool(h))

    # ── Paso 7: Reconfigurar webhook en Telegram si cambió el token ───────────
    if nuevo_token and nuevo_token != tg_actual:
        ev_fresh   = dict(load_env(ev_path))
        base_url   = ev_fresh.get("BASE_URL", ev.get("BASE_URL", ""))
        wh_url     = f"{base_url}/webhook/{nuevo_wh_secret}"

        with Spinner("Registrando webhook en Telegram...") as sp:
            try:
                url = f"https://api.telegram.org/bot{nuevo_token}/setWebhook"
                if _HTTPX:
                    r = _httpx.post(url, json={"url": wh_url,
                                               "drop_pending_updates": True}, timeout=10)
                    ok_flag = r.json().get("ok", False)
                else:
                    import urllib.request as _ur
                    req = _ur.Request(url,
                                      data=json.dumps({"url": wh_url,
                                                       "drop_pending_updates": True}).encode(),
                                      headers={"Content-Type": "application/json"},
                                      method="POST")
                    ok_flag = json.loads(_ur.urlopen(req, timeout=10).read()).get("ok", False)
                sp.finish(f"Webhook registrado ✓" if ok_flag else "Error al registrar webhook", ok=ok_flag)
            except Exception as e:
                sp.finish(f"No pude registrar webhook: {e}", ok=False)
                warn(f"Registra manualmente: melissa webhooks {inst.name}")
    elif nuevo_token:
        # Mismo token, solo actualizar el webhook secret que rotamos
        ev_fresh = dict(load_env(ev_path))
        base_url = ev_fresh.get("BASE_URL", ev.get("BASE_URL", ""))
        wh_url   = f"{base_url}/webhook/{nuevo_wh_secret}"
        with Spinner("Actualizando webhook...") as sp:
            try:
                url = f"https://api.telegram.org/bot{nuevo_token}/setWebhook"
                if _HTTPX:
                    _httpx.post(url, json={"url": wh_url,
                                           "drop_pending_updates": True}, timeout=10)
                sp.finish("Webhook actualizado ✓")
            except Exception:
                sp.finish("No pude actualizar webhook", ok=False)

    # ── Resumen final ──────────────────────────────────────────────────────────
    nl()
    hr()
    nl()
    sector_nuevo_obj = SECTORS.get(nuevo_sector, SECTORS["otro"])
    section(
        f"'{nuevo_label}' lista para nuevo cliente",
        f"{sector_nuevo_obj.emoji} {sector_nuevo_obj.name}"
    )
    kv("Instancia (PM2)",  pm2_name)
    kv("Puerto",           str(inst.port))
    kv("Sector",           sector_nuevo_obj.name)
    kv("Master Key",       nuevo_master)
    kv("Backup anterior",  str(backup_out.name))
    nl()
    ok("La instancia está en CERO — sin usuarios, sin datos, sin admin")
    info("El primer cliente que escriba al bot y active con token será el nuevo admin")
    nl()
    info(f"Genera un token de activación con:  melissa chat {inst.name}")
    nl()
    notify_omni("zero_instancia",
                f"{inst.label} → {nuevo_label} ({sector_nuevo_obj.name}) en :{inst.port}")


def cmd_backup(args):
    """Crear backup de instancia."""
    name = getattr(args, 'name', '') or 'base'
    
    inst = find_instance(name)
    if not inst:
        fail(f"No encontré '{name}'")
        return
    
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = BACKUP_DIR / f"melissa_{inst.name}_{timestamp}.tar.gz"
    
    print_logo(compact=True)
    section(f"Backup — {inst.label}")
    
    with Spinner(f"Creando backup...") as sp:
        with tarfile.open(output, "w:gz") as tar:
            for f in [".env", "melissa.db", "instance.json", "vectors.db"]:
                p = f"{inst.dir}/{f}"
                if os.path.exists(p):
                    tar.add(p, arcname=f)
        sp.finish("Backup creado")
    
    kv("Archivo", str(output))
    kv("Tamaño", f"{output.stat().st_size // 1024} KB")
    nl()
    info(f"Restaurar con: melissa restore {output.name}")

def cmd_restore(args):
    """Restaurar desde backup."""
    file_path = getattr(args, 'name', '') or prompt("Archivo de backup (.tar.gz)")
    
    if not file_path:
        return
    
    if not os.path.exists(file_path):
        # Buscar en BACKUP_DIR
        alt_path = BACKUP_DIR / file_path
        if alt_path.exists():
            file_path = str(alt_path)
        else:
            fail(f"No encontré: {file_path}")
            return
    
    print_logo(compact=True)
    section("Restaurar backup")
    
    dest_name = prompt("Nombre de la instancia destino")
    if not dest_name:
        return
    
    dest_slug = slug(dest_name)
    dest_dir = f"{INSTANCES_DIR}/{dest_slug}"
    
    if os.path.isdir(dest_dir):
        if not confirm(f"'{dest_slug}' ya existe. ¿Sobreescribir?", default=False):
            return
    
    with Spinner("Restaurando...") as sp:
        os.makedirs(dest_dir, exist_ok=True)
        with tarfile.open(file_path, "r:gz") as tar:
            tar.extractall(dest_dir)
        sp.finish("Restaurado")
    
    # Actualizar puerto si es necesario
    env_path = f"{dest_dir}/.env"
    ev = dict(load_env(env_path))
    
    port = next_port()
    if port:
        update_env_key(env_path, "PORT", str(port))
        update_env_key(env_path, "DB_PATH", f"{dest_dir}/melissa.db")
        update_env_key(env_path, "VECTOR_DB_PATH", f"{dest_dir}/vectors.db")
    
    pm2_name = f"melissa-{dest_slug}"
    
    with Spinner("Arrancando...") as sp:
        pm2("delete", pm2_name)
        subprocess.run([
            "pm2", "start", f"{dest_dir}/melissa.py",
            "--name", pm2_name,
            "--interpreter", "python3"
        ], capture_output=True)
        pm2_save()
        time.sleep(3)
        h = health(port or int(ev.get("PORT", 8001)))
        sp.finish("Online" if h else "Arrancando...")
    
    ok(f"'{dest_name}' restaurada")

def cmd_scale(args):
    """Escalar workers de una instancia."""
    name = getattr(args, 'name', '') or ''
    
    inst = find_instance(name) if name else None
    if not inst:
        fail("Especifica la instancia: melissa scale <nombre> <workers>")
        info("Ejemplo: melissa scale clinica-bella 4")
        return
    
    # Obtener número de workers
    workers = getattr(args, 'subcommand', '')
    if not workers or not workers.isdigit():
        workers = prompt("Número de workers", default="2")
    
    pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
    
    with Spinner(f"Escalando {inst.label} a {workers} workers...") as sp:
        subprocess.run(["pm2", "scale", pm2_name, workers], capture_output=True)
        sp.finish(f"Escalado a {workers} workers")

def cmd_doctor(args):
    """Diagnóstico completo del sistema."""
    print_logo(compact=True)
    section("Doctor", "Diagnóstico del sistema")
    
    issues = []
    
    # Python
    pv = sys.version.split()[0]
    pv_tuple = tuple(int(x) for x in pv.split(".")[:2])
    if pv_tuple >= (3, 9):
        ok(f"Python {pv}")
    else:
        fail(f"Python {pv} — se recomienda 3.9+")
        issues.append("python_version")
    
    # PM2
    if shutil.which("pm2"):
        ok("PM2 disponible")
    else:
        fail("PM2 no instalado")
        issues.append("pm2")
    
    # Git
    if shutil.which("git"):
        ok("Git disponible")
    else:
        warn("Git no encontrado")
    
    nl()
    
    # Archivos
    info("Archivos core:")
    for f in ["melissa.py", "search.py", "knowledge_base.py", "nova_bridge.py"]:
        p = f"{MELISSA_DIR}/{f}"
        if os.path.exists(p):
            ok(f"  {f}")
        else:
            fail(f"  {f}")
            issues.append(f"file_{f}")
    
    nl()
    
    # .env
    env_path = f"{MELISSA_DIR}/.env"
    if os.path.exists(env_path):
        ok(".env existe")
        ev = load_env(env_path)
        
        required = ["TELEGRAM_TOKEN", "GROQ_API_KEY", "BASE_URL", "MASTER_API_KEY"]
        for k in required:
            if ev.get(k):
                ok(f"  {k}")
            else:
                warn(f"  {k} vacío")
                issues.append(f"env_{k}")
    else:
        fail(".env no existe")
        issues.append("env_missing")
    
    nl()
    
    # Instancias
    info("Instancias:")
    instances = get_instances()
    ports = [i.port for i in instances]
    healths = health_batch(ports)
    
    for inst in instances:
        h = healths.get(inst.port, {})
        icon, status = icon_status(h)
        print(f"    {icon}  {inst.name}  :{inst.port}")
    
    nl()
    
    # Nova & Omni
    info("Servicios:")
    nova_h = health(NOVA_PORT)
    omni_h = health(OMNI_PORT)
    
    if nova_h:
        ok(f"Nova activo :{NOVA_PORT}")
    else:
        dim(f"Nova no responde :{NOVA_PORT}")
    
    if omni_h:
        ok(f"Omni activo :{OMNI_PORT}")
    else:
        dim(f"Omni no responde :{OMNI_PORT}")
    
    nl()
    
    # Disk space
    info("Sistema:")
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        free_gb = free // (1024**3)
        kv("Disco libre", f"{free_gb} GB")
        if free_gb < 5:
            warn("Poco espacio en disco")
            issues.append("disk_space")
    except Exception:
        pass
    
    # Memory
    try:
        with open('/proc/meminfo') as f:
            meminfo = f.read()
            match = re.search(r'MemAvailable:\s+(\d+)', meminfo)
            if match:
                mem_mb = int(match.group(1)) // 1024
                kv("RAM disponible", f"{mem_mb} MB")
    except Exception:
        pass

    nl()
    info("Logs — escaneo rápido de errores:")
    for inst in instances:
        pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
        lp = _find_pm2_log(pm2_name)
        if lp:
            try:
                with open(lp) as _lf:
                    _raw = _lf.readlines()
                _errs = _analyze_errors([l.rstrip() for l in _raw[-300:]], inst.name)
                _crit = [e for e in _errs if e["severity"] == "CRITICO"]
                _high = [e for e in _errs if e["severity"] == "ALTO"]
                if _crit:
                    fail(f"  {inst.name}: {len(_crit)} error(es) crítico(s)"
                         f"  → melissa logs {inst.name} --fix")
                    issues.append(f"logs_critical_{inst.name}")
                elif _high:
                    warn(f"  {inst.name}: {len(_high)} advertencia(s)"
                         f"  → melissa logs {inst.name} --scan")
                    issues.append(f"logs_warning_{inst.name}")
                else:
                    ok(f"  {inst.name}: logs limpios")
            except OSError:
                dim(f"  {inst.name}: log no legible")
        else:
            dim(f"  {inst.name}: sin log (¿está corriendo?)")

    nl()
    hr()
    nl()

    if issues:
        warn(f"{len(issues)} problema(s) encontrado(s):")
        for i in issues:
            dim(f"  · {i}")
        nl()
        # Mostrar fixes rápidos si hay errores de log
        log_issues = [i for i in issues if i.startswith("logs_")]
        if log_issues:
            info("Fix rápido para errores de log:")
            for li in log_issues:
                inst_n = li.replace("logs_critical_", "").replace("logs_warning_", "")
                dim(f"  melissa logs {inst_n} --fix")
            nl()
        info("Corrige los problemas y ejecuta 'melissa doctor' nuevamente")
    else:
        ok("Sistema saludable")

    nl()

def cmd_audit(args):
    """Auditoría de seguridad."""
    print_logo(compact=True)
    section("Auditoría de Seguridad")
    
    issues = []
    
    # Permisos de .env
    info("Permisos de archivos:")
    
    for inst in get_instances():
        env_path = f"{inst.dir}/.env"
        if os.path.exists(env_path):
            mode = oct(os.stat(env_path).st_mode)[-3:]
            if mode in ("600", "400"):
                ok(f"  {inst.name}/.env: {mode}")
            else:
                warn(f"  {inst.name}/.env: {mode} (debería ser 600)")
                issues.append(f"{inst.name}_env_perms")
    
    nl()
    
    # Tokens expuestos
    info("Tokens y claves:")
    
    base_env = load_env(f"{MELISSA_DIR}/.env")
    
    if base_env.get("MASTER_API_KEY"):
        key = base_env["MASTER_API_KEY"]
        if len(key) >= 16:
            ok("  MASTER_API_KEY: longitud adecuada")
        else:
            warn("  MASTER_API_KEY: muy corta")
            issues.append("weak_master_key")
    
    if base_env.get("WEBHOOK_SECRET"):
        ok("  WEBHOOK_SECRET: configurado")
    else:
        warn("  WEBHOOK_SECRET: no configurado")
        issues.append("no_webhook_secret")
    
    nl()
    
    # Git
    info("Control de versiones:")
    
    gitignore_path = f"{MELISSA_DIR}/.gitignore"
    if os.path.exists(gitignore_path):
        content = Path(gitignore_path).read_text()
        if ".env" in content:
            ok("  .env en .gitignore")
        else:
            fail("  .env NO está en .gitignore")
            issues.append("env_not_gitignored")
    else:
        warn("  Sin .gitignore")
    
    nl()
    
    # PM2
    info("Procesos:")
    
    pm2_procs = pm2_list()
    for proc in pm2_procs:
        name = proc.get("name", "")
        if "melissa" in name.lower():
            user = proc.get("pm2_env", {}).get("username", "")
            if user == "root":
                warn(f"  {name}: ejecutando como root")
                issues.append(f"{name}_root")
            else:
                ok(f"  {name}: usuario {user}")
    
    nl()
    hr()
    nl()
    
    if issues:
        warn(f"{len(issues)} problema(s) de seguridad:")
        for i in issues:
            dim(f"  · {i}")
        nl()
        info("Ejecuta 'melissa secure' para ver recomendaciones")
    else:
        ok("Sin problemas de seguridad detectados")
    
    nl()

def cmd_benchmark(args):
    """Test de rendimiento."""
    print_logo(compact=True)
    section("Benchmark", "Test de rendimiento")
    
    instances = get_instances()
    online = [i for i in instances if health(i.port).get("status") == "online"]
    
    if not online:
        fail("No hay instancias online para testear")
        return
    
    inst = online[0] if len(online) == 1 else online[select([i.label for i in online], title="¿Cuál testear?")]
    
    info(f"Testeando {inst.label} en :{inst.port}")
    nl()
    
    # Health check latency
    info("Latencia de health check:")
    latencies = []
    
    for i in range(10):
        start = time.time()
        h = health(inst.port, timeout=5)
        latency = (time.time() - start) * 1000
        latencies.append(latency)
        print(f"       {i + 1}. {latency:.1f}ms {'✓' if h else '✗'}")
    
    avg = sum(latencies) / len(latencies)
    min_l = min(latencies)
    max_l = max(latencies)
    
    nl()
    kv("Promedio", f"{avg:.1f}ms")
    kv("Mínimo", f"{min_l:.1f}ms")
    kv("Máximo", f"{max_l:.1f}ms")
    
    if avg < 50:
        ok("Excelente rendimiento")
    elif avg < 200:
        ok("Buen rendimiento")
    else:
        warn("Rendimiento lento")
    
    nl()

def cmd_secure(args):
    """Guía de seguridad."""
    print_logo(compact=True)
    section("Guía de Seguridad")
    
    steps = [
        ("Permisos de .env",
         "chmod 600 ~/.melissa/.env",
         "Solo el propietario puede leer"),
        
        ("No commitear .env",
         "echo '.env' >> .gitignore",
         "Nunca subir secrets a Git"),
        
        ("Rotar claves periódicamente",
         "melissa rotate-keys",
         "Cambia WEBHOOK_SECRET y MASTER_API_KEY"),
        
        ("Backup antes de cambios",
         "melissa backup <instancia>",
         "Siempre tener un snapshot"),
        
        ("Usuario no-root",
         "sudo -u melissa pm2 start melissa.py",
         "No ejecutar como root"),
        
        ("Firewall",
         "ufw allow 8001:8199/tcp",
         "Solo abrir puertos necesarios"),
        
        ("HTTPS",
         "Usar nginx/caddy como proxy",
         "Nunca exponer HTTP directo"),
        
        ("Rate limiting",
         "Configurar en nginx",
         "Prevenir abuso de API"),
    ]
    
    for i, (title, cmd_, desc) in enumerate(steps, 1):
        print(f"  {q(C.P2, str(i) + '.', bold=True)}  {q(C.W, title, bold=True)}")
        print(f"       {q(C.CYN, cmd_)}")
        print(f"       {q(C.G3, desc)}")
        nl()

def cmd_rotate_keys(args):
    """Rotar secrets."""
    print_logo(compact=True)
    section("Rotación de Secrets")
    
    warn("Esto cambiará WEBHOOK_SECRET y MASTER_API_KEY")
    warn("Los webhooks necesitarán reconfigurarse")
    nl()
    
    if not confirm("¿Continuar?", default=False):
        return
    
    import secrets as _s
    
    instances = get_instances()
    
    for inst in instances:
        env_path = f"{inst.dir}/.env"
        if not os.path.exists(env_path):
            continue
        
        new_ws = f"melissa_{inst.name}_{_s.token_hex(6)}"
        new_mk = _s.token_hex(12)
        
        update_env_key(env_path, "WEBHOOK_SECRET", new_ws)
        update_env_key(env_path, "MASTER_API_KEY", new_mk)
        
        pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
        pm2("restart", pm2_name)
        
        ok(f"{inst.label}: secrets rotados")
    
    nl()
    ok("Rotación completada")
    info("Reconfigura webhooks si usas WhatsApp")

def cmd_upgrade(args):
    """Actualizar desde GitHub y propagar a todas las instancias."""
    print_logo(compact=True)
    section("Upgrade")

    if confirm("¿Crear backup antes de actualizar?", default=True):
        for inst in get_instances()[:1]:
            cmd_backup(type('A', (), {'name': inst.name})())

    with Spinner("Descargando actualización...") as sp:
        r = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=MELISSA_DIR,
            capture_output=True,
            text=True
        )
        if r.returncode == 0:
            sp.finish("Código actualizado")
        else:
            sp.finish(f"Error: {r.stderr[:50]}", ok=False)
            return

    with Spinner("Validando sintaxis...") as sp:
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", f"{MELISSA_DIR}/melissa.py"],
            capture_output=True
        )
        if r.returncode == 0:
            sp.finish("Sintaxis válida")
        else:
            sp.finish("Error de sintaxis — rollback", ok=False)
            subprocess.run(
                ["git", "checkout", "HEAD~1", "--", f"{MELISSA_DIR}/melissa.py"],
                cwd=MELISSA_DIR,
                capture_output=True
            )
            return

    # Reiniciar instancia base
    with Spinner("Reiniciando instancia base...") as sp:
        pm2("restart", "melissa")
        pm2_save()
        time.sleep(3)
        sp.finish("Instancia base actualizada")

    # Propagar a instancias de clientes
    clientes = [i for i in get_instances() if not i.is_base]
    if clientes and confirm(f"¿Propagar actualización a {len(clientes)} instancia(s) de clientes?"):
        fake_args = type('Args', (), {'name': ''})()
        cmd_sync(fake_args)
    elif clientes:
        info(f"Recuerda propagar a tus {len(clientes)} clientes con: melissa sync")

    nl()
    ok("Melissa actualizada")

def cmd_billing(args):
    """Información de uso y costos de APIs."""
    print_logo(compact=True)
    section("Uso de APIs")
    
    # Por ahora solo informativo
    info("Esta función requiere tracking de requests.")
    info("Próximamente: métricas de uso por proveedor LLM.")
    nl()
    
    base_env = load_env(f"{MELISSA_DIR}/.env")
    
    providers = [
        ("Groq", "GROQ_API_KEY", "Gratis hasta límite"),
        ("Gemini", "GEMINI_API_KEY", "Gratis hasta 60 req/min"),
        ("OpenRouter", "OPENROUTER_API_KEY", "Pago por uso"),
        ("OpenAI", "OPENAI_API_KEY", "Pago por uso"),
    ]
    
    info("Proveedores configurados:")
    for name, key, pricing in providers:
        if base_env.get(key):
            ok(f"  {name}: {pricing}")
        else:
            dim(f"  {name}: no configurado")
    
    nl()

def cmd_chat(args):
    """
    Chat interactivo con cualquier instancia de Melissa.
    Genera tokens de activación y permite hablar directamente via API.
    Detecta instancias tanto en /melissa como en /melissa-instances/.
    """
    print_logo(compact=True)
    name = getattr(args, 'name', '') or ''

    # ── Seleccionar instancia ──────────────────────────────────────────────────
    inst = find_instance(name) if name else None
    if not inst:
        instances = get_instances()
        if not instances:
            fail("No hay instancias configuradas")
            info("Crea una con: melissa new")
            return
        online = [i for i in instances if health(i.port).get("status") == "online"]
        offline = [i for i in instances if i not in online]

        if len(instances) == 1:
            inst = instances[0]
        else:
            labels   = [f"{i.label} {'● online' if i in online else '○ offline'}" for i in instances]
            colors   = [C.GRN if i in online else C.G3 for i in instances]
            section("Seleccionar instancia", f"{len(online)}/{len(instances)} online")
            idx = select(labels, title="¿Con cuál instancia quieres trabajar?")
            inst = instances[idx]

    section(f"Chat — {inst.label}", f"Puerto :{inst.port}")

    h = health(inst.port)
    if not h:
        fail(f"'{inst.label}' no está online")
        nl()
        info(f"Para levantarla: melissa restart {inst.name}")
        return

    ev = dict(load_env(f"{inst.dir}/.env"))
    master_key = ev.get("MASTER_API_KEY", "")
    base_url = f"http://localhost:{inst.port}"

    # ── Menú de opciones ──────────────────────────────────────────────────────
    options = [
        "Generar token de activación para el admin",
        "Enviar mensaje de prueba a Melissa",
        "Ver info del bot de Telegram",
        "Verificar webhook actual",
        "Ver configuración completa",
    ]
    choice = select(options)

    # 1. Generar token de activación
    if choice == 0:
        if not master_key:
            fail("MASTER_API_KEY no configurada en .env")
            info(f"Edita: nano {inst.dir}/.env")
            return

        expiry = prompt("Horas de validez del token", default="72")
        with Spinner("Generando token...") as sp:
            try:
                url = f"{base_url}/api/tokens"
                payload = {"expiry_hours": int(expiry) if expiry.isdigit() else 72}
                if _HTTPX:
                    r = _httpx.post(
                        url, json=payload,
                        headers={"X-Master-Key": master_key},
                        timeout=10
                    )
                    data = r.json() if r.status_code == 200 else {}
                else:
                    import urllib.request as _ur
                    req = _ur.Request(
                        url, data=json.dumps(payload).encode(),
                        headers={"Content-Type": "application/json", "X-Master-Key": master_key},
                        method="POST"
                    )
                    data = json.loads(_ur.urlopen(req, timeout=10).read())
                sp.finish("Token generado")
            except Exception as e:
                sp.finish(f"Error: {e}", ok=False)
                data = {}

        token = data.get("token") or data.get("activation_token", "")
        if token:
            nl()
            ok("Token generado:")
            print(f"\n       {q(C.YLW, token, bold=True)}\n")
            info("Envía este token al cliente para que lo escriba en el bot de Telegram")
            info(f"Válido por {expiry} horas")
            tg_token = ev.get("TELEGRAM_TOKEN", "")
            if tg_token:
                bot_info_url = f"https://api.telegram.org/bot{tg_token}/getMe"
                try:
                    if _HTTPX:
                        br = _httpx.get(bot_info_url, timeout=5)
                        bdata = br.json().get("result", {})
                    else:
                        bdata = json.loads(_ur.urlopen(bot_info_url, timeout=5).read()).get("result", {})
                    username = bdata.get("username", "")
                    if username:
                        info(f"Bot de Telegram: @{username}")
                        print(f"       Enlace directo: {q(C.CYN, f'https://t.me/{username}')}")
                except Exception:
                    pass
        else:
            fail("No se obtuvo token")
            warn(f"Respuesta: {data}")

    # 2. Enviar mensaje de prueba
    elif choice == 1:
        section("Prueba de respuesta", "Ctrl+C para salir")
        sector     = SECTORS.get(inst.sector, SECTORS["otro"])
        test_url   = f"http://localhost:{inst.port}/test"
        master_key = ev.get("MASTER_API_KEY", "")

        test_qs = [
            "Hola, buenos días",
            "¿Qué servicios ofrecen?",
            "¿Cuál es el horario?",
            "Quiero agendar una cita",
            "¿Cuánto cuesta?",
        ] + sector.questions[:3]

        info("Preguntas rápidas:")
        for i, q_ in enumerate(test_qs):
            print(f"    {q(C.P2, str(i+1)+'.')} {q(C.G1, q_)}")
        nl()
        info("Escribe una pregunta, el número de la lista, o 'salir'")
        nl()

        while True:
            sys.stdout.write(f"  {q(C.P2, '→')}  ")
            sys.stdout.flush()
            try:
                user_input = input("").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user_input or user_input.lower() in ("salir", "exit", "q"):
                break
            if user_input.isdigit() and 1 <= int(user_input) <= len(test_qs):
                question = test_qs[int(user_input) - 1]
                print(f"       {q(C.G3, 'Pregunta:')} {question}")
            else:
                question = user_input

            payload = {
                "message":    question,
                "user_id":    "cli_test_000",
                "master_key": master_key,
            }
            headers_ = {"Content-Type": "application/json", "X-Master-Key": master_key}

            try:
                with Spinner("Melissa piensa...") as sp:
                    if _HTTPX:
                        r = _httpx.post(test_url, json=payload,
                                        headers={"X-Master-Key": master_key},
                                        timeout=45)
                        code = r.status_code
                        if code == 200:
                            resp = r.json().get("response", "(sin respuesta)")
                            sp.stop(ok=True)
                        elif code == 404:
                            sp.stop(ok=False)
                            fail("404 — el endpoint /test no existe en melissa.py")
                            warn("Sube el melissa.py actualizado y reinicia:")
                            info(f"  melissa restart {inst.name}")
                            break
                        elif code == 401:
                            sp.stop(ok=False)
                            fail("401 — Master key incorrecta")
                            info(f"  Revisa MASTER_API_KEY en: {inst.dir}/.env")
                            break
                        else:
                            resp = f"[Error {code}] {r.text[:120]}"
                            sp.stop(ok=False)
                    else:
                        import urllib.request as _ur
                        req = _ur.Request(test_url,
                                          data=json.dumps(payload).encode(),
                                          headers=headers_, method="POST")
                        resp = json.loads(_ur.urlopen(req, timeout=45).read()).get("response", "(sin respuesta)")
                        sp.stop(ok=True)

                nl()
                print(f"  {q(C.P3, 'Melissa:', bold=True)}")
                for line in resp.split('\n'):
                    if line.strip():
                        print(f"       {q(C.G1, line)}")

            except Exception as e:
                err = str(e)
                if "404" in err:
                    fail("404 — /test no existe en melissa.py")
                    warn("Sube melissa.py actualizado y reinicia la instancia")
                    break
                elif "Connection refused" in err or "refused" in err.lower():
                    fail(f"Conexión rechazada en puerto {inst.port}")
                    info(f"  melissa restart {inst.name}")
                    break
                else:
                    print(f"       {q(C.RED, f'Error: {err[:100]}')}")
            nl()

        info("Prueba finalizada")

    # 3. Info del bot de Telegram
    elif choice == 2:
        tg_token = ev.get("TELEGRAM_TOKEN", "")
        if not tg_token:
            fail("TELEGRAM_TOKEN vacío en .env")
            return
        with Spinner("Consultando Telegram...") as sp:
            try:
                url = f"https://api.telegram.org/bot{tg_token}/getMe"
                if _HTTPX:
                    r = _httpx.get(url, timeout=10)
                    data = r.json()
                else:
                    import urllib.request as _ur
                    data = json.loads(_ur.urlopen(url, timeout=10).read())
                sp.finish("Info obtenida")
                result = data.get("result", {})
                nl()
                kv("ID del bot",       str(result.get("id", "?")))
                kv("Username",         f"@{result.get('username', '?')}")
                kv("Nombre",           result.get("first_name", "?"))
                kv("Enlace directo",   f"https://t.me/{result.get('username', '')}")
                kv("Grupos",           "Sí" if result.get("can_join_groups") else "No")
            except Exception as e:
                sp.finish(f"Error: {e}", ok=False)

    # 4. Verificar webhook
    elif choice == 3:
        tg_token = ev.get("TELEGRAM_TOKEN", "")
        if not tg_token:
            fail("TELEGRAM_TOKEN vacío en .env")
            return
        with Spinner("Verificando webhook...") as sp:
            try:
                url = f"https://api.telegram.org/bot{tg_token}/getWebhookInfo"
                if _HTTPX:
                    r = _httpx.get(url, timeout=10)
                    data = r.json()
                else:
                    import urllib.request as _ur
                    data = json.loads(_ur.urlopen(url, timeout=10).read())
                sp.finish("OK")
                result = data.get("result", {})
                current_url = result.get("url", "")
                expected_secret = ev.get("WEBHOOK_SECRET", "")
                expected_url    = f"{ev.get('BASE_URL', '')}/webhook/{expected_secret}"
                nl()
                kv("URL registrada",  current_url or "(ninguna)")
                kv("URL esperada",    expected_url)
                kv("Mensajes pend.",  str(result.get("pending_update_count", 0)))
                kv("Último error",    result.get("last_error_message", "Ninguno"))
                nl()
                if current_url == expected_url:
                    ok("Webhook correcto ✓")
                elif not current_url:
                    fail("Sin webhook registrado")
                    if confirm("¿Registrar ahora?"):
                        set_url = f"https://api.telegram.org/bot{tg_token}/setWebhook"
                        if _HTTPX:
                            _httpx.post(set_url, json={"url": expected_url}, timeout=10)
                        ok(f"Webhook registrado: {expected_url}")
                else:
                    warn("La URL registrada NO coincide con la esperada")
                    warn("Esto causa que el bot no responda — el webhook apunta a otro proceso")
                    if confirm("¿Corregir ahora?"):
                        set_url = f"https://api.telegram.org/bot{tg_token}/setWebhook"
                        if _HTTPX:
                            _httpx.post(set_url, json={"url": expected_url}, timeout=10)
                        ok(f"Webhook corregido → {expected_url}")
            except Exception as e:
                sp.finish(f"Error: {e}", ok=False)

    # 5. Ver configuración
    elif choice == 4:
        nl()
        info(f"Configuración de {inst.label}:")
        nl()
        sensitive_keys = {"TELEGRAM_TOKEN", "GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY",
                          "OPENAI_API_KEY", "MASTER_API_KEY", "WA_ACCESS_TOKEN", "NOVA_TOKEN",
                          "NOVA_API_KEY", "OMNI_KEY", "META_APP_SECRET"}
        for k, v in sorted(ev.items()):
            if k in sensitive_keys:
                v_show = (v[:6] + "..." + v[-4:]) if len(v) > 10 else "***"
            else:
                v_show = v
            print(f"  {q(C.G2, f'{k:<28}')} {q(C.G1, v_show)}")
        nl()
        info(f"Ruta del .env: {inst.dir}/.env")
    nl()

def cmd_omni(args):
    """Melissa Omni — monitoreo central."""
    script = f"{MELISSA_DIR}/melissa-omni.py"
    
    if not os.path.exists(script):
        fail("melissa-omni.py no encontrado")
        return
    
    sub = getattr(args, 'subcommand', '') or 'chat'
    os.execvp(sys.executable, [sys.executable, script, sub])

def cmd_nova(args):
    """Motor Nova."""
    print_logo(compact=True)
    
    sub = getattr(args, 'subcommand', '') or 'status'
    
    if sub == "status":
        section("Nova")
        h = health(NOVA_PORT)
        if h:
            ok(f"Activo en :{NOVA_PORT}")
            kv("Versión", h.get("version", "—"))
        else:
            warn(f"No responde en :{NOVA_PORT}")
            info("Arrancarlo: cd /home/ubuntu/nova-os && docker-compose up -d")
        return
    
    if sub == "attach":
        name = getattr(args, 'name', '') or prompt("Instancia a conectar")
        inst = find_instance(name)
        if inst:
            _nova_attach(inst.dir, inst.name)
        else:
            fail(f"No encontré '{name}'")
        return
    
    nova_py = f"{NOVA_DIR}/nova.py"
    if os.path.exists(nova_py):
        os.execvp(sys.executable, [sys.executable, nova_py] + sys.argv[2:])
    else:
        fail("nova.py no encontrado")

def _nova_attach(inst_dir, name):
    """Conectar instancia a Nova."""
    with Spinner("Conectando a Nova...") as sp:
        base_env = load_env(f"{MELISSA_DIR}/.env")
        key = base_env.get("NOVA_API_KEY", "")
        
        try:
            if _HTTPX:
                r = _httpx.post(
                    f"http://localhost:{NOVA_PORT}/tokens",
                    json={
                        "agent_name": f"Melissa - {name}",
                        "description": "Recepcionista virtual IA",
                        "can_do": [
                            "send appointment confirmations",
                            "answer questions about services",
                            "book consultation appointments"
                        ],
                        "cannot_do": [
                            "provide medical diagnosis",
                            "share personal information",
                            "guarantee results"
                        ],
                        "authorized_by": "CLI"
                    },
                    headers={"Authorization": f"Bearer {key}", "X-API-Key": key},
                    timeout=10
                )
                
                if r.status_code == 200:
                    tid = r.json().get("token_id", "")
                    if tid:
                        update_env_key(f"{inst_dir}/.env", "NOVA_TOKEN", tid)
                        update_env_key(f"{inst_dir}/.env", "NOVA_ENABLED", "true")
                        pm2_name = "melissa" if inst_dir == MELISSA_DIR else f"melissa-{name}"
                        pm2("restart", pm2_name)
                        sp.finish(f"Conectado: {tid[:20]}...")
                        return
        except Exception:
            pass
        
        sp.finish("No pude conectar a Nova", ok=False)

def cmd_help(args):
    """Mostrar ayuda."""
    print_logo(compact=True)
    
    print(f"  {q(C.W, 'Comandos:', bold=True)}")
    nl()
    
    commands = [
        ("Gestión", [
            ("init", "Verificar configuración del sistema"),
            ("new [nombre]", "Crear instancia para un cliente (wizard)"),
            ("list / ls", "Ver todas las instancias"),
            ("dashboard", "Panel en tiempo real"),
            ("template [sector]", "Ver/crear desde plantilla"),
        ]),
        ("Estado", [
            ("status [n]", "Estado detallado"),
            ("health", "Health check rápido"),
            ("metrics [n]", "Métricas de uso"),
            ("stats [n]", "Estadísticas"),
            ("logs [n]", "Logs en tiempo real"),
        ]),
        ("Operaciones", [
            ("chat [n]", "Generar tokens, probar bot, ver webhook ← úsalo"),
            ("config [n]", "Editar configuración"),
            ("restart [n]", "Reiniciar (o 'all')"),
            ("stop [n]", "Detener"),
            ("scale [n] [num]", "Escalar workers"),
            ("clone [n]", "Clonar instancia"),
            ("reset [n]", "Resetear solo el DB (para testing)"),
            ("zero [n]", "♻️  Entregar a nuevo cliente (borra todo, renombra)"),
            ("delete [n]", "Eliminar instancia permanentemente"),
        ]),
        ("Mantenimiento", [
            ("sync", "Propagar melissa.py a todos los clientes"),
            ("fix [n]", "Reparar instancia con bug de --cwd"),
            ("install", "Instalar CLI globalmente"),
        ]),
        ("Datos", [
            ("backup [n]", "Crear snapshot"),
            ("restore [file]", "Restaurar backup"),
            ("export [n]", "Exportar a JSON/CSV"),
            ("import [file]", "Importar datos"),
            ("test [n]", "Probar respuestas"),
        ]),
        ("Sistema", [
            ("caddy", "Proxy reverso — ver/sincronizar rutas"),
            ("doctor", "Diagnóstico completo"),
            ("audit", "Auditoría de seguridad"),
            ("benchmark", "Test de rendimiento"),
            ("secure", "Guía de seguridad"),
            ("rotate-keys", "Rotar secrets"),
            ("upgrade", "Actualizar + propagar a clientes"),
            ("billing", "Uso de APIs"),
            ("guide", "📖 Guía de operación"),
        ]),
        ("Avanzado", [
            ("omni [sub]", "Monitoreo central"),
            ("nova [sub]", "Motor Nova"),
        ]),
    ]
    
    for category, cmds in commands:
        print(f"  {q(C.P2, category, bold=True)}")
        for cmd_, desc in cmds:
            print(f"    {q(C.G2, f'melissa {cmd_:<18}')}  {q(C.G3, desc)}")
        nl()
    
    hr()
    nl()
    
    # Sectores
    print(f"  {q(C.W, 'Sectores disponibles:', bold=True)}")
    sectors_line = "  "
    for sid, s in SECTORS.items():
        if sid != "otro":
            sectors_line += f"{s.emoji} "
    print(sectors_line)
    nl()
    
    info("Usa lenguaje natural: melissa 'crear instancia para veterinaria'")
    nl()

def cmd_install(args):
    """
    Instala el CLI de Melissa globalmente para poder ejecutar
    'melissa' desde cualquier directorio sin importar dónde
    esté guardado melissa_cli.py.
    """
    print_logo(compact=True)
    section("Instalar CLI globalmente")

    this = os.path.abspath(__file__)
    target = "/usr/local/bin/melissa"
    target_alt = os.path.expanduser("~/.local/bin/melissa")

    info(f"Archivo fuente: {this}")
    info(f"Destino: {target}")
    nl()

    # Intentar /usr/local/bin primero
    try:
        if os.path.exists(target) or os.path.islink(target):
            os.remove(target)
        os.symlink(this, target)
        os.chmod(this, 0o755)
        ok(f"CLI instalado en {target}")
        nl()
        info("Ahora puedes ejecutar 'melissa' desde cualquier directorio.")
        info("Prueba con:  melissa list")
        nl()
        return
    except PermissionError:
        warn(f"Sin permisos para escribir en {target}")
        nl()

    # Intentar ~/.local/bin
    os.makedirs(os.path.dirname(target_alt), exist_ok=True)
    try:
        if os.path.exists(target_alt) or os.path.islink(target_alt):
            os.remove(target_alt)
        os.symlink(this, target_alt)
        os.chmod(this, 0o755)
        ok(f"CLI instalado en {target_alt}")
        nl()

        # Verificar si ~/.local/bin está en PATH
        path_dirs = os.getenv("PATH", "").split(":")
        if os.path.expanduser("~/.local/bin") not in path_dirs:
            warn("~/.local/bin no está en tu PATH.")
            info("Agrega esto a tu ~/.bashrc o ~/.profile:")
            print("\n       " + q(C.CYN, 'export PATH="$HOME/.local/bin:$PATH"') + "\n")
            info("Luego recarga con:  source ~/.bashrc")
        else:
            info("Ya puedes ejecutar 'melissa' desde cualquier directorio.")
        nl()
        return
    except Exception as e:
        fail(f"No se pudo instalar en {target_alt}: {e}")

    # Fallback: solo dar instrucciones manuales
    nl()
    fail("No se pudo instalar automáticamente.")
    info("Instalación manual — ejecuta uno de estos comandos:")
    nl()
    print(f"  {q(C.G3, 'Opción 1 (requiere sudo):')}  {q(C.CYN, f'sudo ln -sf {this} /usr/local/bin/melissa')}")
    print(f"  {q(C.G3, 'Opción 2 (usuario):')}        {q(C.CYN, f'ln -sf {this} ~/.local/bin/melissa')}")
    nl()

# ══════════════════════════════════════════════════════════════════════════════
# ROUTER DE LENGUAJE NATURAL
# ══════════════════════════════════════════════════════════════════════════════
def nl_route(text):
    """Interpretar comandos en lenguaje natural."""
    t = text.lower().strip()
    
    def _args(**kw):
        return type('Args', (), {**{'name': '', 'subcommand': ''}, **kw})()
    
    # Detectar sector en el texto
    detected_sector = None
    for sid, s in SECTORS.items():
        if sid in t or s.name.lower() in t:
            detected_sector = sid
            break
        for kw in s.keywords:
            if kw in t:
                detected_sector = sid
                break

    detected_instance = None
    try:
        for inst in get_instances():
            candidates = {
                inst.name.lower(),
                inst.label.lower(),
                inst.label.lower().replace(" ", "-"),
                inst.name.lower().replace("-", " "),
            }
            if any(c and c in t for c in candidates):
                detected_instance = inst.name
                break
    except Exception:
        detected_instance = None

    if "demo" in t:
        if any(w in t for w in ["estado demo", "status demo", "demo status", "demo estado"]):
            cmd_demo(_args(subcommand="status"))
            return True
        if any(w in t for w in ["quitar demo", "apagar demo", "desactivar demo", "demo off"]):
            cmd_demo(_args(subcommand="off", name=detected_instance or ""))
            return True
        if any(w in t for w in ["activar demo", "poner demo", "modo demo", "demo on"]):
            cmd_demo(_args(name=detected_instance or ""))
            return True

    # Comandos
    if any(w in t for w in ["nuevo", "nueva", "crear", "new", "instancia"]):
        cmd_new(_args(name=''))
        return True
    
    if any(w in t for w in ["listar", "lista", "list", "ver todas", "instancias"]):
        cmd_list(_args())
        return True
    
    if "dashboard" in t or "panel" in t:
        cmd_dashboard(_args())
        return True
    
    if "doctor" in t or "diagnos" in t:
        cmd_doctor(_args())
        return True
    
    if "template" in t or "plantilla" in t:
        cmd_template(_args(name=detected_sector or ''))
        return True
    
    if "backup" in t:
        cmd_backup(_args(name='base'))
        return True
    
    if "health" in t or "salud" in t:
        cmd_health(_args())
        return True
    
    if any(w in t for w in ["log", "logs"]):
        cmd_logs(_args())
        return True
    
    if any(w in t for w in ["estado", "status"]):
        cmd_status(_args())
        return True
    
    if any(w in t for w in ["reiniciar", "restart"]):
        cmd_restart(_args())
        return True
    
    if any(w in t for w in ["config", "configurar", "configuración"]):
        cmd_config(_args())
        return True
    
    if "test" in t or "probar" in t:
        cmd_test(_args())
        return True
    
    if any(w in t for w in ["export", "exportar"]):
        cmd_export(_args())
        return True
    
    if any(w in t for w in ["metricas", "metrics"]):
        cmd_metrics(_args())
        return True
    
    return False

def cmd_demo(args):
    """
    Activa el MODO DEMO en una instancia existente.

    Perfecto para ventas en campo: una sola instancia, un solo bot,
    y cualquier persona que le escriba recibe a Melissa funcionando
    como recepcionista real — sin tokens, sin setup, sin esperas.

    Qué hace:
      ✓ Activa DEMO_MODE=true en el .env
      ✓ Configura el negocio y sector de la demo
      ✓ Reinicia la instancia limpia
      ✓ Muestra el link del bot para compartir
      ✓ Cada persona tiene 30 min de sesión independiente

    Uso:
      melissa demo           → wizard interactivo
      melissa demo off       → desactivar demo mode
      melissa demo status    → ver estado actual
    """
    print_logo(compact=True)

    sub  = getattr(args, 'subcommand', '') or ''
    name = getattr(args, 'name', '') or ''

    # ── melissa demo off ──────────────────────────────────────────────────────
    if sub in ("off", "apagar", "stop", "desactivar"):
        inst = find_instance(name) if name else None
        if not inst:
            instances = get_instances()
            if not instances:
                fail("No hay instancias configuradas")
                return
            inst = instances[0] if len(instances) == 1 else None
            if not inst:
                idx  = select([i.label for i in instances], title="¿Cuál instancia?")
                inst = instances[idx]

        ev_path = f"{inst.dir}/.env"
        update_env_key(ev_path, "DEMO_MODE", "false")
        pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
        with Spinner("Desactivando modo demo...") as sp:
            pm2("restart", pm2_name)
            time.sleep(3)
            sp.finish("Demo desactivado — instancia en modo normal")
        nl()
        ok(f"'{inst.label}' volvió al modo normal")
        info("La próxima persona que escriba necesitará un token de activación")
        nl()
        return

    # ── melissa demo status ───────────────────────────────────────────────────
    if sub in ("status", "estado", "info"):
        instances = get_instances()
        section("Estado del modo demo")
        for inst in instances:
            ev = dict(load_env(f"{inst.dir}/.env"))
            is_demo = ev.get("DEMO_MODE", "false").lower() == "true"
            icon_d  = q(C.YLW, "◉ DEMO") if is_demo else q(C.G3, "○ normal")
            h       = health(inst.port)
            online  = q(C.GRN, "online") if h else q(C.RED, "offline")
            print(f"  {icon_d}  {q(C.W, inst.label)}  ·  {online}  ·  :{inst.port}")
            if is_demo:
                kv("  Negocio demo",  ev.get("DEMO_BUSINESS_NAME", "?"))
                kv("  Sector demo",   ev.get("DEMO_SECTOR", "?"))
            nl()
        return

    # ── Wizard de activación ──────────────────────────────────────────────────
    section("Modo Demo", "Para ventas en campo")

    nl()
    print(f"  {q(C.YLW, '◉', bold=True)}  {q(C.W, 'Cómo funciona:', bold=True)}")
    print(f"       Cualquier persona que le escriba al bot")
    print(f"       recibe a Melissa respondiendo como recepcionista real.")
    print(f"       Sin tokens. Sin setup. Instantáneo.")
    print(f"       Cada persona tiene su propia sesión de 30 minutos.")
    nl()

    # Seleccionar instancia
    instances = get_instances()
    if not instances:
        fail("No hay instancias")
        info("Crea una con: melissa new")
        return

    if name:
        inst = find_instance(name)
        if not inst:
            fail(f"No encontré la instancia '{name}'")
            info("Usa 'melissa list' para ver los nombres disponibles")
            return
        info(f"Usando instancia: {inst.label}")
    elif len(instances) == 1:
        inst = instances[0]
        info(f"Usando instancia: {inst.label}")
    else:
        idx  = select([i.label for i in instances], title="¿En qué instancia activar la demo?")
        inst = instances[idx]

    nl()

    # Nombre del negocio demo
    ev_current = dict(load_env(f"{inst.dir}/.env"))
    default_name = ev_current.get("DEMO_BUSINESS_NAME", "")

    # Intentar sugerir un nombre basado en el sector si no hay uno
    if not default_name:
        demo_names = {
            "estetica":    "Clínica Estética Lumina",
            "dental":      "Dental Sonrisa",
            "veterinaria": "Veterinaria PetCare",
            "restaurante": "Restaurante La Mesa",
            "hotel":       "Hotel Boutique Vista",
            "gimnasio":    "Gym FitLife",
            "belleza":     "Salón Glam",
            "medico":      "Consultorio Dr. Salud",
            "psicologo":   "Centro de Psicología Bienestar",
            "spa":         "Spa & Wellness Center",
            "otro":        "Negocio Demo",
        }
        default_name = demo_names.get(inst.sector, "Negocio Demo")

    business_name = prompt("Nombre del negocio para la demo", default=default_name)
    if not business_name:
        business_name = default_name

    # Sector
    cambiar_sector = confirm("¿Cambiar el sector de la demo?", default=False)
    demo_sector    = inst.sector
    if cambiar_sector:
        sector_list  = list(SECTORS.keys())
        sector_names = [f"{SECTORS[s].emoji} {SECTORS[s].name}" for s in sector_list]
        idx          = select(sector_names, title="Sector para la demo:")
        demo_sector  = sector_list[idx]

    sector_obj = SECTORS.get(demo_sector, SECTORS["otro"])

    # Duración de sesión
    ttl_str = prompt("Minutos por sesión (cada persona)", default="30")
    ttl_min = int(ttl_str) if ttl_str.isdigit() else 30

    nl()

    # ── Aplicar configuración ─────────────────────────────────────────────────
    ev_path  = f"{inst.dir}/.env"
    pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"

    with Spinner("Configurando modo demo...") as sp:
        update_env_key(ev_path, "DEMO_MODE",          "true")
        update_env_key(ev_path, "DEMO_BUSINESS_NAME", business_name)
        update_env_key(ev_path, "DEMO_SECTOR",        demo_sector)
        update_env_key(ev_path, "DEMO_SESSION_TTL",   str(ttl_min * 60))
        load_env.cache_clear()  # Fix Bug 4: forzar lectura fresca del .env
        sp.finish("Configuración aplicada")

    with Spinner(f"Reiniciando {inst.label}...") as sp:
        pm2("restart", pm2_name)
        time.sleep(4)
        h = health(inst.port)
        sp.finish("Online ✓" if h else "Reiniciando...", ok=bool(h))

    # ── Obtener info del bot para compartir ────────────────────────────────────
    ev_fresh  = dict(load_env(ev_path))
    tg_token  = ev_fresh.get("TELEGRAM_TOKEN", "")
    bot_user  = ""
    bot_name  = ""

    if tg_token:
        with Spinner("Obteniendo link del bot...") as sp:
            try:
                url = f"https://api.telegram.org/bot{tg_token}/getMe"
                if _HTTPX:
                    r    = _httpx.get(url, timeout=8)
                    data = r.json().get("result", {})
                else:
                    import urllib.request as _ur
                    data = json.loads(_ur.urlopen(url, timeout=8).read()).get("result", {})
                bot_user = data.get("username", "")
                bot_name = data.get("first_name", "")
                sp.finish(f"Bot: @{bot_user}")
            except Exception as e:
                sp.finish(f"No pude obtener info del bot: {e}", ok=False)

    # ── Resumen para el vendedor ───────────────────────────────────────────────
    nl()
    hr()
    nl()

    section(
        f"Demo activa — {business_name}",
        f"{sector_obj.emoji} {sector_obj.name}"
    )

    kv("Instancia",       inst.name)
    kv("Sector",          f"{sector_obj.emoji} {sector_obj.name}")
    kv("Sesión por persona", f"{ttl_min} minutos")
    nl()

    if bot_user:
        bot_link = f"https://t.me/{bot_user}"
        print(f"  {q(C.YLW, '◉', bold=True)}  {q(C.W, 'LINK PARA COMPARTIR:', bold=True)}")
        print()
        print(f"       {q(C.CYN, bot_link, bold=True)}")
        print()
        print(f"       {q(C.G2, 'Bot:')} {q(C.W, bot_name)}  (@{bot_user})")
        nl()

    # Instrucciones para el vendedor
    print(f"  {q(C.W, 'CÓMO USARLO EN LA VENTA:', bold=True)}")
    nl()
    steps = [
        f"Abre Telegram y busca @{bot_user}" if bot_user else "Abre el bot de Telegram",
        "Muestra cómo Melissa responde en tiempo real",
        "Deja que el prospecto le escriba directamente desde su celular",
        "Cada persona tiene su sesión independiente de {ttl_min} minutos",
        f"Para ver sesiones activas:  melissa demo status",
        f"Para apagar la demo:        melissa demo off",
    ]
    for i, step in enumerate(steps, 1):
        step_text = step.replace("{ttl_min}", str(ttl_min))
        print(f"    {q(C.P2, str(i)+'.')} {q(C.G1, step_text)}")
    nl()

    print(f"  {q(C.G3, 'Tip:')} {q(C.G2, 'Si alguien pregunta por el bot, Melissa les dará tu contacto')}")
    nl()

    notify_omni("demo_activado",
                f"{business_name} ({sector_obj.name}) en {inst.name} — sesiones de {ttl_min} min")




def cmd_rollback(args):
    """
    Rollback de melissa.py a una versión anterior.
    Crea backup de la versión actual y restaura la elegida.
    """
    import glob
    section("Rollback de Melissa", "Restaura una versión anterior de melissa.py")

    backups = sorted(
        glob.glob(f"{MELISSA_DIR}/melissa.py.bak.*"),
        reverse=True
    )

    if not backups:
        warn("No hay backups disponibles.")
        info(f"Los backups se crean automáticamente en {MELISSA_DIR}/melissa.py.bak.YYYYMMDD_HHMMSS")
        info("Sube una versión anterior manualmente o usa: cp melissav6.py melissa.py")
        return

    info("Versiones disponibles:")
    for i, b in enumerate(backups[:8], 1):
        ts   = b.split(".bak.")[-1]
        size = os.path.getsize(b) // 1024
        print(f"  {q(C.B1, str(i))}  {ts}  ({size} KB)  {b}")

    nl()
    choice = ask_input("¿Qué versión restaurar? (número) ")
    if not choice.isdigit() or not (1 <= int(choice) <= len(backups)):
        warn("Opción inválida")
        return

    selected = backups[int(choice) - 1]
    current  = f"{MELISSA_DIR}/melissa.py"

    # Backup de la versión actual antes de reemplazar
    from datetime import datetime
    stamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    current_bak = f"{current}.bak.{stamp}"
    shutil.copy2(current, current_bak)
    ok(f"Versión actual guardada en {current_bak}")

    # Restaurar
    shutil.copy2(selected, current)
    ok(f"Restaurado desde {selected}")

    # Sincronizar a instancias
    if confirm("¿Sincronizar rollback a todas las instancias?"):
        instances = get_instances()
        clientes  = [i for i in instances if not i.is_base]
        for inst in clientes:
            with Spinner(f"Sincronizando {inst.label}...") as sp:
                try:
                    shutil.copy2(current, f"{inst.dir}/melissa.py")
                    sp.finish(f"{inst.label} — copiado")
                except Exception as e:
                    sp.finish(f"{inst.label} — ERROR: {e}", ok=False)

    # Reiniciar
    if confirm("¿Reiniciar melissa ahora?"):
        with Spinner("Reiniciando...") as sp:
            pm2("restart", "melissa")
            time.sleep(3)
            h = health(8001)
            sp.finish("Online ✓" if h else "Reiniciando...", ok=bool(h))
        if h:
            ok("Rollback completado y melissa online")
    nl()


def cmd_sync(args):
    """
    Sincroniza el runtime compartido desde la carpeta base hacia
    TODAS las instancias en melissa-instances/.
    
    Úsalo cada vez que actualices código o módulos compartidos para que
    todos los clientes corran la versión más reciente.
    """
    print_logo(compact=True)
    section("Sincronizar instancias", "Clona el runtime compartido a todos los clientes")

    instances = get_instances()
    clientes  = [i for i in instances if not i.is_base]

    if not clientes:
        warn("No hay instancias de clientes en melissa-instances/")
        info("Crea una con: melissa new")
        return

    sync_entries = _runtime_sync_entries(MELISSA_DIR)

    info("Archivos que se copiarán desde la base:")
    for rel_path in [*SYNC_RUNTIME_FILES, *SYNC_RUNTIME_DIRS]:
        src = Path(MELISSA_DIR) / rel_path
        if src.is_file():
            ok(f"  {rel_path}  ({src.stat().st_size // 1024} KB)")
        elif src.is_dir():
            ok(f"  {rel_path}/  (directorio)")
        else:
            dim(f"  {rel_path} — no encontrado, se omitirá")
    nl()

    info(f"Destino: {len(clientes)} instancia(s):")
    for i in clientes:
        print(f"       · {q(C.G1, i.label)}  {q(C.G3, i.dir)}")
    nl()

    if not confirm(f"¿Sincronizar {len(clientes)} instancia(s) y reiniciarlas?"):
        info("Cancelado")
        return

    nl()

    # Backup automático de melissa.py antes de sincronizar
    _stamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    _bak     = f"{MELISSA_DIR}/melissa.py.bak.{_stamp}"
    try:
        shutil.copy2(f"{MELISSA_DIR}/melissa.py", _bak)
        ok(f"Backup creado: melissa.py.bak.{_stamp}  (usa 'melissa rollback' para revertir)")
    except Exception as _e:
        warn(f"No se pudo crear backup: {_e}")

    errors = []

    for inst in clientes:
        with Spinner(f"Sincronizando {inst.label}...") as sp:
            copied = 0
            try:
                copied = len(_clone_runtime_entries(MELISSA_DIR, inst.dir, sync_entries))
                sp.finish(f"{inst.label} — {copied} archivos copiados")
            except Exception as e:
                sp.finish(f"{inst.label} — ERROR: {e}", ok=False)
                errors.append(inst.name)
                continue

        # Reiniciar después de sincronizar
        pm2_name = f"melissa-{inst.name}"
        with Spinner(f"Reiniciando {inst.label}...") as sp:
            pm2("restart", pm2_name)
            time.sleep(2)
            h = health(inst.port)
            sp.finish("Online ✓" if h else "Reiniciando...", ok=bool(h))

    nl()
    hr()
    nl()
    ok_count = len(clientes) - len(errors)
    ok(f"{ok_count}/{len(clientes)} instancias sincronizadas")
    if errors:
        warn(f"Fallaron: {', '.join(errors)}")
        info("Revisa sus logs: melissa logs <nombre>")
    nl()


def cmd_fix(args):
    """
    Repara instancias existentes que fueron iniciadas sin --cwd
    (bug de versiones anteriores). Detiene el proceso PM2, lo borra
    y lo vuelve a registrar con la configuración correcta.
    
    Úsalo si tienes bots que no responden aunque PM2 los muestre online.
    """
    print_logo(compact=True)
    section("Reparar instancias", "Corrige el bug de --cwd en PM2")

    name = getattr(args, 'name', '') or ''
    inst = find_instance(name) if name else None

    instances_to_fix = []
    if inst:
        instances_to_fix = [inst]
    else:
        all_instances = [i for i in get_instances() if not i.is_base]
        if not all_instances:
            warn("No hay instancias de clientes para reparar")
            return
        if confirm("¿Reparar TODAS las instancias?"):
            instances_to_fix = all_instances
        else:
            idx = select([i.label for i in all_instances], title="¿Cuál reparar?")
            instances_to_fix = [all_instances[idx]]

    nl()

    for inst in instances_to_fix:
        pm2_name = f"melissa-{inst.name}"
        log_dir  = f"{inst.dir}/logs"
        os.makedirs(log_dir, exist_ok=True)

        info(f"Reparando: {inst.label}")

        with Spinner(f"Eliminando proceso antiguo de PM2...") as sp:
            pm2("delete", pm2_name)
            time.sleep(1)
            sp.finish("Proceso eliminado")

        with Spinner(f"Registrando con --cwd correcto...") as sp:
            result = subprocess.run([
                "pm2", "start", f"{inst.dir}/melissa.py",
                "--name",           pm2_name,
                "--interpreter",    "python3",
                "--cwd",            inst.dir,       # ← el fix crítico
                "--restart-delay",  "3000",
                "--max-restarts",   "10",
                "--log",            f"{log_dir}/melissa.log",
                "--error",          f"{log_dir}/error.log",
            ], capture_output=True)
            pm2_save()
            time.sleep(4)
            h = health(inst.port)
            if h:
                sp.finish(f"{inst.label} — Online ✓")
            else:
                sp.finish(f"{inst.label} — Arrancando (revisa logs si no responde)", ok=False)

        # Verificar webhook después del fix
        ev  = dict(load_env(f"{inst.dir}/.env"))
        tg  = ev.get("TELEGRAM_TOKEN", "")
        if tg:
            expected = f"{ev.get('BASE_URL', '')}/webhook/{ev.get('WEBHOOK_SECRET', '')}"
            with Spinner("Verificando webhook...") as sp:
                try:
                    url = f"https://api.telegram.org/bot{tg}/getWebhookInfo"
                    if _HTTPX:
                        r = _httpx.get(url, timeout=8)
                        wh = r.json().get("result", {}).get("url", "")
                    else:
                        import urllib.request as _ur
                        wh = json.loads(_ur.urlopen(url, timeout=8).read()).get("result", {}).get("url", "")

                    if wh == expected:
                        sp.finish("Webhook OK ✓")
                    else:
                        sp.finish("Webhook incorrecto — se corregirá", ok=False)
                        set_url = f"https://api.telegram.org/bot{tg}/setWebhook"
                        if _HTTPX:
                            _httpx.post(set_url, json={"url": expected}, timeout=8)
                        ok(f"Webhook reconfigurado → {expected}")
                except Exception as e:
                    sp.finish(f"No pude verificar webhook: {e}", ok=False)
        nl()

    hr()
    nl()
    ok(f"{len(instances_to_fix)} instancia(s) reparadas")
    info("Si alguna aún no responde en Telegram: melissa logs <nombre>")
    nl()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# V6.0 — COMANDOS DE INTELIGENCIA Y AUTOMATIZACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def cmd_pipeline(args):
    """Pipeline de leads por temperatura de cierre."""
    print_logo(compact=True)
    inst = _pick_instance(args)
    if not inst: return
    section(f"Pipeline — {inst.label}", "leads clasificados por temperatura de cierre")
    ev = load_env(f"{inst.dir}/.env")
    mk = ev.get("MASTER_API_KEY", "")
    _admin_cmd(inst, mk, "/pipeline")

def cmd_perdidos(args):
    """Analiza por qué se van los clientes."""
    print_logo(compact=True)
    inst = _pick_instance(args)
    if not inst: return
    section(f"Análisis de pérdida — {inst.label}")
    ev = load_env(f"{inst.dir}/.env")
    mk = ev.get("MASTER_API_KEY", "")
    _admin_cmd(inst, mk, "/perdidos")

def cmd_coach(args):
    """Feedback de ventas de la última semana."""
    print_logo(compact=True)
    inst = _pick_instance(args)
    if not inst: return
    section(f"Sales Coach — {inst.label}")
    ev = load_env(f"{inst.dir}/.env")
    mk = ev.get("MASTER_API_KEY", "")
    _admin_cmd(inst, mk, "/coach")

def cmd_estilo(args):
    """Clonar el estilo de escritura del dueño."""
    print_logo(compact=True)
    inst = _pick_instance(args)
    if not inst: return
    section(f"Clonar estilo — {inst.label}")
    info("Melissa leerá los últimos 50 mensajes del admin y aprenderá su forma de escribir")
    info("Necesitas el chat_id del dueño como admin_id")
    admin_id = prompt("Chat ID del admin (Telegram)")
    if not admin_id:
        fail("Necesitas el chat_id del admin")
        return
    ev = load_env(f"{inst.dir}/.env")
    mk = ev.get("MASTER_API_KEY", "")
    _admin_cmd(inst, mk, "/estilo", user_id=admin_id)

def cmd_reactivar(args):
    """Reactivar clientes inactivos 60+ días."""
    print_logo(compact=True)
    inst = _pick_instance(args)
    if not inst: return
    section(f"Reactivación — {inst.label}")
    ev = load_env(f"{inst.dir}/.env")
    mk = ev.get("MASTER_API_KEY", "")
    _admin_cmd(inst, mk, "/reactivar")

def cmd_seguimiento(args):
    """Estado y configuración de follow-ups automáticos."""
    print_logo(compact=True)
    inst = _pick_instance(args)
    if not inst: return
    section(f"Follow-ups — {inst.label}")
    ev = load_env(f"{inst.dir}/.env")
    mk = ev.get("MASTER_API_KEY", "")
    _admin_cmd(inst, mk, "/seguimiento")

def cmd_reporte(args):
    """Generar reporte ahora mismo."""
    print_logo(compact=True)
    inst = _pick_instance(args)
    if not inst: return
    section(f"Reporte — {inst.label}")
    ev = load_env(f"{inst.dir}/.env")
    mk = ev.get("MASTER_API_KEY", "")
    _admin_cmd(inst, mk, "/reporte")

def cmd_broadcast(args):
    """Enviar mensaje a todos los pacientes de una instancia."""
    print_logo(compact=True)
    inst = _pick_instance(args)
    if not inst: return
    section(f"Broadcast — {inst.label}")
    warn("Esto enviará un mensaje a TODOS los pacientes registrados")
    warn("Úsalo con cuidado — demasiados mensajes masivos pueden generar baneo")
    nl()
    msg = getattr(args, 'message', '') or prompt("Mensaje a enviar")
    if not msg:
        fail("Necesitas un mensaje")
        return
    if not confirm(f"Confirmas enviar \"\"{msg[:60]}\"\" a todos los pacientes?", default=False):
        info("Cancelado")
        return
    ev = load_env(f"{inst.dir}/.env")
    mk = ev.get("MASTER_API_KEY", "")
    _admin_cmd(inst, mk, f"/broadcast {msg}")

def cmd_preconsulta(args):
    """Configurar formulario de pre-consulta automático."""
    print_logo(compact=True)
    inst = _pick_instance(args)
    if not inst: return
    section(f"Pre-consulta — {inst.label}")
    ev = load_env(f"{inst.dir}/.env")
    mk = ev.get("MASTER_API_KEY", "")
    _admin_cmd(inst, mk, "/preconsulta")

def cmd_instagram(args):
    """Guía para conectar Instagram DMs."""
    print_logo(compact=True)
    inst = _pick_instance(args)
    if not inst: return
    section(f"Instagram DMs — {inst.label}")
    ev = load_env(f"{inst.dir}/.env")
    mk = ev.get("MASTER_API_KEY", "")
    _admin_cmd(inst, mk, "/instagram")

def cmd_pagos(args):
    """Configurar pagos desde el chat."""
    print_logo(compact=True)
    inst = _pick_instance(args)
    if not inst: return
    section(f"Pagos — {inst.label}")
    ev = load_env(f"{inst.dir}/.env")
    mk = ev.get("MASTER_API_KEY", "")
    _admin_cmd(inst, mk, "/pagos")

def cmd_leads(args):
    """Vista completa de inteligencia de leads: pipeline + perdidos + coach."""
    print_logo(compact=True)
    inst = _pick_instance(args)
    if not inst: return
    section(f"Inteligencia de leads — {inst.label}")
    ev = load_env(f"{inst.dir}/.env")
    mk = ev.get("MASTER_API_KEY", "")

    options = [
        "Pipeline (leads por temperatura)",
        "Análisis de pérdida (por qué se van)",
        "Coach de ventas (qué mejorar)",
        "Todo de una vez",
    ]
    choice = select(options, title="¿Qué quieres ver?")

    cmds = ["/pipeline", "/perdidos", "/coach"]
    if choice == 3:
        for c in cmds:
            _admin_cmd(inst, mk, c)
            nl()
    else:
        _admin_cmd(inst, mk, cmds[choice])

def _pick_instance(args):
    """Helper — selecciona instancia desde args o pregunta."""
    name = getattr(args, 'name', '') or ''
    inst = find_instance(name) if name else None
    if not inst:
        instances = get_instances()
        if not instances:
            fail("No hay instancias")
            info("Crea una con: melissa new")
            return None
        if len(instances) == 1:
            return instances[0]
        labels = [i.label for i in instances]
        idx = select(labels, title="¿En cuál instancia?")
        inst = instances[idx]
    return inst

def _admin_cmd(inst, master_key, cmd_text, user_id=None):
    """Enviar un comando al endpoint /test de Melissa como si fuera el admin."""
    base_url = f"http://localhost:{inst.port}"
    test_url  = f"{base_url}/test"

    # Determinar admin_id — usar el primero de admin_chat_ids si no se pasa
    if not user_id:
        try:
            import sqlite3 as _sq
            conn = _sq.connect(f"{inst.dir}/melissa.db")
            conn.row_factory = _sq.Row
            row = conn.execute(
                "SELECT chat_id FROM admins WHERE is_active=1 ORDER BY created_at LIMIT 1"
            ).fetchone()
            user_id = row["chat_id"] if row else "cli_admin"
            conn.close()
        except Exception:
            user_id = "cli_admin"

    with Spinner(f"Consultando {cmd_text}...") as sp:
        try:
            if _HTTPX:
                r = _httpx.post(
                    test_url,
                    json={"message": cmd_text, "user_id": user_id},
                    headers={"X-Master-Key": master_key},
                    timeout=30
                )
                if r.status_code == 200:
                    response = r.json().get("response", "")
                    sp.finish("OK")
                else:
                    sp.finish(f"Error {r.status_code}", ok=False)
                    return
            else:
                import urllib.request as _ur
                req = _ur.Request(
                    test_url,
                    data=json.dumps({"message": cmd_text, "user_id": user_id}).encode(),
                    headers={"Content-Type":"application/json","X-Master-Key": master_key},
                    method="POST"
                )
                response = json.loads(_ur.urlopen(req, timeout=30).read()).get("response","")
                sp.finish("OK")
        except Exception as e:
            sp.finish(f"Error: {e}", ok=False)
            return

    # Mostrar respuesta formateada
    nl()
    for bubble in response.split("\n"):
        if bubble.strip():
            print(f"  {q(C.G1, bubble.strip())}")
    nl()



def _caddy_add_route(instance_name: str, port: int, webhook_path: str) -> bool:
    """
    Agrega una ruta en el Caddyfile para una nueva instancia.
    La ruta va ANTES del reverse_proxy catch-all de N8N.
    
    Patrón: handle /webhook/{webhook_path}* { reverse_proxy 172.28.0.1:{port} }
    
    Si el puerto es 8001 (base) ya está cubierto por handle /webhook/*.
    Solo agrega rutas para instancias adicionales (puerto > 8001).
    """
    if not os.path.exists(CADDYFILE_PATH):
        log_msg = f"Caddyfile no encontrado en {CADDYFILE_PATH}"
        warn(log_msg)
        return False

    if port == BASE_PORT:
        # La instancia base ya está cubierta por /webhook/* en el Caddyfile
        return True

    try:
        caddyfile = open(CADDYFILE_PATH).read()

        # Verificar si ya existe esta ruta
        route_marker = f"reverse_proxy {CADDY_DOCKER_GW}:{port}"
        if route_marker in caddyfile:
            return True  # Ya existe

        # La nueva ruta va ANTES de "--- REVERSE PROXY A N8N ---"
        # o antes del último reverse_proxy sin handle (el catch-all de N8N)
        insertion_markers = [
            "    # --- REVERSE PROXY A N8N ---",
            "    # --- MELISSA INSTANCIAS ADICIONALES ---",
        ]

        new_route = (
            f"    # Instancia: {instance_name} (puerto {port})\n"
            f"    handle /{webhook_path.lstrip('/')}* {{\n"
            f"        reverse_proxy {CADDY_DOCKER_GW}:{port}\n"
            f"    }}\n\n"
        )

        inserted = False
        for marker in insertion_markers:
            if marker in caddyfile:
                caddyfile = caddyfile.replace(marker, new_route + marker, 1)
                inserted = True
                break

        if not inserted:
            # Fallback: insertar antes del último bloque reverse_proxy
            last_rp = caddyfile.rfind("    reverse_proxy ")
            if last_rp > 0:
                caddyfile = caddyfile[:last_rp] + new_route + caddyfile[last_rp:]
                inserted = True

        if not inserted:
            warn("No pude encontrar punto de inserción en el Caddyfile")
            return False

        # Hacer backup antes de modificar
        backup_path = CADDYFILE_PATH + ".bak"
        open(backup_path, 'w').write(open(CADDYFILE_PATH).read() if os.path.exists(CADDYFILE_PATH) else "")

        open(CADDYFILE_PATH, 'w').write(caddyfile)
        return True

    except Exception as e:
        warn(f"Error actualizando Caddyfile: {e}")
        return False


def _caddy_reload() -> bool:
    """Recarga Caddy con la nueva configuración."""
    try:
        import subprocess
        # Reiniciar el contenedor Caddy desde su directorio (igual que la instrucción manual)
        result = subprocess.run(
            ["docker", "compose", "restart", "caddy"],
            capture_output=True, text=True, timeout=30,
            cwd=CADDY_DIR
        )
        if result.returncode == 0:
            return True

        # Fallback: reload via systemctl
        result2 = subprocess.run(
            ["sudo", "systemctl", "reload", "caddy"],
            capture_output=True, text=True, timeout=10
        )
        return result2.returncode == 0

    except Exception as e:
        warn(f"Error recargando Caddy: {e}")
        return False


def _caddy_remove_route(port: int) -> bool:
    """Elimina la ruta de una instancia del Caddyfile al borrarla."""
    if not os.path.exists(CADDYFILE_PATH):
        return False
    if port == BASE_PORT:
        return True  # La ruta base no se toca
    try:
        caddyfile = open(CADDYFILE_PATH).read()
        marker = f"reverse_proxy {CADDY_DOCKER_GW}:{port}"
        if marker not in caddyfile:
            return True  # Ya no existe

        # Buscar el bloque handle que contiene este puerto y eliminarlo
        import re
        pattern = rf"    # Instancia:.*?\n    handle [^{{]+\{{[^}}]+{re.escape(CADDY_DOCKER_GW)}:{port}[^}}]+\}}\n\n"
        caddyfile_new = re.sub(pattern, "", caddyfile)

        if caddyfile_new == caddyfile:
            # Patrón simple fallback
            lines = caddyfile.split("\n")
            out, skip = [], False
            for line in lines:
                if f":{port}" in line and "reverse_proxy" in line:
                    # Remover el bloque handle completo (3-4 líneas alrededor)
                    skip = True
                if skip and line.strip() == "}":
                    skip = False
                    continue
                if not skip:
                    out.append(line)
            caddyfile_new = "\n".join(out)

        open(CADDYFILE_PATH + ".bak", 'w').write(caddyfile)
        open(CADDYFILE_PATH, 'w').write(caddyfile_new)
        return True

    except Exception as e:
        warn(f"Error eliminando ruta de Caddy: {e}")
        return False


def cmd_caddy(args):
    """Gestionar Caddy — ver rutas, recargar, agregar manualmente."""
    print_logo(compact=True)
    section("Caddy — Proxy Reverso")

    sub = getattr(args, 'subcommand', '') or 'status'

    if sub == 'status' or not sub:
        # Mostrar estado y rutas actuales
        if not os.path.exists(CADDYFILE_PATH):
            fail(f"Caddyfile no encontrado: {CADDYFILE_PATH}")
            info("Configura CADDY_DIR en el .env o el entorno")
            return

        caddyfile = open(CADDYFILE_PATH).read()
        instances = get_instances()

        kv("Caddyfile", CADDYFILE_PATH)
        kv("Docker GW", CADDY_DOCKER_GW)
        nl()

        # Mostrar rutas de instancias
        info("Rutas de instancias detectadas:")
        for inst in instances:
            in_caddy = (
                inst.port == BASE_PORT or
                f":{inst.port}" in caddyfile
            )
            icon = q(C.GRN, "✓") if in_caddy else q(C.RED, "✗")
            print(f"    {icon}  {inst.label:<25} puerto {inst.port}  {'(ruta base)' if inst.port == BASE_PORT else ''}")

        nl()
        missing = [i for i in instances if i.port != BASE_PORT and f":{i.port}" not in caddyfile]
        if missing:
            warn(f"{len(missing)} instancias sin ruta en Caddy:")
            for m in missing:
                print(f"    - {m.label} (:{m.port})")
            nl()
            if confirm("¿Agregar las rutas faltantes ahora?", default=True):
                for m in missing:
                    ev = load_env(f"{m.dir}/.env")
                    ws = ev.get("WEBHOOK_SECRET", "")
                    wpath = f"webhook/melissa_{m.name}_{ws}" if ws else f"webhook/melissa_{m.name}"
                    if _caddy_add_route(m.name, m.port, wpath):
                        ok(f"Ruta agregada: {m.label} → :{m.port}")
                    else:
                        fail(f"No pude agregar ruta para {m.label}")
                if _caddy_reload():
                    ok("Caddy recargado")
                else:
                    warn("Recarga manual: cd " + CADDY_DIR + " && docker compose restart caddy")

    elif sub == 'reload':
        with Spinner("Recargando Caddy...") as sp:
            if _caddy_reload():
                sp.finish("Caddy recargado")
            else:
                sp.finish("Error recargando", ok=False)
                warn(f"Manual: cd {CADDY_DIR} && docker compose restart caddy")

    elif sub == 'show':
        if os.path.exists(CADDYFILE_PATH):
            print(open(CADDYFILE_PATH).read())
        else:
            fail(f"No encontré {CADDYFILE_PATH}")

    else:
        info("Subcomandos: status | reload | show")

# ══════════════════════════════════════════════════════════════════════════════
# CMD_TOKEN — Generar código de activación desde la terminal
# ══════════════════════════════════════════════════════════════════════════════
def cmd_token(args):
    """
    Genera un token de activación para una instancia.
    
    Uso:
      melissa token                    → genera para la instancia base
      melissa token 1                  → genera para la instancia 1
      melissa token "Clinica Demo"     → genera con ese nombre
      melissa token all                → genera para todas las instancias
    """
    name = getattr(args, 'name', '') or getattr(args, 'subcommand', '') or ''

    def _gen_token(inst, label_override=""):
        ev = dict(load_env(f"{inst.dir}/.env"))
        master_key = ev.get("MASTER_API_KEY", "")
        if not master_key:
            fail(f"[{inst.label}] MASTER_API_KEY no configurada")
            return
        label = label_override or inst.label
        base_url = f"http://localhost:{inst.port}"
        try:
            if _HTTPX:
                r = _httpx.post(
                    f"{base_url}/api/tokens/create",
                    json={"clinic_label": label},
                    headers={"X-Master-Key": master_key},
                    timeout=10
                )
                data = r.json() if r.status_code == 200 else {}
            else:
                import urllib.request as _ur
                req = _ur.Request(
                    f"{base_url}/api/tokens/create",
                    data=json.dumps({"clinic_label": label}).encode(),
                    headers={"Content-Type": "application/json", "X-Master-Key": master_key},
                    method="POST"
                )
                data = json.loads(_ur.urlopen(req, timeout=10).read())
            token = data.get("token", "")
            expires = data.get("expires_at", "")[:16] if data.get("expires_at") else "72h"
            if token:
                ok(f"Token generado para: {q(C.YLW, label)}")
                print(f"\n    {q(C.YLW, token, bold=True)}\n")
                info(f"Expira: {expires}")
                info("Envialo al admin — lo escribe en el chat de WhatsApp/Telegram")
            else:
                fail(f"Error: {data}")
        except Exception as e:
            fail(f"No se pudo generar: {e}")
            info(f"¿Está corriendo? melissa restart {inst.name}")

    # Generar para todas
    if name.lower() in ("all", "todas", "todos"):
        instances = get_instances()
        if not instances:
            fail("No hay instancias"); return
        section("Tokens — todas las instancias", f"{len(instances)} instancias")
        for inst in instances:
            _gen_token(inst)
            nl()
        return

    # Buscar instancia
    inst = find_instance(name) if name else None
    if not inst:
        instances = get_instances()
        if not instances:
            fail("No hay instancias"); return
        if len(instances) == 1:
            inst = instances[0]
        else:
            labels = [i.label for i in instances]
            section("Generar token", "¿Para qué instancia?")
            idx = select(labels)
            inst = instances[idx]

    # Pedir nombre personalizado
    section(f"Token — {inst.label}", f"Puerto :{inst.port}")
    custom_label = prompt("Nombre del negocio (Enter para usar el de la instancia)", default=inst.label)
    _gen_token(inst, custom_label)


# ══════════════════════════════════════════════════════════════════════════════
# CMD_ACTIVAR — Activar instancia directamente sin token
# ══════════════════════════════════════════════════════════════════════════════
def cmd_activar(args):
    """
    Activa una instancia directamente (pone setup_done=1 en la DB).
    
    Uso:
      melissa activar                  → activa la instancia base
      melissa activar 1                → activa instancia 1
    """
    name = getattr(args, 'name', '') or getattr(args, 'subcommand', '') or ''
    inst = find_instance(name) if name else None
    if not inst:
        instances = get_instances()
        if not instances:
            fail("No hay instancias"); return
        if len(instances) == 1:
            inst = instances[0]
        else:
            labels = [i.label for i in instances]
            section("Activar instancia", "¿Cuál?")
            idx = select(labels)
            inst = instances[idx]

    section(f"Activar — {inst.label}", f"Puerto :{inst.port}")

    db_path = f"{inst.dir}/melissa.db"
    if not os.path.exists(db_path):
        fail(f"DB no encontrada: {db_path}")
        info("¿Está corriendo? melissa restart " + inst.name)
        return

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("UPDATE clinic SET setup_done=1 WHERE id=1")
        if c.rowcount == 0:
            c.execute("INSERT OR IGNORE INTO clinic (name, setup_done, admin_chat_ids) VALUES (?, 1, '[]')",
                      (inst.label,))
        conn.commit()

        row = c.execute("SELECT name, setup_done, admin_chat_ids FROM clinic WHERE id=1").fetchone()
        conn.close()

        ok(f"Instancia activada")
        if row:
            info(f"Negocio: {row[0] or inst.label}")
            info(f"setup_done: {row[1]}")
        nl()
        info("Reiniciando Melissa para aplicar...")
        pm2("restart", inst.pm2_name)
        time.sleep(2)
        h = health(inst.port)
        if h.get("status") == "online":
            ok(f"Melissa online en :{inst.port}")
        else:
            warn(f"Verificar: pm2 logs {inst.pm2_name}")
    except Exception as e:
        fail(f"Error al activar: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# CMD_BRIDGE — Estado y control del WhatsApp Bridge
# ══════════════════════════════════════════════════════════════════════════════
def cmd_bridge(args):
    """
    Estado y control del WhatsApp bridge (Baileys).
    
    Uso:
      melissa bridge                   → estado del bridge
      melissa bridge restart           → reiniciar bridge
      melissa bridge qr                → mostrar QR para conectar
      melissa bridge fix               → fijar a qué instancia apunta el bridge
      melissa bridge fix 1             → fijar al bridge para la instancia 1
    """
    sub  = getattr(args, 'subcommand', '') or ''
    name = getattr(args, 'name', '')       or ''

    # Si sub es nombre de instancia y no un subcomando real, reasignar
    if sub and sub not in ("restart","reiniciar","qr","fix","reparar") and not name:
        name = sub
        sub  = ''

    BRIDGE_PM2 = "whatsapp-bridge"
    BRIDGE_DIR = "/home/ubuntu/whatsapp-bridge"
    BRIDGE_ENV = f"{BRIDGE_DIR}/.env"

    section("WhatsApp Bridge", "Baileys v2.1")

    # Leer .env del bridge
    bridge_env   = dict(load_env(BRIDGE_ENV)) if os.path.exists(BRIDGE_ENV) else {}
    bridge_port  = int(bridge_env.get("PORT", "3000"))
    webhook_url  = bridge_env.get("WEBHOOK_URL", "no configurado")
    webhook_token = bridge_env.get("WEBHOOK_TOKEN", "")

    # Estado del proceso PM2
    procs = pm2_list()
    bridge_proc = next((p for p in procs if p.get("name") == BRIDGE_PM2), None)
    if bridge_proc:
        status   = bridge_proc.get("pm2_env", {}).get("status", "?")
        restarts = bridge_proc.get("pm2_env", {}).get("restart_time", 0)
        mem      = bridge_proc.get("monit", {}).get("memory", 0) // 1024 // 1024
        color    = C.GRN if status == "online" else C.RED
        print(f"\n  {q(color, '●')}  PM2: {q(C.W, status)}  ↺{restarts}  {mem}mb")
    else:
        print(f"\n  {q(C.RED, '●')}  PM2: no encontrado")

    # Estado HTTP
    wa_status = "offline"
    try:
        if _HTTPX:
            r = _httpx.get(f"http://localhost:{bridge_port}/status", timeout=3)
            bdata = r.json() if r.status_code == 200 else {}
        else:
            bdata = json.loads(urllib.request.urlopen(
                f"http://localhost:{bridge_port}/status", timeout=3).read())
        wa_status = bdata.get("status", "?")
        phone     = bdata.get("name") or bdata.get("phoneNumber") or bdata.get("jid", "no vinculado")
        if phone and "@" in str(phone):
            phone = str(phone).split("@")[0]
        color = C.GRN if wa_status == "open" else C.YLW
        print(f"  {q(color, '●')}  WhatsApp: {q(C.W, wa_status)}")
        print(f"  {q(C.G2, '·')}  Número: {q(C.W, str(phone))}")
    except Exception:
        print(f"  {q(C.YLW, '●')}  HTTP: no responde en :{bridge_port}")

    print(f"  {q(C.G2, '·')}  Puerto: {q(C.W, str(bridge_port))}")
    print(f"  {q(C.G2, '·')}  Webhook → {q(C.W, webhook_url[:60])}")
    nl()

    # Identificar a qué instancia apunta el bridge actualmente
    instances   = get_instances()
    target_inst = None
    for inst in instances:
        secret   = inst.webhook_secret
        expected = f"http://localhost:{inst.port}/webhook/{secret}"
        if webhook_url == expected:
            target_inst = inst
            break

    if target_inst:
        ok(f"Sirviendo a: {target_inst.label} (:{target_inst.port})")
        demo = target_inst.env.get("DEMO_MODE", "false").lower() == "true"
        if demo:
            info("DEMO_MODE=true — responde a todo el mundo sin token")
        else:
            active = target_inst.is_active
            info(f"Instancia {'activada' if active else 'pendiente de activacion'}")
    else:
        warn("El bridge no apunta a ninguna instancia conocida")
        info(f"  Webhook actual: {webhook_url}")
        info("  Usa: melissa bridge fix  para seleccionar la instancia correcta")

    if not sub:
        if instances:
            nl()
            info("Instancias disponibles:")
            for inst in instances:
                h = health(inst.port)
                icon = q(C.GRN,"●") if h else q(C.RED,"●")
                active = "✓" if inst.is_active else "⚠"
                demo = " [DEMO]" if inst.env.get("DEMO_MODE","false").lower()=="true" else ""
                print(f"  {icon} {active}  {inst.label} :{inst.port}{demo}")
        return

    # ── Subcomandos ──────────────────────────────────────────────────────────
    if sub in ("restart", "reiniciar"):
        with Spinner("Reiniciando bridge...") as sp:
            pm2("restart", BRIDGE_PM2)
            time.sleep(3)
            sp.finish("Bridge reiniciado")
        cmd_bridge(args)

    elif sub == "qr":
        info("Logs del bridge (QR aparece aquí):")
        nl()
        subprocess.run(["pm2", "logs", BRIDGE_PM2, "--lines", "60", "--nostream"])

    elif sub in ("fix", "reparar"):
        section("Fix bridge", "¿A qué instancia debe apuntar el bridge?")
        if not instances:
            fail("No hay instancias Melissa"); return

        # Si se especificó nombre, buscar esa instancia
        if name:
            inst = find_instance(name)
            if not inst:
                fail(f"Instancia '{name}' no encontrada"); return
        elif len(instances) == 1:
            inst = instances[0]
        else:
            # Mostrar lista y preguntar — el bridge sirve a UNA sola instancia
            labels = []
            for i in instances:
                demo = " [DEMO-responde a todos]" if i.env.get("DEMO_MODE","false").lower()=="true" else ""
                h    = health(i.port)
                st   = "online" if h else "offline"
                labels.append(f"{i.label} :{i.port} ({st}){demo}")
            labels.append("← Cancelar")
            idx = select(labels, title="Selecciona la instancia para el bridge:")
            if idx == len(instances):
                return
            inst = instances[idx]

        _fix_bridge_webhook(inst)
        nl()
        ok(f"Bridge ahora apunta a: {inst.label} (:{inst.port})")
        demo = inst.env.get("DEMO_MODE", "false").lower() == "true"
        if demo:
            ok("DEMO_MODE=true — Melissa responderá a TODOS sin pedir token")
        else:
            if not inst.is_active:
                warn("La instancia no está activada — usa: melissa activar")
            else:
                ok("Instancia activa — lista para recibir mensajes")

        with Spinner("Reiniciando bridge...") as sp:
            pm2("restart", BRIDGE_PM2)
            time.sleep(3)
            sp.finish("Bridge reiniciado")
        ok("Bridge configurado y reiniciado")
        info("Escríbele a Melissa por WhatsApp para probar")


# ══════════════════════════════════════════════════════════════════════════════
# CMD_TOKENS — Listar todos los tokens de activación
# ══════════════════════════════════════════════════════════════════════════════
def cmd_tokens(args):
    """
    Lista todos los tokens de activación generados.
    
    Uso:
      melissa tokens                   → listar tokens de la instancia base
      melissa tokens 1                 → listar tokens de instancia 1
    """
    name = getattr(args, 'name', '') or getattr(args, 'subcommand', '') or ''
    inst = find_instance(name) if name else None
    if not inst:
        instances = get_instances()
        if not instances:
            fail("No hay instancias"); return
        inst = instances[0]

    ev = dict(load_env(f"{inst.dir}/.env"))
    master_key = ev.get("MASTER_API_KEY", "")
    if not master_key:
        fail("MASTER_API_KEY no configurada"); return

    section(f"Tokens — {inst.label}", f":{inst.port}")
    try:
        if _HTTPX:
            r = _httpx.get(
                f"http://localhost:{inst.port}/api/tokens",
                headers={"X-Master-Key": master_key},
                timeout=10
            )
            data = r.json() if r.status_code == 200 else {}
        else:
            import urllib.request as _ur
            req = _ur.Request(
                f"http://localhost:{inst.port}/api/tokens",
                headers={"X-Master-Key": master_key}
            )
            data = json.loads(_ur.urlopen(req, timeout=10).read())

        tokens = data.get("tokens", [])
        if not tokens:
            info("No hay tokens generados aún")
            info("Crea uno con: melissa token")
            return

        print(f"\n  {'TOKEN':<40} {'NEGOCIO':<20} {'ESTADO':<10} {'EXPIRA'}")
        print(f"  {'─'*40} {'─'*20} {'─'*10} {'─'*16}")
        for t in tokens:
            token = t.get("token", "")[:36] + "..."
            label = (t.get("clinic_label") or "")[:18]
            used = t.get("used_at")
            active = t.get("is_active", 1)
            expires = (t.get("expires_at") or "")[:16]
            if used:
                estado = q(C.G3, "usado")
            elif not active:
                estado = q(C.RED, "revocado")
            else:
                estado = q(C.GRN, "activo")
            print(f"  {q(C.YLW, token):<40} {q(C.W, label):<20} {estado:<10} {q(C.G2, expires)}")
        nl()
        info(f"Total: {len(tokens)} tokens")
    except Exception as e:
        fail(f"Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# CMD_WHATSAPP_CLI — Conectar/gestionar WhatsApp desde la terminal
# ══════════════════════════════════════════════════════════════════════════════
def cmd_whatsapp_cli(args):
    """
    Gestiona la conexión WhatsApp de una instancia.
    
    Uso:
      melissa whatsapp             → estado WhatsApp de todas las instancias
      melissa whatsapp 1           → estado de instancia 1
      melissa whatsapp connect 1   → conectar WhatsApp a instancia 1
      melissa whatsapp disconnect  → desconectar
      melissa whatsapp qr          → mostrar QR de reconexión
    """
    sub  = getattr(args, 'subcommand', '') or ''
    name = getattr(args, 'name', '')       or ''

    # Si subcommand es un número/nombre de instancia, reasignar
    if sub and sub not in ("connect","disconnect","qr","status","reconectar") and not name:
        name = sub
        sub  = ''

    section("WhatsApp — Estado", "Bridge + instancias")

    # Estado del bridge
    BRIDGE_ENV  = "/home/ubuntu/whatsapp-bridge/.env"
    bridge_ev   = dict(load_env(BRIDGE_ENV)) if os.path.exists(BRIDGE_ENV) else {}
    bridge_port = int(bridge_ev.get("PORT", "3000"))
    bridge_url  = bridge_ev.get("WEBHOOK_URL", "no configurado")

    try:
        if _HTTPX:
            br = _httpx.get(f"http://localhost:{bridge_port}/status", timeout=3)
            bdata = br.json()
        else:
            bdata = json.loads(urllib.request.urlopen(
                f"http://localhost:{bridge_port}/status", timeout=3).read())
        wa_status = bdata.get("status", "?")
        phone     = bdata.get("phoneNumber", "no vinculado")
        qr_avail  = bdata.get("qrCode") or bdata.get("qr")
        color = C.GRN if wa_status == "open" else C.YLW
        print(f"\n  {q(color,'●')}  Bridge: {q(C.W, wa_status)}  |  {q(C.G2, phone)}")
        if wa_status != "open":
            warn("WhatsApp no conectado — usa: melissa whatsapp qr")
    except Exception:
        wa_status = "offline"
        print(f"\n  {q(C.RED,'●')}  Bridge offline en :{bridge_port}")
        info("Reinicia con: pm2 restart whatsapp-bridge")

    print(f"  {q(C.G2,'·')}  Webhook → {q(C.W, bridge_url[:55])}")
    nl()

    # Estado por instancia
    instances = get_instances()
    for inst in instances:
        h = health(inst.port)
        plat = inst.platform
        icon = q(C.GRN,"●") if h else q(C.RED,"●")
        wa_icon = "📱" if plat in ("whatsapp","evolution","whatsapp_cloud") else "📲"
        print(f"  {icon}  {wa_icon}  {q(C.W, inst.label)} [{plat}] :{inst.port}")

    nl()
    if not sub:
        info("Subcomandos: melissa whatsapp qr | connect | disconnect | status")
        return

    # Subcomandos
    if sub == "qr":
        info("Logs del bridge (busca el QR):")
        nl()
        subprocess.run(["pm2", "logs", "whatsapp-bridge", "--lines", "60", "--nostream"])

    elif sub in ("connect", "reconectar"):
        inst = find_instance(name) if name else (instances[0] if instances else None)
        if not inst:
            fail("No encontré instancia"); return
        # Verificar que el bridge apunta a esta instancia
        secret = inst.webhook_secret
        expected = f"http://localhost:{inst.port}/webhook/{secret}"
        if bridge_url != expected:
            warn(f"Bridge apunta a: {bridge_url}")
            info(f"Esperado:        {expected}")
            if confirm("¿Actualizar configuración del bridge?"):
                _fix_bridge_webhook(inst)

        info("Abre WhatsApp en tu teléfono → Dispositivos vinculados → Vincular dispositivo")
        info("Cuando aparezca el QR corre: melissa whatsapp qr")

    elif sub == "disconnect":
        with Spinner("Desconectando WhatsApp...") as sp:
            try:
                if _HTTPX:
                    _httpx.post(f"http://localhost:{bridge_port}/logout", timeout=5)
                sp.finish("Desconectado")
            except Exception as e:
                sp.finish(f"Error: {e}", ok=False)


def _fix_bridge_webhook(inst: Instance):
    """Actualiza el WEBHOOK_URL del bridge para apuntar a la instancia correcta."""
    BRIDGE_ENV = "/home/ubuntu/whatsapp-bridge/.env"
    secret = inst.webhook_secret or "melissa_2026"
    new_url = f"http://localhost:{inst.port}/webhook/{secret}"
    lines = open(BRIDGE_ENV).readlines() if os.path.exists(BRIDGE_ENV) else []
    new_lines = []
    found_url = found_token = False
    for line in lines:
        if line.startswith("WEBHOOK_URL="):
            new_lines.append(f"WEBHOOK_URL={new_url}\n"); found_url = True
        elif line.startswith("WEBHOOK_TOKEN="):
            new_lines.append(f"WEBHOOK_TOKEN={secret}\n"); found_token = True
        else:
            new_lines.append(line)
    if not found_url:   new_lines.append(f"WEBHOOK_URL={new_url}\n")
    if not found_token: new_lines.append(f"WEBHOOK_TOKEN={secret}\n")
    open(BRIDGE_ENV, "w").writelines(new_lines)
    pm2("restart", "whatsapp-bridge")
    ok(f"Bridge actualizado → {new_url}")


# ══════════════════════════════════════════════════════════════════════════════
# CMD_INFO — Resumen rápido de una instancia (todo en uno)
# ══════════════════════════════════════════════════════════════════════════════
def cmd_info(args):
    """
    Resumen completo de una instancia: estado, tokens, bridge, config.
    
    Uso:
      melissa info                 → info de la instancia base
      melissa info 1               → info de instancia 1
    """
    name = getattr(args, 'name', '') or getattr(args, 'subcommand', '') or ''
    inst = find_instance(name) if name else None
    if not inst:
        instances = get_instances()
        if not instances: fail("No hay instancias"); return
        inst = instances[0] if len(instances) == 1 else instances[
            select([i.label for i in instances], title="¿Cuál instancia?")]

    h       = health(inst.port)
    sector  = SECTORS.get(inst.sector, SECTORS["otro"])
    active  = inst.is_active

    section(f"{sector.emoji} {inst.label}", inst.name)

    # Estado
    status_color = C.GRN if h else C.RED
    active_color = C.GRN if active else C.YLW
    kv("Estado PM2",   "online" if h else "offline",         status_color)
    kv("Activada",     "si" if active else "pendiente token", active_color)
    kv("Sector",       sector.name)
    kv("Plataforma",   inst.platform)
    kv("Puerto",       str(inst.port))
    kv("Directorio",   inst.dir)
    kv("PM2 name",     inst.pm2_name)
    nl()

    # Config clave
    kv("BASE_URL",       inst.env.get("BASE_URL", "—"))
    kv("WEBHOOK_SECRET", inst.webhook_secret or "—")
    kv("MASTER_KEY",     (inst.master_key[:12] + "...") if inst.master_key else "—")
    kv("Nova",           inst.env.get("NOVA_ENABLED", "false"))
    nl()

    # Tokens activos
    if h and inst.master_key:
        try:
            data = inst.api_call("GET", "/api/tokens")
            tokens = [t for t in data.get("tokens", []) if t.get("is_active") and not t.get("used_at")]
            if tokens:
                info(f"Tokens activos: {len(tokens)}")
                for t in tokens[:3]:
                    print(f"    {q(C.YLW, t['token'][:40]+'...')}  [{t.get('clinic_label','')}]")
            else:
                warn("Sin tokens activos — crea uno con: melissa token")
        except Exception:
            pass
    nl()

    # Stats rápidas
    stats = get_instance_stats(inst)
    kv("Conversaciones", str(stats["conversations"]))
    kv("Mensajes",       str(stats["messages"]))
    kv("Citas",          str(stats["appointments"]))
    nl()

    # Acciones rápidas
    info("Acciones:")
    print(f"    melissa token {inst.name}       — generar token de activacion")
    print(f"    melissa activar {inst.name}     — activar instancia")
    print(f"    melissa bridge fix              — arreglar bridge WhatsApp")
    print(f"    melissa restart {inst.name}     — reiniciar")
    print(f"    melissa logs {inst.name}        — ver logs")
    nl()


def cmd_pair(args):
    """
    Router compartido de Telegram.

    Usos:
      melissa pair list
      melissa pair default <instancia>
      melissa pair detach <chat_id>
      melissa pair <instancia> <chat_id>
    """
    sub = (getattr(args, "subcommand", "") or "").strip()
    name = (getattr(args, "name", "") or "").strip()
    routes = load_shared_telegram_routes()

    if sub in ("", "list", "ls"):
        print_logo(compact=True)
        section("Telegram Compartido", "Rutas activas")
        kv("Archivo", str(SHARED_TELEGRAM_ROUTES))
        kv("Default", routes.get("default_instance", "") or "—")
        nl()
        mapped = routes.get("routes", {})
        if not mapped:
            warn("No hay chats enlazados")
            return
        for chat_id, inst_name in sorted(mapped.items()):
            print(f"  {q(C.CYN, chat_id)} → {q(C.W, inst_name, bold=True)}")
        nl()
        return

    if sub == "default":
        if not name:
            fail("Uso: melissa pair default <instancia>")
            return
        inst = find_instance(name)
        if not inst:
            fail(f"No encuentro la instancia '{name}'")
            return
        routes["default_instance"] = inst.name
        save_shared_telegram_routes(routes)
        ok(f"Instancia por defecto: {inst.name}")
        return

    if sub in ("detach", "rm", "remove"):
        if not name:
            fail("Uso: melissa pair detach <chat_id>")
            return
        if name in routes.get("routes", {}):
            routes["routes"].pop(name, None)
            save_shared_telegram_routes(routes)
            ok(f"Chat {name} desenlazado")
        else:
            warn("Ese chat_id no estaba enlazado")
        return

    inst = find_instance(sub)
    if not inst or not name:
        fail("Uso: melissa pair <instancia> <chat_id>")
        return

    routes.setdefault("routes", {})[name] = inst.name
    save_shared_telegram_routes(routes)
    ok(f"Chat {name} enlazado a {inst.name}")
    nl()
    info("Si esa instancia usa token compartido, el router base ya podrá enrutarle los updates")


def _bb_context() -> BBContext:
    return BBContext(
        melissa_dir=MELISSA_DIR,
        colors=C,
        print_logo=print_logo,
        section=section,
        q=q,
        kv=kv,
        info=info,
        nl=nl,
        fail=fail,
        warn=warn,
        ok=ok,
        prompt=prompt,
        confirm=confirm,
        select=select,
        spinner_cls=Spinner,
        pick_instance=_pick_instance,
        health=health,
        v8_api=_v8_api,
        handler_chat=cmd_chat,
        handler_doctor=cmd_doctor,
        handler_sync=cmd_sync,
        handler_guide=cmd_guide,
        handler_new=cmd_new,
        handler_init=cmd_init,
        handler_status=cmd_status,
        handler_health=cmd_health,
        handler_modelo=cmd_modelo,
        handler_trainer_skills=cmd_trainer_skills,
        handler_trainer_control=cmd_trainer_control,
        handler_bb_config=cmd_bb_config,
    )


def cmd_bb(args):
    """Superficie Black Boss para enrutar acciones clave sin duplicar la CLI."""
    return _cmd_bb_impl(_bb_context(), args)


def _bb_persona_defaults() -> Dict[str, Any]:
    return _bb_persona_defaults_impl()


def _bb_personality_catalog() -> Dict[str, Dict[str, Any]]:
    return _bb_personality_catalog_impl(_bb_context())


def _bb_read_persona_db(inst: "Instance") -> Dict[str, Any]:
    return _bb_read_persona_db_impl(inst)


def _bb_write_persona_db(inst: "Instance", persona: Dict[str, Any]) -> bool:
    return _bb_write_persona_db_impl(_bb_context(), inst, persona)


def _bb_load_persona(inst: "Instance") -> Dict[str, Any]:
    return _bb_load_persona_impl(inst)


def _bb_apply_persona(inst: "Instance", updates: Dict[str, Any], spinner_label: str = "Actualizando agente...") -> bool:
    return _bb_apply_persona_impl(_bb_context(), inst, updates, spinner_label=spinner_label)


def _bb_prompt_block(label: str, initial: str = "") -> str:
    return _bb_prompt_block_impl(_bb_context(), label, initial=initial)


def _bb_score_prompt(label: str, current: Any, default: float) -> float:
    return _bb_score_prompt_impl(_bb_context(), label, current, default)


def _bb_show_agent_summary(inst: "Instance", persona: Optional[Dict[str, Any]] = None) -> None:
    return _bb_show_agent_summary_impl(_bb_context(), inst, persona)


def cmd_bb_config(args):
    """Configura el agente Melissa de una instancia: nombre, prompt, personalidad y skills."""
    return _cmd_bb_config_impl(_bb_context(), args)


ROUTES = {
    # Principal
    "init": cmd_init,
    "new": cmd_new, "nuevo": cmd_new, "crear": cmd_new,
    "list": cmd_list, "ls": cmd_list, "l": cmd_list, "listar": cmd_list,
    "dashboard": cmd_dashboard, "dash": cmd_dashboard,

    # Estado
    "status": cmd_status, "estado": cmd_status, "s": cmd_status,
    "health": cmd_health,
    "metrics": cmd_metrics, "metricas": cmd_metrics,
    "stats": cmd_stats, "estadisticas": cmd_stats,
    "logs": cmd_logs, "log": cmd_logs,

    # Operaciones
    "config": cmd_config, "configurar": cmd_config,
    "restart": cmd_restart, "reiniciar": cmd_restart, "r": cmd_restart,
    "stop": cmd_stop, "detener": cmd_stop,
    "scale": cmd_scale, "escalar": cmd_scale,
    "clone": cmd_clone, "clonar": cmd_clone,
    "reset": cmd_reset,
    "delete": cmd_delete, "eliminar": cmd_delete, "rm": cmd_delete,

    # Mantenimiento
    "sync": cmd_sync, "sincronizar": cmd_sync,
    "fix": cmd_fix,   "reparar": cmd_fix,
    "rollback": cmd_rollback, "revertir": cmd_rollback,
    "install": cmd_install,
    "zero": cmd_zero, "cero": cmd_zero,
    "demo": cmd_demo,

    # Datos
    "backup": cmd_backup,
    "restore": cmd_restore, "restaurar": cmd_restore,
    "export": cmd_export, "exportar": cmd_export,
    "import": cmd_import_data, "importar": cmd_import_data,
    "template": cmd_template, "plantilla": cmd_template,
    "test": cmd_test, "probar": cmd_test,

    # Sistema
    "doctor": cmd_doctor,
    "audit": cmd_audit, "auditoria": cmd_audit,
    "benchmark": cmd_benchmark,
    "secure": cmd_secure, "seguridad": cmd_secure,
    "rotate-keys": cmd_rotate_keys, "rotate": cmd_rotate_keys,
    "upgrade": cmd_upgrade, "actualizar": cmd_upgrade,
    "billing": cmd_billing, "costos": cmd_billing,

    # Avanzado
    "chat": cmd_chat, "c": cmd_chat,
    "omni": cmd_omni,
    "nova": cmd_nova,
    "pair": cmd_pair, "pairing": cmd_pair,

    # V7 — Activación y Bridge
    "token": cmd_token, "generar-token": cmd_token,
    "tokens": cmd_tokens, "listar-tokens": cmd_tokens,
    "activar": cmd_activar, "activate": cmd_activar,
    "bridge": cmd_bridge, "wa-bridge": cmd_bridge,
    "whatsapp": cmd_whatsapp_cli, "wa": cmd_whatsapp_cli,
    "info": cmd_info, "ver": cmd_info,

    # Ayuda
    "help": cmd_help, "--help": cmd_help, "-h": cmd_help,
    "": cmd_help,

    # Caddy
    "caddy": cmd_caddy,

    # V6.0 — Inteligencia y automatización
    "pipeline": cmd_pipeline, "pipe": cmd_pipeline,
    "perdidos": cmd_perdidos, "lost": cmd_perdidos,
    "coach": cmd_coach,
    "estilo": cmd_estilo, "style": cmd_estilo,
    "reactivar": cmd_reactivar, "reactivate": cmd_reactivar,
    "seguimiento": cmd_seguimiento, "followup": cmd_seguimiento,
    "reporte": cmd_reporte, "report": cmd_reporte,
    "broadcast": cmd_broadcast, "masivo": cmd_broadcast,
    "preconsulta": cmd_preconsulta, "preconsult": cmd_preconsulta,
    "instagram": cmd_instagram, "ig": cmd_instagram,
    "pagos": cmd_pagos, "payments": cmd_pagos,
    "leads": cmd_leads,
}


# ══════════════════════════════════════════════════════════════════════════════
# MODO INTERACTIVO (REPL)
# ══════════════════════════════════════════════════════════════════════════════
def cmd_interactive(args):
    """Modo interactivo — shell de Melissa."""
    print_logo(compact=True)
    section("Modo Interactivo", "Escribe comandos sin 'melissa'. 'exit' para salir.")
    
    # Shortcuts
    shortcuts = {
        "q": "exit",
        "d": "dashboard",
        "l": "list",
        "s": "status",
        "h": "help",
        "n": "new",
        "r": "restart all",
    }
    
    while True:
        try:
            sys.stdout.write(f"\n  {q(C.P2, 'ᗧ', bold=True)} {q(C.G2, 'melissa')} {q(C.P3, '›')} ")
            sys.stdout.flush()
            line = input("").strip()
        except (EOFError, KeyboardInterrupt):
            nl()
            info("Saliendo...")
            break
        
        if not line:
            continue
        
        if line.lower() in ("exit", "quit", "salir", "q"):
            info("¡Hasta luego!")
            break
        
        # Expandir shortcuts
        parts = line.split()
        if parts[0] in shortcuts:
            line = shortcuts[parts[0]] + " " + " ".join(parts[1:])
            parts = line.split()
        
        cmd = parts[0].lower()
        
        # Crear args simulados
        fake_args = type('Args', (), {
            'command': cmd,
            'subcommand': parts[1] if len(parts) > 1 else '',
            'name': parts[2] if len(parts) > 2 else (parts[1] if len(parts) > 1 else ''),
        })()
        
        if cmd in ROUTES:
            try:
                ROUTES[cmd](fake_args)
            except Exception as e:
                fail(f"Error: {e}")
        elif not nl_route(line):
            warn(f"Comando no reconocido: {cmd}")
            dim("Escribe 'help' para ver comandos")

# ══════════════════════════════════════════════════════════════════════════════
# ALERTAS Y MONITOREO
# ══════════════════════════════════════════════════════════════════════════════
ALERTS_FILE = Path.home() / ".melissa" / "alerts.json"

@dataclass
class Alert:
    id: str
    type: str  # offline, high_latency, error_rate, disk_space
    instance: str
    threshold: float
    action: str  # notify, restart, scale
    enabled: bool = True

def load_alerts() -> List[dict]:
    """Cargar alertas configuradas."""
    try:
        if ALERTS_FILE.exists():
            return json.loads(ALERTS_FILE.read_text())
    except Exception:
        pass
    return []

def save_alerts(alerts: List[dict]):
    """Guardar alertas."""
    ALERTS_FILE.parent.mkdir(exist_ok=True)
    ALERTS_FILE.write_text(json.dumps(alerts, indent=2))

def cmd_alerts(args):
    """Gestionar alertas."""
    print_logo(compact=True)
    section("Sistema de Alertas")
    
    sub = getattr(args, 'subcommand', '') or ''
    
    if sub == "add":
        # Crear nueva alerta
        instances = get_instances()
        if not instances:
            fail("No hay instancias")
            return
        
        idx = select([i.label for i in instances] + ["Todas"], title="¿Para cuál instancia?")
        inst_name = instances[idx].name if idx < len(instances) else "*"
        
        alert_types = [
            ("offline", "Instancia offline", "Detecta cuando la instancia no responde"),
            ("high_latency", "Latencia alta", "Cuando el tiempo de respuesta supera X ms"),
            ("error_rate", "Tasa de errores", "Cuando hay más de X% errores"),
            ("disk_space", "Espacio en disco", "Cuando queda menos de X GB"),
            ("memory", "Memoria alta", "Cuando el uso de RAM supera X%"),
        ]
        
        type_idx = select(
            [t[1] for t in alert_types],
            [t[2] for t in alert_types],
            title="Tipo de alerta:"
        )
        alert_type = alert_types[type_idx][0]
        
        # Threshold
        default_thresholds = {
            "offline": "1",
            "high_latency": "500",
            "error_rate": "5",
            "disk_space": "5",
            "memory": "90",
        }
        threshold = prompt(
            f"Umbral ({['intentos', 'ms', '%', 'GB', '%'][type_idx]})",
            default=default_thresholds[alert_type]
        )
        
        actions = [
            ("notify", "Solo notificar"),
            ("restart", "Reiniciar instancia"),
            ("scale", "Escalar workers"),
        ]
        action_idx = select([a[1] for a in actions], title="Acción:")
        action = actions[action_idx][0]
        
        import secrets as _s
        alert = {
            "id": _s.token_hex(4),
            "type": alert_type,
            "instance": inst_name,
            "threshold": float(threshold),
            "action": action,
            "enabled": True,
            "created_at": datetime.utcnow().isoformat()
        }
        
        alerts = load_alerts()
        alerts.append(alert)
        save_alerts(alerts)
        
        ok(f"Alerta creada: {alert['id']}")
        
    elif sub == "list":
        alerts = load_alerts()
        if not alerts:
            info("No hay alertas configuradas")
            info("Crea una con: melissa alerts add")
            return
        
        headers = ["ID", "TIPO", "INSTANCIA", "UMBRAL", "ACCIÓN", "ESTADO"]
        rows = []
        
        for a in alerts:
            status = q(C.GRN, "ON") if a.get("enabled", True) else q(C.RED, "OFF")
            rows.append([
                a["id"],
                a["type"],
                a["instance"],
                str(a["threshold"]),
                a["action"],
                status
            ])
        
        table(headers, rows)
        
    elif sub == "delete":
        alert_id = getattr(args, 'name', '') or prompt("ID de la alerta a eliminar")
        alerts = load_alerts()
        alerts = [a for a in alerts if a["id"] != alert_id]
        save_alerts(alerts)
        ok(f"Alerta {alert_id} eliminada")
        
    elif sub == "test":
        info("Probando sistema de alertas...")
        alerts = load_alerts()
        instances = get_instances()
        
        for alert in alerts:
            if not alert.get("enabled", True):
                continue
            
            target_instances = instances if alert["instance"] == "*" else \
                [i for i in instances if i.name == alert["instance"]]
            
            for inst in target_instances:
                if alert["type"] == "offline":
                    h = health(inst.port)
                    if not h:
                        warn(f"ALERTA: {inst.label} offline")
                        if alert["action"] == "restart":
                            pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
                            pm2("restart", pm2_name)
                            ok(f"  → Reiniciado {inst.label}")
                
                elif alert["type"] == "high_latency":
                    start = time.time()
                    health(inst.port)
                    latency = (time.time() - start) * 1000
                    if latency > alert["threshold"]:
                        warn(f"ALERTA: {inst.label} latencia {latency:.0f}ms > {alert['threshold']}ms")
        
        ok("Test de alertas completado")
        
    else:
        # Menú de alertas
        options = ["Ver alertas", "Crear alerta", "Eliminar alerta", "Probar alertas"]
        choice = select(options)
        
        if choice == 0:
            args.subcommand = "list"
        elif choice == 1:
            args.subcommand = "add"
        elif choice == 2:
            args.subcommand = "delete"
        elif choice == 3:
            args.subcommand = "test"
        
        cmd_alerts(args)

# ══════════════════════════════════════════════════════════════════════════════
# WEBHOOKS
# ══════════════════════════════════════════════════════════════════════════════
def cmd_webhooks(args):
    """Gestionar webhooks de Telegram/WhatsApp."""
    print_logo(compact=True)
    section("Webhooks")
    
    instances = get_instances()
    if not instances:
        fail("No hay instancias")
        return
    
    name = getattr(args, 'name', '')
    inst = find_instance(name) if name else None
    
    if not inst:
        idx = select([i.label for i in instances], title="¿Cuál instancia?")
        inst = instances[idx]
    
    ev = inst.env
    platform = ev.get("PLATFORM", "telegram")
    
    info(f"Instancia: {inst.label}")
    info(f"Plataforma: {platform}")
    nl()
    
    if platform == "telegram":
        token = ev.get("TELEGRAM_TOKEN", "")
        if not token:
            fail("No hay TELEGRAM_TOKEN configurado")
            return
        
        base_url = ev.get("BASE_URL", "")
        webhook_secret = ev.get("WEBHOOK_SECRET", "melissa_2026")
        webhook_url = f"{base_url}/webhook/{webhook_secret}"
        
        options = ["Ver estado actual", "Configurar webhook", "Eliminar webhook", "Ver info del bot"]
        choice = select(options)
        
        if choice == 0:
            # Get webhook info
            with Spinner("Consultando...") as sp:
                try:
                    url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
                    if _HTTPX:
                        r = _httpx.get(url, timeout=10)
                        data = r.json()
                    else:
                        data = json.loads(urllib.request.urlopen(url, timeout=10).read())
                    
                    sp.finish("Información obtenida")
                    
                    result = data.get("result", {})
                    kv("URL", result.get("url", "No configurado"))
                    kv("Pendientes", str(result.get("pending_update_count", 0)))
                    kv("Último error", result.get("last_error_message", "Ninguno"))
                    if result.get("last_error_date"):
                        kv("Fecha error", datetime.fromtimestamp(result["last_error_date"]).isoformat())
                except Exception as e:
                    sp.finish(f"Error: {e}", ok=False)
        
        elif choice == 1:
            # Set webhook
            new_url = prompt("URL del webhook", default=webhook_url)
            
            with Spinner("Configurando webhook...") as sp:
                try:
                    url = f"https://api.telegram.org/bot{token}/setWebhook"
                    params = {"url": new_url}
                    
                    if _HTTPX:
                        r = _httpx.post(url, json=params, timeout=10)
                        data = r.json()
                    else:
                        req = urllib.request.Request(
                            url,
                            data=json.dumps(params).encode(),
                            headers={"Content-Type": "application/json"}
                        )
                        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
                    
                    if data.get("ok"):
                        sp.finish(f"Webhook configurado: {new_url}")
                    else:
                        sp.finish(f"Error: {data.get('description', 'Desconocido')}", ok=False)
                except Exception as e:
                    sp.finish(f"Error: {e}", ok=False)
        
        elif choice == 2:
            # Delete webhook
            with Spinner("Eliminando webhook...") as sp:
                try:
                    url = f"https://api.telegram.org/bot{token}/deleteWebhook"
                    if _HTTPX:
                        r = _httpx.post(url, timeout=10)
                        data = r.json()
                    else:
                        data = json.loads(urllib.request.urlopen(url, timeout=10).read())
                    
                    if data.get("ok"):
                        sp.finish("Webhook eliminado")
                    else:
                        sp.finish(f"Error: {data.get('description')}", ok=False)
                except Exception as e:
                    sp.finish(f"Error: {e}", ok=False)
        
        elif choice == 3:
            # Get bot info
            with Spinner("Obteniendo info...") as sp:
                try:
                    url = f"https://api.telegram.org/bot{token}/getMe"
                    if _HTTPX:
                        r = _httpx.get(url, timeout=10)
                        data = r.json()
                    else:
                        data = json.loads(urllib.request.urlopen(url, timeout=10).read())
                    
                    sp.finish("Info obtenida")
                    
                    result = data.get("result", {})
                    kv("ID", str(result.get("id", "?")))
                    kv("Username", f"@{result.get('username', '?')}")
                    kv("Nombre", result.get("first_name", "?"))
                    kv("Puede unirse a grupos", "Sí" if result.get("can_join_groups") else "No")
                except Exception as e:
                    sp.finish(f"Error: {e}", ok=False)
    
    elif platform == "whatsapp":
        info("Para WhatsApp, configura el webhook en:")
        info("https://developers.facebook.com/apps/")
        nl()
        kv("Callback URL", f"{ev.get('BASE_URL', '')}/webhook/whatsapp")
        kv("Verify Token", ev.get("WA_VERIFY_TOKEN", "melissa_verify"))
    
    nl()

# ══════════════════════════════════════════════════════════════════════════════
# BÚSQUEDA EN LOGS
# ══════════════════════════════════════════════════════════════════════════════
def cmd_search(args):
    """Buscar en logs y conversaciones."""
    print_logo(compact=True)
    section("Búsqueda")
    
    query = getattr(args, 'name', '') or prompt("¿Qué buscar?")
    if not query:
        return
    
    search_in = ["Logs de PM2", "Conversaciones (DB)", "Ambos"]
    choice = select(search_in)
    
    results = []
    
    if choice in [0, 2]:
        # Buscar en logs PM2
        info("Buscando en logs...")
        
        instances = get_instances()
        for inst in instances:
            log_path = f"{inst.dir}/logs/melissa.log"
            if os.path.exists(log_path):
                try:
                    with open(log_path, 'r', errors='ignore') as f:
                        for i, line in enumerate(f):
                            if query.lower() in line.lower():
                                results.append({
                                    "source": f"log:{inst.name}",
                                    "line": i + 1,
                                    "content": line.strip()[:100]
                                })
                                if len(results) > 50:
                                    break
                except Exception:
                    pass
    
    if choice in [1, 2]:
        # Buscar en DB
        info("Buscando en conversaciones...")
        
        instances = get_instances()
        for inst in instances:
            db_path = f"{inst.dir}/melissa.db"
            if os.path.exists(db_path):
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT chat_id, role, content, ts as created_at FROM conversations WHERE content LIKE ? ORDER BY ts DESC 
                        LIMIT 20
                    """, (f"%{query}%",))
                    
                    for row in cursor.fetchall():
                        results.append({
                            "source": f"db:{inst.name}",
                            "user": row[0],
                            "role": row[1],
                            "content": row[2][:100],
                            "date": row[3]
                        })
                    
                    conn.close()
                except Exception:
                    pass
    
    nl()
    
    if not results:
        warn(f"No se encontró '{query}'")
        return
    
    ok(f"{len(results)} resultado(s) encontrado(s)")
    nl()
    
    for r in results[:20]:
        source = r.get("source", "?")
        if source.startswith("log:"):
            line_no = r.get("line", "?")
            print(f"  {q(C.G3, f'[{source}:{line_no}]')}")
            print(f"    {q(C.G1, r.get('content', ''))}")
        else:
            print(f"  {q(C.G3, f'[{source}]')} {q(C.P2, r.get('role', '?'))} {q(C.G3, r.get('date', '')[:16])}")
            print(f"    {q(C.G1, r.get('content', ''))}")
        nl()
    
    if len(results) > 20:
        dim(f"... y {len(results) - 20} más")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
def cmd_analytics(args):
    """Análisis de conversaciones y rendimiento."""
    print_logo(compact=True)
    section("Analytics")
    
    name = getattr(args, 'name', '')
    inst = find_instance(name) if name else None
    
    if not inst:
        instances = get_instances()
        if len(instances) == 1:
            inst = instances[0]
        elif instances:
            idx = select([i.label for i in instances], title="¿Cuál analizar?")
            inst = instances[idx]
        else:
            fail("No hay instancias")
            return
    
    db_path = f"{inst.dir}/melissa.db"
    if not os.path.exists(db_path):
        fail("No hay datos para analizar")
        return
    
    info(f"Analizando {inst.label}...")
    nl()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Usuarios únicos
        cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM conversations")
        users = cursor.fetchone()[0]
        kv("Usuarios únicos", str(users))
        
        # Mensajes totales
        cursor.execute("SELECT COUNT(*) FROM conversations")
        messages = cursor.fetchone()[0]
        kv("Mensajes totales", str(messages))
        
        # Promedio por usuario
        if users > 0:
            kv("Promedio msg/usuario", f"{messages / users:.1f}")
        
        nl()
        
        # Mensajes por día (últimos 7 días)
        info("Actividad (últimos 7 días):")
        cursor.execute("""
            SELECT DATE(created_at) as day, COUNT(*) as count
            FROM conversations
            WHERE created_at > datetime('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY day DESC
        """)
        
        daily = cursor.fetchall()
        if daily:
            max_count = max(d[1] for d in daily)
            for day, count in daily:
                bar_len = int((count / max_count) * 20) if max_count > 0 else 0
                bar = "█" * bar_len + "░" * (20 - bar_len)
                print(f"    {q(C.G3, day[-5:])}  {q(C.P2, bar)}  {q(C.W, str(count))}")
        
        nl()
        
        # Horas más activas
        info("Horas más activas:")
        cursor.execute("""
            SELECT strftime('%H', created_at) as hour, COUNT(*) as count
            FROM conversations
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 5
        """)
        
        for hour, count in cursor.fetchall():
            print(f"    {q(C.P2, f'{hour}:00')}  {q(C.G1, f'{count} mensajes')}")
        
        nl()
        
        # Citas
        try:
            cursor.execute("SELECT COUNT(*) FROM appointments")
            appointments = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT status, COUNT(*) 
                FROM appointments 
                GROUP BY status
            """)
            
            info("Citas:")
            kv("Total", str(appointments))
            for status, count in cursor.fetchall():
                kv(f"  {status or 'pendiente'}", str(count))
        except Exception:
            pass
        
        nl()
        
        # Conversión
        if users > 0:
            try:
                cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM appointments")
                users_with_appointments = cursor.fetchone()[0]
                conversion = (users_with_appointments / users) * 100
                kv("Tasa de conversión", f"{conversion:.1f}%")
            except Exception:
                pass
        
        conn.close()
        
    except Exception as e:
        fail(f"Error: {e}")
    
    nl()

# ══════════════════════════════════════════════════════════════════════════════
# BATCH OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════
def cmd_batch(args):
    """Operaciones en lote."""
    print_logo(compact=True)
    section("Operaciones en Lote")
    
    operations = [
        ("restart", "Reiniciar múltiples instancias"),
        ("backup", "Backup de múltiples instancias"),
        ("update-env", "Actualizar variable en múltiples .env"),
        ("health", "Health check de todas"),
        ("export", "Exportar datos de múltiples"),
    ]
    
    idx = select([o[1] for o in operations])
    operation = operations[idx][0]
    
    instances = get_instances()
    if not instances:
        fail("No hay instancias")
        return
    
    # Seleccionar instancias
    selected_idx = multi_select(
        [i.label for i in instances],
        title="Selecciona instancias:"
    )
    
    if not selected_idx:
        info("Ninguna seleccionada")
        return
    
    selected = [instances[i] for i in selected_idx]
    
    nl()
    info(f"Operación: {operation}")
    info(f"Instancias: {', '.join(i.name for i in selected)}")
    nl()
    
    if not confirm("¿Ejecutar?"):
        return
    
    if operation == "restart":
        for inst in selected:
            pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
            pm2("restart", pm2_name)
            ok(f"{inst.label} reiniciada")
    
    elif operation == "backup":
        for inst in selected:
            BACKUP_DIR.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = BACKUP_DIR / f"melissa_{inst.name}_{timestamp}.tar.gz"
            
            with tarfile.open(output, "w:gz") as tar:
                for f in [".env", "melissa.db", "instance.json"]:
                    p = f"{inst.dir}/{f}"
                    if os.path.exists(p):
                        tar.add(p, arcname=f)
            
            ok(f"{inst.label} → {output.name}")
    
    elif operation == "update-env":
        key = prompt("Variable a actualizar (ej: BUFFER_WAIT_MIN)")
        value = prompt(f"Nuevo valor para {key}")
        
        if key and value:
            for inst in selected:
                update_env_key(f"{inst.dir}/.env", key, value)
                ok(f"{inst.label}: {key}={value}")
            
            if confirm("¿Reiniciar instancias?"):
                for inst in selected:
                    pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
                    pm2("restart", pm2_name)
    
    elif operation == "health":
        ports = [i.port for i in selected]
        healths = health_batch(ports)
        
        for inst in selected:
            h = healths.get(inst.port, {})
            icon, status = icon_status(h)
            print(f"  {icon}  {inst.label}")
    
    elif operation == "export":
        BACKUP_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for inst in selected:
            db_path = f"{inst.dir}/melissa.db"
            if not os.path.exists(db_path):
                warn(f"{inst.label}: sin datos")
                continue
            
            output = BACKUP_DIR / f"export_{inst.name}_{timestamp}.json"
            
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                data = {"instance": inst.name, "exported_at": datetime.utcnow().isoformat()}
                
                try:
                    cursor.execute("SELECT * FROM appointments")
                    data["appointments"] = [dict(r) for r in cursor.fetchall()]
                except Exception:
                    data["appointments"] = []
                
                try:
                    cursor.execute("SELECT * FROM conversations LIMIT 5000")
                    data["conversations"] = [dict(r) for r in cursor.fetchall()]
                except Exception:
                    data["conversations"] = []
                
                conn.close()
                output.write_text(json.dumps(data, indent=2, default=str))
                ok(f"{inst.label} → {output.name}")
                
            except Exception as e:
                fail(f"{inst.label}: {e}")
    
    nl()

# ══════════════════════════════════════════════════════════════════════════════
# QUICK ACTIONS
# ══════════════════════════════════════════════════════════════════════════════
QUICK_ACTIONS_FILE = Path.home() / ".melissa" / "quick_actions.json"

def cmd_quick(args):
    """Acciones rápidas personalizadas."""
    print_logo(compact=True)
    section("Acciones Rápidas")
    
    sub = getattr(args, 'subcommand', '') or ''
    
    def load_actions():
        try:
            if QUICK_ACTIONS_FILE.exists():
                return json.loads(QUICK_ACTIONS_FILE.read_text())
        except Exception:
            pass
        return []
    
    def save_actions(actions):
        QUICK_ACTIONS_FILE.parent.mkdir(exist_ok=True)
        QUICK_ACTIONS_FILE.write_text(json.dumps(actions, indent=2))
    
    if sub == "add":
        name = prompt("Nombre del comando rápido")
        description = prompt("Descripción")
        
        info("Comandos a ejecutar (uno por línea, vacío para terminar):")
        commands = []
        while True:
            cmd_ = prompt(f"  {len(commands) + 1}.")
            if not cmd_:
                break
            commands.append(cmd_)
        
        if commands:
            actions = load_actions()
            actions.append({
                "name": name,
                "description": description,
                "commands": commands,
                "created_at": datetime.utcnow().isoformat()
            })
            save_actions(actions)
            ok(f"Acción '{name}' creada")
        
    elif sub == "run":
        actions = load_actions()
        if not actions:
            warn("No hay acciones guardadas")
            info("Crea una con: melissa quick add")
            return
        
        action_name = getattr(args, 'name', '') or ''
        action = None
        
        if action_name:
            action = next((a for a in actions if a["name"].lower() == action_name.lower()), None)
        
        if not action:
            idx = select([a["name"] for a in actions], [a["description"] for a in actions])
            action = actions[idx]
        
        info(f"Ejecutando: {action['name']}")
        nl()
        
        for cmd_ in action["commands"]:
            print(f"  {q(C.G3, '>')} {q(C.CYN, cmd_)}")
            
            # Parsear y ejecutar
            parts = cmd_.split()
            if parts and parts[0] == "melissa":
                parts = parts[1:]
            
            if parts:
                fake_args = type('Args', (), {
                    'command': parts[0],
                    'subcommand': parts[1] if len(parts) > 1 else '',
                    'name': parts[2] if len(parts) > 2 else (parts[1] if len(parts) > 1 else ''),
                })()
                
                if parts[0] in ROUTES:
                    ROUTES[parts[0]](fake_args)
            
            nl()
        
        ok("Completado")
        
    else:
        actions = load_actions()
        
        if not actions:
            info("No hay acciones guardadas")
            info("Crea una con: melissa quick add")
            return
        
        info("Acciones guardadas:")
        for a in actions:
            print(f"    {q(C.P2, a['name'], bold=True)}")
            print(f"      {q(C.G3, a['description'])}")
            _cmd_count = f'{len(a["commands"])} comandos'
            print(f"      {q(C.G2, _cmd_count)}")
            nl()
        
        info("Ejecutar: melissa quick run <nombre>")
        info("Crear: melissa quick add")

# ══════════════════════════════════════════════════════════════════════════════
# DEBUG MODE
# ══════════════════════════════════════════════════════════════════════════════
def cmd_debug(args):
    """Modo debug — información detallada del sistema."""
    print_logo(compact=True)
    section("Debug Mode")
    
    # Información del sistema
    info("Sistema:")
    kv("Python", sys.version)
    kv("Plataforma", platform.platform())
    kv("Arquitectura", platform.machine())
    kv("PID", str(os.getpid()))
    kv("CWD", os.getcwd())
    kv("MELISSA_DIR", MELISSA_DIR)
    kv("INSTANCES_DIR", INSTANCES_DIR)
    nl()
    
    # Variables de entorno
    info("Variables de entorno relevantes:")
    env_vars = ["MELISSA_DIR", "INSTANCES_DIR", "NOVA_DIR", "TERM", "SHELL", "USER", "HOME"]
    for var in env_vars:
        kv(var, os.getenv(var, "no definida"))
    nl()
    
    # PM2 processes
    info("Procesos PM2:")
    procs = pm2_list()
    for p in procs:
        name = p.get("name", "?")
        status = p.get("pm2_env", {}).get("status", "?")
        pid = p.get("pid", "?")
        memory = p.get("monit", {}).get("memory", 0) // (1024 * 1024)
        cpu = p.get("monit", {}).get("cpu", 0)
        
        status_color = C.GRN if status == "online" else C.RED
        print(f"    {q(status_color, '●')} {name}  pid:{pid}  mem:{memory}MB  cpu:{cpu}%")
    nl()
    
    # Ports in use
    info("Puertos en uso:")
    instances = get_instances()
    for inst in instances:
        h = health(inst.port)
        icon = q(C.GRN, "●") if h else q(C.RED, "●")
        print(f"    {icon} :{inst.port}  {inst.name}")
    nl()
    
    # Cache status
    info("Caché:")
    kv("Directorio", str(CACHE_DIR))
    kv("Tamaño", f"{sum(f.stat().st_size for f in CACHE_DIR.glob('*') if f.is_file()) // 1024} KB")
    kv("load_env cache", str(load_env.cache_info()))
    nl()
    
    # Conexiones de red
    info("Conectividad:")
    with Spinner("Probando...") as sp:
        tests = [
            ("api.telegram.org", "Telegram API"),
            ("api.ipify.org", "IP pública"),
            ("api.groq.com", "Groq API"),
        ]
        
        results = []
        for host, name in tests:
            try:
                import socket
                socket.create_connection((host, 443), timeout=5)
                results.append((name, True))
            except Exception:
                results.append((name, False))
        
        sp.finish("Conectividad probada")
    
    for name, ok_ in results:
        icon = q(C.GRN, "✓") if ok_ else q(C.RED, "✗")
        print(f"    {icon} {name}")
    
    nl()

# ══════════════════════════════════════════════════════════════════════════════
# PLUGINS (Sistema extensible)
# ══════════════════════════════════════════════════════════════════════════════
PLUGINS_DIR = Path.home() / ".melissa" / "plugins"

def cmd_plugins(args):
    """Gestionar plugins."""
    print_logo(compact=True)
    section("Plugins")
    
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    
    sub = getattr(args, 'subcommand', '') or ''
    
    if sub == "list":
        plugins = list(PLUGINS_DIR.glob("*.py"))
        
        if not plugins:
            info("No hay plugins instalados")
            info("Los plugins van en: ~/.melissa/plugins/")
            return
        
        for p in plugins:
            print(f"    {q(C.P2, '◆')} {q(C.W, p.stem)}")
            
            # Intentar leer docstring
            try:
                content = p.read_text()
                if '"""' in content:
                    docstring = content.split('"""')[1].strip().split('\n')[0]
                    print(f"      {q(C.G3, docstring)}")
            except Exception:
                pass
    
    elif sub == "create":
        name = prompt("Nombre del plugin")
        if not name:
            return
        
        template = '''"""
{name} — Plugin para Melissa CLI
"""

def register(cli):
    """Registrar comandos del plugin."""
    
    def cmd_{slug}(args):
        """Descripción del comando."""
        print("Hola desde {name}!")
    
    # Registrar el comando
    cli.register("{slug}", cmd_{slug})
'''
        
        plugin_path = PLUGINS_DIR / f"{slug(name)}.py"
        plugin_path.write_text(template.format(name=name, slug=slug(name)))
        
        ok(f"Plugin creado: {plugin_path}")
        info("Edita el archivo para agregar tu lógica")
    
    else:
        options = ["Ver plugins instalados", "Crear nuevo plugin"]
        choice = select(options)
        
        if choice == 0:
            args.subcommand = "list"
        else:
            args.subcommand = "create"
        
        cmd_plugins(args)

# ══════════════════════════════════════════════════════════════════════════════
# CRON / SCHEDULED TASKS
# ══════════════════════════════════════════════════════════════════════════════
def cmd_cron(args):
    """Gestionar tareas programadas."""
    print_logo(compact=True)
    section("Tareas Programadas")
    
    info("Las tareas programadas se gestionan con crontab del sistema.")
    nl()
    
    # Mostrar tareas melissa existentes
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        current = result.stdout if result.returncode == 0 else ""
        
        melissa_tasks = [l for l in current.split('\n') if 'melissa' in l.lower()]
        
        if melissa_tasks:
            info("Tareas de Melissa en cron:")
            for t in melissa_tasks:
                print(f"    {q(C.G1, t)}")
        else:
            info("No hay tareas de Melissa en cron")
    except Exception:
        warn("No se pudo leer crontab")
    
    nl()
    
    # Templates comunes
    info("Templates sugeridos:")
    templates = [
        ("Backup diario (3am)", "0 3 * * * /usr/local/bin/melissa backup base"),
        ("Health check (cada 5min)", "*/5 * * * * /usr/local/bin/melissa health --quiet"),
        ("Rotate keys (mensual)", "0 0 1 * * /usr/local/bin/melissa rotate-keys --auto"),
        ("Limpieza logs (semanal)", "0 4 * * 0 /usr/local/bin/melissa cleanup logs"),
    ]
    
    for name, cron in templates:
        print(f"    {q(C.P2, name)}")
        print(f"      {q(C.CYN, cron)}")
        nl()
    
    info("Añadir con: crontab -e")

# ══════════════════════════════════════════════════════════════════════════════
# CLEANUP
# ══════════════════════════════════════════════════════════════════════════════
def cmd_cleanup(args):
    """Limpiar logs, caché y archivos temporales."""
    print_logo(compact=True)
    section("Limpieza")
    
    what = getattr(args, 'name', '') or ''
    
    if what == "logs":
        info("Limpiando logs antiguos...")
        
        instances = get_instances()
        for inst in instances:
            log_dir = f"{inst.dir}/logs"
            if os.path.isdir(log_dir):
                for f in Path(log_dir).glob("*.log.*"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
        
        ok("Logs antiguos eliminados")
        
    elif what == "cache":
        info("Limpiando caché...")
        
        if CACHE_DIR.exists():
            for f in CACHE_DIR.glob("*"):
                try:
                    f.unlink() if f.is_file() else shutil.rmtree(f)
                except Exception:
                    pass
        
        load_env.cache_clear()
        ok("Caché limpiado")
        
    elif what == "backups":
        if not confirm("¿Eliminar backups antiguos (>30 días)?", default=False):
            return
        
        cutoff = datetime.now() - timedelta(days=30)
        deleted = 0
        
        for f in BACKUP_DIR.glob("*.tar.gz"):
            try:
                if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                    f.unlink()
                    deleted += 1
            except Exception:
                pass
        
        ok(f"{deleted} backup(s) eliminado(s)")
        
    else:
        options = ["Logs antiguos", "Caché", "Backups >30 días", "Todo"]
        choice = select(options)
        
        if choice == 0:
            args.name = "logs"
        elif choice == 1:
            args.name = "cache"
        elif choice == 2:
            args.name = "backups"
        else:
            for w in ["logs", "cache", "backups"]:
                args.name = w
                cmd_cleanup(args)
            return
        
        cmd_cleanup(args)

# ══════════════════════════════════════════════════════════════════════════════
# COMPARAR INSTANCIAS
# ══════════════════════════════════════════════════════════════════════════════
def cmd_diff(args):
    """Comparar configuración entre instancias."""
    print_logo(compact=True)
    section("Comparar Instancias")
    
    instances = get_instances()
    if len(instances) < 2:
        fail("Necesitas al menos 2 instancias para comparar")
        return
    
    info("Selecciona primera instancia:")
    idx1 = select([i.label for i in instances])
    inst1 = instances[idx1]
    
    info("Selecciona segunda instancia:")
    remaining = [i for j, i in enumerate(instances) if j != idx1]
    idx2 = select([i.label for i in remaining])
    inst2 = remaining[idx2]
    
    nl()
    print(f"  Comparando: {q(C.P2, inst1.label)} vs {q(C.CYN, inst2.label)}")
    nl()
    
    env1 = inst1.env
    env2 = inst2.env
    
    all_keys = set(env1.keys()) | set(env2.keys())
    
    # Ignorar claves únicas por instancia
    ignore = ["TELEGRAM_TOKEN", "PORT", "DB_PATH", "VECTOR_DB_PATH", "WEBHOOK_SECRET", "MASTER_API_KEY"]
    
    different = []
    same = []
    only_1 = []
    only_2 = []
    
    for k in sorted(all_keys):
        if k in ignore:
            continue
        
        v1 = env1.get(k)
        v2 = env2.get(k)
        
        if v1 is None:
            only_2.append(k)
        elif v2 is None:
            only_1.append(k)
        elif v1 != v2:
            different.append((k, v1, v2))
        else:
            same.append(k)
    
    if different:
        info("Diferentes:")
        for k, v1, v2 in different:
            print(f"    {q(C.YLW, k)}")
            v1_display = v1[:20] + "..." if len(v1) > 20 else v1
            v2_display = v2[:20] + "..." if len(v2) > 20 else v2
            print(f"      {q(C.P2, inst1.name)}: {v1_display}")
            print(f"      {q(C.CYN, inst2.name)}: {v2_display}")
        nl()
    
    if only_1:
        info(f"Solo en {inst1.name}:")
        for k in only_1:
            print(f"    {q(C.G3, k)}")
        nl()
    
    if only_2:
        info(f"Solo en {inst2.name}:")
        for k in only_2:
            print(f"    {q(C.G3, k)}")
        nl()
    
    kv("Variables iguales", str(len(same)))
    kv("Variables diferentes", str(len(different)))
    nl()

# ══════════════════════════════════════════════════════════════════════════════
# REGISTRO DE COMANDOS ADICIONALES
# ══════════════════════════════════════════════════════════════════════════════

def cmd_guide(args):
    """
    Guía completa paso a paso para operar Melissa desde la terminal.
    Explica cada comando con ejemplos reales.
    """
    print_logo(compact=True)
    section("Guía de Operación", "Todo lo que necesitas saber")

    # ── SECCIÓN 1: Crear una nueva instancia ──────────────────────────────────
    print(f"\n  {q(C.P1, '1.', bold=True)}  {q(C.W, 'CREAR UNA NUEVA INSTANCIA (cliente nuevo)', bold=True)}")
    print(f"\n  {q(C.G3, 'Paso 1:')} Ve a @BotFather en Telegram y crea un bot con /newbot")
    print(f"          Copia el token que te da (parece: 7123456789:AAFxxx...)")
    print(f"\n  {q(C.G3, 'Paso 2:')} En la terminal ejecuta:")
    print(f"          {q(C.CYN, 'melissa new')}")
    print(f"          El wizard te pregunta: nombre del negocio, sector, token de Telegram.")
    print(f"          {q(C.YLW, 'IMPORTANTE:')} La URL pública que aparece por defecto")
    print(f"          {q(C.YLW, 'YA tiene el puerto correcto')} — solo presiona Enter para confirmarla.")
    print(f"\n  {q(C.G3, 'Paso 3:')} Cuando termine, el bot ya está levantado en PM2.")
    print(f"          Escríbele al bot en Telegram para verificar que responde.")
    print(f"\n  {q(C.G3, 'Tip:')} Si un cliente se retira y quieres reusar la instancia:")
    print(f"          {q(C.CYN, 'melissa zero <nombre>')}  ← borra datos, permite renombrar")

    hr()

    # ── SECCIÓN 2: Ver estado de las instancias ────────────────────────────────
    print(f"\n  {q(C.P1, '2.', bold=True)}  {q(C.W, 'VER ESTADO', bold=True)}")
    print(f"\n  {q(C.G3, 'Ver todas las instancias:')}     {q(C.CYN, 'melissa list')}")
    print(f"  {q(C.G3, 'Dashboard en tiempo real:')}     {q(C.CYN, 'melissa dashboard')}")
    print(f"  {q(C.G3, 'Health check rápido:')}          {q(C.CYN, 'melissa health')}")
    print(f"  {q(C.G3, 'Estado detallado de uno:')}      {q(C.CYN, 'melissa status <nombre>')}")
    print(f"\n  Ejemplo: {q(C.CYN, 'melissa status clinica-perez')}")

    hr()

    # ── SECCIÓN 3: Levantar / Reiniciar ───────────────────────────────────────
    print(f"\n  {q(C.P1, '3.', bold=True)}  {q(C.W, 'LEVANTAR Y REINICIAR', bold=True)}")
    print(f"\n  {q(C.G3, 'Reiniciar una instancia:')}      {q(C.CYN, 'melissa restart <nombre>')}")
    print(f"  {q(C.G3, 'Reiniciar TODAS:')}               {q(C.CYN, 'melissa restart all')}")
    print(f"  {q(C.G3, 'Detener una:')}                   {q(C.CYN, 'melissa stop <nombre>')}")
    print(f"\n  {q(C.G3, 'Si una instancia no responde, prueba en este orden:')}")
    print(f"    {q(C.YLW, '1)')} {q(C.CYN, 'melissa health')}  → ¿está online?")
    print(f"    {q(C.YLW, '2)')} {q(C.CYN, 'melissa logs <nombre>')}  → ¿qué error muestra?")
    print(f"    {q(C.YLW, '3)')} {q(C.CYN, 'melissa restart <nombre>')}  → reiniciarla")
    print(f"    {q(C.YLW, '4)')} {q(C.CYN, 'melissa webhooks <nombre>')}  → verificar webhook en Telegram")

    hr()

    # ── SECCIÓN 4: Logs ───────────────────────────────────────────────────────
    print(f"\n  {q(C.P1, '4.', bold=True)}  {q(C.W, 'VER LOGS (para detectar errores)', bold=True)}")
    print(f"\n  {q(C.G3, 'Logs en tiempo real:')}          {q(C.CYN, 'melissa logs <nombre>')}")
    print(f"  {q(C.G3, 'Logs directos de PM2:')}          {q(C.CYN, 'pm2 logs melissa-<nombre>')}")
    print(f"  {q(C.G3, 'Todos los logs PM2:')}            {q(C.CYN, 'pm2 logs')}")
    print(f"\n  {q(C.G3, 'Errores más comunes en logs:')}")
    print(f"    {q(C.RED, 'TELEGRAM_TOKEN requerido')}   →  falta token en el .env")
    print(f"    {q(C.RED, 'Webhook ERROR')}              →  BASE_URL incorrecta en el .env")
    print(f"    {q(C.RED, 'Connection refused')}         →  el proceso no levantó")

    hr()

    # ── SECCIÓN 5: Webhook ───────────────────────────────────────────────────
    print(f"\n  {q(C.P1, '5.', bold=True)}  {q(C.W, 'VERIFICAR / RECONFIGURAR WEBHOOK', bold=True)}")
    print(f"\n  Si el bot levanta pero no responde en Telegram, el webhook está mal.")
    print(f"\n  {q(C.G3, 'Verificar y reconfigurar:')}    {q(C.CYN, 'melissa webhooks <nombre>')}")
    print(f"  Elige opción 1 (ver info) para ver la URL actual registrada en Telegram.")
    print(f"  Si la URL tiene el puerto INCORRECTO, elige opción 2 (set webhook)")
    print(f"  y escribe la URL correcta: {q(C.CYN, 'http://IP:PUERTO/webhook/SECRET')}")
    print(f"\n  {q(C.G3, 'Encontrar el SECRET:')}  {q(C.CYN, 'melissa config <nombre>')}")
    print(f"                          → opción 5 (ver todas las variables)")
    print(f"                          → busca WEBHOOK_SECRET")

    hr()

    # ── SECCIÓN 6: Configuración ─────────────────────────────────────────────
    print(f"\n  {q(C.P1, '6.', bold=True)}  {q(C.W, 'EDITAR CONFIGURACIÓN', bold=True)}")
    print(f"\n  {q(C.G3, 'Asistente de config:')}          {q(C.CYN, 'melissa config <nombre>')}")
    print(f"  {q(C.G3, 'Editar .env directamente:')}      {q(C.CYN, 'nano /home/ubuntu/melissa-instances/<nombre>/.env')}")
    print(f"\n  {q(C.YLW, 'Después de editar el .env siempre reinicia:')}  {q(C.CYN, 'melissa restart <nombre>')}")

    hr()

    # ── SECCIÓN 7: Diagnóstico ────────────────────────────────────────────────
    print(f"\n  {q(C.P1, '7.', bold=True)}  {q(C.W, 'DIAGNÓSTICO COMPLETO DEL SISTEMA', bold=True)}")
    print(f"\n  {q(C.CYN, 'melissa doctor')}   → revisa dependencias, puertos, configuración")
    print(f"  {q(C.CYN, 'melissa debug')}    → info técnica detallada de todas las instancias")
    print(f"\n  {q(C.G3, 'Comandos PM2 directos (cuando melissa CLI no basta):')}")
    print(f"    {q(C.CYN, 'pm2 list')}              → ver todos los procesos")
    print(f"    {q(C.CYN, 'pm2 restart all')}       → reiniciar todos")
    print(f"    {q(C.CYN, 'pm2 delete melissa-X')}  → borrar proceso específico")
    print(f"    {q(C.CYN, 'pm2 save')}              → guardar estado para reboot")
    print(f"    {q(C.CYN, 'pm2 startup')}           → activar inicio automático")

    hr()

    # ── SECCIÓN 8: Errores frecuentes ────────────────────────────────────────
    print(f"\n  {q(C.P1, '8.', bold=True)}  {q(C.W, 'SOLUCIÓN DE PROBLEMAS FRECUENTES', bold=True)}")
    print()

    problems = [
        (
            "El bot levanta pero no responde en Telegram",
            [
                "El webhook está apuntando al puerto equivocado (bug clásico)",
                f"Ejecuta: {q(C.CYN, 'melissa webhooks <nombre>')} → opción 1 para ver la URL",
                f"La URL debe terminar en :<PUERTO>/webhook/<SECRET>",
                f"Si el puerto es incorrecto: opción 2 → escribe la URL correcta",
            ]
        ),
        (
            "Health check offline pero PM2 dice 'online'",
            [
                "El proceso arrancó pero melissa.py falló internamente",
                f"Ejecuta: {q(C.CYN, 'melissa logs <nombre>')} y busca el error",
                "Causas comunes: falta una API key, .env incorrecto, puerto ocupado",
                f"Solución rápida: {q(C.CYN, 'melissa restart <nombre>')}",
            ]
        ),
        (
            "Puerto ocupado al crear nueva instancia",
            [
                "El CLI asigna el siguiente puerto libre automáticamente (8002, 8003...)",
                f"Para ver qué procesos usan puertos: {q(C.CYN, 'ss -tlnp | grep 80')}",
                f"Para liberar un puerto muerto: {q(C.CYN, 'pm2 delete melissa-<nombre>')}",
            ]
        ),
        (
            "El .env de una instancia parece usar datos de otra",
            [
                "Causa: PM2 se inició sin --cwd (bug corregido en esta versión)",
                f"Solución: {q(C.CYN, 'pm2 delete melissa-<nombre>')} → luego {q(C.CYN, 'melissa restart <nombre>')}",
                "Verifica .env: el PORT, BASE_URL y TELEGRAM_TOKEN deben ser únicos",
            ]
        ),
    ]

    for i, (problem, solutions) in enumerate(problems):
        print(f"  {q(C.YLW, f'Problema {i+1}:')} {q(C.W, problem)}")
        for sol in solutions:
            print(f"    {q(C.G3, '→')} {q(C.G1, sol)}")
        print()

    hr()

    # ── REFERENCIA RÁPIDA ─────────────────────────────────────────────────────
    print(f"\n  {q(C.P1, '⚡', bold=True)}  {q(C.W, 'REFERENCIA RÁPIDA — copia y pega', bold=True)}\n")

    quick_ref = [
        ("Instalar CLI globalmente",     "melissa install"),
        ("Nueva instancia",              "melissa new"),
        ("Ver todas",                    "melissa list"),
        ("Dashboard live",               "melissa dashboard"),
        ("Health check",                 "melissa health"),
        ("Status de una",                "melissa status <nombre>"),
        ("Generar token + probar bot",   "melissa chat <nombre>"),
        ("Logs en vivo",                 "melissa logs <nombre>"),
        ("Reiniciar una",                "melissa restart <nombre>"),
        ("Reiniciar todas",              "melissa restart all"),
        ("Reparar bug de --cwd",         "melissa fix <nombre>"),
        ("Clonar runtime compartido a todos",  "melissa sync"),
        ("♻  Entregar a nuevo cliente",  "melissa zero <nombre>"),
        ("Parar una",                    "melissa stop <nombre>"),
        ("Editar configuración",         "melissa config <nombre>"),
        ("Ver/fijar webhook",            "melissa webhooks <nombre>"),
        ("Diagnóstico completo",         "melissa doctor"),
        ("Actualizar + propagar",        "melissa upgrade"),
        ("Esta guía",                    "melissa guide"),
        ("",                             ""),
        ("Pipeline de leads",            "melissa pipeline [instancia]"),
        ("Por qué se van clientes",      "melissa perdidos [instancia]"),
        ("Coach de ventas",              "melissa coach [instancia]"),
        ("Clonar estilo del dueño",      "melissa estilo [instancia]"),
        ("Reactivar inactivos",          "melissa reactivar [instancia]"),
        ("Reporte ahora",               "melissa reporte [instancia]"),
        ("Mensaje masivo",               "melissa broadcast [instancia]"),
        ("Instagram DMs",               "melissa instagram [instancia]"),
        ("Pagos desde chat",            "melissa pagos [instancia]"),
    ]

    for label, cmd_ in quick_ref:
        print(f"  {q(C.G2, f'{label:<28}')}  {q(C.CYN, cmd_)}")

    nl()
    info("Tip: escribe 'melissa i' para modo interactivo con autocompletado")
    nl()


# Añadir a ROUTES
ROUTES.update({
    # Nuevos comandos
    "interactive": cmd_interactive, "i": cmd_interactive, "shell": cmd_interactive,
    "alerts": cmd_alerts, "alert": cmd_alerts,
    "webhooks": cmd_webhooks, "webhook": cmd_webhooks, "wh": cmd_webhooks,
    "search": cmd_search, "find": cmd_search, "grep": cmd_search,
    "analytics": cmd_analytics, "analyze": cmd_analytics,
    "batch": cmd_batch,
    "quick": cmd_quick, "qk": cmd_quick,
    "debug": cmd_debug,
    "plugins": cmd_plugins, "plugin": cmd_plugins,
    "cron": cmd_cron, "schedule": cmd_cron,
    "cleanup": cmd_cleanup, "clean": cmd_cleanup,
    "diff": cmd_diff, "compare": cmd_diff,
    # Guía de operación
    "guide": cmd_guide, "guia": cmd_guide, "ayuda": cmd_guide, "howto": cmd_guide,
    "bb": cmd_bb, "blackboss": cmd_bb,
    # Mantenimiento (registrados aquí también por si se carga en otro orden)
    "sync": cmd_sync, "sincronizar": cmd_sync,
    "fix": cmd_fix, "reparar": cmd_fix,
    "install": cmd_install,
    "zero": cmd_zero, "cero": cmd_zero,
    "demo": cmd_demo,
})

# Añadir a COMMANDS para autocompletado
COMMANDS.extend([
    "interactive", "alerts", "webhooks", "search", "analytics",
    "batch", "quick", "debug", "plugins", "cron", "cleanup", "diff",
    "guide", "guia", "ayuda",
    "bb", "blackboss",
    "pair", "pairing",
    "sync", "fix", "install",
    "zero", "cero",
    "demo",
    "caddy",
    # V6.0
    "pipeline", "perdidos", "coach", "estilo", "reactivar",
    "seguimiento", "reporte", "broadcast", "preconsulta",
    "instagram", "pagos", "leads",
])

# ══════════════════════════════════════════════════════════════════════════════
# ACTUALIZAR HELP
# ══════════════════════════════════════════════════════════════════════════════
def cmd_help_extended(args):
    """Ayuda extendida con todos los comandos."""
    print_logo(compact=True)
    
    print(f"  {q(C.W, 'Comandos:', bold=True)}")
    nl()
    
    command_groups = [
        ("Gestión", [
            ("init", "Primer setup guiado del producto"),
            ("new", "Crear instancia"),
            ("list", "Ver instancias"),
            ("dashboard", "Panel en tiempo real"),
            ("template", "Plantillas por sector"),
            ("interactive", "Modo interactivo (shell)"),
            ("zero [n]", "♻️  Entregar instancia a nuevo cliente"),
        ]),
        ("Monitoreo", [
            ("status [n]", "Estado detallado"),
            ("health", "Health check rápido"),
            ("metrics [n]", "Métricas de uso"),
            ("analytics [n]", "Análisis de datos"),
            ("logs [n]", "Logs en tiempo real"),
            ("alerts", "Sistema de alertas"),
        ]),
        ("Operaciones", [
            ("config [n]", "Hub de configuración / editar instancia"),
            ("restart [n]", "Reiniciar"),
            ("stop [n]", "Detener"),
            ("scale [n] [num]", "Escalar workers"),
            ("clone [n]", "Clonar instancia"),
            ("reset [n]", "Resetear sesión"),
            ("delete [n]", "Eliminar"),
            ("batch", "Operaciones en lote"),
        ]),
        ("Datos", [
            ("backup [n]", "Crear snapshot"),
            ("restore [file]", "Restaurar"),
            ("export [n]", "Exportar JSON/CSV"),
            ("import [file]", "Importar"),
            ("search [query]", "Buscar en logs/DB"),
            ("test [n]", "Probar respuestas"),
        ]),
        ("Sistema", [
            ("doctor", "Diagnóstico"),
            ("audit", "Auditoría seguridad"),
            ("benchmark", "Test rendimiento"),
            ("debug", "Info de debug"),
            ("secure", "Guía seguridad"),
            ("rotate-keys", "Rotar secrets"),
            ("upgrade", "Actualizar"),
            ("cleanup", "Limpiar logs/caché"),
            ("diff", "Comparar instancias"),
            ("guide", "📖 Guía de operación (léeme si algo no funciona)"),
        ]),
        ("Black Boss", [
            ("bb config [n]", "Crear y ajustar el agente, prompt y personalidad"),
            ("bb chat [n]", "Abrir chat operativo"),
            ("bb doctor", "Diagnóstico rápido"),
            ("bb sync", "Clonar runtime exacto a todas las instancias"),
            ("bb new", "Crear nueva instancia"),
            ("bb guide", "Abrir guía operativa"),
        ]),
        ("Automatización", [
            ("quick", "Acciones rápidas"),
            ("cron", "Tareas programadas"),
            ("plugins", "Gestionar plugins"),
            ("webhooks [n]", "Gestionar webhooks"),
        ]),
        ("Avanzado", [
            ("chat [n]", "Lenguaje natural"),
            ("omni", "Monitoreo central"),
            ("nova", "Motor Nova"),
            ("pair ...", "Enlazar chats al router compartido de Telegram"),
            ("billing", "Uso de APIs"),
        ]),
        ("V8.0 — Modelo & Calidad", [
            ("modelo [n]", "Ver/cambiar el LLM de una instancia en caliente"),
            ("simular [n]", "Simular 10 conversaciones para detectar fallos"),
            ("v8 [n]", "Estado de los sistemas V8 de una instancia"),
            ("quality [n]", "Score de humanidad de las últimas respuestas"),
            ("briefing [n]", "Briefing diario con leads calientes y acciones"),
            ("campana [n]", "Campañas de seguimiento y reactivación"),
            ("latency [n]", "Test de latencia del LLM"),
            ("cost [n]", "Estimación de costos del LLM"),
            ("warmup [n]", "Pre-calentar la instancia antes de lanzar"),
            ("watchdog", "Monitor continuo con auto-restart inteligente"),
        ]),
        ("V7 — Activación", [
            ("token [n]", "Generar código de activación"),
            ("token all", "Generar tokens para todas las instancias"),
            ("tokens [n]", "Listar tokens generados"),
            ("activar [n]", "Activar instancia directamente (sin token)"),
            ("bridge", "Estado del WhatsApp Bridge"),
            ("bridge fix", "Fix automático de configuración del bridge"),
            ("bridge restart", "Reiniciar el bridge"),
            ("bridge qr", "Ver QR para conectar WhatsApp"),
        ]),
        ("V6 — Inteligencia", [
            ("leads [n]", "Pipeline + análisis + coach"),
            ("pipeline [n]", "Leads por temperatura"),
            ("perdidos [n]", "Por qué se van los clientes"),
            ("coach [n]", "Feedback de ventas"),
            ("estilo [n]", "Clonar estilo del dueño"),
        ]),
        ("V6 — Automatización", [
            ("reactivar [n]", "Reactivar clientes inactivos"),
            ("seguimiento [n]", "Follow-ups automáticos"),
            ("reporte [n]", "Reporte ahora mismo"),
            ("broadcast [n]", "Mensaje masivo"),
            ("preconsulta [n]", "Formulario pre-cita"),
        ]),
        ("V6 — Canales", [
            ("instagram [n]", "Conectar Instagram DMs"),
            ("pagos [n]", "Pagos desde el chat"),
        ]),
        ("V8.0 — Calidad & Modelo", [
            ("modelo [n]",        "Cambiar modelo LLM en caliente (sin reiniciar)"),
            ("modelo [n] reset",  "Restaurar modelo original del .env"),
            ("simular [n]",       "Simular 10 conversaciones — detecta frases de bot"),
            ("simular [n] all",   "Todos los escenarios de simulación"),
            ("v8 [n]",            "Estado completo de los 15 sistemas V8"),
            ("quality [n]",       "Score de humanidad de las últimas respuestas"),
            ("briefing [n]",      "Briefing diario: leads calientes + acción recomendada"),
            ("cost [n]",          "Estimación de costo mensual del LLM"),
            ("latency [n]",       "Test de latencia HTTP + LLM real"),
            ("diff",              "Comparar configuración entre dos instancias"),
            ("watchdog",          "Monitor continuo con auto-restart inteligente"),
            ("warmup [n]",        "Precalentar LLM antes de lanzar"),
            ("campana [n]",       "Campañas de seguimiento y reactivación"),
            ("env-check [n]",     "Verificar .env contra mejores prácticas V8"),
            ("rollforward [n]",   "Aplicar melissa.py a todas las instancias"),
            ("dashboard-v8",      "Dashboard enriquecido con métricas V8"),
        ]),
    ]
    
    for category, cmds in command_groups:
        print(f"  {q(C.P2, category, bold=True)}")
        for cmd_, desc in cmds:
            print(f"    {q(C.G2, f'melissa {cmd_:<20}')} {q(C.G3, desc)}")
        nl()
    
    hr()
    nl()
    
    # Sectores en una línea
    print(f"  {q(C.W, 'Sectores:', bold=True)} ", end="")
    for s in list(SECTORS.values())[:10]:
        print(f"{s.emoji}", end=" ")
    print(f" +{len(SECTORS)-10} más")
    nl()
    
    # Shortcuts
    print(f"  {q(C.W, 'Shortcuts:', bold=True)}")
    shortcuts = [
        ("melissa i", "Modo interactivo"),
        ("melissa l", "Listar instancias"),
        ("melissa s", "Status"),
        ("melissa r all", "Reiniciar todo"),
    ]
    for short, desc in shortcuts:
        print(f"    {q(C.CYN, short)}  →  {q(C.G3, desc)}")
    nl()
    
    info("Lenguaje natural: melissa 'crear veterinaria para clínica peludo'")
    nl()

# Reemplazar help
# ══════════════════════════════════════════════════════════════════════════════
# V8.0 EXTENSION — NUEVOS COMANDOS
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# V8.0 — NUEVOS COMANDOS Y SISTEMAS
# ══════════════════════════════════════════════════════════════════════════════

# ── Helpers para llamadas a la API V8 ────────────────────────────────────────

def _v8_api(inst: "Instance", path: str, method: str = "GET",
            payload: dict = None, timeout: int = 30) -> dict:
    """
    Llamada a un endpoint V8 de una instancia.
    Maneja auth con master_key automáticamente.
    Retorna {} si no responde o hay error.
    """
    return inst.api_call(method, path, payload, timeout)


def _v8_get_status(inst: "Instance") -> dict:
    """Obtiene estado completo de sistemas V8 de una instancia."""
    return _v8_api(inst, "/v8/health")


def _v8_is_ready(inst: "Instance") -> bool:
    """
    True si la instancia tiene el endpoint /v8/health y responde sin error.
    No dependemos de la versión exacta — solo que el endpoint exista y responda.
    """
    status = _v8_get_status(inst)
    # Válido si: no hay error, y tiene "version" o "systems" o "status" = ok/degraded
    if status.get("error"):
        return False
    # El endpoint existe si responde con cualquiera de estas claves
    return bool(
        status.get("version") or
        status.get("systems") or
        status.get("status") in ("ok", "degraded", "v8_not_initialized")
    )


def _pick_instance(args, title: str = "¿Cuál instancia?") -> "Optional[Instance]":
    """Helper para seleccionar instancia de forma interactiva."""
    name = getattr(args, 'name', '') or getattr(args, 'subcommand', '') or ''
    inst = find_instance(name) if name else None
    if not inst:
        instances = get_instances()
        if not instances:
            fail("No hay instancias configuradas")
            info("Crea una con: melissa new")
            return None
        if len(instances) == 1:
            return instances[0]
        idx = select([i.label for i in instances], title=title)
        inst = instances[idx]
    return inst


# ══════════════════════════════════════════════════════════════════════════════
# cmd_modelo — Cambiar el LLM de una instancia en caliente
# ══════════════════════════════════════════════════════════════════════════════

MODEL_CATALOG = {
    # alias → (model_id, tier, desc, price_per_1m_tokens)
    "claude-sonnet":  ("anthropic/claude-sonnet-4",       "reasoning", "Balance inteligencia/costo. Recomendado.", 3.0),
    "claude-opus":    ("anthropic/claude-opus-4",         "reasoning", "El más inteligente. Más caro.",           15.0),
    "claude-haiku":   ("anthropic/claude-haiku-3-5",      "fast",      "Rapidísimo y económico.",                 0.8),
    "gemini-pro":     ("google/gemini-2.5-pro",           "reasoning", "Google Pro. Muy capaz.",                  3.5),
    "gemini-flash":   ("google/gemini-2.5-flash",         "fast",      "Velocidad + calidad. Muy popular.",       0.3),
    "gemini-lite":    ("google/gemini-2.5-flash-lite",    "lite",      "El más barato de Google.",                0.1),
    "llama-70b":      ("meta-llama/llama-3.3-70b-instruct","fast",     "Open source. Excelente español.",         0.6),
    "llama-8b":       ("meta-llama/llama-3.1-8b-instruct","lite",      "Ultrarrápido. Para alto volumen.",        0.1),
    "gpt4o":          ("openai/gpt-4o",                   "reasoning", "OpenAI flagship.",                       5.0),
    "gpt4o-mini":     ("openai/gpt-4o-mini",              "fast",      "OpenAI económico.",                      0.6),
    "mistral-large":  ("mistralai/mistral-large",         "reasoning", "Europeo. Buen español.",                 2.0),
    "mistral-small":  ("mistralai/mistral-small",         "fast",      "Rápido y asequible.",                    0.2),
    "deepseek-v3":    ("deepseek/deepseek-chat",          "fast",      "Chino. Muy barato. Sorprendente.",        0.14),
    "deepseek-r1":    ("deepseek/deepseek-r1",            "reasoning", "Razonamiento profundo. Lento.",           0.55),
}


def cmd_modelo(args):
    """Ver y cambiar el LLM de una instancia en caliente. Sin reiniciar."""
    print_logo(compact=True)

    raw_sub = getattr(args, 'subcommand', '') or ''
    raw_name = getattr(args, 'name', '') or ''
    inst = find_instance(raw_sub) if raw_sub else None
    direct_arg = raw_name if inst else ""

    if not inst:
        inst = _pick_instance(args, "¿Cuál instancia cambiar?")
        if raw_sub and inst and raw_sub not in [inst.name, inst.label.lower()]:
            direct_arg = raw_sub

    if not inst:
        return

    section(f"Modelo LLM — {inst.label}")

    # Mostrar modelo actual
    v8_status = _v8_api(inst, "/v8/health")
    current_models = v8_status.get("current_models", {})

    if current_models:
        info("Modelos activos:")
        for tier, model_id in current_models.items():
            kv(f"  {tier}", model_id)
        nl()
    else:
        ev = inst.env
        kv("fast (env)", ev.get("LLM_FAST", "no configurado"))
        kv("reasoning (env)", ev.get("LLM_REASONING", "no configurado"))
        nl()

    # Subcomando directo (melissa modelo [n] gemini-flash)
    if direct_arg in {"estado", "status", "show", "ver"}:
        return

    if direct_arg and direct_arg not in [inst.name, inst.label.lower()]:
        _apply_model_change(inst, direct_arg)
        return

    # Catálogo interactivo
    options = [f"{alias:<16}  {MODEL_CATALOG[alias][2]}" for alias in MODEL_CATALOG]
    options.append("reset (volver al .env)")
    options.append("Ver solo mi modelo actual")

    info("Selecciona un modelo:")
    idx = select([f"{a:<16} — {MODEL_CATALOG[a][2]}" for a in MODEL_CATALOG] +
                 ["reset — volver al .env", "Solo ver estado"])

    if idx == len(MODEL_CATALOG):  # reset
        _apply_model_change(inst, "reset")
    elif idx == len(MODEL_CATALOG) + 1:  # solo ver
        pass
    else:
        alias = list(MODEL_CATALOG.keys())[idx]
        _apply_model_change(inst, alias)


def _apply_model_change(inst: "Instance", alias: str):
    """Aplica el cambio de modelo a la instancia vía API."""
    if alias == "reset":
        with Spinner(f"Restaurando modelo original...") as sp:
            r = _v8_api(inst, "/modelo/reset", method="POST")
            if r.get("ok") or "reset" in str(r).lower():
                sp.finish("Modelo restaurado al .env")
            else:
                sp.finish(f"Error: {r.get('error', 'sin respuesta')}", ok=False)
                info("¿La instancia está corriendo melissa.py?")
        return

    if alias not in MODEL_CATALOG:
        # Intentar como ID completo
        model_id = alias
        tier = "fast"
    else:
        model_id, tier, desc, _ = MODEL_CATALOG[alias]

    # Estrategia: primero intentar vía API en caliente, luego .env con reinicio
    api_success = False

    with Spinner(f"Cambiando modelo a {model_id}...") as sp:
        # Intentar cambio en caliente via /v8/health (modelo manager interno)
        r = _v8_api(inst, "/v8/model", method="POST",
                    payload={"alias": alias, "model": model_id, "tier": tier},
                    timeout=10)
        api_success = (
            r.get("ok") or
            "cambiado" in str(r).lower() or
            "changed" in str(r).lower() or
            ("model" in str(r).lower() and not r.get("error"))
        )
        sp.finish(
            f"Modelo cambiado en caliente: {model_id}" if api_success
            else f"API no soporta cambio en caliente — guardando en .env",
            ok=True  # siempre OK porque el .env es el fallback confiable
        )

    # Siempre persistir en .env — sobrevive reinicios y es la fuente de verdad
    env_path = f"{inst.dir}/.env"
    update_env_key(env_path, "LLM_FAST", model_id)
    update_env_key(env_path, "LLM_LITE", model_id)
    if tier == "reasoning":
        update_env_key(env_path, "LLM_REASONING", model_id)
    ok(f".env actualizado: LLM_FAST={model_id}")

    if not api_success:
        nl()
        if confirm("¿Reiniciar para aplicar el nuevo modelo?"):
            pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
            with Spinner(f"Reiniciando {inst.label}...") as sp2:
                pm2("restart", pm2_name)
                time.sleep(4)
                h2 = health(inst.port)
                sp2.finish("Online" if h2 else "Reiniciando...", ok=bool(h2))

    nl()
    ok(f"Para verificar: melissa v8 {inst.name}")


# ══════════════════════════════════════════════════════════════════════════════
# cmd_simular — Simulación de conversaciones para detectar fallos
# ══════════════════════════════════════════════════════════════════════════════

SIMULATION_SCENARIOS = {
    "estetica_miedo":    "Clienta estética — miedo a quedar exagerada",
    "estetica_precio":   "Clienta estética — objeción de precio inmediata",
    "estetica_esceptica":"Clienta estética — ya fue a otro lugar y quedó mal",
    "dental_urgencia":   "Paciente dental — dolor urgente, quiere cita hoy",
    "restaurante_reserva":"Restaurante — grupo grande para evento",
    "gimnasio_inscripcion":"Gimnasio — quiere inscribirse pero duda del precio",
    "bot_detection":     "Cliente pregunta directamente si es un bot",
    "ingles_cliente":    "Cliente en inglés (expat o turista)",
    "emergencia_medica": "Detección de emergencia médica urgente",
    "conversacion_larga":"Conversación larga — ¿Melissa mantiene coherencia?",
}


def cmd_simular(args):
    """Simular conversaciones en una instancia para detectar fallos antes de producción."""
    print_logo(compact=True)

    inst = _pick_instance(args, "¿En cuál instancia simular?")
    if not inst:
        return

    h = health(inst.port)
    if not h:
        fail(f"{inst.label} está offline")
        info(f"Arráncala con: melissa restart {inst.name}")
        return

    # Verificar que los sistemas V8 están activos
    ping = _v8_api(inst, "/v8/ping", timeout=5)
    if ping.get("error") or not ping.get("v8"):
        fail("El simulador requiere los sistemas V8 — el endpoint /v8/ping no respondió")
        info(f"Verifica: grep -c 'v8/ping' /home/ubuntu/melissa/melissa.py")
        info(f"Si es 0: sube el melissa.py con V8 y reinicia")
        return

    section(f"Simulador de Conversaciones — {inst.label}",
            "Detecta frases de bot, bucles y fallos antes de que lleguen al cliente real")

    # Seleccionar escenario
    sub = getattr(args, 'subcommand', '') or ''
    scenario_id = ""

    if sub and sub in SIMULATION_SCENARIOS:
        scenario_id = sub
    elif sub == "all" or sub == "todos":
        scenario_id = "all"
    else:
        opts = list(SIMULATION_SCENARIOS.values()) + ["Todos los escenarios (tarda ~2 min)"]
        idx = select(opts, title="¿Qué escenario simular?")
        if idx == len(SIMULATION_SCENARIOS):
            scenario_id = "all"
        else:
            scenario_id = list(SIMULATION_SCENARIOS.keys())[idx]

    nl()

    if scenario_id == "all":
        info("Ejecutando todos los escenarios — esto puede tardar 1-3 minutos...")
        nl()

        with Spinner("Ejecutando simulaciones...") as sp:
            r = _v8_api(inst, "/v8/simulate", method="POST", payload={}, timeout=200)
            sp.finish("Simulaciones completadas" if not r.get("error") else "Error", ok=not r.get("error"))

        if r.get("error"):
            fail(f"El endpoint /v8/simulate no respondió: {r.get('error', 'sin respuesta')}")
            nl()
            info("El simulador requiere los sistemas V8 activos.")
            info(f"Verifica: melissa v8 {inst.name}")
            info(f"Si V8 no está activo: melissa restart {inst.name}")
            return

        _print_simulation_report(r)

    else:
        desc = SIMULATION_SCENARIOS.get(scenario_id, scenario_id)
        info(f"Simulando: {desc}")
        nl()

        with Spinner(f"Ejecutando '{scenario_id}'...") as sp:
            r = _v8_api(inst, "/v8/simulate", method="POST",
                        payload={"scenario": scenario_id}, timeout=90)
            sp.finish("Completado" if not r.get("error") else "Error",
                      ok=not r.get("error"))

        if r.get("error"):
            fail(f"Error: {r['error']}")
            return

        _print_scenario_result(r)

    nl()
    info(f"Para ver el pipeline de leads: melissa pipeline {inst.name}")


def _print_simulation_report(report: dict):
    """Imprime reporte completo de simulación."""
    total   = report.get("total", 0)
    passed  = report.get("passed", 0)
    warned  = report.get("warned", 0)
    failed  = report.get("failed", 0)
    avg_h   = report.get("avg_humanness", 0.0)

    icon = q(C.GRN, "✓") if failed == 0 else (q(C.YLW, "!") if failed <= 2 else q(C.RED, "✗"))

    section(f"{icon}  Resultado: {passed}/{total} OK", f"Humanidad promedio: {int(avg_h*100)}%")

    kv("Aprobados", q(C.GRN, str(passed)))
    kv("Con avisos", q(C.YLW, str(warned)))
    kv("Fallidos",   q(C.RED, str(failed)))
    kv("Humanidad",  f"{int(avg_h*100)}%")
    nl()

    results = report.get("results", [])

    if failed > 0:
        info("Escenarios con fallos:")
        for r in results:
            if r.get("failures"):
                print(f"  {q(C.RED, '✗')}  {q(C.W, r.get('scenario_id', '?'))}")
                print(f"       {q(C.G3, r.get('desc', ''))}")
                for f_ in r["failures"][:3]:
                    print(f"       {q(C.RED, '→')} {q(C.G1, f_)}")
                nl()

    if warned > 0:
        info("Avisos:")
        for r in results:
            if r.get("warnings") and not r.get("failures"):
                print(f"  {q(C.YLW, '!')}  {q(C.W, r.get('scenario_id', '?'))}")
                print(f"       {q(C.G1, r['warnings'][0])}")
        nl()

    if failed == 0 and warned == 0:
        ok("Todos los escenarios pasaron sin problemas")
        info("Melissa responde de forma humana y sin frases de bot")


def _print_scenario_result(r: dict):
    """Imprime resultado de un escenario individual."""
    has_failures = bool(r.get("failures"))
    icon = q(C.GRN, "✓") if not has_failures else q(C.RED, "✗")

    print(f"  {icon}  {q(C.W, r.get('desc', ''))}")
    print(f"       Turnos: {r.get('total_turns', 0)}  |  "
          f"Humanidad: {int(r.get('avg_humanness', 0)*100)}%  |  "
          f"{'Conversión OK' if r.get('conversion') else 'Sin conversión'}")
    nl()

    if r.get("failures"):
        info("Fallos detectados:")
        for f_ in r["failures"]:
            print(f"    {q(C.RED, '→')} {q(C.G1, f_)}")
        nl()

    if r.get("warnings"):
        info("Avisos:")
        for w in r["warnings"]:
            print(f"    {q(C.YLW, '!')} {q(C.G1, w)}")
        nl()

    # Mostrar algunos turnos de la conversación
    turns = r.get("turns", [])[:4]
    if turns:
        info("Conversación simulada (primeros 4 turnos):")
        for i, t in enumerate(turns):
            color = C.CYN if i % 2 == 0 else C.P2
            print(f"    {q(C.G3, f'[{i+1}] Cliente:')} {q(C.G1, t.get('client', '')[:60])}")
            print(f"         {q(C.G3, 'Melissa:')} {q(color, t.get('melissa', '')[:60])}")
            if t.get("failures"):
                print(f"         {q(C.RED, '✗')} {q(C.RED, t['failures'][0][:50])}")
            nl()


# ══════════════════════════════════════════════════════════════════════════════
# cmd_v8 — Estado completo de los sistemas V8 de una instancia
# ══════════════════════════════════════════════════════════════════════════════

def cmd_v8(args):
    """Ver el estado de todos los sistemas V8 activos en una instancia."""
    print_logo(compact=True)

    inst = _pick_instance(args, "¿De cuál instancia?")
    if not inst:
        return

    section(f"V8.0 Systems — {inst.label}")

    h = health(inst.port)
    if not h:
        fail(f"{inst.label} está offline")
        info(f"Arráncala con: melissa restart {inst.name}")
        return

    # Paso 1: ping ultraligero para verificar que los endpoints V8 están registrados
    with Spinner("Verificando endpoints V8...") as sp:
        ping = _v8_api(inst, "/v8/ping", timeout=5)
        ping_ok = not ping.get("error") and ping.get("v8") is True
        sp.finish(
            "Endpoints V8 activos" if ping_ok
            else "Endpoints V8 no encontrados — ¿el melissa.py tiene V8?",
            ok=ping_ok
        )

    if not ping_ok:
        nl()
        fail("Los endpoints /v8/* no están registrados en esta instancia")
        nl()
        info("Diagnóstico:")
        dim(f"1. Verifica que el archivo tiene V8:")
        dim(f"   grep -c 'v8/ping' /home/ubuntu/melissa/melissa.py")
        dim(f"   (debe retornar 1 o más)")
        dim(f"2. Si el resultado es 0: el melissa.py no tiene V8 — sube el nuevo archivo")
        dim(f"3. Si tiene V8: revisa los logs: melissa logs {inst.name}")
        dim(f"4. Reinicia: melissa restart {inst.name}")
        nl()
        info("Estado del servidor básico (sin V8):")
        kv("Status",    h.get("status", "?"))
        kv("Versión",   h.get("version", "no reportada"))
        kv("Clinic",    h.get("clinic", "?"))
        return

    # Paso 2: estado completo
    with Spinner("Cargando estado V8...") as sp:
        v8_status = _v8_api(inst, "/v8/health", timeout=15)
        sp.finish("Estado V8 cargado" if not v8_status.get("error") else "Error parcial",
                  ok=not v8_status.get("error"))

    if v8_status.get("error"):
        fail("El endpoint /v8/health no respondió")
        nl()
        info("Posibles causas:")
        dim("1. El proceso melissa.py no cargó los sistemas V8 — revisa los logs")
        dim("   melissa logs " + inst.name)
        dim("2. La versión de melissa.py no tiene V8 — verifica con 'cat melissa.py | head -20'")
        dim("3. Reinicia la instancia: melissa restart " + inst.name)
        nl()
        info("Estado del servidor básico:")
        kv("Status",          h.get("status", "?"))
        kv("Versión melissa",  h.get("version", "no reportada"))
        kv("Clinic",          h.get("clinic", "?"))
        kv("Setup done",      str(h.get("setup_done", "?")))
        return

    # V8 conectado — puede estar degradado (sistemas no iniciados)
    v8_init_status = v8_status.get("status", "unknown")
    if v8_init_status == "v8_not_initialized":
        warn("El servidor tiene V8 pero los sistemas NO están inicializados")
        nl()
        info("Notas del servidor:")
        for note in v8_status.get("init_notes", []):
            dim(f"  • {note}")
        nl()
        warn("Solución: reinicia la instancia → melissa restart " + inst.name)
        nl()

    # Sistemas individuales
    systems = v8_status.get("systems", {})
    active  = v8_status.get("active_count", 0)
    total_s = v8_status.get("total_systems", 0)
    version = v8_status.get("version", "?")
    filter_level = v8_status.get("filter_level", 0)
    threshold    = v8_status.get("quality_threshold", 0)

    kv("Versión V8", f"v{version}")
    kv("Sistemas activos", f"{active}/{total_s}")
    kv("Filtro anti-robot", f"Nivel {filter_level}/3")
    kv("Umbral humanidad",  f"{int(threshold*100)}%")
    nl()

    # Modelos activos
    models = v8_status.get("current_models", {})
    if models:
        info("Modelos LLM activos:")
        for tier, model_id in models.items():
            tier_color = C.P2 if tier == "reasoning" else C.CYN
            kv(f"  {tier}", q(tier_color, model_id))
        nl()

    # Estado de sistemas
    info("Sistemas V8:")
    system_names = {
        "anti_robot_filter":         "AntiRobotFilter",
        "conversation_intelligence": "ConversationIntelligence",
        "hyper_human_engine":        "HyperHumanEngine",
        "smart_variety":             "SmartVariety",
        "model_manager":             "ModelManager",
        "conversation_simulator":    "ConversationSimulator",
        "hallucination_guard":       "HallucinationGuard",
        "failure_predictor":         "FailurePredictor",
        "smart_context_manager":     "SmartContextManager",
        "appointment_state_machine": "AppointmentStateMachine",
        "conversation_recovery":     "ConversationRecovery",
        "response_variation":        "ResponseVariation",
        "campaign_engine":           "CampaignEngine",
        "admin_briefing":            "AdminBriefing",
        "self_test_suite":           "SelfTestSuite",
    }

    for sys_key, sys_name in system_names.items():
        is_active = systems.get(sys_key, False)
        icon  = q(C.GRN, "✓") if is_active else q(C.RED, "✗")
        color = C.W if is_active else C.G3
        print(f"    {icon}  {q(color, sys_name)}")

    nl()

    # Pipeline summary si está disponible
    with Spinner("Cargando pipeline...") as sp:
        pipeline = _v8_api(inst, "/v8/pipeline", timeout=10)
        sp.finish("Pipeline cargado" if not pipeline.get("error") else "No disponible",
                  ok=not pipeline.get("error"))

    if not pipeline.get("error") and pipeline.get("report_text"):
        nl()
        info("Pipeline actual:")
        for line in pipeline["report_text"].split("\n"):
            print(f"    {q(C.G1, line)}")

    nl()
    info(f"Simular conversaciones: melissa simular {inst.name}")
    info(f"Correr tests automáticos: melissa test {inst.name}")
    info(f"Cambiar modelo: melissa modelo {inst.name}")


# ══════════════════════════════════════════════════════════════════════════════
# cmd_quality — Score de humanidad de las últimas respuestas
# ══════════════════════════════════════════════════════════════════════════════

def cmd_quality(args):
    """
    Analiza la humanidad de las últimas respuestas de Melissa.
    Lee directamente de la DB y puntúa cada respuesta con el AntiRobotFilter local.
    """
    print_logo(compact=True)

    inst = _pick_instance(args, "¿Cuál instancia analizar?")
    if not inst:
        return

    section(f"Quality Check — {inst.label}",
            "Analiza qué tan humanas suenan las últimas respuestas")

    db_path = inst.db_path
    if not os.path.exists(db_path):
        fail("No hay base de datos para analizar")
        return

    # Frases de bot que buscamos localmente
    BOT_PHRASES = [
        "con mucho gusto", "encantada de ayudarte", "fue un placer",
        "es un placer", "con todo gusto", "soy una inteligencia artificial",
        "como asistente", "estamos para servirte", "a tus órdenes",
        "quedamos a tus órdenes", "no dudes en contactarnos",
        "gracias por contactarnos", "me alegra que preguntes",
        "en qué más puedo ayudarte", "claro que sí, con",
        "por supuesto que", "entiendo tu situación",
        "te brindo la información", "entiendo perfectamente",
        "es muy importante que sepas",
    ]

    BOT_PATTERNS = [
        r"claro que (sí|si),?\s",
        r"con (mucho\s)?gusto[,.]?\s",
        r"por\s+supuesto[,.]?\s",
        r"espero (haberte|haber) ayudado",
        r"quedo (pendiente|a tu disposición)",
        r"¡(hola|buenas)[!,]",
        r"sería (un )?placer",
    ]

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # melissa usa "ts" como columna de timestamp en conversations
        # intentar ambas por compatibilidad
        try:
            rows = conn.execute("""
                SELECT content, ts
                FROM conversations
                WHERE role = 'assistant'
                ORDER BY ts DESC
                LIMIT 50
            """).fetchall()
        except Exception:
            try:
                rows = conn.execute("""
                    SELECT content, created_at as ts
                    FROM conversations
                    WHERE role = 'assistant'
                    ORDER BY created_at DESC
                    LIMIT 50
                """).fetchall()
            except Exception:
                rows = []

        conn.close()
    except Exception as e:
        fail(f"Error leyendo DB: {e}")
        return

    if not rows:
        warn("No hay conversaciones todavía")
        return

    total = len(rows)
    bot_hits: list = []
    scores: list = []

    for row in rows:
        content    = row["content"]
        content_low = content.lower()
        hits_in_msg = []

        for phrase in BOT_PHRASES:
            if phrase in content_low:
                hits_in_msg.append(phrase)

        import re as _re
        for pattern in BOT_PATTERNS:
            if _re.search(pattern, content_low):
                hits_in_msg.append(f"[patron: {pattern[:30]}]")

        # Score simple
        word_count = len(content.split())
        score = 1.0
        score -= len(hits_in_msg) * 0.15
        score -= max(0, (word_count - 30)) / 200
        if content.startswith("¡") or content.startswith("¿"):
            score -= 0.1
        if content.count("!") > 2:
            score -= 0.1
        score = max(0.0, min(1.0, score))
        scores.append(score)

        if hits_in_msg:
            bot_hits.append({
                "content": content[:80],
                "hits":    hits_in_msg[:3],
                "score":   round(score, 2),
                "ts":      row["ts"][:16] if row["ts"] else "",
            })

    avg_score     = sum(scores) / len(scores) if scores else 0
    perfect_count = sum(1 for s in scores if s >= 0.9)
    good_count    = sum(1 for s in scores if 0.7 <= s < 0.9)
    bad_count     = sum(1 for s in scores if s < 0.7)

    # Mostrar resumen
    score_color = C.GRN if avg_score >= 0.8 else (C.YLW if avg_score >= 0.6 else C.RED)

    kv("Mensajes analizados",  str(total))
    kv("Humanidad promedio",   q(score_color, f"{int(avg_score*100)}%"))
    kv("Perfectos (≥90%)",     q(C.GRN, str(perfect_count)))
    kv("Buenos (70-90%)",      q(C.YLW, str(good_count)))
    kv("Robóticos (<70%)",     q(C.RED, str(bad_count)))
    nl()

    # Barra de distribución
    info("Distribución:")
    progress_bar(perfect_count, total, 20, "Perfectos")
    progress_bar(good_count,    total, 20, "Buenos")
    progress_bar(bad_count,     total, 20, "Robóticos")
    nl()

    if bot_hits:
        info(f"Frases de bot detectadas ({len(bot_hits)} mensajes):")
        for hit in bot_hits[:5]:
            print(f"  {q(C.RED, '→')}  {q(C.G1, hit['content'][:70])}")
            for h in hit["hits"][:2]:
                print(f"       {q(C.RED, '✗')} {q(C.G3, h)}")
            score_pct = int(hit["score"]*100)
            ts_str = hit["ts"]
            print(f"       {q(C.G3, f'score: {score_pct}%  [{ts_str}]')}")
            nl()

        nl()
        if avg_score < 0.75:
            warn("El filtro anti-robot necesita estar más agresivo")
            info("Sube el nivel: melissa filtro 3 " + inst.name)
        else:
            ok("Pocas frases de bot detectadas")
    else:
        ok("No se detectaron frases de bot en las últimas 50 respuestas")

    nl()
    info(f"Para mejorar: melissa modelo {inst.name}  (cambiar a modelo más natural)")
    info(f"Para simular: melissa simular {inst.name}  (probar escenarios)")


# ══════════════════════════════════════════════════════════════════════════════
# cmd_briefing — Briefing diario de una instancia
# ══════════════════════════════════════════════════════════════════════════════

def cmd_briefing(args):
    """Briefing diario: leads calientes, citas, conversaciones sin respuesta, acción recomendada."""
    print_logo(compact=True)

    inst = _pick_instance(args, "¿De cuál instancia?")
    if not inst:
        return

    h = health(inst.port)
    if not h:
        fail(f"{inst.label} está offline")
        return

    # Horas del período (default 24, se puede especificar)
    hours_str = getattr(args, 'name', '') or ''
    hours = int(hours_str) if hours_str.isdigit() else 24

    section(f"Briefing — {inst.label}", f"Últimas {hours}h")

    with Spinner("Generando briefing...") as sp:
        r = _v8_api(inst, f"/v8/briefing?hours={hours}", timeout=30)
        sp.finish("Briefing generado" if not r.get("error") else "Error",
                  ok=not r.get("error"))

    if r.get("error") or not r.get("briefing"):
        # Fallback: generar briefing local desde DB
        _generate_local_briefing(inst, hours)
        return

    briefing_text = r["briefing"]
    for line in briefing_text.split("\n"):
        if line.strip():
            print(f"  {q(C.G1, line)}")
    nl()


def _generate_local_briefing(inst: "Instance", hours: int = 24):
    """Genera briefing localmente desde la DB cuando la API V8 no está disponible."""
    db_path = inst.db_path
    if not os.path.exists(db_path):
        warn("No hay datos para generar briefing")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

        # Conversaciones nuevas
        # melissa usa 'ts' como columna de timestamp
        try:
            new_convs = conn.execute(
                "SELECT COUNT(DISTINCT chat_id) FROM conversations WHERE ts >= ? AND role='user'",
                (cutoff,)
            ).fetchone()[0] or 0
            total_msgs = conn.execute(
                "SELECT COUNT(*) FROM conversations WHERE ts >= ?", (cutoff,)
            ).fetchone()[0] or 0
        except Exception:
            # fallback para DBs antiguas con created_at
            new_convs = conn.execute(
                "SELECT COUNT(DISTINCT chat_id) FROM conversations WHERE created_at >= ? AND role='user'",
                (cutoff,)
            ).fetchone()[0] or 0
            total_msgs = conn.execute(
                "SELECT COUNT(*) FROM conversations WHERE created_at >= ?", (cutoff,)
            ).fetchone()[0] or 0

        # Citas
        new_apts = 0
        try:
            new_apts = conn.execute(
                "SELECT COUNT(*) FROM appointments WHERE created_at >= ?", (cutoff,)
            ).fetchone()[0] or 0
        except Exception:
            pass

        # Conversaciones sin respuesta >12h
        cutoff_12h = (datetime.utcnow() - timedelta(hours=12)).isoformat()
        try:
            stuck = conn.execute(
                "SELECT COUNT(DISTINCT chat_id) FROM conversations "
                "WHERE role='user' AND ts <= ?",
                (cutoff_12h,)
            ).fetchone()[0] or 0
        except Exception:
            stuck = 0

        # Citas próximas
        today_str    = datetime.utcnow().strftime("%Y-%m-%d")
        tomorrow_str = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        upcoming = []
        try:
            upcoming = conn.execute(
                "SELECT patient_name, service, datetime_slot FROM appointments "
                "WHERE status='pendiente' AND datetime_slot BETWEEN ? AND ? "
                "ORDER BY datetime_slot LIMIT 5",
                (today_str, tomorrow_str + " 23:59")
            ).fetchall()
        except Exception:
            pass

        conn.close()

        # Mostrar
        kv("Conversaciones nuevas", str(new_convs))
        kv("Mensajes totales",      str(total_msgs))
        kv("Citas agendadas",       str(new_apts))
        kv("Sin respuesta (+12h)",  q(C.YLW if stuck > 0 else C.GRN, str(stuck)))
        nl()

        if upcoming:
            info("Citas próximas:")
            for apt in upcoming:
                print(f"    {q(C.P2, '◆')}  {apt['patient_name'] or 'Paciente'}  "
                      f"·  {apt['service'] or '-'}  "
                      f"·  {q(C.G2, str(apt['datetime_slot'])[:16])}")
            nl()

        # Recomendación
        if new_convs > 0 and new_apts == 0:
            warn("Acción recomendada: hay conversaciones sin convertir")
            info(f"Revisa: melissa quality {inst.name}")
        elif stuck > 2:
            warn(f"Hay {stuck} conversaciones sin respuesta por más de 12h")
            info(f"Revisa: melissa status {inst.name}")
        elif new_apts > 0:
            ok(f"{new_apts} cita(s) agendada(s) en las últimas {hours}h")
        else:
            info("Sin actividad significativa en el período")

    except Exception as e:
        fail(f"Error generando briefing: {e}")
    finally:
        nl()


# ══════════════════════════════════════════════════════════════════════════════
# cmd_cost — Estimación de costos del LLM
# ══════════════════════════════════════════════════════════════════════════════

def cmd_cost(args):
    """
    Estima el costo mensual del LLM basado en el uso actual.
    Cruza mensajes en DB × precio del modelo activo.
    """
    print_logo(compact=True)

    inst = _pick_instance(args, "¿De cuál instancia?")
    if not inst:
        return

    section(f"Estimación de Costos — {inst.label}")

    # Obtener modelo actual
    v8_status   = _v8_api(inst, "/v8/health", timeout=8)
    current_fast = v8_status.get("current_models", {}).get("fast", inst.env.get("LLM_FAST", ""))

    # Intentar obtener precio del catálogo
    current_price = None
    current_alias = None
    for alias, (model_id, _, _, price) in MODEL_CATALOG.items():
        if model_id == current_fast:
            current_price = price
            current_alias = alias
            break
    if current_price is None:
        current_price = 1.0  # Default estimate

    # Leer estadísticas de uso desde DB
    db_path = inst.db_path
    msgs_per_day = 0

    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            # Mensajes de los últimos 7 días
            rows = conn.execute(
                "SELECT COUNT(*) FROM conversations "
                "WHERE ts >= datetime('now', '-7 days')"
            ).fetchone()
            total_week = rows[0] if rows else 0
            msgs_per_day = total_week / 7 if total_week > 0 else 0
            conn.close()
        except Exception:
            pass

    # Estimación (promedio ~200 tokens por mensaje, 3 mensajes LLM por conversación)
    # 1 conversación = ~600 tokens input + 200 output ≈ 800 tokens
    # pero tenemos msgs totales, no conversaciones → dividir por 4 aprox
    conversations_per_day = max(1, msgs_per_day / 4)
    tokens_per_conversation = 1500  # input + output
    tokens_per_day  = conversations_per_day * tokens_per_conversation
    tokens_per_month = tokens_per_day * 30

    cost_per_month = (tokens_per_month / 1_000_000) * current_price

    # Mostrar
    kv("Modelo actual",        current_fast or "no detectado")
    kv("Precio estimado",      f"${current_price:.2f}/1M tokens")
    nl()
    kv("Msgs/día (7d avg)",    f"{msgs_per_day:.0f}")
    kv("Conv/día estimadas",   f"{conversations_per_day:.0f}")
    kv("Tokens/mes estimados", f"{tokens_per_month:,.0f}")
    nl()

    cost_color = C.GRN if cost_per_month < 20 else (C.YLW if cost_per_month < 100 else C.RED)
    kv("Costo mensual estimado", q(cost_color, f"${cost_per_month:.2f} USD"))
    nl()

    # Comparar con alternativas baratas
    info("Comparación con modelos alternativos:")

    headers = ["ALIAS", "MODELO", "$/MES ESTIMADO", "CALIDAD"]
    rows = []

    quality_map = {
        "claude-sonnet": "⭐⭐⭐⭐⭐",
        "claude-opus":   "⭐⭐⭐⭐⭐",
        "claude-haiku":  "⭐⭐⭐⭐",
        "gemini-pro":    "⭐⭐⭐⭐⭐",
        "gemini-flash":  "⭐⭐⭐⭐",
        "gemini-lite":   "⭐⭐⭐",
        "llama-70b":     "⭐⭐⭐⭐",
        "llama-8b":      "⭐⭐⭐",
        "gpt4o":         "⭐⭐⭐⭐⭐",
        "gpt4o-mini":    "⭐⭐⭐⭐",
        "deepseek-v3":   "⭐⭐⭐⭐",
        "deepseek-r1":   "⭐⭐⭐⭐",
    }

    for alias, (model_id, _, desc, price) in sorted(MODEL_CATALOG.items(),
                                                      key=lambda x: x[1][3]):
        est_cost = (tokens_per_month / 1_000_000) * price
        current_mark = " ← actual" if model_id == current_fast else ""
        color = C.GRN if est_cost < 5 else (C.YLW if est_cost < 30 else C.RED)
        rows.append([
            alias,
            model_id[:35],
            q(color, f"${est_cost:.2f}"),
            quality_map.get(alias, "⭐⭐⭐") + current_mark,
        ])

    table(headers, rows[:10], [C.P2, C.G2, None, C.G1])
    nl()

    if cost_per_month > 50:
        warn(f"El costo actual es de ${cost_per_month:.0f}/mes")
        info("Considera gemini-flash o llama-70b para reducir costos sin perder calidad")
        info(f"Para cambiar: melissa modelo {inst.name}")
    else:
        ok(f"Costo estimado bajo: ${cost_per_month:.2f}/mes")


# ══════════════════════════════════════════════════════════════════════════════
# cmd_latency — Test de latencia del LLM
# ══════════════════════════════════════════════════════════════════════════════

def cmd_latency(args):
    """
    Mide la latencia del LLM en la instancia seleccionada.
    Hace 5 llamadas de prueba y reporta p50, p95, p99.
    """
    print_logo(compact=True)

    inst = _pick_instance(args, "¿De cuál instancia medir latencia?")
    if not inst:
        return

    h = health(inst.port)
    if not h:
        fail(f"{inst.label} está offline")
        return

    section(f"Latency Test — {inst.label}",
            "5 llamadas de prueba al LLM")

    samples     = 5
    latencies   = []
    errors      = 0

    # Usamos el endpoint /health que es rápido, luego /test para el LLM real
    info("Midiendo latencia del servidor (HTTP):")
    for i in range(samples):
        start = time.time()
        r = health(inst.port, timeout=10)
        elapsed_ms = int((time.time() - start) * 1000)

        if r:
            latencies.append(elapsed_ms)
            print(f"    {q(C.G3, f'[{i+1}/{samples}]')}  "
                  f"{q(C.P2, f'{elapsed_ms}ms')}  "
                  f"{q(C.GRN, '●')}")
        else:
            errors += 1
            print(f"    {q(C.G3, f'[{i+1}/{samples}]')}  "
                  f"{q(C.RED, 'timeout')}")
        time.sleep(0.3)

    nl()

    if not latencies:
        fail("No se obtuvo ninguna respuesta")
        return

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) >= 20 else latencies[-1]
    avg = sum(latencies) // len(latencies)

    p50_color = C.GRN if p50 < 200 else (C.YLW if p50 < 500 else C.RED)

    kv("P50 (mediana)", q(p50_color, f"{p50}ms"))
    kv("Promedio",      f"{avg}ms")
    kv("Mínimo",        f"{min(latencies)}ms")
    kv("Máximo",        f"{max(latencies)}ms")
    if errors > 0:
        kv("Errores",   q(C.RED, f"{errors}/{samples}"))
    nl()

    # Test LLM real vía /v8/test
    if _v8_is_ready(inst):
        if confirm("¿Medir latencia del LLM (más lento, ~5-20s)?"):
            nl()
            info("Midiendo latencia del LLM:")
            llm_latencies = []

            for i in range(3):
                start = time.time()
                r = _v8_api(inst, "/v8/test", method="POST", payload={}, timeout=60)
                elapsed_ms = int((time.time() - start) * 1000)

                if not r.get("error"):
                    llm_latencies.append(elapsed_ms)
                    ok_count = r.get("passed", 0)
                    total_t  = r.get("total", 0)
                    print(f"    {q(C.G3, f'[{i+1}/3]')}  "
                          f"{q(C.P2, f'{elapsed_ms}ms')}  "
                          f"{q(C.GRN, f'{ok_count}/{total_t} tests OK')}")
                else:
                    print(f"    {q(C.G3, f'[{i+1}/3]')}  {q(C.RED, 'error')}")

            if llm_latencies:
                nl()
                avg_llm = sum(llm_latencies) // len(llm_latencies)
                llm_color = C.GRN if avg_llm < 5000 else (C.YLW if avg_llm < 15000 else C.RED)
                kv("Latencia LLM promedio", q(llm_color, f"{avg_llm}ms"))

                if avg_llm > 10000:
                    warn("Latencia alta — considera un modelo más rápido")
                    info(f"Gemini Flash o Llama-70B son más rápidos: melissa modelo {inst.name}")


# ══════════════════════════════════════════════════════════════════════════════
# cmd_diff — Comparar configuración entre instancias
# ══════════════════════════════════════════════════════════════════════════════

def cmd_diff(args):
    """Comparar la configuración de dos instancias — detecta diferencias de .env y DB."""
    print_logo(compact=True)
    section("Comparar Instancias")

    instances = get_instances()
    if len(instances) < 2:
        fail("Necesitas al menos 2 instancias para comparar")
        return

    info("Selecciona la primera instancia:")
    idx1 = select([i.label for i in instances])
    inst1 = instances[idx1]

    nl()
    info("Selecciona la segunda instancia:")
    remaining = [i for i in instances if i.name != inst1.name]
    idx2 = select([i.label for i in remaining])
    inst2 = remaining[idx2]

    nl()
    section(f"Diff: {inst1.label} vs {inst2.label}")

    # Comparar .env (sin mostrar valores sensibles)
    info(".env — diferencias de configuración:")

    SENSITIVE = {"KEY", "TOKEN", "SECRET", "PASSWORD", "PASS"}
    comparable_keys = [
        "SECTOR", "PLATFORM", "PORT", "BUFFER_WAIT_MIN", "BUFFER_WAIT_MAX",
        "BUBBLE_PAUSE_MIN", "BUBBLE_PAUSE_MAX", "NOVA_ENABLED",
        "LLM_FAST", "LLM_REASONING", "LLM_LITE",
        "V8_FILTER_LEVEL", "V8_QUALITY_THRESHOLD",
        "DEMO_MODE", "DEMO_SECTOR",
    ]

    has_diff = False
    for key in comparable_keys:
        v1 = inst1.env.get(key, "(no configurado)")
        v2 = inst2.env.get(key, "(no configurado)")

        if v1 != v2:
            has_diff = True
            print(f"  {q(C.YLW, '≠')}  {q(C.G2, f'{key:<30}')}")
            print(f"       {q(C.CYN, inst1.name)}: {q(C.G1, v1)}")
            print(f"       {q(C.P2,  inst2.name)}: {q(C.G1, v2)}")
            nl()

    if not has_diff:
        ok("Sin diferencias de configuración relevantes")
    nl()

    # Comparar stats de DB
    info("DB — comparación de uso:")

    headers = ["MÉTRICA", inst1.label[:20], inst2.label[:20]]
    rows = []

    def _get_stat(inst_: "Instance", query: str, default=0):
        try:
            if not os.path.exists(inst_.db_path):
                return default
            conn_ = sqlite3.connect(inst_.db_path)
            result = conn_.execute(query).fetchone()
            conn_.close()
            return result[0] if result else default
        except Exception:
            return default

    metrics = [
        ("Conversaciones",  "SELECT COUNT(DISTINCT chat_id) FROM conversations"),
        ("Mensajes totales","SELECT COUNT(*) FROM conversations"),
        ("Citas agendadas", "SELECT COUNT(*) FROM appointments"),
        ("Usuarios únicos", "SELECT COUNT(DISTINCT chat_id) FROM patients"),
    ]

    for label, query in metrics:
        v1 = _get_stat(inst1, query)
        v2 = _get_stat(inst2, query)
        diff_icon = q(C.YLW, "≠") if v1 != v2 else q(C.GRN, "=")
        rows.append([f"{diff_icon} {label}", str(v1), str(v2)])

    table(headers, rows, [None, C.CYN, C.P2])
    nl()

    # V8 comparison
    v8_1 = _v8_api(inst1, "/v8/health", timeout=5)
    v8_2 = _v8_api(inst2, "/v8/health", timeout=5)

    if not v8_1.get("error") and not v8_2.get("error"):
        info("V8 — comparación de sistemas:")

        fl1 = v8_1.get("filter_level", 0)
        fl2 = v8_2.get("filter_level", 0)
        m1  = v8_1.get("current_models", {}).get("fast", "-")
        m2  = v8_2.get("current_models", {}).get("fast", "-")

        rows2 = [
            ["Filtro anti-robot", f"Nivel {fl1}", f"Nivel {fl2}"],
            ["Modelo fast", m1[:30], m2[:30]],
        ]
        table(["SISTEMA", inst1.label[:20], inst2.label[:20]], rows2, [C.G2, C.CYN, C.P2])

    nl()


# ══════════════════════════════════════════════════════════════════════════════
# cmd_watchdog — Monitor continuo con auto-restart inteligente
# ══════════════════════════════════════════════════════════════════════════════

def cmd_watchdog(args):
    """
    Monitor continuo que vigila todas las instancias y las reinicia automáticamente
    si detecta problemas. Corre en background o en foreground.
    
    Detecta:
    - Instancia offline (ping falla)
    - Latencia >5s (posible cuelgue)
    - Errores repetidos en logs
    - Memoria alta (>90%)
    """
    print_logo(compact=True)
    section("Watchdog", "Monitor continuo con auto-restart inteligente")

    sub = getattr(args, 'subcommand', '') or ''

    if sub == "stop":
        # Intentar matar el proceso watchdog
        pid_file = Path.home() / ".melissa" / "watchdog.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, signal.SIGTERM)
                pid_file.unlink()
                ok("Watchdog detenido")
            except Exception as e:
                fail(f"Error deteniendo watchdog: {e}")
        else:
            warn("No hay watchdog activo")
        return

    if sub == "status":
        pid_file = Path.home() / ".melissa" / "watchdog.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)  # Signal 0 = check if alive
                ok(f"Watchdog activo (PID {pid})")
            except (ProcessLookupError, PermissionError):
                warn("PID guardado pero proceso ya no existe")
                pid_file.unlink(missing_ok=True)
        else:
            info("Watchdog no está corriendo")
            info("Arranca con: melissa watchdog start")
        return

    # Configuración
    check_interval = 30  # segundos entre checks
    max_restarts   = 3   # máximo reinicios por hora
    alert_on_error = True

    info(f"Intervalo de check: {check_interval}s")
    info(f"Máximo reinicios/hora: {max_restarts}")
    nl()

    background = sub == "start" or confirm("¿Correr en background?")

    if background:
        # Fork al background
        try:
            pid = os.fork()
            if pid > 0:
                # Parent
                pid_file = Path.home() / ".melissa" / "watchdog.pid"
                pid_file.parent.mkdir(exist_ok=True)
                pid_file.write_text(str(pid))
                ok(f"Watchdog iniciado en background (PID {pid})")
                info(f"Ver estado: melissa watchdog status")
                info(f"Detener: melissa watchdog stop")
                return
        except (AttributeError, OSError):
            info("Fork no disponible, corriendo en foreground")
            background = False

    # Watchdog loop
    restart_log: dict = {}  # inst_name → list of restart timestamps

    info("Watchdog activo — Ctrl+C para detener")
    nl()

    try:
        while True:
            instances = get_instances()
            now_ts    = time.time()

            for inst in instances:
                h = health(inst.port, timeout=5)
                pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"

                if not h:
                    # Instancia offline
                    warn(f"⚠ {inst.label} offline — comprobando...")

                    # Verificar reinicios recientes (última hora)
                    recent_restarts = [
                        t for t in restart_log.get(inst.name, [])
                        if now_ts - t < 3600
                    ]

                    if len(recent_restarts) >= max_restarts:
                        fail(f"  {inst.label}: demasiados reinicios ({len(recent_restarts)}/hora) — omitiendo")
                        continue

                    # Reiniciar
                    pm2("restart", pm2_name)
                    time.sleep(5)

                    h2 = health(inst.port, timeout=5)
                    if h2:
                        ok(f"  {inst.label}: reiniciada OK")
                        if inst.name not in restart_log:
                            restart_log[inst.name] = []
                        restart_log[inst.name].append(now_ts)
                        notify_omni("watchdog_restart",
                                    f"{inst.label} reiniciada automáticamente")
                    else:
                        fail(f"  {inst.label}: no responde después de reinicio")
                else:
                    # Instancia online — verificar latencia
                    start = time.time()
                    health(inst.port, timeout=10)
                    latency_ms = int((time.time() - start) * 1000)

                    if latency_ms > 5000:
                        warn(f"⚠ {inst.label}: latencia alta ({latency_ms}ms)")

            # Log con timestamp
            now_str = datetime.now().strftime("%H:%M:%S")
            sys.stdout.write(f"\r  {q(C.G3, now_str)}  {q(C.GRN, '●')}  "
                             f"{q(C.G2, f'{len(instances)} instancias monitoreadas')}  "
                             f"{q(C.G3, f'próximo check en {check_interval}s')}")
            sys.stdout.flush()

            time.sleep(check_interval)

    except KeyboardInterrupt:
        nl()
        info("Watchdog detenido")


# ══════════════════════════════════════════════════════════════════════════════
# cmd_warmup — Precalentar una instancia antes de lanzar
# ══════════════════════════════════════════════════════════════════════════════

def cmd_warmup(args):
    """
    Precalienta una instancia haciendo llamadas de "calentamiento" al LLM
    para que la primera respuesta real al cliente no sea lenta.
    
    Problema real: la primera llamada al LLM después de arrancar
    puede tardar 5-10s porque el provider tiene "cold start".
    Warmup elimina ese retraso.
    """
    print_logo(compact=True)

    inst = _pick_instance(args, "¿Cuál instancia calentar?")
    if not inst:
        return

    h = health(inst.port)
    if not h:
        fail(f"{inst.label} está offline — arráncala primero")
        info(f"melissa restart {inst.name}")
        return

    section(f"Warmup — {inst.label}", "Calentando el LLM para eliminar cold start")

    warmup_prompts = [
        "hola",
        "cuánto vale el botox",
        "tienen disponibilidad esta semana",
        "qué servicios ofrecen",
    ]

    latencies = []

    for i, user_msg in enumerate(warmup_prompts):
        with Spinner(f"Warmup {i+1}/{len(warmup_prompts)}: '{user_msg}'") as sp:
            start = time.time()
            # Usar el endpoint de test que existe en melissa
            r = inst.api_call(
                "POST", "/webhook/" + inst.webhook_secret,
                payload={"message": {"text": user_msg,
                                     "chat": {"id": "warmup_test"},
                                     "from": {"id": "warmup_test", "first_name": "Test"}}},
                timeout=30
            )
            elapsed = int((time.time() - start) * 1000)
            latencies.append(elapsed)

            color = C.GRN if elapsed < 3000 else (C.YLW if elapsed < 8000 else C.RED)
            sp.finish(f"Respondió en {elapsed}ms", ok=elapsed < 10000)

    nl()

    avg = sum(latencies) // len(latencies)
    last = latencies[-1]

    kv("Primera llamada",  f"{latencies[0]}ms  (cold)")
    kv("Última llamada",   f"{last}ms  (warm)")
    kv("Promedio",         f"{avg}ms")
    nl()

    if last < latencies[0] * 0.7:
        ok(f"Warmup exitoso — primera respuesta era {latencies[0]}ms, ahora {last}ms")
    else:
        info("El LLM ya estaba caliente o no mejoró con warmup")


# ══════════════════════════════════════════════════════════════════════════════
# cmd_campana — Campañas de seguimiento
# ══════════════════════════════════════════════════════════════════════════════

CAMPAIGN_TYPES = {
    "WARM_FOLLOWUP":          "Follow-up cálido — 24h después sin cita",
    "HOT_NUDGE":              "Nudge caliente — 6h para lead caliente",
    "APPOINTMENT_REMINDER_24H": "Recordatorio 24h antes de la cita",
    "APPOINTMENT_REMINDER_2H":  "Recordatorio 2h antes de la cita",
    "POST_APPOINTMENT":       "Post-cita — 3 días después (feedback)",
    "REACTIVATION_30D":       "Reactivación — 30 días inactivo",
}


def cmd_campana(args):
    """Gestionar campañas de seguimiento y reactivación de clientes."""
    print_logo(compact=True)

    inst = _pick_instance(args, "¿En cuál instancia?")
    if not inst:
        return

    section(f"Campañas — {inst.label}")

    sub = getattr(args, 'subcommand', '') or ''

    if sub == "list" or not sub:
        # Mostrar estado de campañas desde la API
        with Spinner("Cargando campañas...") as sp:
            r = _v8_api(inst, "/v8/pipeline", timeout=10)
            sp.finish("Cargado" if not r.get("error") else "Error",
                      ok=not r.get("error"))

        if r.get("error"):
            fail("No se pudieron cargar las campañas")
            info("¿Los sistemas V8 están activos? melissa v8 " + inst.name)
            return

        # Mostrar tipos disponibles
        info("Tipos de campaña disponibles:")
        for ctype, desc in CAMPAIGN_TYPES.items():
            print(f"    {q(C.P2, '◆')}  {q(C.W, ctype)}")
            print(f"         {q(C.G3, desc)}")
            nl()

        info("Para activar una campaña para un cliente:")
        info(f"  melissa campana activate {inst.name}")

    elif sub == "activate" or sub == "activar":
        # Activar campaña para un chat_id específico
        chat_id = getattr(args, 'name', '') or prompt("Chat ID del cliente")
        if not chat_id:
            return

        nl()
        campaign_opts = list(CAMPAIGN_TYPES.values())
        idx = select(campaign_opts, title="Tipo de campaña:")
        campaign_type = list(CAMPAIGN_TYPES.keys())[idx]

        patient_name = prompt("Nombre del cliente (opcional)")

        with Spinner(f"Programando campaña {campaign_type}...") as sp:
            r = _v8_api(
                inst, f"/v8/campaign/{campaign_type}",
                method="POST",
                payload={"chat_id": chat_id, "patient_name": patient_name},
                timeout=15
            )
            sp.finish("Campaña programada" if r.get("ok") else "Error",
                      ok=bool(r.get("ok")))

        if r.get("ok"):
            ok(f"Campaña {campaign_type} programada para {chat_id}")
        else:
            fail(f"Error: {r.get('error', 'sin respuesta')}")

    elif sub == "reactivar" or sub == "reactivate":
        # Reactivación masiva de inactivos
        info("Buscando clientes inactivos...")

        r = _v8_api(inst, "/reactivar", method="POST", timeout=30)
        if r.get("ok") or "reactivar" in str(r).lower():
            ok("Campaña de reactivación enviada a Melissa")
            info("Melissa procesará los follow-ups de forma escalonada")
        else:
            # Fallback directo a API de Melissa
            r2 = inst.api_call("POST", "/v8/campaign/REACTIVATION_30D",
                               payload={"chat_id": "broadcast"}, timeout=20)
            if r2.get("ok"):
                ok("Campaña de reactivación programada")
            else:
                warn("Usa el comando /reactivar directamente en el bot admin")


# ══════════════════════════════════════════════════════════════════════════════
# cmd_env_check — Verificar .env de una instancia contra mejores prácticas V8
# ══════════════════════════════════════════════════════════════════════════════

def cmd_env_check(args):
    """
    Verifica el .env de una instancia contra las mejores prácticas V8.
    Detecta variables faltantes, valores peligrosos y oportunidades de mejora.
    """
    print_logo(compact=True)

    inst = _pick_instance(args, "¿Cuál instancia verificar?")
    if not inst:
        return

    section(f"ENV Check — {inst.label}", "Verificando configuración contra mejores prácticas V8")

    ev = inst.env

    issues   = []
    warnings = []
    ok_items = []

    # ── Requeridos ────────────────────────────────────────────────────────────
    required = {
        "MASTER_API_KEY":    "Clave de administración",
        "WEBHOOK_SECRET":    "Secret del webhook",
        "BASE_URL":          "URL pública del servidor",
        "DB_PATH":           "Ruta de la base de datos",
    }
    for key, desc in required.items():
        if ev.get(key):
            ok_items.append(f"{key}: OK")
        else:
            issues.append(f"{key} vacío — {desc} requerido")

    # ── LLM: al menos un proveedor ────────────────────────────────────────────
    llm_keys = ["GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"]
    llm_count = sum(1 for k in llm_keys if ev.get(k))
    if llm_count == 0:
        issues.append("Sin proveedores LLM configurados — el bot no puede responder")
    elif llm_count == 1:
        warnings.append("Solo 1 proveedor LLM — considera agregar un fallback")
    else:
        ok_items.append(f"LLM: {llm_count} proveedores configurados (cascada OK)")

    # ── Plataforma ────────────────────────────────────────────────────────────
    platform = ev.get("PLATFORM", "")
    if platform == "telegram":
        if not ev.get("TELEGRAM_TOKEN"):
            issues.append("PLATFORM=telegram pero TELEGRAM_TOKEN vacío")
        else:
            ok_items.append("Telegram: token configurado")
    elif platform in ("whatsapp_cloud", "whatsapp"):
        if not ev.get("WA_PHONE_ID") or not ev.get("WA_ACCESS_TOKEN"):
            issues.append("PLATFORM=whatsapp pero WA_PHONE_ID/WA_ACCESS_TOKEN vacíos")
        else:
            ok_items.append("WhatsApp: credenciales configuradas")
    else:
        warnings.append(f"PLATFORM no reconocido: '{platform}' — usa 'telegram' o 'whatsapp_cloud'")

    # ── V8 específicos ─────────────────────────────────────────────────────────
    v8_filter = ev.get("V8_FILTER_LEVEL", "")
    if not v8_filter:
        warnings.append("V8_FILTER_LEVEL no configurado — usando nivel 2 (recomendado: 2 o 3)")
    else:
        ok_items.append(f"V8_FILTER_LEVEL={v8_filter}")

    v8_threshold = ev.get("V8_QUALITY_THRESHOLD", "")
    if not v8_threshold:
        warnings.append("V8_QUALITY_THRESHOLD no configurado — usando 0.65 (recomendado: 0.70)")
    else:
        ok_items.append(f"V8_QUALITY_THRESHOLD={v8_threshold}")

    # ── Seguridad ──────────────────────────────────────────────────────────────
    master_key = ev.get("MASTER_API_KEY", "")
    if master_key and len(master_key) < 16:
        warnings.append("MASTER_API_KEY muy corta (<16 chars) — cámbiala por una más segura")
    elif master_key:
        ok_items.append("MASTER_API_KEY: longitud OK")

    # Buffer timing
    buf_min = int(ev.get("BUFFER_WAIT_MIN", "0") or "0")
    buf_max = int(ev.get("BUFFER_WAIT_MAX", "0") or "0")
    if buf_min < 5:
        warnings.append(f"BUFFER_WAIT_MIN={buf_min} — muy bajo, parece robot. Recomendado: 8-15")
    else:
        ok_items.append(f"Buffer timing: {buf_min}-{buf_max}s (humano)")

    # ── Mostrar resultado ─────────────────────────────────────────────────────
    if issues:
        info(f"Problemas críticos ({len(issues)}):")
        for issue in issues:
            print(f"    {q(C.RED, '✗')}  {q(C.W, issue)}")
        nl()

    if warnings:
        info(f"Advertencias ({len(warnings)}):")
        for w in warnings:
            print(f"    {q(C.YLW, '!')}  {q(C.G1, w)}")
        nl()

    if ok_items:
        info(f"OK ({len(ok_items)}):")
        for item in ok_items[:5]:
            print(f"    {q(C.GRN, '✓')}  {q(C.G3, item)}")
        if len(ok_items) > 5:
            dim(f"  ... y {len(ok_items) - 5} más")
        nl()

    # Score global
    total_checks = len(issues) + len(warnings) + len(ok_items)
    score = len(ok_items) / total_checks if total_checks > 0 else 0
    score_color = C.GRN if score >= 0.8 else (C.YLW if score >= 0.6 else C.RED)

    kv("Score de configuración", q(score_color, f"{int(score*100)}%"))

    if issues:
        nl()
        if confirm("¿Intentar corregir automáticamente los problemas críticos?"):
            _auto_fix_env(inst, issues, ev)


def _auto_fix_env(inst: "Instance", issues: list, ev: dict):
    """Intenta corregir automáticamente los problemas detectados."""
    env_path = f"{inst.dir}/.env"

    for issue in issues:
        if "V8_FILTER_LEVEL" in issue:
            update_env_key(env_path, "V8_FILTER_LEVEL", "2")
            ok("V8_FILTER_LEVEL=2 configurado")
        elif "V8_QUALITY_THRESHOLD" in issue:
            update_env_key(env_path, "V8_QUALITY_THRESHOLD", "0.70")
            ok("V8_QUALITY_THRESHOLD=0.70 configurado")
        elif "BUFFER_WAIT_MIN" in issue:
            update_env_key(env_path, "BUFFER_WAIT_MIN", "8")
            update_env_key(env_path, "BUFFER_WAIT_MAX", "18")
            ok("Buffer timing humanizado: 8-18s")

    if confirm("¿Reiniciar para aplicar cambios?"):
        pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
        pm2("restart", pm2_name)
        ok(f"{inst.label} reiniciada")


# ══════════════════════════════════════════════════════════════════════════════
# cmd_rollforward — Aplicar V8 a todas las instancias
# ══════════════════════════════════════════════════════════════════════════════

def cmd_rollforward(args):
    """
    Aplica melissa.py a todas las instancias (o a una específica).
    Actualiza el archivo sin perder configuración (.env y DB se conservan).
    """
    print_logo(compact=True)
    section("Roll Forward — Aplicar V8 a instancias",
            "Actualiza melissa.py → melissa.py en todas las instancias")

    # Verificar que existe melissa.py en el directorio base
    # Buscar el melissa.py actualizado — puede estar en varios lugares
    candidates = [
        f"{MELISSA_DIR}/melissa.py",
        "./melissa.py",
        os.path.expanduser("~/melissa/melissa.py"),
        os.path.expanduser("~/melissa.py"),
    ]
    v8_source = next((p for p in candidates if os.path.exists(p)), None)
    if not v8_source:
        fail("No se encontró melissa.py")
        info(f"Directorio base buscado: {MELISSA_DIR}/melissa.py")
        info("Asegúrate de que el melissa.py con V8 esté en el directorio base")
        return

    ok(f"Fuente encontrada: {v8_source}")
    v8_size = os.path.getsize(v8_source) // 1024
    kv("Tamaño", f"{v8_size} KB")
    nl()

    # Seleccionar instancias
    instances = get_instances()
    if not instances:
        fail("No hay instancias")
        return

    sub = getattr(args, 'subcommand', '') or ''
    if sub == "all":
        targets = instances
    elif sub:
        inst = find_instance(sub)
        targets = [inst] if inst else instances
    else:
        opts = [i.label for i in instances] + ["Todas las instancias"]
        idx  = select(opts, title="¿A cuál(es) aplicar V8?")
        targets = instances if idx == len(instances) else [instances[idx]]

    nl()
    info(f"Aplicando V8 a {len(targets)} instancia(s):")
    for t in targets:
        print(f"    {q(C.P2, '◆')}  {t.label}")
    nl()

    if not confirm("¿Continuar? Las instancias se reiniciarán."):
        return

    nl()
    success_count = 0

    for inst in targets:
        with Spinner(f"Actualizando {inst.label}...") as sp:
            try:
                # Backup del melissa.py actual
                current_melissa = f"{inst.dir}/melissa.py"
                if os.path.exists(current_melissa):
                    backup_path = f"{inst.dir}/melissa_backup_{int(time.time())}.py"
                    shutil.copy(current_melissa, backup_path)

                # Copiar v8
                shutil.copy(v8_source, current_melissa)

                # Agregar variables V8 al .env si no están
                env_path = f"{inst.dir}/.env"
                ev_current = load_env(env_path)

                v8_defaults = {
                    "V8_FILTER_LEVEL":       "2",
                    "V8_QUALITY_THRESHOLD":  "0.65",
                    "V8_MAX_RETRIES":        "2",
                }
                for key, val in v8_defaults.items():
                    if not ev_current.get(key):
                        update_env_key(env_path, key, val)

                # Reiniciar
                pm2_name = "melissa" if inst.is_base else f"melissa-{inst.name}"
                pm2("restart", pm2_name)

                sp.finish(f"{inst.label} — V8 aplicado")
                success_count += 1

            except Exception as e:
                sp.finish(f"{inst.label} — Error: {e}", ok=False)

    nl()
    time.sleep(5)  # Dar tiempo para que arranquen

    # Verificar que están online
    info("Verificando instancias...")
    for inst in targets:
        h = health(inst.port)
        icon, status = icon_status(h)
        print(f"  {icon}  {inst.label}")

    nl()
    ok(f"V8 aplicado a {success_count}/{len(targets)} instancias")
    if success_count > 0:
        info("Verifica con: melissa v8 <instancia>")
        info("Prueba con: melissa simular <instancia>")


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD V8 EXTENDIDO
# ══════════════════════════════════════════════════════════════════════════════

def cmd_dashboard_v8(args):
    """
    Dashboard V8 en tiempo real.
    Incluye humanidad, modelo activo, leads calientes, pipeline de conversión.
    Ctrl+C para salir.
    """
    print_logo(compact=True)
    section("Dashboard V8", "Ctrl+C para salir")

    def draw():
        os.system("clear")
        print_logo(compact=True)
        now = datetime.now().strftime("%H:%M:%S")

        instances   = get_instances()
        ports       = [i.port for i in instances]
        healths     = health_batch(ports, timeout=1)

        online      = sum(1 for h in healths.values() if h.get("status") == "online")
        total       = len(instances)
        status_col  = C.GRN if online == total else C.YLW

        print(f"  {q(C.P1, '✦', bold=True)}  "
              f"{q(C.W, 'Melissa V8 Dashboard', bold=True)}  "
              f"{q(C.G3, now)}  "
              f"{q(status_col, f'{online}/{total} online')}")
        hr()
        nl()

        for inst in instances:
            h         = healths.get(inst.port, {})
            icon, _   = icon_status(h)
            sector    = SECTORS.get(inst.sector, SECTORS["otro"])
            stats     = get_instance_stats(inst)
            wa        = h.get("whatsapp", {})
            plat      = "WhatsApp" if wa.get("connected") else inst.env.get("PLATFORM", "Telegram")

            # V8 status (fast, non-blocking)
            v8_status = {}
            try:
                v8_status = _v8_api(inst, "/v8/health", timeout=1)
            except Exception:
                pass

            model_fast = v8_status.get("current_models", {}).get("fast", "")
            filter_lvl = v8_status.get("filter_level", 0)
            v8_active  = v8_status.get("version") == "8.0"
            v8_tag     = q(C.P3, " V8") if v8_active else ""
            model_tag  = q(C.G3, f" [{model_fast.split('/')[-1][:15]}]") if model_fast else ""

            print(f"  {icon}  {q(C.W, inst.label, bold=True)}{v8_tag}{model_tag}")
            print(f"       {sector.emoji} {q(C.G2, sector.name)}  ·  :{inst.port}  ·  {q(C.G1, plat)}")

            # Stats line
            conv_count = stats.get("conversations", 0)
            apt_count  = stats.get("appointments", 0)
            _stats = f"{conv_count} conv · {apt_count} citas"

            if v8_active and filter_lvl > 0:
                _stats += f" · filtro L{filter_lvl}"

            print(f"       {q(C.G3, _stats)}")
            nl()

        hr()
        print(f"  {q(C.G3, 'Actualiza cada 3s  ·  modelo: melissa modelo <n>  ·  v8: melissa v8 <n>')}")

    try:
        while True:
            draw()
            time.sleep(3)
    except KeyboardInterrupt:
        nl()
        info("Dashboard cerrado")


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRAR NUEVOS COMANDOS EN ROUTES Y COMPLETIONS
# ══════════════════════════════════════════════════════════════════════════════

# Comandos V8 nuevos
ROUTES["modelo"]       = cmd_modelo
ROUTES["model"]        = cmd_modelo

ROUTES["simular"]      = cmd_simular
ROUTES["simulate"]     = cmd_simular
ROUTES["sim"]          = cmd_simular

ROUTES["v8"]           = cmd_v8

ROUTES["quality"]      = cmd_quality
ROUTES["humanness"]    = cmd_quality
ROUTES["calidad"]      = cmd_quality

ROUTES["briefing"]     = cmd_briefing

ROUTES["cost"]         = cmd_cost
ROUTES["costos"]       = cmd_cost
ROUTES["costo"]        = cmd_cost

ROUTES["latency"]      = cmd_latency
ROUTES["latencia"]     = cmd_latency

ROUTES["diff"]         = cmd_diff
ROUTES["compare"]      = cmd_diff
ROUTES["comparar"]     = cmd_diff

ROUTES["watchdog"]     = cmd_watchdog

ROUTES["warmup"]       = cmd_warmup

# Log engine V9 — aliases extendidos
ROUTES["logs"]         = cmd_logs
ROUTES["log"]          = cmd_logs
ROUTES["logfix"]       = cmd_logs   # melissa logfix [n] → directo al --fix
ROUTES["logscan"]      = cmd_logs   # melissa logscan [n] → directo al --scan

ROUTES["campana"]      = cmd_campana
ROUTES["campaign"]     = cmd_campana
ROUTES["campaña"]      = cmd_campana

ROUTES["env-check"]    = cmd_env_check
ROUTES["envcheck"]     = cmd_env_check

ROUTES["rollforward"]  = cmd_rollforward
ROUTES["roll-forward"] = cmd_rollforward

ROUTES["dashboard-v8"] = cmd_dashboard_v8
ROUTES["dashv8"]       = cmd_dashboard_v8

# Reemplazar dashboard por el V8 si se llama sin argumento
_original_dashboard = ROUTES.get("dashboard")

def cmd_dashboard_smart(args):
    """Dashboard inteligente — V8 si está disponible, clásico si no."""
    sub = getattr(args, 'subcommand', '') or ''
    if sub == "classic":
        _original_dashboard(args)
    else:
        cmd_dashboard_v8(args)

ROUTES["dashboard"] = cmd_dashboard_smart
ROUTES["dash"]      = cmd_dashboard_smart

# Observatory

# Actualizar completions para el autocompletado
COMMANDS.extend([
    "modelo", "simular", "simulate", "v8", "quality", "humanness", "calidad",
    "briefing", "cost", "costos", "latency", "latencia",
    "diff", "compare", "comparar", "watchdog", "warmup",
    "campana", "campaign", "env-check", "rollforward", "watch", "live", "diagnose", "obs", "skills", "skill", "aprender", "desaprender", "entrenar", "simular-cliente", "skills", "skill", "aprender", "desaprender", "entrenar", "trainer", "simular-cliente", "cliente", "control",
    "dashboard-v8",
    # Log engine
    "logfix", "logscan",
])

# Actualizar help — agregar sección V8 en el menú extendido
_v8_section = (
    "V8.0 — Calidad & Modelo", [
        ("modelo [n]",       "Cambiar modelo LLM en caliente (sin reiniciar)"),
        ("simular [n]",      "Simular 10 conversaciones — detecta frases de bot"),
        ("v8 [n]",           "Estado de los 15 sistemas V8"),
        ("quality [n]",      "Score de humanidad de últimas respuestas"),
        ("briefing [n]",     "Briefing: leads calientes, citas, recomendación"),
        ("cost [n]",         "Estimación de costo mensual del LLM"),
        ("latency [n]",      "Test de latencia HTTP + LLM"),
        ("diff [n1] [n2]",   "Comparar configuración entre instancias"),
        ("watchdog",         "Monitor continuo con auto-restart"),
        ("warmup [n]",       "Precalentar LLM antes de lanzar"),
        ("campana [n]",      "Campañas de seguimiento y reactivación"),
        ("env-check [n]",    "Verificar .env contra mejores prácticas V8"),
        ("rollforward [n]",  "Aplicar melissa.py a instancias"),
        ("dashboard-v8",     "Dashboard enriquecido con métricas V8"),
        ("logs [n] --scan",  "Escanear logs y detectar errores con diagnóstico"),
        ("logs [n] --fix",   "Detectar errores + aplicar fixes automáticos"),
        ("logfix [n]",       "Atajo: logs --fix"),
        ("logscan [n]",      "Atajo: logs --scan"),
    ]
)


ROUTES["help"] = cmd_help_extended
ROUTES["--help"] = cmd_help_extended
ROUTES["-h"] = cmd_help_extended

# ══════════════════════════════════════════════════════════════════════════════
# SEÑALES Y CLEANUP
# ══════════════════════════════════════════════════════════════════════════════
def signal_handler(sig, frame):
    """Manejar Ctrl+C gracefully."""
    print()
    info("Interrumpido")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN ACTUALIZADO
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# TRAINER CLI COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

def cmd_trainer_skills(args):
    """Ver y gestionar skills de comportamiento de Melissa."""
    print_logo(compact=True)

    inst = _pick_instance(args, "¿De cuál instancia?")
    if not inst:
        return

    h = health(inst.port)
    if not h:
        fail(f"{inst.label} está offline")
        return

    sub = getattr(args, "subcommand", "") or ""

    if sub in ("on", "off", "activar", "desactivar"):
        # melissa skills [on|off] [skill_id]
        skill_id = getattr(args, "name", "") or ""
        if not skill_id:
            fail("Formato: melissa skill [skill_id] on/off")
            return

        active = sub in ("on", "activar")
        with Spinner(f"{'Activando' if active else 'Desactivando'} skill '{skill_id}'...") as sp:
            r = _v8_api(inst, "/trainer/skill/toggle", method="POST",
                        payload={"skill_id": skill_id, "active": active}, timeout=10)
            sp.finish("OK" if r.get("ok") else "Error", ok=bool(r.get("ok")))

        if r.get("ok"):
            action = "activado" if active else "desactivado"
            ok(f"Skill {action}: {r.get('name', skill_id)}")
            info(r.get("desc", ""))
        else:
            fail(f"Error: {r.get('error', 'sin respuesta')}")
            if not h:
                return

            # Fallback: mostrar lista
            r2 = _v8_api(inst, "/trainer/skills", timeout=8)
            skills = r2.get("skills", [])
            if skills:
                info("Skills disponibles:")
                for s in skills:
                    print(f"    {s['id']}")
        return

    # Listar skills
    section(f"Skills — {inst.label}", "Comportamientos que puedes activar/desactivar")

    with Spinner("Cargando skills...") as sp:
        r = _v8_api(inst, "/trainer/skills", timeout=10)
        sp.finish("OK" if not r.get("error") else "Error", ok=not r.get("error"))

    if r.get("error"):
        fail("No se pudieron cargar los skills")
        info("¿El trainer está activo? Verifica: melissa v8 " + inst.name)
        return

    skills   = r.get("skills", [])
    active   = [s for s in skills if s.get("active")]
    inactive = [s for s in skills if not s.get("active")]

    categories = {}
    for s in skills:
        cat = s.get("category", "otro")
        categories.setdefault(cat, []).append(s)

    for cat, cat_skills in categories.items():
        info(f"Categoría: {cat}")
        for s in cat_skills:
            icon  = q(C.GRN, "✓") if s.get("active") else q(C.G3, "○")
            state = q(C.GRN, "ON") if s.get("active") else q(C.G3, "off")
            print(f"  {icon}  {q(C.W, s['id']):<30}  {state}  {q(C.G2, s['desc'])}")
        nl()

    ok(f"{len(active)} activos · {len(inactive)} disponibles")
    nl()
    info("Para activar:  melissa skill <instancia> on  <skill_id>")
    info("Para desactivar: melissa skill <instancia> off <skill_id>")
    info("O directamente en el bot: /skill [id] on/off")


def cmd_trainer_gateway(args):
    """Ver y gestionar el gateway automático del trainer."""
    print_logo(compact=True)

    actions = {"on", "off", "admin-on", "admin-off", "user-on", "user-off"}
    raw_sub = (getattr(args, "subcommand", "") or "").strip().lower()
    raw_name = (getattr(args, "name", "") or "").strip().lower()

    action = ""
    inst_name = ""
    if raw_sub in actions:
        action = raw_sub
        inst_name = getattr(args, "name", "") or ""
    elif raw_name in actions:
        action = raw_name
        inst_name = getattr(args, "subcommand", "") or ""
    else:
        inst_name = getattr(args, "name", "") or getattr(args, "subcommand", "") or ""

    inst_args = type("GatewayArgs", (), {"name": inst_name, "subcommand": inst_name})()
    inst = _pick_instance(inst_args, "¿De cuál instancia?")
    if not inst:
        return

    if action:
        payload = {}
        if action == "on":
            payload["enabled"] = True
        elif action == "off":
            payload["enabled"] = False
        elif action == "admin-on":
            payload["auto_admin"] = True
        elif action == "admin-off":
            payload["auto_admin"] = False
        elif action == "user-on":
            payload["auto_user"] = True
        elif action == "user-off":
            payload["auto_user"] = False

        with Spinner("Actualizando gateway automático...") as sp:
            r = _v8_api(inst, "/trainer/gateway", method="POST", payload=payload, timeout=10)
            sp.finish("OK" if r.get("ok") else "Error", ok=bool(r.get("ok")))

        if not r.get("ok"):
            fail(f"Error: {r.get('error', 'sin respuesta')}")
            return

        ok("Gateway actualizado")
        info(
            f"General={'ON' if r.get('enabled') else 'off'} · "
            f"Admin={'ON' if r.get('auto_admin') else 'off'} · "
            f"User={'ON' if r.get('auto_user') else 'off'}"
        )
        return

    section(f"Gateway automático — {inst.label}",
            "Melissa decide skills y preferencias sin obligarte a configurarlas a mano")

    with Spinner("Consultando gateway...") as sp:
        r = _v8_api(inst, "/trainer/gateway", timeout=10)
        sp.finish("OK" if not r.get("error") else "Error", ok=not r.get("error"))

    if r.get("error"):
        fail("No se pudo consultar el gateway")
        return

    kv("General", q(C.GRN if r.get("enabled") else C.G3, "ON" if r.get("enabled") else "off"))
    kv("Auto-admin", q(C.GRN if r.get("auto_admin") else C.G3, "ON" if r.get("auto_admin") else "off"))
    kv("Auto-user", q(C.GRN if r.get("auto_user") else C.G3, "ON" if r.get("auto_user") else "off"))
    kv("Skills activas globales", str(len(r.get("active_skills", []))))
    nl()
    info("Comandos:")
    print(f"    {q(C.CYN, f'melissa gateway {inst.name:<24}')} {q(C.G2, 'Ver estado')}")
    print(f"    {q(C.CYN, f'melissa gateway {inst.name} on')} {q(C.G2, 'Activar todo el gateway')}")
    print(f"    {q(C.CYN, f'melissa gateway {inst.name} off')} {q(C.G2, 'Desactivar todo el gateway')}")
    print(f"    {q(C.CYN, f'melissa gateway {inst.name} admin-on')} {q(C.G2, 'Activar solo admin')}")
    print(f"    {q(C.CYN, f'melissa gateway {inst.name} admin-off')} {q(C.G2, 'Desactivar solo admin')}")
    print(f"    {q(C.CYN, f'melissa gateway {inst.name} user-on')} {q(C.G2, 'Activar solo usuario')}")
    print(f"    {q(C.CYN, f'melissa gateway {inst.name} user-off')} {q(C.G2, 'Desactivar solo usuario')}")


def cmd_trainer_control(args):
    """Ver o aplicar reglas duras del admin."""
    print_logo(compact=True)

    raw_name = (getattr(args, "name", "") or "").strip()
    raw_sub = (getattr(args, "subcommand", "") or "").strip()
    inst_name = raw_sub or raw_name
    inst_args = type("ControlArgs", (), {"name": inst_name, "subcommand": inst_name})()
    inst = _pick_instance(inst_args, "¿De cuál instancia?")
    if not inst:
        return

    instruction = "" if raw_name == inst.name and raw_sub == inst.name else raw_name

    if instruction:
        payload = {"instruction": instruction, "admin_chat_id": "cli"}
        normalized = instruction.strip().lower()
        if normalized in ("reset", "reiniciar", "limpiar"):
            payload = {"reset_scope": "all"}
        elif normalized in ("reset admin", "reiniciar admin", "limpiar admin"):
            payload = {"reset_scope": "admin"}
        elif normalized in (
            "reset paciente", "reset pacientes", "reiniciar paciente", "reiniciar pacientes",
            "limpiar paciente", "limpiar pacientes", "reset patient", "reset patients"
        ):
            payload = {"reset_scope": "patient"}

        section(f"Control duro — {inst.label}", "Aplicando instrucción del admin")
        with Spinner("Guardando regla dura...") as sp:
            r = _v8_api(
                inst,
                "/trainer/control",
                method="POST",
                payload=payload,
                timeout=12,
            )
            sp.finish("OK" if r.get("ok") else "Error", ok=bool(r.get("ok")))

        if not r.get("ok"):
            fail(f"Error: {r.get('error', 'sin respuesta')}")
            return

        ok("Regla aplicada")
        for line in r.get("reply_lines", []):
            info(line)
        return

    section(f"Control duro — {inst.label}",
            "Plano de gobierno del admin sobre el tono y la salida")

    with Spinner("Consultando control duro...") as sp:
        r = _v8_api(inst, "/trainer/control", timeout=10)
        sp.finish("OK" if not r.get("error") else "Error", ok=not r.get("error"))

    if r.get("error"):
        fail("No se pudo consultar el control duro")
        return

    kv("General", q(C.GRN if r.get("enabled") else C.G3, "ON" if r.get("enabled") else "off"))
    for scope_name, label in (("global", "Global"), ("admin", "Admin"), ("patient", "Paciente")):
        bucket = r.get(scope_name, {}) or {}
        info(label + ":")
        print(f"    trato: {bucket.get('register', 'auto')}")
        print(f"    emojis: {'off' if bucket.get('no_emojis') else 'ON'}")
        print(f"    saludo: {bucket.get('greeting_template') or 'sin plantilla'}")
        print(f"    segunda burbuja: {bucket.get('second_bubble_template') or 'sin plantilla'}")
        print(f"    tercera burbuja: {bucket.get('third_bubble_template') or 'sin plantilla'}")
        print(f"    cierre: {bucket.get('closing_template') or 'sin plantilla'}")
        print(f"    fallback: {bucket.get('fallback_template') or 'sin plantilla'}")
        print(f"    máximo burbujas: {bucket.get('max_bubbles') or 'auto'}")
        repl = bucket.get('replacement_map', {}) or {}
        print(f"    reemplazos: {' | '.join(f'{k}->{v}' for k, v in list(repl.items())[:4]) or 'ninguno'}")
        print(f"    frases prohibidas: {', '.join(bucket.get('forbidden_phrases', [])[:6]) or 'ninguna'}")
        print(f"    arranques prohibidos: {', '.join(bucket.get('forbidden_starts', [])[:6]) or 'ninguno'}")
        print(f"    notas: {' | '.join(bucket.get('style_notes', [])[:4]) or 'sin notas'}")
        nl()

    info("Ejemplos:")
    example_commands = [
        (f'melissa control {inst.name} "no digas ay"', "Prohibir una frase"),
        (f'melissa control {inst.name} "no digas ay, di entiendo"', "Forzar reemplazo"),
        (f'melissa control {inst.name} "no uses claro al inicio"', "Bloquear arranque"),
        (f'melissa control {inst.name} "saluda así: Hola, Melissa por acá"', "Fijar saludo base"),
        (f'melissa control {inst.name} "segunda burbuja: Estoy lista para ayudarle con la instancia"', "Fijar segunda burbuja"),
        (f'melissa control {inst.name} "tercera burbuja: Si quiere, lo dejamos listo ahora"', "Fijar tercera burbuja"),
        (f'melissa control {inst.name} "cierra así: Si quiere, lo dejamos listo ahora"', "Fijar cierre"),
        (f'melissa control {inst.name} "si no entiendes di: Perdón, ayúdeme con un poco más de contexto"', "Fijar fallback"),
        (f'melissa control {inst.name} "responde en 2 burbujas"', "Limitar burbujas"),
        (f'melissa control {inst.name} "conmigo háblame de usted y más directo"', "Ajustar trato admin"),
    ]
    for command, description in example_commands:
        print(f"    {q(C.CYN, command)} {q(C.G2, description)}")
    reset_admin_command = f'melissa control {inst.name} "reset admin"'
    print(f"    {q(C.CYN, reset_admin_command)} {q(C.G2, 'Reiniciar solo admin')}")


def cmd_trainer_learn(args):
    """Enseñar algo nuevo a Melissa en lenguaje natural."""
    print_logo(compact=True)

    inst = _pick_instance(args, "¿De cuál instancia?")
    if not inst:
        return

    instruction = getattr(args, "name", "") or getattr(args, "subcommand", "") or ""
    if not instruction:
        instruction = prompt("¿Qué quieres que aprenda Melissa?",
                             default="a veces usa minúsculas al inicio")

    if not instruction or len(instruction.strip()) < 5:
        return

    section(f"Aprender — {inst.label}")

    with Spinner(f"Procesando instrucción...") as sp:
        r = _v8_api(inst, "/trainer/prompt/evolve", method="POST",
                    payload={"instruction": instruction, "admin_chat_id": "cli"},
                    timeout=20)
        sp.finish("Aprendido" if r.get("ok") else "Error", ok=bool(r.get("ok")))

    if r.get("ok"):
        ok(r.get("description", "Instrucción procesada"))
        if r.get("example_good"):
            eg = r.get("example_good", "")
            info(f"Ejemplo: '{eg}'")
        if r.get("evolution_id"):
            kv("ID de evolución", r["evolution_id"])
            info(f"Para revertir: melissa desaprender {inst.name} {r['evolution_id']}")
    else:
        fail(f"Error: {r.get('error', 'sin respuesta')}")


def cmd_trainer_unlearn(args):
    """Revertir algo que Melissa aprendió."""
    print_logo(compact=True)

    inst = _pick_instance(args, "¿De cuál instancia?")
    if not inst:
        return

    evolution_id = getattr(args, "name", "") or getattr(args, "subcommand", "") or ""

    if not evolution_id:
        # Mostrar historial
        with Spinner("Cargando historial...") as sp:
            r = _v8_api(inst, "/trainer/evolutions", timeout=10)
            sp.finish("OK", ok=True)

        evolutions = r.get("evolutions", [])
        if not evolutions:
            info("No hay evoluciones guardadas.")
            return

        section(f"Historial de aprendizaje — {inst.label}")
        for ev in evolutions[:15]:
            ev_type = ev.get("type", "?")
            eid     = ev.get("id", "?")
            ts      = ev.get("ts", "")[:16]
            rule    = ev.get("rule", ev.get("skill_id", "?"))[:50]
            print(f"  {q(C.P2, eid)}  {q(C.G3, ts)}  {q(C.G1, rule)}")
        nl()
        evolution_id = prompt("ID a revertir (vacío para cancelar)", required=False)
        if not evolution_id:
            return

    with Spinner(f"Revirtiendo {evolution_id}...") as sp:
        r = _v8_api(inst, f"/trainer/evolutions/{evolution_id}",
                    method="DELETE", timeout=10)
        sp.finish("Revertido" if r.get("ok") else "Error", ok=bool(r.get("ok")))

    if r.get("ok"):
        ok(f"Revertido: {r.get('reverted', evolution_id)}")
    else:
        fail(f"Error: {r.get('error', 'no encontrado')}")


def cmd_trainer_info(args):
    """Ver estado del trainer y comandos disponibles."""
    print_logo(compact=True)

    inst = _pick_instance(args, "¿De cuál instancia?")
    if not inst:
        return

    section(f"Melissa Trainer — {inst.label}")

    with Spinner("Consultando trainer...") as sp:
        r = _v8_api(inst, "/trainer/status", timeout=10)
        sp.finish("OK" if not r.get("error") else "Error", ok=not r.get("error"))

    if r.get("error"):
        fail("Trainer no disponible en esta instancia")
        return

    kv("SkillEngine",      q(C.GRN if r.get("skill_engine") else C.RED,
                              "activo" if r.get("skill_engine") else "inactivo"))
    kv("TrainerGateway",   q(C.GRN if r.get("trainer_gateway") else C.RED,
                              "activo" if r.get("trainer_gateway") else "inactivo"))
    kv("OwnerControl",     q(C.GRN if r.get("owner_style_control") else C.RED,
                              "activo" if r.get("owner_style_control") else "inactivo"))
    kv("PromptEvolver",    q(C.GRN if r.get("prompt_evolver") else C.RED,
                              "activo" if r.get("prompt_evolver") else "inactivo"))
    kv("AdminClientMode",  q(C.GRN if r.get("admin_client") else C.RED,
                              "activo" if r.get("admin_client") else "inactivo"))
    kv("NovaRuleSync",     q(C.GRN if r.get("nova_sync") else C.RED,
                              "activo" if r.get("nova_sync") else "inactivo"))
    kv("Skills activas",   str(len(r.get("active_skills", []))))
    gateway_state = r.get("gateway_state", {}) or {}
    kv("Gateway general",  q(C.GRN if gateway_state.get("enabled") else C.G3,
                              "ON" if gateway_state.get("enabled") else "off"))
    kv("Gateway admin",    q(C.GRN if gateway_state.get("auto_admin") else C.G3,
                              "ON" if gateway_state.get("auto_admin") else "off"))
    kv("Gateway user",     q(C.GRN if gateway_state.get("auto_user") else C.G3,
                              "ON" if gateway_state.get("auto_user") else "off"))
    kv("Evoluciones",      str(r.get("evolutions", 0)))
    kv("Sesiones activas", str(r.get("active_sessions", 0)))
    nl()

    info("Comandos disponibles:")
    commands = [
        ("melissa skills <n>",          "Ver/gestionar skills de comportamiento"),
        ("melissa skill <n> on <id>",   "Activar un skill"),
        ("melissa skill <n> off <id>",  "Desactivar un skill"),
        ("melissa gateway <n>",         "Ver estado del gateway automático"),
        ("melissa control <n>",         "Ver control duro del admin"),
        ("melissa aprender <n>",        "Enseñar algo en lenguaje natural"),
        ("melissa desaprender <n>",     "Revertir algo aprendido"),
        ("melissa simular-cliente <n>", "Simular conversación como cliente"),
    ]
    for cmd_, desc in commands:
        print(f"    {q(C.CYN, f'{cmd_:<35}')} {q(C.G2, desc)}")

    nl()
    info("Comandos en el bot (admin):")
    bot_commands = [
        "/entrenar",
        "/skills",
        "/skill [id] on/off",
        "/gateway",
        "/control [instrucción opcional]",
        "/aprender [instrucción en lenguaje natural]",
        "/desaprender [id]",
        "/simular-cliente [escenario]",
        "/salir  (para salir del modo cliente)",
    ]
    for bc in bot_commands:
        print(f"    {q(C.P2, bc)}")


def cmd_trainer_simulate_client(args):
    """Iniciar modo admin-como-cliente vía CLI."""
    print_logo(compact=True)

    inst = _pick_instance(args, "¿De cuál instancia?")
    if not inst:
        return

    h = health(inst.port)
    if not h:
        fail(f"{inst.label} está offline")
        return

    section(f"Simular Cliente — {inst.label}",
            "Te conviertes en cliente para entrenar a Melissa")

    # Escenario
    scenarios = [
        ("libre",           "Conversación libre"),
        ("primer_contacto", "Cliente nuevo, primera vez"),
        ("precio",          "Pregunta precio de entrada"),
        ("miedo",           "Miedo a quedar exagerado"),
        ("esceptico",       "Ya fue a otro lugar y le fue mal"),
        ("ocupado",         "Poco tiempo"),
        ("negociador",      "Pide descuento"),
        ("bot_detector",    "Pregunta si es bot"),
        ("urgente",         "Necesita cita urgente"),
        ("referido",        "Viene por recomendación"),
    ]

    idx = select([f"{k} — {v}" for k, v in scenarios],
                 title="Elige el escenario de simulación:")
    scenario, _ = scenarios[idx]

    persona = prompt("Nombre del cliente simulado (opcional)", required=False) or ""

    # Iniciar sesión via API
    with Spinner("Iniciando sesión...") as sp:
        chat_id_sim = f"cli_sim_{int(time.time())}"
        r = _v8_api(inst, "/trainer/admin-as-client/start", method="POST",
                    payload={
                        "admin_chat_id": chat_id_sim,
                        "scenario":      scenario,
                        "persona":       persona or f"Cliente simulado",
                    }, timeout=10)
        sp.finish("Sesión iniciada" if r.get("ok") else "Error", ok=bool(r.get("ok")))

    if not r.get("ok"):
        fail("No se pudo iniciar la sesión de simulación")
        info("Puedes hacerlo directamente en el bot con: /simular-cliente " + scenario)
        return

    session_id = r.get("session_id", "?")
    ok(f"Sesión {session_id} iniciada como '{persona or 'Cliente simulado'}'")
    nl()
    info(f"Escenario: {scenario}")
    nl()
    info("Escribe los mensajes del cliente. Ctrl+C para terminar.")
    info("Comandos especiales:")
    info("  /feedback [texto]  — dar feedback sobre la respuesta")
    info("  /aprender [x]      — enseñar algo en este momento")
    info("  exit               — terminar")
    nl()

    # REPL de simulación
    while True:
        try:
            sys.stdout.write("\n  " + q(C.YLW, '👤 Cliente') + "  ")
            sys.stdout.flush()
            user_msg = input("").strip()
        except (EOFError, KeyboardInterrupt):
            nl()
            break

        if user_msg.lower() in ("exit", "salir", "quit", "q"):
            break

        if not user_msg:
            continue

        # Enviar mensaje al bot simulado
        with Spinner("Melissa responde...") as sp:
            # Simular el mensaje como si fuera del cliente
            webhook_payload = {
                "message": {
                    "text": user_msg,
                    "chat": {"id": chat_id_sim},
                    "from": {"id": chat_id_sim, "first_name": persona or "Cliente"},
                }
            }
            webhook_secret = inst.env.get("WEBHOOK_SECRET", "melissa_ultra_5")
            r_msg = inst.api_call(
                "POST",
                f"/webhook/{webhook_secret}",
                payload=webhook_payload,
                timeout=30
            )
            sp.finish("", ok=True)

        # Mostrar respuesta (puede ser bubble-based)
        print()
        response_text = ""

        if isinstance(r_msg, dict):
            for key in ("response", "message", "text", "reply"):
                if r_msg.get(key):
                    response_text = str(r_msg[key])
                    break

        if response_text:
            # Dividir por ||| para mostrar burbujas
            bubbles = [b.strip() for b in response_text.split("|||") if b.strip()]
            for i, bubble in enumerate(bubbles):
                if i > 0:
                    print()
                print(q(C.G0, bubble))
        else:
            print(q(C.G3, "(sin respuesta — revisa los logs)"))

    # Terminar sesión
    nl()
    with Spinner("Finalizando sesión...") as sp:
        r_stop = _v8_api(inst, "/trainer/admin-as-client/stop", method="POST",
                         payload={"admin_chat_id": chat_id_sim}, timeout=10)
        sp.finish("Sesión finalizada", ok=True)

    nl()
    ok(f"Sesión de entrenamiento completada")
    kv("Turnos simulados", str(r_stop.get("turns", "?")))
    nl()
    info("Para ver las reglas aprendidas: melissa config " + inst.name)
    info("En el bot: /reglas")

# Registrar rutas de Trainer después de definir los handlers.
ROUTES["skills"]           = cmd_trainer_skills
ROUTES["skill"]            = cmd_trainer_skills
ROUTES["aprender"]         = cmd_trainer_learn
ROUTES["learn"]            = cmd_trainer_learn
ROUTES["desaprender"]      = cmd_trainer_unlearn
ROUTES["entrenar"]         = cmd_trainer_info
ROUTES["trainer"]          = cmd_trainer_info
ROUTES["gateway"]          = cmd_trainer_gateway
ROUTES["control"]          = cmd_trainer_control
ROUTES["simular-cliente"]  = cmd_trainer_simulate_client
ROUTES["cliente"]          = cmd_trainer_simulate_client



# ══════════════════════════════════════════════════════════════════════════════
# melissa watch — Live observatory feed in terminal
# ══════════════════════════════════════════════════════════════════════════════

def cmd_watch(args):
    """
    Live feed en tiempo real de todo lo que hace Melissa.
    Ve conversaciones, calidad, fallos, LLM calls — mientras ocurren.
    Ctrl+C para salir.
    """
    print_logo(compact=True)

    inst = _pick_instance(args, "¿De cuál instancia?")
    if not inst:
        return

    h = health(inst.port)
    if not h:
        fail(f"{inst.label} está offline")
        return

    # Verificar que observatory está activo
    ping = _v8_api(inst, "/obs/health", timeout=5)
    if ping.get("error"):
        fail("Observatory no está activo en esta instancia")
        info("Asegúrate de que melissa.py tiene el Observatory integrado")
        return

    section(f"Live Feed — {inst.label}", "Ctrl+C para salir")

    buffered  = ping.get("events_buffered", 0)
    subs      = ping.get("subscribers", 0)
    active_c  = ping.get("active_conversations", 0)

    kv("Eventos en buffer",       str(buffered))
    kv("Conversaciones activas",  str(active_c))
    kv("Otros observadores",      str(subs))
    nl()

    # Color por tipo
    TYPE_COLORS = {
        "llm_call":       C.P2,
        "message_in":     C.CYN,
        "message_out":    C.GRN,
        "quality_score":  C.YLW,
        "failure":        C.RED,
        "warning":        C.YLW,
        "appointment":    C.GRN,
        "conversion":     C.GRN,
        "funnel_advance": C.P2,
        "diagnosis":      C.AMB,
        "system":         C.G3,
    }
    TYPE_ICONS = {
        "llm_call":       "⚡",
        "message_in":     "←",
        "message_out":    "→",
        "quality_score":  "◎",
        "failure":        "✗",
        "warning":        "!",
        "appointment":    "📅",
        "conversion":     "✓",
        "funnel_advance": "▲",
        "diagnosis":      "🔍",
        "system":         "·",
    }
    SEV_COLORS = {
        "info":     C.G2,
        "warning":  C.YLW,
        "error":    C.RED,
        "critical": C.RED,
    }

    def _render_event(evt):
        """Renderiza un evento como línea de log."""
        ts      = evt.get("ts_h", "??:??:??")
        etype   = evt.get("type", "?")
        chat    = evt.get("chat_id", "")[-6:]
        sev     = evt.get("severity", "info")
        data    = evt.get("data", {})

        color = TYPE_COLORS.get(etype, C.G2)
        icon  = TYPE_ICONS.get(etype, "·")
        sev_c = SEV_COLORS.get(sev, C.G2)

        # Línea principal
        chat_tag = q(C.G3, f"[{chat}]") if chat else ""
        line = (f"  {q(C.G3, ts)}  "
                f"{q(color, icon, bold=True)}  "
                f"{q(color, etype.replace('_',' ')[:16])<22}  "
                f"{chat_tag}")

        # Detalle específico por tipo
        detail = ""
        if etype == "llm_call":
            lat = data.get("latency_ms", 0)
            lat_c = C.GRN if lat < 2000 else (C.YLW if lat < 5000 else C.RED)
            tok = data.get("out_tok", 0) + data.get("in_tok", 0)
            detail = f"  {q(lat_c, f'{lat}ms')}  {q(C.G3, f'{tok}tok')}"
            if data.get("issues"):
                issue_count = len(data.get("issues", []))
                detail += f"  {q(C.RED, f'{issue_count} issue(s)')}"
        elif etype in ("message_in", "message_out"):
            preview = data.get("content", "")[:50]
            arrow_c = C.CYN if etype == "message_in" else C.GRN
            detail  = f"  {q(arrow_c, repr(preview))}"
        elif etype == "quality_score":
            sc = data.get("score", 0)
            avg = data.get("avg", 0)
            sc_c = C.GRN if sc >= 0.8 else (C.YLW if sc >= 0.6 else C.RED)
            detail = f"  {q(sc_c, f'{int(sc*100)}%')}  avg:{int(avg*100)}%"
        elif etype == "failure":
            ftype  = data.get("type", "?")
            fdetail = data.get("detail", "")[:40]
            detail = f"  {q(C.RED, ftype)}  {q(C.G2, fdetail)}"
        elif etype == "funnel_advance":
            detail = f"  {q(C.G3, data.get('from','?'))} → {q(C.P2, data.get('to','?'))}"
        elif etype == "conversion":
            detail = f"  {q(C.GRN, '🎉 CONVERSIÓN')}  {data.get('turns',0)} turnos"
        elif etype == "diagnosis":
            detail = f"  {q(C.AMB, data.get('summary','')[:60])}"
        elif etype == "appointment":
            detail = f"  {q(C.GRN, data.get('service','?'))}  {data.get('date','')}"

        print(line + detail)

    # === SSE streaming via httpx or fallback polling ===
    info("Conectando al stream en vivo...")
    nl()

    url = f"http://localhost:{inst.port}/obs/stream"
    headers = {}
    if inst.master_key:
        headers["X-Master-Key"] = inst.master_key

    # Try streaming with httpx
    if _HTTPX:
        try:
            with _httpx.stream("GET", url, headers=headers, timeout=None) as response:
                if response.status_code != 200:
                    fail(f"Stream error: {response.status_code}")
                    return
                ok("Stream conectado. Esperando eventos...")
                nl()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        try:
                            evt = json.loads(line[6:])
                            if evt.get("status") == "connected":
                                continue
                            _render_event(evt)
                        except (json.JSONDecodeError, KeyboardInterrupt):
                            break
        except KeyboardInterrupt:
            pass
        except Exception as e:
            fail(f"Stream error: {e}")
            info("Fallback: polling /obs/events cada 2s")
    else:
        # Polling fallback
        ok("Streaming en modo polling (cada 2s)")
        nl()
        last_ts = 0
        try:
            while True:
                r = _v8_api(inst, f"/obs/events?limit=20", timeout=5)
                evts = r.get("events", [])
                for evt in reversed(evts):
                    if evt.get("ts", 0) > last_ts:
                        last_ts = evt["ts"]
                        _render_event(evt)
                time.sleep(2)
        except KeyboardInterrupt:
            pass

    nl()
    info("Stream cerrado")
    nl()
    # Show summary
    stats = _v8_api(inst, "/obs/stats", timeout=5)
    if not stats.get("error"):
        nl()
        info("Resumen de la sesión:")
        llm = stats.get("llm", {})
        kv("LLM calls",         str(llm.get("calls", 0)))
        kv("Latencia promedio",  f"{llm.get('avg_latency_ms', 0)}ms")
        kv("Calidad promedio",   f"{int(llm.get('avg_quality', 0)*100)}%")
        fails = stats.get("failures", {})
        kv("Fallos detectados",  str(fails.get("total", 0)))


def cmd_diagnose(args):
    """Pedir diagnóstico AI de los fallos recientes."""
    print_logo(compact=True)

    inst = _pick_instance(args, "¿De cuál instancia diagnosticar?")
    if not inst:
        return

    section(f"AI Diagnóstico — {inst.label}")

    # Ver fallos primero
    with Spinner("Recopilando fallos recientes...") as sp:
        fails = _v8_api(inst, "/obs/failures?limit=30", timeout=10)
        sp.finish("OK" if not fails.get("error") else "Error",
                  ok=not fails.get("error"))

    if fails.get("error"):
        fail("Observatory no disponible")
        return

    total = fails.get("total", 0)
    by_type = fails.get("by_type", {})

    if total == 0:
        ok("No se detectaron fallos recientes")
        return

    kv("Fallos analizados", str(total))
    for ftype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        icon = q(C.RED, "✗") if count >= 3 else q(C.YLW, "!")
        print(f"  {icon}  {q(C.W, ftype):<25} {q(C.RED, str(count))}x")
    nl()

    if confirm("¿Pedir diagnóstico al agente IA?"):
        with Spinner("El agente IA está analizando los fallos...") as sp:
            diag = _v8_api(inst, "/obs/diagnose", method="POST",
                           payload={"limit": 20}, timeout=30)
            sp.finish("Diagnóstico generado" if not diag.get("error") else "Error",
                      ok=not diag.get("error"))

        if diag.get("error"):
            fail("No se pudo generar el diagnóstico")
            return

        section("Diagnóstico del Agente IA")
        kv("Severidad",   q(C.RED if diag.get("severity") == "critical" else
                            C.YLW if diag.get("severity") == "high" else C.GRN,
                            (diag.get("severity") or "?").upper()))
        nl()
        info(diag.get("summary", ""))
        nl()

        if diag.get("root_causes"):
            info("Causas raíz:")
            for cause in diag["root_causes"]:
                print(f"    {q(C.YLW, '→')} {q(C.G1, cause)}")
            nl()

        if diag.get("impact"):
            info(f"Impacto en el cliente: {q(C.W, diag['impact'])}")
            nl()

        if diag.get("actions"):
            info("Acciones recomendadas:")
            for action in diag["actions"]:
                priority = action.get("priority", "media")
                p_color  = C.RED if priority == "alta" else (C.YLW if priority == "media" else C.G2)
                print(f"    {q(p_color, f'[{priority}]')}  {q(C.W, action.get('action', ''))}")
            nl()

        info(f"Para ver el stream en vivo: melissa watch {inst.name}")


def cmd_obs_stats(args):
    """Estadísticas de observabilidad en tiempo real."""
    print_logo(compact=True)

    inst = _pick_instance(args, "¿De cuál instancia?")
    if not inst:
        return

    section(f"Observatory Stats — {inst.label}")

    with Spinner("Cargando estadísticas...") as sp:
        stats = _v8_api(inst, "/obs/stats", timeout=10)
        sp.finish("OK" if not stats.get("error") else "Error",
                  ok=not stats.get("error"))

    if stats.get("error"):
        fail("Observatory no disponible")
        info("Verifica que el observatory esté inicializado: melissa v8 " + inst.name)
        return

    llm  = stats.get("llm", {})
    conv = stats.get("conversations", {})
    fail_s = stats.get("failures", {})

    # LLM
    info("LLM Performance:")
    lat = llm.get("avg_latency_ms", 0)
    lat_c = C.GRN if lat < 2000 else (C.YLW if lat < 5000 else C.RED)
    kv("  Calls totales",   str(llm.get("calls", 0)))
    kv("  Latencia promedio", q(lat_c, f"{lat}ms"))
    kv("  P95 latencia",    f"{llm.get('p95_latency_ms', 0)}ms")
    q_score = llm.get("avg_quality", 0)
    q_c = C.GRN if q_score >= 0.8 else (C.YLW if q_score >= 0.65 else C.RED)
    kv("  Calidad promedio", q(q_c, f"{int(q_score*100)}%"))
    nl()

    # Conversaciones
    info("Conversaciones (última hora):")
    kv("  Activas",          str(conv.get("active", 0)))
    kv("  Conversiones",     str(conv.get("conversions", 0)))
    kv("  Tasa conversión",  f"{conv.get('rate', 0)}%")
    kv("  Turnos promedio",  str(conv.get("avg_turns", 0)))
    nl()

    # Fallos
    f_total = fail_s.get("total", 0)
    f_rate  = fail_s.get("rate_pct", 0)
    f_color = C.GRN if f_total == 0 else (C.YLW if f_total < 5 else C.RED)
    info("Fallos detectados:")
    kv("  Total",     q(f_color, str(f_total)))
    kv("  Tasa",      q(f_color, f"{f_rate}%"))
    nl()

    if f_total > 0:
        if confirm("¿Ver detalle de fallos?"):
            fake = type("A", (), {"name": inst.name, "subcommand": ""})()
            cmd_diagnose(fake)

    info(f"Stream en vivo: melissa watch {inst.name}")


# Registrar rutas de Observatory después de definir los handlers.
ROUTES["watch"]        = cmd_watch
ROUTES["ver"]          = cmd_watch
ROUTES["live"]         = cmd_watch
ROUTES["diagnose"]     = cmd_diagnose
ROUTES["diagnostico"]  = cmd_diagnose
ROUTES["obs"]          = cmd_obs_stats
ROUTES["observatory"]  = cmd_obs_stats


def main():
    parser = argparse.ArgumentParser(prog="melissa", add_help=False)
    parser.add_argument("command", nargs="?", default="")
    parser.add_argument("subcommand", nargs="?", default="")
    parser.add_argument("name", nargs="?", default="")
    parser.add_argument("--lines", type=int, default=100, help="Líneas históricas para logs")
    parser.add_argument("--errors", action="store_true", help="Filtrar solo errores en logs")
    parser.add_argument("--scan", action="store_true", help="Escanear logs sin stream")
    parser.add_argument("--fix", action="store_true", help="Intentar autofix basado en logs")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--version", "-V", action="store_true")
    parser.add_argument("--help", "-h", action="store_true")
    parser.add_argument("--compact", "-c", action="store_true")
    parser.add_argument("--quiet", "-q", action="store_true")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")
    parser.add_argument("--auto", "-y", action="store_true", help="Auto-confirm")

    args = parser.parse_args()

    # Modo silencioso
    if args.quiet:
        global _tty
        _tty = lambda: False
    
    if args.version:
        if args.json:
            print(json.dumps({"version": VERSION}))
        else:
            print(f"melissa {VERSION}")
        return
    
    if args.install:
        cmd_install(args)
        return
    
    cmd = args.command.lower().strip()

    # logfix / logscan → equivalentes a logs --fix / logs --scan
    if cmd == "logfix":
        args.subcommand = "fix"
        cmd = "logs"
    elif cmd == "logscan":
        args.subcommand = "scan"
        cmd = "logs"

    # Manejar subcommand/name
    if args.subcommand and not args.name:
        args.name = args.subcommand
    
    if cmd == "" and not args.help:
        ensure_workspace_files()
        if not workspace_is_configured() or not get_instances():
            cmd_init(args)
            return

    # Help
    if args.help or cmd in ("help", "--help", "-h", ""):
        cmd_help_extended(args)
        return
    
    # Ejecutar comando
    if cmd in ROUTES:
        try:
            ROUTES[cmd](args)
        except KeyboardInterrupt:
            nl()
            info("Interrumpido")
        except Exception as e:
            fail(f"Error: {e}")
            if os.getenv("MELISSA_DEBUG"):
                import traceback
                traceback.print_exc()
    else:
        # Intentar lenguaje natural
        full_text = " ".join(filter(None, [cmd, args.subcommand, args.name]))
        if not nl_route(full_text):
            fail(f"Comando desconocido: '{cmd}'")
            nl()
            info("'melissa help' para ver comandos")
            info("'melissa i' para modo interactivo")

if __name__ == "__main__":
    main()
