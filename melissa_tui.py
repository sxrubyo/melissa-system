#!/usr/bin/env python3
"""
melissa_tui — Interfaz interactiva de Melissa con flechas ↑↓

Reemplaza el texto de ayuda estático por un menú navegable.
Se activa cuando el usuario corre 'melissa' sin argumentos.

Instalar:
  Copia este archivo a ~/melissa/melissa_tui.py
  El parche en melissa_sync_fix.py lo activa automáticamente.

Uso directo:
  python3 melissa_tui.py
"""

import curses
import os
import sys
import json
import subprocess
import time
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

# ── Config (mismos defaults que melissa_cli.py) ─────────────────────────────
VERSION       = "8.0.2"
MELISSA_HOME  = os.getenv("MELISSA_HOME",  str(Path.home() / ".melissa"))
MELISSA_DIR   = os.getenv("MELISSA_DIR",   str(Path(__file__).resolve().parent))
INSTANCES_DIR = os.getenv("INSTANCES_DIR", str(Path.home() / "melissa-instances"))
CLI_SCRIPT    = os.getenv("MELISSA_CLI",   str(Path(__file__).resolve().parent / "melissa_cli.py"))

# ── Colores curses (índices de par) ─────────────────────────────────────────
CP_LOGO   = 1   # Lavanda — letras MELISSA
CP_TITLE  = 2   # Blanco bold — subtítulo
CP_DIM    = 3   # Gris dim — descripción
CP_SEL    = 4   # Item seleccionado (bg highlight)
CP_OK     = 5   # Verde ✓
CP_WARN   = 6   # Amarillo
CP_BAR    = 7   # Bordes de la caja y separadores
CP_INST   = 8   # Instancia activa
CP_HINT   = 9   # Ayuda de teclas


# ── Estructura de instancia ──────────────────────────────────────────────────
class Instance:
    def __init__(self, name: str, label: str, port: int, online: bool,
                 sector: str = "otro", path: str = "", is_base: bool = False):
        self.name    = name
        self.label   = label
        self.port    = port
        self.online  = online
        self.sector  = sector
        self.path    = path
        self.is_base = is_base

    @property
    def status_char(self):
        return "●" if self.online else "○"

    @property
    def status_str(self):
        return "online" if self.online else "offline"


# ── Menú principal ──────────────────────────────────────────────────────────
MENU_ITEMS = [
    # (id, emoji, label, descripción, requiere_instancia)
    ("new",       "✨", "Nueva instancia",      "Crear recepcionista para un cliente",  False),
    ("sync",      "🔄", "Sincronizar todo",      "Copiar updates del core a clientes",   False),
    ("list",      "📋", "Ver instancias",        "Listar todas con estado y puerto",     False),
    ("dashboard", "📊", "Dashboard",             "Panel en tiempo real",                 False),
    ("health",    "🩺", "Health check",          "Verificar que todas estén online",     False),
    ("logs",      "📜", "Ver logs",              "Stream de logs en vivo",               True),
    ("restart",   "↺ ", "Reiniciar",             "Reiniciar instancia o todas",          True),
    ("config",    "⚙ ", "Configurar",            "Editar persona, token, ajustes",       True),
    ("status",    "🔍", "Estado detallado",      "CPU, memoria, webhook, env",           True),
    ("doctor",    "💊", "Diagnóstico",           "Detectar y reparar problemas",         False),
    ("backup",    "💾", "Backup",                "Snapshot de instancia",                True),
    ("delete",    "🗑 ", "Eliminar instancia",    "Borrar instancia por completo",        True),
    ("_exit",     "✕ ", "Salir",                 "",                                     False),
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _check_port(port: int, timeout: float = 0.4) -> bool:
    """Verificar si hay algo escuchando en el puerto."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except Exception:
        return False


def _load_instances() -> List[Instance]:
    instances: List[Instance] = []

    # Base instance
    base_env_path = Path(MELISSA_DIR) / ".env"
    if base_env_path.exists():
        port = _env_val(base_env_path, "PORT", "8001")
        try:
            port_int = int(port)
        except ValueError:
            port_int = 8001
        online = _check_port(port_int)
        instances.append(Instance(
            name="base",
            label="Base (template)",
            port=port_int,
            online=online,
            path=MELISSA_DIR,
            is_base=True,
        ))

    # Client instances
    inst_root = Path(INSTANCES_DIR)
    if inst_root.is_dir():
        for d in sorted(inst_root.iterdir()):
            if not d.is_dir():
                continue
            env_file = d / ".env"
            if not env_file.exists():
                continue
            port_str = _env_val(env_file, "PORT", "8002")
            try:
                port_int = int(port_str)
            except ValueError:
                port_int = 8002

            # Cargar metadata de instance.json
            label = d.name.replace("-", " ").title()
            sector = "otro"
            meta_path = d / "instance.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                    label  = meta.get("label", label)
                    sector = meta.get("sector", sector)
                except Exception:
                    pass

            online = _check_port(port_int)
            instances.append(Instance(
                name=d.name,
                label=label,
                port=port_int,
                online=online,
                sector=sector,
                path=str(d),
                is_base=False,
            ))

    return instances


def _env_val(env_file: Path, key: str, default: str = "") -> str:
    try:
        for line in env_file.read_text(errors="replace").splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line[len(key) + 1:].strip().strip('"').strip("'")
    except Exception:
        pass
    return default


def _run_melissa(*args: str) -> None:
    """Llamar a melissa_cli.py con argumentos."""
    curses.endwin()
    print()
    try:
        if Path(CLI_SCRIPT).exists():
            cmd = [sys.executable, CLI_SCRIPT] + list(args)
        else:
            cmd = ["melissa"] + list(args)
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n  Interrumpido")
    print()
    input("  Presiona Enter para volver al menú... ")


def _ask_instance(instances: List[Instance]) -> Optional[Instance]:
    """Selector simple de instancia (fuera de curses)."""
    clients = [i for i in instances if not i.is_base]
    if not clients:
        print("\n  ⚠  No hay instancias de clientes todavía.")
        print("     Usa 'Nueva instancia' para crear una.\n")
        input("  Presiona Enter para volver... ")
        return None
    if len(clients) == 1:
        return clients[0]
    print()
    for idx, inst in enumerate(clients, 1):
        dot = "●" if inst.online else "○"
        print(f"  {idx}.  {dot}  {inst.label}  (:{inst.port})")
    print()
    while True:
        try:
            v = input("  Elige número (o Enter para cancelar): ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if v == "":
            return None
        if v.isdigit() and 1 <= int(v) <= len(clients):
            return clients[int(v) - 1]
        print("  Escribe el número de la opción")


def _execute_menu_action(action_id: str, instances: List[Instance]) -> None:
    """Ejecutar la acción seleccionada del menú."""
    if action_id == "_exit":
        return

    needs_instance = next(
        (item[4] for item in MENU_ITEMS if item[0] == action_id), False
    )

    if needs_instance:
        curses.endwin()
        inst = _ask_instance(instances)
        if inst is None:
            return
        _run_melissa(action_id, inst.name)
    else:
        _run_melissa(action_id)


# ── Logo — idéntico al banner de `melissa init` ──────────────────────────────
#
# Cada entrada: (texto, color_pair, bold)
# CP_LOGO  → letras MELISSA      (lavanda/púrpura)
# CP_DIM   → tagline             (gris dim)
# CP_TITLE → versión / sectores  (blanco)
# CP_BAR   → línea separadora    (gris medio)
#
_SEP_LINE = "  ──────────────────────────────────────────────────────"

LOGO_LINES = [
    ("  ███╗   ███╗███████╗██╗     ██╗███████╗███████╗ █████╗ ",           CP_LOGO,  True),
    ("  ████╗ ████║██╔════╝██║     ██║██╔════╝██╔════╝██╔══██╗",           CP_LOGO,  True),
    ("  ██╔████╔██║█████╗  ██║     ██║███████╗███████╗███████║",            CP_LOGO,  True),
    ("  ██║╚██╔╝██║██╔══╝  ██║     ██║╚════██║╚════██║██╔══██║",           CP_LOGO,  True),
    ("  ██║ ╚═╝ ██║███████╗███████╗██║███████║███████║██║  ██║",            CP_LOGO,  True),
    ("  ╚═╝     ╚═╝╚══════╝╚══════╝╚═╝╚══════╝╚══════╝╚═╝  ╚═╝",          CP_LOGO,  True),
    ("  Multi-sector. Multi-canal. Siempre disponible.",                    CP_DIM,   False),
    (f"  ✦ Melissa v{VERSION}  ·  20 sectores",                             CP_TITLE, True),
    (_SEP_LINE,                                                             CP_BAR,   False),
]

LOGO_COMPACT = "  ✦  melissa"


def _draw_logo(win, row: int, cols: int, compact: bool = False) -> int:
    """Dibuja el logo. Devuelve la siguiente fila libre."""
    if compact or cols < 64:
        # Modo compacto: una sola línea
        try:
            win.addstr(row, 0, LOGO_COMPACT, curses.color_pair(CP_LOGO) | curses.A_BOLD)
            win.addstr(row, len(LOGO_COMPACT) + 2,
                       f"v{VERSION}", curses.color_pair(CP_DIM))
        except curses.error:
            pass
        return row + 2
    else:
        # Modo completo: idéntico a `melissa init`
        for i, (line, pair, bold) in enumerate(LOGO_LINES):
            try:
                attr = curses.color_pair(pair)
                if bold:
                    attr |= curses.A_BOLD
                win.addstr(row + i, 0, line[:cols - 1], attr)
            except curses.error:
                pass
        return row + len(LOGO_LINES) + 1


def _draw_instances(win, row: int, instances: List[Instance], cols: int) -> int:
    """Dibuja la barra de estado de instancias."""
    try:
        win.addstr(row, 0, "  ", curses.color_pair(CP_DIM))
        win.addstr(row, 2, "Instancias: ", curses.color_pair(CP_DIM))
    except curses.error:
        pass

    col = 14
    clients = [i for i in instances if not i.is_base]
    if not clients:
        try:
            win.addstr(row, col, "ninguna aún — usa Nueva instancia",
                       curses.color_pair(CP_WARN))
        except curses.error:
            pass
        return row + 2

    for inst in clients[:6]:
        dot_attr   = curses.color_pair(CP_OK) if inst.online else curses.color_pair(CP_WARN)
        label_s    = f" {inst.label[:18]} "
        try:
            win.addstr(row, col, inst.status_char, dot_attr | curses.A_BOLD)
            win.addstr(row, col + 2, label_s[:cols - col - 4],
                       curses.color_pair(CP_TITLE))
        except curses.error:
            pass
        col += len(label_s) + 3
        if col > cols - 20:
            break

    if len(clients) > 6:
        try:
            win.addstr(row, col, f"+{len(clients)-6} más",
                       curses.color_pair(CP_DIM))
        except curses.error:
            pass
    return row + 2


def _draw_menu(win, row: int, items: list, selected: int, cols: int) -> int:
    """Dibuja el menú con highlight en item seleccionado."""
    pad   = 4
    width = min(cols - pad * 2, 68)

    try:
        win.addstr(row, pad, "┌" + "─" * (width - 2) + "┐",
                   curses.color_pair(CP_BAR))
    except curses.error:
        pass
    row += 1

    for idx, (action_id, emoji, label, desc, _req) in enumerate(items):
        is_sel = (idx == selected)

        prefix = "  ▶  " if is_sel else "     "
        line   = f"{prefix}{emoji}  {label}"
        if desc and not is_sel:
            gap  = width - 4 - len(line)
            line = line + " " * max(0, gap - len(desc) - 2) + f"  {desc}"

        inner = line[:width - 4]
        inner = inner + " " * max(0, width - 4 - len(inner))

        try:
            if is_sel:
                win.addstr(row, pad, "  │", curses.color_pair(CP_BAR))
                win.addstr(row, pad + 3,
                           f"  {inner}  ",
                           curses.color_pair(CP_SEL) | curses.A_BOLD)
                win.addstr(row, pad + 3 + 2 + len(inner) + 2,
                           "│", curses.color_pair(CP_BAR))
            else:
                win.addstr(row, pad, "  │", curses.color_pair(CP_BAR))
                main_part = f"  {prefix}{emoji}  {label}"
                win.addstr(row, pad + 3,
                           main_part[:width - 4],
                           curses.color_pair(CP_TITLE))
                if desc:
                    dp  = pad + 3 + len(main_part)
                    gap = width - 4 - len(main_part) - len(desc) - 2
                    if gap > 0 and dp + gap + len(desc) + 4 < cols:
                        win.addstr(row, dp + max(1, gap), desc[:24],
                                   curses.color_pair(CP_DIM))
                avail_end = pad + 3 + width - 4
                win.addstr(row, avail_end, "  │", curses.color_pair(CP_BAR))
        except curses.error:
            pass

        row += 1

    try:
        win.addstr(row, pad, "└" + "─" * (width - 2) + "┘",
                   curses.color_pair(CP_BAR))
    except curses.error:
        pass
    row += 2

    hint = "  ↑ ↓  navegar    Enter  seleccionar    q / Esc  salir"
    try:
        win.addstr(row, 0, hint[:cols - 1], curses.color_pair(CP_HINT))
    except curses.error:
        pass
    return row + 1


# ── Main TUI loop ────────────────────────────────────────────────────────────

def _tui_main(stdscr) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    curses.noecho()
    curses.cbreak()
    stdscr.nodelay(False)

    curses.start_color()
    curses.use_default_colors()

    # Paleta — misma identidad visual que el banner del CLI
    curses.init_pair(CP_LOGO,  183, -1)   # Lavanda (letras MELISSA)
    curses.init_pair(CP_TITLE,  15, -1)   # Blanco
    curses.init_pair(CP_DIM,   240, -1)   # Gris dim
    curses.init_pair(CP_SEL,    15, 57)   # Blanco sobre púrpura (highlight)
    curses.init_pair(CP_OK,    114, -1)   # Verde ✓
    curses.init_pair(CP_WARN,  221, -1)   # Amarillo ⚠
    curses.init_pair(CP_BAR,   241, -1)   # Bordes (gris medio)
    curses.init_pair(CP_INST,  141, -1)   # Instancia activa
    curses.init_pair(CP_HINT,  236, -1)   # Hint muy dim

    selected    = 0
    instances   = []
    last_load   = 0.0
    need_reload = True

    while True:
        now = time.monotonic()
        if need_reload or now - last_load > 10:
            instances   = _load_instances()
            last_load   = now
            need_reload = False

        rows, cols = stdscr.getmaxyx()
        stdscr.erase()

        compact = rows < 22   # Menos filas → modo compacto

        r = 0
        r = _draw_logo(stdscr, r, cols, compact=compact)
        r = _draw_instances(stdscr, r, instances, cols)
        r = _draw_menu(stdscr, r, MENU_ITEMS, selected, cols)

        stdscr.refresh()

        try:
            key = stdscr.getch()
        except KeyboardInterrupt:
            break

        if key in (ord('q'), ord('Q'), 27):   # q / Esc
            break
        elif key == curses.KEY_UP:
            selected = (selected - 1) % len(MENU_ITEMS)
        elif key == curses.KEY_DOWN:
            selected = (selected + 1) % len(MENU_ITEMS)
        elif key == curses.KEY_HOME:
            selected = 0
        elif key == curses.KEY_END:
            selected = len(MENU_ITEMS) - 1
        elif key in (curses.KEY_ENTER, 10, 13):
            action_id = MENU_ITEMS[selected][0]
            if action_id == "_exit":
                break
            _execute_menu_action(action_id, instances)
            need_reload = True
        elif key == curses.KEY_RESIZE:
            stdscr.erase()
            stdscr.refresh()


# ── Entry point ──────────────────────────────────────────────────────────────

def run_tui() -> None:
    """
    Lanza el TUI interactivo. Llamar desde melissa_cli.py main()
    cuando no se pasan argumentos en una terminal real.
    """
    if not sys.stdout.isatty():
        _simple_help()
        return

    try:
        curses.wrapper(_tui_main)
    except curses.error as e:
        print(f"\n  (TUI no disponible en esta terminal: {e})")
        print("  Usa: melissa help\n")
    except Exception as e:
        curses.endwin()
        print(f"\n  Error en TUI: {e}")
        print("  Usa: melissa help\n")


def _simple_help() -> None:
    """Fallback en terminales sin soporte interactivo."""
    print(f"""
  ✦  melissa  v{VERSION}

  Comandos esenciales:
    melissa new           Crear instancia para un cliente
    melissa sync          Sincronizar updates a todas las instancias
    melissa list          Ver todas las instancias
    melissa dashboard     Panel en tiempo real
    melissa health        Health check rápido
    melissa logs [n]      Logs en vivo
    melissa restart [n]   Reiniciar instancia
    melissa doctor        Diagnóstico del sistema

  Instancias en: {INSTANCES_DIR}
""")


if __name__ == "__main__":
    run_tui()
