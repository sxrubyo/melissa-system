#!/usr/bin/env python3
"""
melissa_sync_fix.py — Parcha melissa_cli.py con 3 correcciones críticas

Bugs que corrige:
  1. INSTANCES_DIR apuntaba a ~/.melissa/instances en vez de ~/melissa-instances
  2. 'personas' en SYNC_RUNTIME_DIRS sobrescribía identidades de clientes
  3. _clone_runtime_entries usaba rmtree en directorios (destructivo)

Uso:
  cd ~/melissa
  python3 melissa_sync_fix.py

El script crea un backup antes de modificar.
"""

import sys
import os
import shutil
import re
from pathlib import Path
from datetime import datetime

CLI_PATH = Path(__file__).resolve().parent / "melissa_cli.py"

# ══════════════════════════════════════════════════════════════════════════════
# Parches exactos (old_str → new_str)
# ══════════════════════════════════════════════════════════════════════════════

PATCHES = [

    # ── FIX 1: INSTANCES_DIR default path ────────────────────────────────────
    {
        "id":   "fix-instances-dir",
        "desc": "Corregir INSTANCES_DIR: ~/.melissa/instances → ~/melissa-instances",
        "old":  'INSTANCES_DIR = os.getenv("INSTANCES_DIR", str(Path(MELISSA_HOME) / "instances"))',
        "new":  'INSTANCES_DIR = os.getenv("INSTANCES_DIR", str(Path.home() / "melissa-instances"))',
    },

    # ── FIX 2: Remove 'personas' from SYNC_RUNTIME_DIRS ─────────────────────
    {
        "id":   "fix-sync-dirs",
        "desc": "Proteger directorios de identidad de instancias en sync",
        "old":  '''SYNC_RUNTIME_DIRS = [
    "v7",
    "melissa_core",
    "melissa_agents",
    "melissa_skills",
    "melissa_integrations",
    "personas",
]''',
        "new":  '''# ── Directorios que se sincronizan a todas las instancias ──────────────────
SYNC_RUNTIME_DIRS = [
    "v7",
    "melissa_core",
    "melissa_agents",
    "melissa_skills",
    "melissa_integrations",
    # "personas" INTENCIONALMENTE EXCLUIDO:
    # cada instancia tiene su propia identidad, prompts y tono.
    # Usa 'melissa config <nombre>' para editar la persona de un cliente.
]

# ── Paths que NUNCA se tocan durante sync ──────────────────────────────────
INSTANCE_PROTECTED_PATHS = {
    ".env",
    "melissa.db", "melissa.db-shm", "melissa.db-wal",
    "melissa_ultra.db", "vectors.db", "data.db",
    "logs",
    "identity",       # Nombre, voz, tono del agente
    "soul",           # Valores y ética del agente
    "personas",       # Prompts de sistema del cliente
    "knowledge_base", # Base de conocimiento del cliente
    "instance.json",
    "auth_info_multi.txt",
    "__pycache__",
    "backups",
    ".venv",
}
''',
    },

    # ── FIX 3: Smart directory sync (no rmtree) ───────────────────────────────
    {
        "id":   "fix-clone-entries",
        "desc": "Sync inteligente: actualiza archivos sin borrar los específicos de la instancia",
        "old":  '''def _clone_runtime_entries(source_root: str, dest_root: str, entries: Optional[List[str]] = None) -> List[str]:
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
    return copied''',
        "new":  '''def _sync_dir_smart(src: Path, dst: Path) -> None:
    """
    Sync de directorio que ACTUALIZA archivos sin borrar extras.
    A diferencia de copytree(dirs_exist_ok=False), no elimina archivos
    que solo existen en el destino (configuraciones del cliente).
    """
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        # Nunca pisar rutas protegidas dentro de subdirectorios
        top = rel.parts[0] if rel.parts else ""
        if top in INSTANCE_PROTECTED_PATHS:
            continue
        try:
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
        except Exception:
            pass  # permisos u otros errores no detienen el sync


def _clone_runtime_entries(source_root: str, dest_root: str, entries: Optional[List[str]] = None) -> List[str]:
    src_root = Path(source_root)
    dst_root = Path(dest_root)
    copied: List[str] = []
    for rel_path in entries or _runtime_sync_entries(source_root):
        # Saltar rutas protegidas de la instancia
        top_level = Path(rel_path).parts[0] if Path(rel_path).parts else rel_path
        if top_level in INSTANCE_PROTECTED_PATHS:
            continue
        src = src_root / rel_path
        dst = dst_root / rel_path
        if not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            # Sync inteligente: actualiza sin borrar archivos del cliente
            _sync_dir_smart(src, dst)
        else:
            if dst.exists() or dst.is_symlink():
                _remove_runtime_target(dst)
            shutil.copy2(src, dst)
        copied.append(rel_path)
    return copied''',
    },

    # ── FIX 4: Lanzar TUI cuando melissa se corre sin args ───────────────────
    {
        "id":   "fix-tui-launch",
        "desc": "Lanzar melissa_tui cuando no hay argumentos",
        "old":  '''    if cmd == "" and not args.help:
        ensure_workspace_files()
        if not workspace_is_configured() or not get_instances():
            cmd_init(args)
            return

    # Help
    if args.help or cmd in ("help", "--help", "-h", ""):
        cmd_help_extended(args)
        return''',
        "new":  '''    if cmd == "" and not args.help:
        # ── Intentar lanzar TUI interactivo ──────────────────────────────
        _tui_path = Path(__file__).resolve().parent / "melissa_tui.py"
        if sys.stdout.isatty() and _tui_path.exists():
            try:
                import importlib.util as _ilu
                _spec = _ilu.spec_from_file_location("melissa_tui", str(_tui_path))
                _mod  = _ilu.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                _mod.run_tui()
                return
            except Exception:
                pass  # Fallback a help normal

        ensure_workspace_files()
        if not workspace_is_configured() or not get_instances():
            cmd_init(args)
            return

    # Help
    if args.help or cmd in ("help", "--help", "-h", ""):
        cmd_help_extended(args)
        return''',
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# Motor del patcher
# ══════════════════════════════════════════════════════════════════════════════

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def _c(color, text): return f"{color}{text}{RESET}"


def apply_patches(cli_path: Path) -> None:
    print(f"\n  {_c(BOLD, 'melissa_sync_fix')}  —  Parcheando {cli_path.name}")
    print()

    if not cli_path.exists():
        print(f"  {_c(RED, '✗')}  No encontré {cli_path}")
        print(f"     Asegúrate de correr este script desde ~/melissa/")
        sys.exit(1)

    # Backup
    stamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak     = cli_path.with_suffix(f".py.bak.{stamp}")
    shutil.copy2(cli_path, bak)
    print(f"  {_c(GREEN, '✓')}  Backup creado: {bak.name}")
    print()

    content = cli_path.read_text(encoding="utf-8", errors="replace")
    applied = 0
    skipped = 0

    for patch in PATCHES:
        pid  = patch["id"]
        desc = patch["desc"]
        old  = patch["old"]
        new  = patch["new"]

        if old not in content:
            # Verificar si el nuevo código ya está presente (ya parcheado)
            if new.strip()[:40] in content:
                print(f"  {_c(DIM, '·')}  [{pid}] Ya estaba aplicado — {_c(DIM, desc)}")
            else:
                print(f"  {_c(YELLOW, '!')}  [{pid}] No encontré el fragmento exacto — {_c(DIM, desc)}")
                print(f"     {_c(DIM, 'Puede que el código haya cambiado. Revisa manualmente.')}")
            skipped += 1
            continue

        content = content.replace(old, new, 1)
        applied += 1
        print(f"  {_c(GREEN, '✓')}  [{pid}] {desc}")

    print()

    if applied > 0:
        cli_path.write_text(content, encoding="utf-8")
        print(f"  {_c(GREEN, '✓')}  {applied} fix(es) aplicado(s) correctamente")
    else:
        print(f"  {_c(YELLOW, '·')}  Nada que aplicar — todos los fixes ya estaban presentes")

    if skipped > 0 and applied == 0:
        print(f"  {_c(YELLOW, '!')}  {skipped} patch(es) no coincidieron — revisa el CHANGELOG abajo")
        print()
        print("  ── Fixes manuales si el auto-patch no funcionó ─────────────────")
        _print_manual_guide()

    print()
    print(f"  {_c(CYAN, 'Siguiente paso:')}  pm2 restart melissa-clinica-americas")
    print(f"  {_c(CYAN, 'Probar sync:')}    melissa sync")
    print()


def _print_manual_guide():
    print("""
  FIX 1 — INSTANCES_DIR (línea ~158 en melissa_cli.py)
  ┌──────────────────────────────────────────────────────────────────
  │ - INSTANCES_DIR = os.getenv("INSTANCES_DIR", str(Path(MELISSA_HOME) / "instances"))
  │ + INSTANCES_DIR = os.getenv("INSTANCES_DIR", str(Path.home() / "melissa-instances"))
  └──────────────────────────────────────────────────────────────────

  FIX 2 — SYNC_RUNTIME_DIRS (línea ~192)
  ┌──────────────────────────────────────────────────────────────────
  │   Elimina "personas" de la lista SYNC_RUNTIME_DIRS
  │   (esa lista está al principio del archivo)
  └──────────────────────────────────────────────────────────────────

  FIX 3 — _clone_runtime_entries (función)
  ┌──────────────────────────────────────────────────────────────────
  │   En el loop, agrega antes del if src.is_dir():
  │     top_level = Path(rel_path).parts[0]
  │     if top_level in {".env","melissa.db","personas","identity","soul","logs"}:
  │         continue
  │   Y reemplaza:
  │     _remove_runtime_target(dst)
  │     shutil.copytree(src, dst)
  │   Por un loop que copie solo archivos nuevos/modificados
  └──────────────────────────────────────────────────────────────────
""")


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    target = CLI_PATH
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])

    apply_patches(target)
