from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Optional


@dataclass
class BBContext:
    melissa_dir: str
    colors: Any
    print_logo: Callable[..., None]
    section: Callable[..., None]
    q: Callable[..., str]
    kv: Callable[..., None]
    info: Callable[..., None]
    nl: Callable[..., None]
    fail: Callable[..., None]
    warn: Callable[..., None]
    ok: Callable[..., None]
    prompt: Callable[..., str]
    confirm: Callable[..., bool]
    select: Callable[..., int]
    spinner_cls: Any
    pick_instance: Callable[..., Any]
    health: Callable[..., Any]
    v8_api: Callable[..., Dict[str, Any]]
    handler_chat: Callable[..., None]
    handler_doctor: Callable[..., None]
    handler_sync: Callable[..., None]
    handler_guide: Callable[..., None]
    handler_new: Callable[..., None]
    handler_init: Callable[..., None]
    handler_status: Callable[..., None]
    handler_health: Callable[..., None]
    handler_modelo: Callable[..., None]
    handler_trainer_skills: Callable[..., None]
    handler_trainer_control: Callable[..., None]
    handler_bb_config: Callable[..., None]


def bb_persona_defaults() -> Dict[str, Any]:
    return {
        "name": "Melissa",
        "role": "recepcionista IA",
        "archetype": "amigable",
        "tone": "natural",
        "tone_instruction": "",
        "formality_level": 0.35,
        "warmth_level": 0.80,
        "humor_level": 0.10,
        "verbosity": 0.35,
        "greetings": [],
        "closings": [],
        "affirmations": [],
        "forbidden_words": [],
        "custom_phrases": [],
    }


@lru_cache(maxsize=4)
def _bb_personality_catalog_for_path(melissa_dir: str) -> Dict[str, Dict[str, Any]]:
    melissa_path = Path(melissa_dir) / "melissa.py"
    fallback = {
        "amigable": {
            "desc": "Cercana y natural. La opción segura por defecto.",
            "formality": 0.35,
            "warmth": 0.80,
            "humor": 0.15,
            "verbosity": 0.35,
            "greetings": ["hola", "buenas"],
            "affirmations": ["claro", "listo"],
            "closings": ["cualquier cosa me escribes"],
            "forbidden": ["estimado", "cordialmente"],
            "tone_instruction": "",
        }
    }
    try:
        module = ast.parse(melissa_path.read_text(encoding="utf-8"))
        for node in module.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "PERSONALITY_ARCHETYPES":
                        data = ast.literal_eval(node.value)
                        if isinstance(data, dict) and data:
                            return data
    except Exception:
        pass
    return fallback


def bb_personality_catalog(ctx: BBContext) -> Dict[str, Dict[str, Any]]:
    return _bb_personality_catalog_for_path(ctx.melissa_dir)


def bb_read_persona_db(inst: Any) -> Dict[str, Any]:
    db_path = Path(inst.db_path)
    if not db_path.exists():
        return {}
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT persona_config FROM clinic WHERE id=1").fetchone()
        if not row:
            row = conn.execute("SELECT persona_config FROM clinic LIMIT 1").fetchone()
        conn.close()
    except Exception:
        return {}
    if not row or not row[0]:
        return {}
    raw = row[0]
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def bb_write_persona_db(ctx: BBContext, inst: Any, persona: Dict[str, Any]) -> bool:
    db_path = Path(inst.db_path)
    if not db_path.exists():
        ctx.fail(f"No encontré la base de datos de {inst.label}: {db_path}")
        return False
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT id FROM clinic WHERE id=1").fetchone()
        payload = json.dumps(persona, ensure_ascii=False)
        if row:
            conn.execute("UPDATE clinic SET persona_config=? WHERE id=1", (payload,))
        else:
            any_row = conn.execute("SELECT id FROM clinic LIMIT 1").fetchone()
            if any_row:
                conn.execute("UPDATE clinic SET persona_config=? WHERE id=?", (payload, any_row[0]))
            else:
                conn.execute("INSERT INTO clinic (id, persona_config) VALUES (1, ?)", (payload,))
        conn.commit()
        conn.close()
        return True
    except Exception as exc:
        ctx.fail(f"No pude guardar la personalidad en SQLite: {exc}")
        return False


def bb_load_persona(inst: Any) -> Dict[str, Any]:
    persona = bb_persona_defaults()
    persona.update(bb_read_persona_db(inst))
    return persona


def bb_apply_persona(
    ctx: BBContext,
    inst: Any,
    updates: Dict[str, Any],
    spinner_label: str = "Actualizando agente...",
) -> bool:
    current = bb_load_persona(inst)
    current.update({key: value for key, value in updates.items() if value is not None})

    if ctx.health(inst.port):
        with ctx.spinner_cls(spinner_label) as spinner:
            response = ctx.v8_api(inst, "/personality", method="PATCH", payload=updates, timeout=12)
            if response.get("ok"):
                spinner.finish("Agente actualizado")
                return True
            spinner.finish(f"API no respondió: {response.get('error', 'sin respuesta')}", ok=False)
        ctx.warn("La instancia no aceptó el cambio por API; guardando directamente en la base local.")

    if bb_write_persona_db(ctx, inst, current):
        ctx.ok("Agente actualizado en la base local")
        return True
    return False


def bb_prompt_block(ctx: BBContext, label: str, initial: str = "") -> str:
    editor = os.getenv("EDITOR") or (
        "notepad" if os.name == "nt" else ("nano" if shutil.which("nano") else "vi" if shutil.which("vi") else "")
    )
    if editor and shutil.which(editor):
        if ctx.confirm(f"¿Abrir {editor} para editar {label.lower()}?", default=True):
            fd, tmp_path = tempfile.mkstemp(prefix="melissa-bb-", suffix=".txt")
            os.close(fd)
            temp_file = Path(tmp_path)
            temp_file.write_text((initial or "").strip() + "\n", encoding="utf-8")
            subprocess.run([editor, str(temp_file)], check=False)
            try:
                value = temp_file.read_text(encoding="utf-8").strip()
            finally:
                temp_file.unlink(missing_ok=True)
            return value or initial
    return ctx.prompt(label, default=initial)


def bb_score_prompt(ctx: BBContext, label: str, current: Any, default: float) -> float:
    raw_default = current if current not in (None, "") else default
    raw = ctx.prompt(label, default=str(raw_default))
    try:
        value = float(raw)
    except Exception:
        ctx.warn("Valor inválido; mantengo el actual.")
        return float(raw_default)
    return max(0.0, min(1.0, value))


def bb_show_agent_summary(ctx: BBContext, inst: Any, persona: Optional[Dict[str, Any]] = None) -> None:
    persona = persona or bb_load_persona(inst)
    catalog = bb_personality_catalog(ctx)
    archetype = persona.get("archetype", "amigable")
    archetype_info = catalog.get(archetype, {})
    ctx.section(f"Black Boss Config — {inst.label}", "Agente, prompt y personalidad")
    ctx.kv("Agente", persona.get("name", "Melissa"))
    ctx.kv("Rol", persona.get("role", "recepcionista IA"))
    ctx.kv("Arquetipo", f"{archetype} · {archetype_info.get('desc', 'sin descripción')}")
    ctx.kv("Formalidad", f"{float(persona.get('formality_level', 0.35)):.2f}")
    ctx.kv("Calidez", f"{float(persona.get('warmth_level', 0.80)):.2f}")
    ctx.kv("Humor", f"{float(persona.get('humor_level', 0.10)):.2f}")
    ctx.kv("Detalle", f"{float(persona.get('verbosity', 0.35)):.2f}")
    tone_instruction = (persona.get("tone_instruction", "") or "").strip()
    if tone_instruction:
        ctx.info("Prompt maestro:")
        print(f"    {ctx.q(ctx.colors.G1, tone_instruction[:160] + ('…' if len(tone_instruction) > 160 else ''))}")
    else:
        ctx.info("Prompt maestro: usando el del arquetipo activo")
    ctx.nl()


def bb_pick_archetype(ctx: BBContext, current_id: str) -> Optional[str]:
    catalog = bb_personality_catalog(ctx)
    keys = list(catalog.keys())
    labels = [key.replace("_", " ").title() for key in keys]
    descs = [catalog[key].get("desc", "") for key in keys]
    idx = ctx.select(labels, descs=descs, title=f"Elige la personalidad base (actual: {current_id})")
    return keys[idx] if 0 <= idx < len(keys) else None


def bb_forward_inst(handler: Callable[..., None], inst: Any, *, name: str = "", subcommand: str = "") -> None:
    forwarded = argparse.Namespace(name=name, subcommand=subcommand or inst.name, command="")
    handler(forwarded)


def cmd_bb(ctx: BBContext, args: Any) -> None:
    action = (getattr(args, "subcommand", "") or "").strip().lower()
    target_name = getattr(args, "name", "")

    if not action:
        ctx.print_logo(compact=True)
        ctx.section("Black Boss", "Capa operativa rápida para Melissa")
        shortcuts = [
            ("melissa bb config [n]", "Crear y ajustar el agente de una instancia"),
            ("melissa bb chat [n]", "Entrar al chat operativo"),
            ("melissa bb doctor", "Diagnóstico completo"),
            ("melissa bb sync", "Clonar runtime exacto a todas las instancias"),
            ("melissa bb new", "Crear nueva instancia"),
            ("melissa bb guide", "Abrir guía operativa"),
        ]
        for cmd_text, desc in shortcuts:
            print(f"  {ctx.q(ctx.colors.CYN, cmd_text):<30} {ctx.q(ctx.colors.G1, desc)}")
        ctx.nl()
        ctx.info("Usa el patrón: melissa bb <acción> [instancia]")
        return

    bb_routes = {
        "config": ctx.handler_bb_config,
        "chat": ctx.handler_chat,
        "doctor": ctx.handler_doctor,
        "sync": ctx.handler_sync,
        "guide": ctx.handler_guide,
        "guia": ctx.handler_guide,
        "new": ctx.handler_new,
        "crear": ctx.handler_new,
        "init": ctx.handler_init,
        "start": ctx.handler_init,
        "status": ctx.handler_status,
        "health": ctx.handler_health,
    }
    handler = bb_routes.get(action)
    if not handler:
        ctx.fail(f"Acción BB desconocida: '{action}'")
        ctx.info("Prueba con: melissa bb config | chat | doctor | sync | new | guide")
        return

    forwarded = argparse.Namespace(**vars(args))
    forwarded.command = action
    forwarded.subcommand = ""
    forwarded.name = target_name
    handler(forwarded)


def cmd_bb_config(ctx: BBContext, args: Any) -> None:
    inst = ctx.pick_instance(args, "¿Cuál agente Melissa quieres ajustar?")
    if not inst:
        return

    while True:
        ctx.print_logo(compact=True, sector=inst.sector)
        persona = bb_load_persona(inst)
        bb_show_agent_summary(ctx, inst, persona)

        options = [
            "Crear / renombrar agente",
            "Elegir personalidad base",
            "Editar prompt maestro",
            "Ajustar tono fino",
            "Cambiar modelo LLM",
            "Activar / desactivar skills",
            "Control duro y frases prohibidas",
            "Enseñarle una instrucción nueva",
            "Ver resumen otra vez",
            "Salir",
        ]
        descs = [
            "Nombre visible, rol y perfil del agente.",
            "Aplica un arquetipo base listo para usar.",
            "Edita la instrucción central del agente.",
            "Formalidad, calidez, humor y nivel de detalle.",
            "Abre el catálogo de modelos para esta instancia.",
            "Gestiona skills del agente en caliente.",
            "Ajusta frases prohibidas, saludo y estilo duro.",
            "Le enseña un patrón nuevo sin tocar código.",
            "Recarga la configuración actual.",
            "Volver a la terminal.",
        ]
        choice = ctx.select(options, descs=descs, title="¿Qué quieres cambiar en este agente?")

        if choice == 0:
            new_name = ctx.prompt("Nombre visible del agente", default=persona.get("name", "Melissa"))
            new_role = ctx.prompt("Rol del agente", default=persona.get("role", "recepcionista IA"))
            bb_apply_persona(
                ctx,
                inst,
                {"name": new_name, "role": new_role},
                spinner_label="Actualizando identidad del agente...",
            )
        elif choice == 1:
            archetype_id = bb_pick_archetype(ctx, persona.get("archetype", "amigable"))
            if not archetype_id:
                continue
            data = bb_personality_catalog(ctx).get(archetype_id, {})
            bb_apply_persona(
                ctx,
                inst,
                {
                    "archetype": archetype_id,
                    "tone": data.get("desc", persona.get("tone", "natural")),
                    "tone_instruction": data.get("tone_instruction", ""),
                    "formality_level": data.get("formality", persona.get("formality_level", 0.35)),
                    "warmth_level": data.get("warmth", persona.get("warmth_level", 0.80)),
                    "humor_level": data.get("humor", persona.get("humor_level", 0.10)),
                    "verbosity": data.get("verbosity", persona.get("verbosity", 0.35)),
                    "greetings": data.get("greetings", []),
                    "affirmations": data.get("affirmations", []),
                    "closings": data.get("closings", []),
                    "forbidden_words": data.get("forbidden", []),
                },
                spinner_label="Aplicando personalidad base...",
            )
        elif choice == 2:
            new_prompt = bb_prompt_block(ctx, "Prompt maestro", initial=persona.get("tone_instruction", ""))
            if new_prompt.strip():
                bb_apply_persona(
                    ctx,
                    inst,
                    {"tone_instruction": new_prompt.strip()},
                    spinner_label="Guardando prompt maestro...",
                )
        elif choice == 3:
            tone = ctx.prompt("Descripción corta del tono", default=persona.get("tone", "natural"))
            formality = bb_score_prompt(ctx, "Formalidad (0.0 a 1.0)", persona.get("formality_level"), 0.35)
            warmth = bb_score_prompt(ctx, "Calidez (0.0 a 1.0)", persona.get("warmth_level"), 0.80)
            humor = bb_score_prompt(ctx, "Humor (0.0 a 1.0)", persona.get("humor_level"), 0.10)
            verbosity = bb_score_prompt(ctx, "Nivel de detalle (0.0 a 1.0)", persona.get("verbosity"), 0.35)
            bb_apply_persona(
                ctx,
                inst,
                {
                    "tone": tone,
                    "formality_level": formality,
                    "warmth_level": warmth,
                    "humor_level": humor,
                    "verbosity": verbosity,
                },
                spinner_label="Ajustando tono del agente...",
            )
        elif choice == 4:
            bb_forward_inst(ctx.handler_modelo, inst, name=inst.name, subcommand=inst.name)
        elif choice == 5:
            bb_forward_inst(ctx.handler_trainer_skills, inst, name="", subcommand=inst.name)
        elif choice == 6:
            bb_forward_inst(ctx.handler_trainer_control, inst, name=inst.name, subcommand=inst.name)
        elif choice == 7:
            instruction = ctx.prompt("¿Qué quieres que aprenda este agente?", default="")
            if instruction.strip():
                with ctx.spinner_cls("Enseñando al agente...") as spinner:
                    response = ctx.v8_api(
                        inst,
                        "/trainer/prompt/evolve",
                        method="POST",
                        payload={"instruction": instruction.strip(), "admin_chat_id": "cli"},
                        timeout=20,
                    )
                    spinner.finish("Aprendido" if response.get("ok") else "Error", ok=bool(response.get("ok")))
                if response.get("ok"):
                    ctx.ok(response.get("description", "Instrucción procesada"))
                else:
                    ctx.fail(f"Error: {response.get('error', 'sin respuesta')}")
        elif choice == 8:
            continue
        else:
            break
        ctx.nl()


__all__ = [
    "BBContext",
    "bb_apply_persona",
    "bb_load_persona",
    "bb_persona_defaults",
    "bb_personality_catalog",
    "bb_prompt_block",
    "bb_read_persona_db",
    "bb_score_prompt",
    "bb_show_agent_summary",
    "bb_write_persona_db",
    "cmd_bb",
    "cmd_bb_config",
]
