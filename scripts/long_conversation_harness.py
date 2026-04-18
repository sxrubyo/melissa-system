#!/usr/bin/env python3
"""Harness HTTP agnóstico para conversaciones largas con Melissa.

Envía escenarios secuenciales contra un endpoint HTTP arbitrario, acepta
respuestas en texto plano o JSON y genera un reporte con latencia, repetición
normalizada, sospecha de bot, número de burbujas y un resumen legible.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys
import time
import unicodedata
from dataclasses import dataclass, field, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

try:
    import yaml
except Exception as exc:  # pragma: no cover - PyYAML is available in this workspace.
    yaml = None
    YAML_IMPORT_ERROR = exc
else:
    YAML_IMPORT_ERROR = None


RESPONSE_KEYS = (
    "response",
    "reply",
    "text",
    "message",
    "content",
    "output",
)

BOT_PHRASES = (
    "como ia",
    "como un bot",
    "estoy aqui para ayudarte",
    "estoy aquí para ayudarte",
    "con gusto",
    "encantada de ayudarte",
    "encantado de ayudarte",
    "si tienes mas preguntas",
    "si tienes más preguntas",
    "¿hay algo mas",
    "hay algo mas",
    "hay algo más",
    "te ayudo con",
    "a tu disposicion",
    "a tu disposición",
    "nuestro equipo",
    "atencion al cliente",
    "atención al cliente",
)

GENERIC_OPENERS = (
    "hola",
    "buenas",
    "claro",
    "perfecto",
    "entiendo",
    "por supuesto",
    "con gusto",
)


@dataclass
class ScenarioTurn:
    index: int
    user: str


@dataclass
class Scenario:
    id: str
    title: str
    description: str
    turns: List[ScenarioTurn] = field(default_factory=list)


@dataclass
class TurnResult:
    scenario_id: str
    scenario_title: str
    turn_index: int
    user_text: str
    response_text: str
    response_bubbles: List[str]
    latency_ms: float
    normalized_repetition: float
    bot_suspicion: float
    suspicious_bot: bool
    bubble_count: int
    status: str
    error: str = ""
    normalized_response: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Harness HTTP agnóstico para conversaciones largas con Melissa"
    )
    parser.add_argument("--endpoint", required=True, help="URL HTTP del endpoint a probar")
    parser.add_argument(
        "--scenario-file",
        required=True,
        help="Ruta al YAML con los escenarios de conversación",
    )
    parser.add_argument(
        "--chat-prefix",
        required=True,
        help="Prefijo para el chat_id/identificador de conversación",
    )
    parser.add_argument(
        "--output-json",
        nargs="?",
        const="long_conversation_report.json",
        default="",
        help="Ruta del JSON de salida. Si se pasa sin valor usa long_conversation_report.json",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="Límite opcional de turnos totales a ejecutar",
    )
    parser.add_argument(
        "--master-key",
        default=os.getenv("MELISSA_MASTER_KEY", ""),
        help="Master key opcional para endpoints protegidos",
    )
    return parser.parse_args()


def load_scenarios(path: Path) -> List[Scenario]:
    if yaml is None:
        raise RuntimeError(f"PyYAML no disponible: {YAML_IMPORT_ERROR}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(raw, list):
        raw = {"scenarios": raw}

    scenarios_raw = raw.get("scenarios", [])
    if not isinstance(scenarios_raw, list):
        raise ValueError("El YAML debe contener una lista bajo la clave 'scenarios'")

    scenarios: List[Scenario] = []
    for scenario_idx, item in enumerate(scenarios_raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Escenario #{scenario_idx} inválido: se esperaba un objeto")
        scenario_id = str(item.get("id") or item.get("key") or f"scenario_{scenario_idx}").strip()
        title = str(item.get("title") or item.get("name") or scenario_id).strip()
        description = str(item.get("description") or "").strip()
        turns_raw = item.get("turns", [])
        if not isinstance(turns_raw, list):
            raise ValueError(f"Escenario '{scenario_id}' debe definir una lista en 'turns'")

        turns: List[ScenarioTurn] = []
        for turn_idx, turn_item in enumerate(turns_raw, start=1):
            if isinstance(turn_item, str):
                user_text = turn_item.strip()
            elif isinstance(turn_item, dict):
                user_text = str(
                    turn_item.get("user")
                    or turn_item.get("text")
                    or turn_item.get("message")
                    or ""
                ).strip()
            else:
                user_text = str(turn_item).strip()

            if not user_text:
                continue
            turns.append(ScenarioTurn(index=turn_idx, user=user_text))

        if not turns:
            raise ValueError(f"Escenario '{scenario_id}' no contiene turnos válidos")

        scenarios.append(Scenario(id=scenario_id, title=title, description=description, turns=turns))

    if not scenarios:
        raise ValueError("No se encontraron escenarios en el archivo YAML")
    return scenarios


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = text.replace("|||", " ")
    text = re.sub(r"[^a-z0-9áéíóúñü\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> List[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    tokens = normalized.split()
    return [tok for tok in tokens if len(tok) > 1]


def bubbleize(text: str) -> List[str]:
    if not text:
        return []
    if isinstance(text, str) and "|||" in text:
        parts = [part.strip() for part in text.split("|||")]
        return [part for part in parts if part]
    return [text.strip()] if text.strip() else []


def extract_text_from_json(value: Any) -> Tuple[str, List[str]]:
    if value is None:
        return "", []

    if isinstance(value, str):
        return value, bubbleize(value)

    if isinstance(value, list):
        bubbles: List[str] = []
        for item in value:
            if isinstance(item, str):
                bubbles.extend(bubbleize(item))
            elif isinstance(item, dict):
                text, nested_bubbles = extract_text_from_json(item)
                if text:
                    bubbles.extend(bubbleize(text))
                bubbles.extend(nested_bubbles)
        joined = " ||| ".join(bubbles)
        return joined, bubbles

    if isinstance(value, dict):
        if isinstance(value.get("bubbles"), list):
            bubbles = []
            for bubble in value["bubbles"]:
                if isinstance(bubble, str):
                    bubbles.append(bubble.strip())
                elif isinstance(bubble, dict):
                    nested_text, nested_bubbles = extract_text_from_json(bubble)
                    if nested_text:
                        bubbles.extend(bubbleize(nested_text))
                    bubbles.extend(nested_bubbles)
            bubbles = [bubble for bubble in bubbles if bubble]
            if bubbles:
                return " ||| ".join(bubbles), bubbles

        for key in RESPONSE_KEYS:
            if key in value:
                text, bubbles = extract_text_from_json(value.get(key))
                if text or bubbles:
                    return text, bubbles

        for nested_key in ("data", "result", "payload", "message"):
            nested = value.get(nested_key)
            if isinstance(nested, (dict, list, str)):
                text, bubbles = extract_text_from_json(nested)
                if text or bubbles:
                    return text, bubbles

        choices = value.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message")
                if isinstance(msg, dict):
                    text = str(msg.get("content") or "").strip()
                    return text, bubbleize(text)
                text = str(first.get("text") or "").strip()
                return text, bubbleize(text)

    return str(value).strip(), bubbleize(str(value).strip())


def normalize_and_split_response(response: httpx.Response) -> Tuple[str, List[str]]:
    content_type = (response.headers.get("content-type") or "").lower()
    body = response.text or ""

    if "json" in content_type:
        try:
            parsed = response.json()
        except Exception:
            parsed = None
        if parsed is not None:
            text, bubbles = extract_text_from_json(parsed)
            if text or bubbles:
                return text, bubbles

    stripped = body.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except Exception:
            parsed = None
        if parsed is not None:
            text, bubbles = extract_text_from_json(parsed)
            if text or bubbles:
                return text, bubbles

    return body.strip(), bubbleize(body)


def similarity_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    tokens_a = set(tokenize(a))
    tokens_b = set(tokenize(b))
    if tokens_a and tokens_b:
        jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    else:
        jaccard = 0.0

    seq = SequenceMatcher(None, a, b).ratio()
    return max(jaccard, seq)


def repetition_score(normalized_response: str, previous_responses: Iterable[str]) -> float:
    scores = [similarity_score(normalized_response, prev) for prev in previous_responses if prev]
    return max(scores) if scores else 0.0


def bot_suspicion_score(
    response_text: str,
    normalized_response: str,
    normalized_repetition: float,
    bubble_count: int,
    turn_index: int,
) -> float:
    score = 0.0
    lowered = normalize_text(response_text)

    if normalized_repetition >= 0.9:
        score += 0.35
    elif normalized_repetition >= 0.75:
        score += 0.2

    if any(phrase in lowered for phrase in BOT_PHRASES):
        score += 0.25

    if turn_index > 1 and any(lowered.startswith(opener) for opener in GENERIC_OPENERS):
        score += 0.10

    if bubble_count >= 4:
        score += 0.15
    elif bubble_count == 3:
        score += 0.08

    word_count = len(tokenize(response_text))
    if word_count > 70:
        score += 0.15
    elif word_count > 45:
        score += 0.08

    if "\n" in response_text and response_text.count("\n") >= 2:
        score += 0.10

    if re.search(r"(^|\n)\s*[-*•]\s+", response_text):
        score += 0.10

    if normalized_response and normalized_response.endswith("hola"):
        score += 0.05

    return min(score, 1.0)


def build_payload(
    scenario: Scenario,
    turn: ScenarioTurn,
    chat_id: str,
    history: List[Dict[str, Any]],
    scenario_turn_count: int,
    global_turn_number: int,
) -> Dict[str, Any]:
    return {
        "chat_id": chat_id,
        "user_id": chat_id,
        "session_id": chat_id,
        "chat_prefix": chat_id.rsplit("-", 1)[0] if "-" in chat_id else chat_id,
        "scenario_id": scenario.id,
        "scenario_title": scenario.title,
        "scenario_description": scenario.description,
        "turn_index": turn.index,
        "scenario_turn_count": scenario_turn_count,
        "global_turn_number": global_turn_number,
        "message": turn.user,
        "text": turn.user,
        "user_text": turn.user,
        "prompt": turn.user,
        "history": history,
        "messages": history,
        "conversation": history,
    }


def send_turn(
    client: httpx.Client,
    endpoint: str,
    payload: Dict[str, Any],
    timeout: float,
    master_key: str = "",
) -> Tuple[str, List[str], int]:
    started = time.perf_counter()
    headers: Dict[str, str] = {}
    outbound = dict(payload)
    if master_key:
        headers["X-Master-Key"] = master_key
        outbound.setdefault("master_key", master_key)
    response = client.post(endpoint, json=outbound, headers=headers, timeout=timeout)
    latency_ms = int(round((time.perf_counter() - started) * 1000))
    response.raise_for_status()
    text, bubbles = normalize_and_split_response(response)
    return text, bubbles, latency_ms


def format_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def compute_p95(values: List[float]) -> float:
    if not values:
        return 0.0
    if len(values) < 20:
        return max(values)
    return statistics.quantiles(values, n=20, method="inclusive")[18]


def run_harness(
    endpoint: str,
    scenario_file: Path,
    chat_prefix: str,
    max_turns: Optional[int],
    master_key: str = "",
) -> Dict[str, Any]:
    scenarios = load_scenarios(scenario_file)
    run_started = time.time()
    run_started_perf = time.perf_counter()
    total_turns_budget = max_turns if max_turns is not None and max_turns >= 0 else None
    executed_turns = 0
    results: List[TurnResult] = []
    scenario_summaries: List[Dict[str, Any]] = []

    timeout = 45.0
    headers = {"Accept": "application/json, text/plain, */*"}
    endpoint = endpoint if re.match(r"^https?://", endpoint, re.IGNORECASE) else f"http://{endpoint}"

    with httpx.Client(headers=headers, follow_redirects=True) as client:
        for scenario_index, scenario in enumerate(scenarios, start=1):
            if total_turns_budget is not None and executed_turns >= total_turns_budget:
                break

            chat_id = f"{chat_prefix}-{scenario.id}"
            history: List[Dict[str, Any]] = []
            previous_assistant_texts: List[str] = []
            scenario_results: List[TurnResult] = []
            scenario_limit = len(scenario.turns)
            if total_turns_budget is not None:
                scenario_limit = min(scenario_limit, total_turns_budget - executed_turns)

            print()
            print(f"[{scenario_index:02d}] {scenario.title} ({scenario.id})")
            if scenario.description:
                print(f"    {scenario.description}")

            for turn in scenario.turns[:scenario_limit]:
                global_turn_number = executed_turns + 1
                payload = build_payload(
                    scenario=scenario,
                    turn=turn,
                    chat_id=chat_id,
                    history=history,
                    scenario_turn_count=len(scenario.turns),
                    global_turn_number=global_turn_number,
                )

                turn_started = time.perf_counter()
                try:
                    response_text, bubbles, latency_ms = send_turn(
                        client=client,
                        endpoint=endpoint,
                        payload=payload,
                        timeout=timeout,
                        master_key=master_key,
                    )
                    normalized_response = normalize_text(response_text)
                    normalized_repetition = repetition_score(normalized_response, previous_assistant_texts)
                    bubble_count = len(bubbles) if bubbles else (1 if response_text else 0)
                    bot_score = bot_suspicion_score(
                        response_text=response_text,
                        normalized_response=normalized_response,
                        normalized_repetition=normalized_repetition,
                        bubble_count=bubble_count,
                        turn_index=turn.index,
                    )
                    suspicious = bot_score >= 0.45
                    status = "ok"
                    error = ""
                except Exception as exc:
                    latency_ms = int(round((time.perf_counter() - turn_started) * 1000))
                    response_text = ""
                    bubbles = []
                    normalized_response = ""
                    normalized_repetition = 0.0
                    bot_score = 0.0
                    suspicious = False
                    status = "error"
                    error = f"{type(exc).__name__}: {exc}"

                result = TurnResult(
                    scenario_id=scenario.id,
                    scenario_title=scenario.title,
                    turn_index=turn.index,
                    user_text=turn.user,
                    response_text=response_text,
                    response_bubbles=bubbles,
                    latency_ms=float(latency_ms),
                    normalized_repetition=normalized_repetition,
                    bot_suspicion=bot_score,
                    suspicious_bot=suspicious,
                    bubble_count=len(bubbles) if bubbles else (1 if response_text else 0),
                    status=status,
                    error=error,
                    normalized_response=normalized_response,
                )
                results.append(result)
                scenario_results.append(result)
                executed_turns += 1

                history.append({"role": "user", "content": turn.user})
                if response_text:
                    history.append({"role": "assistant", "content": response_text})
                    previous_assistant_texts.append(normalized_response)

                if status == "ok":
                    print(
                        f"  turn {turn.index:02d} | {result.latency_ms:6.1f} ms | "
                        f"bubbles {result.bubble_count:2d} | rep {format_pct(result.normalized_repetition)} | "
                        f"bot {format_pct(result.bot_suspicion)}"
                    )
                else:
                    print(
                        f"  turn {turn.index:02d} | ERROR | {result.error}"
                    )

                if response_text:
                    preview = response_text if len(response_text) <= 220 else response_text[:217] + "..."
                    print(f"    ↳ {preview}")
                else:
                    print("    ↳ (sin respuesta)")

                if total_turns_budget is not None and executed_turns >= total_turns_budget:
                    break

            if scenario_results:
                scenario_summaries.append(
                    {
                        "scenario_id": scenario.id,
                        "title": scenario.title,
                        "description": scenario.description,
                        "turns_requested": len(scenario.turns),
                        "turns_executed": len(scenario_results),
                        "avg_latency_ms": round(statistics.mean(r.latency_ms for r in scenario_results), 2),
                        "avg_bubbles": round(statistics.mean(r.bubble_count for r in scenario_results), 2),
                        "avg_repetition": round(statistics.mean(r.normalized_repetition for r in scenario_results), 4),
                        "avg_bot_suspicion": round(statistics.mean(r.bot_suspicion for r in scenario_results), 4),
                        "max_bot_suspicion": round(max(r.bot_suspicion for r in scenario_results), 4),
                        "suspicious_turns": sum(1 for r in scenario_results if r.suspicious_bot),
                    }
                )

    latency_values = [r.latency_ms for r in results if r.status == "ok"]
    repetition_values = [r.normalized_repetition for r in results if r.status == "ok"]
    bot_values = [r.bot_suspicion for r in results if r.status == "ok"]
    bubble_values = [r.bubble_count for r in results if r.status == "ok"]

    summary = {
        "endpoint": endpoint,
        "chat_prefix": chat_prefix,
        "scenario_file": str(scenario_file),
        "started_at": run_started,
        "duration_s": round(time.perf_counter() - run_started_perf, 3),
        "scenarios_total": len(scenarios),
        "scenarios_executed": len(scenario_summaries),
        "turns_total_available": sum(len(s.turns) for s in scenarios),
        "turns_executed": len(results),
        "turns_failed": sum(1 for r in results if r.status != "ok"),
        "avg_latency_ms": round(statistics.mean(latency_values), 2) if latency_values else 0.0,
        "p95_latency_ms": round(compute_p95(latency_values), 2),
        "avg_normalized_repetition": round(statistics.mean(repetition_values), 4) if repetition_values else 0.0,
        "max_normalized_repetition": round(max(repetition_values), 4) if repetition_values else 0.0,
        "avg_bot_suspicion": round(statistics.mean(bot_values), 4) if bot_values else 0.0,
        "max_bot_suspicion": round(max(bot_values), 4) if bot_values else 0.0,
        "suspicious_turns": sum(1 for r in results if r.suspicious_bot),
        "avg_bubbles": round(statistics.mean(bubble_values), 2) if bubble_values else 0.0,
        "bubble_total": sum(bubble_values),
    }

    return {
        "summary": summary,
        "scenarios": scenario_summaries,
        "turns": [asdict(result) for result in results],
    }


def print_human_report(report: Dict[str, Any]) -> None:
    summary = report["summary"]
    scenarios = report["scenarios"]
    turns = report["turns"]

    print()
    print("=" * 72)
    print("Resumen global")
    print("=" * 72)
    print(f"Endpoint:               {summary['endpoint']}")
    print(f"Escenarios ejecutados:   {summary['scenarios_executed']}/{summary['scenarios_total']}")
    print(f"Turnos ejecutados:       {summary['turns_executed']} de {summary['turns_total_available']}")
    print(f"Fallos de request:       {summary['turns_failed']}")
    print(f"Latencia promedio:       {summary['avg_latency_ms']:.2f} ms")
    print(f"Latencia p95:            {summary['p95_latency_ms']:.2f} ms")
    print(f"Repetición normalizada:   {summary['avg_normalized_repetition']:.4f} promedio")
    print(f"Sospecha de bot:         {summary['avg_bot_suspicion']:.4f} promedio")
    print(f"Burbujas promedio:       {summary['avg_bubbles']:.2f}")
    print(f"Burbujas totales:        {summary['bubble_total']}")
    print(f"Turnos sospechosos:      {summary['suspicious_turns']}")

    print()
    print("Resumen por escenario")
    print("-" * 72)
    for scenario in scenarios:
        print(
            f"{scenario['scenario_id']:<22} "
            f"{scenario['turns_executed']:>2}/{scenario['turns_requested']:<2} turnos  "
            f"{scenario['avg_latency_ms']:>7.2f} ms  "
            f"rep {scenario['avg_repetition']:.4f}  "
            f"bot {scenario['avg_bot_suspicion']:.4f}  "
            f"burbujas {scenario['avg_bubbles']:.2f}"
        )

    print()
    print("Alertas")
    print("-" * 72)
    suspicious = [turn for turn in turns if turn["suspicious_bot"]]
    if suspicious:
        for turn in suspicious[:12]:
            preview = turn["response_text"][:120].replace("\n", " ")
            print(
                f"{turn['scenario_id']} turn {turn['turn_index']:02d} | "
                f"bot {turn['bot_suspicion']:.3f} | rep {turn['normalized_repetition']:.3f} | {preview}"
            )
        if len(suspicious) > 12:
            print(f"... {len(suspicious) - 12} alertas adicionales")
    else:
        print("Sin turnos marcados como sospechosos.")


def main() -> int:
    args = parse_args()
    scenario_file = Path(args.scenario_file).expanduser().resolve()
    if not scenario_file.exists():
        print(f"Archivo de escenarios no encontrado: {scenario_file}", file=sys.stderr)
        return 2

    try:
        report = run_harness(
            endpoint=args.endpoint,
            scenario_file=scenario_file,
            chat_prefix=args.chat_prefix,
            max_turns=args.max_turns,
            master_key=args.master_key,
        )
    except Exception as exc:
        print(f"Error ejecutando harness: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print_human_report(report)

    if args.output_json:
        output_path = Path(args.output_json).expanduser().resolve()
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print()
        print(f"JSON guardado en: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
