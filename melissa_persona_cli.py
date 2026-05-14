#!/usr/bin/env python3
"""melissa_persona_cli.py — Agency persona control CLI."""
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

import httpx

PERSONAS_DIR = Path("/home/ubuntu/melissa/personas")
INSTANCES_DIR = Path("/home/ubuntu/melissa-instances")
API_BASE = "http://localhost:8001"


def get_persona_path(instance_id: str) -> Path:
    candidates = [
        INSTANCES_DIR / instance_id / "personas" / "persona.yaml",
        PERSONAS_DIR / instance_id / "persona.yaml",
        PERSONAS_DIR / instance_id / "runtime_override.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return PERSONAS_DIR / instance_id / "persona.yaml"


def _get_key():
    return os.getenv("ADMIN_API_KEY", os.getenv("MASTER_API_KEY", "melissa_master_2026_santiago"))


def cmd_list(args):
    print("Available instances:")
    if INSTANCES_DIR.exists():
        for d in sorted(INSTANCES_DIR.iterdir()):
            if d.is_dir() and (d / ".env").exists():
                print(f"  {d.name} (instance)")
    if PERSONAS_DIR.exists():
        for d in sorted(PERSONAS_DIR.iterdir()):
            if d.is_dir():
                print(f"  {d.name} (persona)")


def cmd_show(args):
    path = get_persona_path(args.instance)
    if not path.exists():
        print(f"No persona found for '{args.instance}'")
        return
    print(f"Persona: {args.instance} ({path})")
    print("─" * 50)
    print(path.read_text())


def cmd_set(args):
    payload = {args.field: args.value}
    if args.field == "forbidden_topics":
        payload[args.field] = [t.strip() for t in args.value.split(",")]
    try:
        r = httpx.post(f"{API_BASE}/admin/{args.instance}/persona",
                       json=payload, headers={"X-Admin-Key": _get_key()}, timeout=10)
        if r.status_code == 200:
            print(f"✓ Set {args.field}={args.value} for {args.instance}")
        else:
            print(f"✗ Error: {r.status_code} — {r.text}")
    except Exception as e:
        print(f"✗ Connection error: {e}")


def cmd_test(args):
    key = os.getenv("MASTER_API_KEY", "melissa_master_2026_santiago")
    test_messages = [
        "Hola, quiero una cita",
        "Cuánto cuesta la consulta?",
        "Tienen disponibilidad mañana?",
        "Gracias, me agendas a las 3pm",
        "Chao, bendiciones",
    ]
    print(f"Testing persona for: {args.instance}")
    print("─" * 50)
    for msg in test_messages:
        try:
            r = httpx.post(f"{API_BASE}/test",
                           json={"message": msg, "chat_id": f"persona_test_{args.instance}"},
                           headers={"X-Master-Key": key}, timeout=30)
            data = r.json()
            print(f"  [USER] {msg}")
            print(f"  [MELISSA] {data.get('response', 'error')[:120]}")
            print()
        except Exception as e:
            print(f"  [ERROR] {e}")


def cmd_status(args):
    try:
        r = httpx.get(f"{API_BASE}/admin/{args.instance}/status",
                      headers={"X-Admin-Key": _get_key()}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            print(f"Instance: {data.get('instance_id')}")
            print(f"Persona: {json.dumps(data.get('persona', {}), indent=2, ensure_ascii=False)}")
            print(f"Gaps today: {data.get('gaps_today', 0)}")
        else:
            print(f"Error: {r.status_code}")
    except Exception as e:
        print(f"Connection error: {e}")


def cmd_export(args):
    path = get_persona_path(args.instance)
    if path.exists():
        print(path.read_text())
    else:
        print(f"No persona found for {args.instance}", file=sys.stderr)
        sys.exit(1)


def cmd_history(args):
    path = get_persona_path(args.instance)
    if path.exists():
        print(f"Persona file: {path}")
        print(f"Last modified: {datetime.fromtimestamp(path.stat().st_mtime).isoformat()}")
    else:
        print(f"No persona file found for {args.instance}")


def main():
    parser = argparse.ArgumentParser(prog="melissa persona", description="Agency persona control")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List available instances")
    p = sub.add_parser("show", help="Show persona config"); p.add_argument("instance")
    p = sub.add_parser("set", help="Set a field"); p.add_argument("instance"); p.add_argument("field"); p.add_argument("value")
    p = sub.add_parser("test", help="Dry-run test"); p.add_argument("instance")
    p = sub.add_parser("status", help="Runtime status"); p.add_argument("instance")
    p = sub.add_parser("export", help="Export persona"); p.add_argument("instance")
    p = sub.add_parser("history", help="Change history"); p.add_argument("instance")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    cmds = {"list": cmd_list, "show": cmd_show, "set": cmd_set, "test": cmd_test,
            "status": cmd_status, "export": cmd_export, "history": cmd_history}
    cmds[args.command](args)


if __name__ == "__main__":
    main()
