#!/usr/bin/env python3
"""melissa_demo_v2.py — Ultra-realistic demo with Colombian personas and memory."""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import httpx

API_URL = "http://localhost:8001/test"
MASTER_KEY = os.getenv("MASTER_API_KEY", "melissa_master_2026_santiago")

DEMO_PERSONAS = {
    "dona_carmen": {
        "profile": "Mujer 65 años, Medellín, no tecnológica, formal",
        "typing_wpm": 20,
        "typos": True,
        "messages": [
            "buenas tardes quiero saber si hay cita para el medico",
            "es que me duele el pecho hace dias",
            "cuanto vale la consulta",
            "y el doctor atiende mañana",
            "no pues gracias mija que Dios la bendiga",
        ],
    },
    "juan_ejecutivo": {
        "profile": "Hombre 35 años, ocupado, directo, WhatsApp",
        "typing_wpm": 60,
        "typos": False,
        "messages": [
            "Hola! Cita cardio para mañana si hay?",
            "Cuánto tarda la espera normalmente",
            "Ok perfecto, quedamos así entonces 👍",
        ],
    },
    "mama_preocupada": {
        "profile": "Mamá 40 años, hijo enfermo, ansiosa",
        "typing_wpm": 45,
        "typos": False,
        "messages": [
            "Hola urgente mi hijo de 8 años tiene fiebre alta",
            "Me pueden atender hoy??",
            "Tiene 39.5 grados y lleva 2 días así",
            "A qué hora hay pediatra",
        ],
    },
    "joven_curioso": {
        "profile": "Hombre 22 años, primera vez, informal",
        "typing_wpm": 70,
        "typos": True,
        "messages": [
            "ey hola q tal",
            "quiero saber si hacen limpieza facial",
            "y eso duele? jaja",
            "bueno listo agendame pa cuando haya",
            "vale gracias bro",
        ],
    },
    "abuela_tecnologica": {
        "profile": "Mujer 72 años, nietos le enseñaron WhatsApp, muy educada",
        "typing_wpm": 15,
        "typos": True,
        "messages": [
            "Buenos dias señorita",
            "Disculpe la molestia quisiera saber si puedo sacar una cita",
            "Es para un control de tension arterial",
            "Mi nombre es Rosa Elena Martinez",
            "Muchas gracias señorita muy amable Dios la bendiga",
        ],
    },
}

TYPO_MAP = {
    "que": "q", "para": "pa", "por favor": "porfa", "está": "esta",
    "también": "tambien", "después": "despues", "cuánto": "cuanto",
}


def inject_typos(text: str, rate: float = 0.05) -> str:
    """Inject realistic typos based on rate."""
    words = text.split()
    result = []
    for w in words:
        if random.random() < rate and len(w) > 3:
            # Swap two adjacent chars
            i = random.randint(0, len(w) - 2)
            w = w[:i] + w[i + 1] + w[i] + w[i + 2:]
        result.append(w)
    return " ".join(result)


def simulate_typing_delay(text: str, wpm: int = 35) -> float:
    """Calculate realistic typing delay."""
    chars_per_second = (wpm * 5) / 60
    delay = len(text) / chars_per_second
    return min(delay, 6.0)


def color(text, code):
    return f"\033[{code}m{text}\033[0m"


async def send_to_melissa(message: str, chat_id: str) -> Dict:
    """Send message to Melissa API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            API_URL,
            json={"message": message, "chat_id": chat_id},
            headers={"X-Master-Key": MASTER_KEY, "Content-Type": "application/json"},
        )
        return r.json()


async def run_demo(persona_key: str = "dona_carmen", instance_id: str = "default"):
    """Run a full multi-turn demo with a persona."""
    persona = DEMO_PERSONAS.get(persona_key)
    if not persona:
        print(f"Persona '{persona_key}' not found. Available: {list(DEMO_PERSONAS.keys())}")
        return

    chat_id = f"demo_{persona_key}_{int(time.time())}"

    print()
    print(color("╔══════════════════════════════════════════════╗", "1;36"))
    print(color("║  MELISSA DEMO v2.0 — Simulación Realista     ║", "1;36"))
    print(color("╚══════════════════════════════════════════════╝", "1;36"))
    print(f"  Persona: {color(persona_key, '1')} — {persona['profile']}")
    print(f"  Instance: {instance_id}")
    print(f"  Velocidad: {persona['typing_wpm']} WPM | Typos: {'sí' if persona['typos'] else 'no'}")
    print("─" * 50)
    print()

    for i, msg in enumerate(persona["messages"]):
        # Simulate typing delay
        delay = simulate_typing_delay(msg, persona["typing_wpm"])
        if i > 0:
            # Thinking time before next message
            await asyncio.sleep(random.uniform(1.5, 4.0))

        # Apply typos if persona has them
        display_msg = msg
        if persona["typos"] and random.random() < 0.3:
            display_msg = inject_typos(msg, rate=0.08)

        # Show user typing indicator
        print(f"  {color('...typing...', '90')}", end="\r")
        await asyncio.sleep(min(delay, 3.0))
        print(f"  {color(f'[{persona_key.upper()}]', '1;33')} {display_msg}")

        # Get Melissa's response
        try:
            result = await send_to_melissa(display_msg, chat_id)
            bubbles = result.get("bubbles", [result.get("response", "error")])
            # Simulate Melissa "thinking"
            await asyncio.sleep(random.uniform(1.0, 2.5))
            for bubble in bubbles:
                print(f"  {color('[MELISSA]', '1;35')} {bubble}")
                if len(bubbles) > 1:
                    await asyncio.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            print(f"  {color('[ERROR]', '31')} {e}")

        print()

    print("─" * 50)
    print(color("  Demo completada.", "90"))
    print(f"  {len(persona['messages'])} turnos | Chat ID: {chat_id}")
    print()


async def run_all_demos(instance_id: str = "default"):
    """Run all demo personas sequentially."""
    for persona_key in DEMO_PERSONAS:
        await run_demo(persona_key, instance_id)
        print("\n" + "═" * 50 + "\n")
        await asyncio.sleep(2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Melissa Demo v2 — Realistic Colombian personas")
    parser.add_argument("--persona", "-p", default="dona_carmen",
                        choices=list(DEMO_PERSONAS.keys()) + ["all"],
                        help="Which persona to simulate")
    parser.add_argument("--instance", "-i", default="default", help="Instance ID")
    parser.add_argument("--list", "-l", action="store_true", help="List available personas")
    args = parser.parse_args()

    if args.list:
        print("Available demo personas:")
        for key, p in DEMO_PERSONAS.items():
            print(f"  {key:20s} — {p['profile']}")
        return

    if args.persona == "all":
        asyncio.run(run_all_demos(args.instance))
    else:
        asyncio.run(run_demo(args.persona, args.instance))


if __name__ == "__main__":
    main()
