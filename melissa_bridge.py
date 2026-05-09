#!/usr/bin/env python3
"""
Bridge de terminal para Melissa con memoria local en SQLite.

Funciones principales:
- Conversacion interactiva y no interactiva contra /test
- Persistencia de turnos en la tabla bridge_sessions de melissa.db
- Comandos /history, /clear, /export
- Modo --test-mode con 10 turnos y validaciones de contexto
- Evidencia en logs/bridge_YYYYMMDD_HHMMSS.txt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

import httpx


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT_DIR / "melissa.db"
DEFAULT_ENV_PATH = ROOT_DIR / ".env"
DEFAULT_LOGS_DIR = ROOT_DIR / "logs"
DEFAULT_URL = os.getenv("MELISSA_BRIDGE_URL", "http://localhost:8001")
DEFAULT_TIMEOUT = float(os.getenv("MELISSA_BRIDGE_TIMEOUT", "45"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def stamp_now() -> str:
    return utc_now().strftime("%Y%m%d_%H%M%S")


def load_env_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not path.exists():
        return data
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        data[key.strip()] = value
    return data


def build_log_path(logs_dir: Path) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / f"bridge_{stamp_now()}.txt"


def default_export_path(logs_dir: Path, session_id: str) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / f"bridge_export_{session_id}_{stamp_now()}.json"


def parse_history_limit(parts: Sequence[str]) -> Optional[int]:
    if len(parts) < 2:
        return None
    try:
        value = int(parts[1])
    except ValueError as exc:
        raise ValueError("Usage: /history [limit]") from exc
    if value <= 0:
        raise ValueError("History limit must be > 0")
    return value


@dataclass
class BridgeTurn:
    session_id: str
    runtime_user_id: str
    turn_index: int
    role: str
    content: str
    created_at: str
    command: str = ""
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TransportReply:
    response: str
    raw: Dict[str, Any]


class Transport(Protocol):
    def send(self, message: str, user_id: str) -> TransportReply:
        ...


class BridgeStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bridge_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    runtime_user_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    command TEXT NOT NULL DEFAULT '',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_bridge_sessions_session_turn
                ON bridge_sessions(session_id, turn_index, id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_bridge_sessions_runtime
                ON bridge_sessions(runtime_user_id, created_at)
                """
            )

    def next_turn_index(self, session_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(turn_index), 0) AS max_turn FROM bridge_sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
        return int(row["max_turn"] or 0) + 1

    def append_turn(
        self,
        session_id: str,
        runtime_user_id: str,
        role: str,
        content: str,
        *,
        command: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BridgeTurn:
        turn_index = self.next_turn_index(session_id)
        created_at = iso_now()
        payload = json.dumps(metadata or {}, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bridge_sessions
                (session_id, runtime_user_id, turn_index, role, content, command, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, runtime_user_id, turn_index, role, content, command, payload, created_at),
            )
        return BridgeTurn(
            session_id=session_id,
            runtime_user_id=runtime_user_id,
            turn_index=turn_index,
            role=role,
            content=content,
            command=command,
            metadata=metadata or {},
            created_at=created_at,
        )

    def get_history(self, session_id: str, limit: Optional[int] = None) -> List[BridgeTurn]:
        query = """
            SELECT session_id, runtime_user_id, turn_index, role, content, command, metadata, created_at
            FROM bridge_sessions
            WHERE session_id=?
            ORDER BY turn_index ASC, id ASC
        """
        params: Tuple[Any, ...] = (session_id,)
        if limit:
            query = """
                SELECT * FROM (
                    SELECT session_id, runtime_user_id, turn_index, role, content, command, metadata, created_at
                    FROM bridge_sessions
                    WHERE session_id=?
                    ORDER BY turn_index DESC, id DESC
                    LIMIT ?
                ) recent
                ORDER BY turn_index ASC
            """
            params = (session_id, limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        history: List[BridgeTurn] = []
        for row in rows:
            try:
                metadata = json.loads(row["metadata"] or "{}")
            except json.JSONDecodeError:
                metadata = {}
            history.append(
                BridgeTurn(
                    session_id=row["session_id"],
                    runtime_user_id=row["runtime_user_id"],
                    turn_index=row["turn_index"],
                    role=row["role"],
                    content=row["content"],
                    command=row["command"],
                    metadata=metadata,
                    created_at=row["created_at"],
                )
            )
        return history

    def export_session(self, session_id: str) -> Dict[str, Any]:
        turns = self.get_history(session_id)
        runtime_user_id = turns[0].runtime_user_id if turns else ""
        return {
            "session_id": session_id,
            "runtime_user_id": runtime_user_id,
            "turn_count": len(turns),
            "exported_at": iso_now(),
            "turns": [
                {
                    "turn_index": turn.turn_index,
                    "role": turn.role,
                    "content": turn.content,
                    "command": turn.command,
                    "metadata": turn.metadata or {},
                    "created_at": turn.created_at,
                }
                for turn in turns
            ],
        }


class MelissaTransport:
    def __init__(self, base_url: str, master_key: str = "", timeout: float = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.master_key = master_key
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def send(self, message: str, user_id: str) -> TransportReply:
        headers = {"Content-Type": "application/json"}
        if self.master_key:
            headers["X-Master-Key"] = self.master_key
        response = self._client.post(
            f"{self.base_url}/test",
            json={"message": message, "user_id": user_id},
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        body = payload.get("response") or "\n".join(str(item) for item in payload.get("bubbles") or [])
        return TransportReply(response=body.strip() or "(sin respuesta)", raw=payload)

    def close(self) -> None:
        self._client.close()


class LocalMelissaTransport:
    def __init__(self) -> None:
        import melissa as melissa_module

        self._module = melissa_module
        if getattr(self._module, "melissa", None) is None:
            asyncio.run(self._module.init_melissa())

    def send(self, message: str, user_id: str) -> TransportReply:
        responses = asyncio.run(self._module.melissa.process_message(user_id, message))
        bubbles = [str(item) for item in responses or [] if str(item).strip()]
        body = "\n".join(bubbles).strip() or "(sin respuesta)"
        payload = {
            "ok": True,
            "message": message,
            "user_id": user_id,
            "bubbles": bubbles,
            "response": body,
            "transport": "local",
        }
        return TransportReply(response=body, raw=payload)

    def close(self) -> None:
        return None


class BridgeLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")
        self._closed = False
        self.write("system", f"log_start path={self.path}")

    def write(self, role: str, content: str) -> None:
        line = f"[{iso_now()}] {role.upper()}: {content}\n"
        self._fh.write(line)
        self._fh.flush()

    def close(self) -> None:
        if self._closed:
            return
        self.write("system", "log_end")
        self._fh.close()
        self._closed = True


class MelissaBridge:
    def __init__(
        self,
        store: BridgeStore,
        transport: Transport,
        logger: BridgeLogger,
        *,
        session_id: Optional[str] = None,
        runtime_user_id: Optional[str] = None,
        logs_dir: Optional[Path] = None,
    ) -> None:
        self.store = store
        self.transport = transport
        self.logger = logger
        self.logs_dir = logs_dir or DEFAULT_LOGS_DIR
        self.session_id = session_id or self._new_session_id()
        self.runtime_user_id = runtime_user_id or self._new_runtime_user_id(self.session_id)
        self.logger.write(
            "system",
            f"session_started session_id={self.session_id} runtime_user_id={self.runtime_user_id}",
        )

    @staticmethod
    def _new_session_id() -> str:
        return f"bridge_{stamp_now()}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _new_runtime_user_id(session_id: str) -> str:
        return f"{session_id}_user"

    def send(self, message: str) -> TransportReply:
        clean = message.strip()
        if not clean:
            raise ValueError("Empty message")
        self.store.append_turn(self.session_id, self.runtime_user_id, "user", clean)
        self.logger.write("user", clean)
        reply = self.transport.send(clean, self.runtime_user_id)
        self.store.append_turn(
            self.session_id,
            self.runtime_user_id,
            "assistant",
            reply.response,
            metadata={"raw": reply.raw},
        )
        self.logger.write("assistant", reply.response)
        return reply

    def format_history(self, limit: Optional[int] = None) -> str:
        turns = self.store.get_history(self.session_id, limit=limit)
        visible = [turn for turn in turns if turn.role in {"user", "assistant"}]
        if not visible:
            return "(sin historial)"
        return "\n".join(
            f"[{turn.turn_index:02d}] {turn.role}: {turn.content}" for turn in visible
        )

    def export_session(self, export_path: Optional[Path] = None) -> Path:
        export_path = export_path or default_export_path(self.logs_dir, self.session_id)
        payload = self.store.export_session(self.session_id)
        export_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.logger.write("command", f"/export -> {export_path}")
        return export_path

    def clear_session(self) -> Tuple[str, str]:
        old_session = self.session_id
        new_session_id = self._new_session_id()
        self.store.append_turn(
            self.session_id,
            self.runtime_user_id,
            "command",
            "session cleared",
            command="/clear",
            metadata={"next_session_id": new_session_id},
        )
        new_runtime_user_id = self._new_runtime_user_id(new_session_id)
        self.session_id = new_session_id
        self.runtime_user_id = new_runtime_user_id
        self.logger.write(
            "command",
            f"/clear old_session={old_session} new_session={new_session_id}",
        )
        return old_session, new_session_id

    def handle_command(self, line: str) -> str:
        parts = line.strip().split()
        command = parts[0].lower()

        if command == "/history":
            limit = parse_history_limit(parts)
            output = self.format_history(limit=limit)
            self.logger.write("command", f"/history limit={limit or 'all'}")
            return output

        if command == "/clear":
            old_session, new_session = self.clear_session()
            return f"Session cleared. old={old_session} new={new_session}"

        if command == "/export":
            export_path = Path(parts[1]).expanduser() if len(parts) > 1 else None
            path = self.export_session(export_path)
            return f"Exported session to {path}"

        if command in {"/help", "/?"}:
            return "Commands: /history [limit], /clear, /export [path], /help, /exit"

        if command in {"/exit", "/quit"}:
            return "__EXIT__"

        raise ValueError(f"Unknown command: {command}")

    def process_line(self, line: str) -> str:
        if line.strip().startswith("/"):
            return self.handle_command(line)
        return self.send(line).response

    def run_interactive(self) -> int:
        print(f"Bridge session: {self.session_id}")
        print("Commands: /history [limit], /clear, /export [path], /exit")
        while True:
            try:
                line = input("you> ").strip()
            except EOFError:
                return 0
            except KeyboardInterrupt:
                print()
                return 130
            if not line:
                continue
            try:
                output = self.process_line(line)
            except Exception as exc:
                print(f"error> {exc}")
                self.logger.write("error", str(exc))
                continue
            if output == "__EXIT__":
                return 0
            print(f"melissa> {output}")

    def run_messages(self, messages: Iterable[str]) -> int:
        for raw in messages:
            line = raw.rstrip("\n")
            if not line:
                continue
            output = self.process_line(line)
            if output == "__EXIT__":
                return 0
            print(output)
        return 0

    def _build_test_scenario(self) -> List[Tuple[str, Optional[Tuple[str, ...]]]]:
        if self.transport.__class__.__name__ == "FakeTransport":
            return [
                (
                    "Esto es una prueba de memoria conversacional, no una venta. No cambies de tema y responde breve.",
                    None,
                ),
                ("Guarda este nombre de cliente: Laura Vega.", None),
                ("Guarda esta ciudad: Medellin.", None),
                ("Guarda este tratamiento de interes: botox.", None),
                ("Guarda este codigo exacto: lima742. Repitelo exacto.", ("lima742",)),
                ("Confirma con una respuesta breve y sigamos.", None),
                ("Sin hablar de ti, responde solo con el nombre de cliente que te di antes.", ("laura",)),
                ("Responde solo con la ciudad que te dije antes.", ("medellin",)),
                ("Responde solo con el tratamiento de interes que te dije antes.", ("botox",)),
                ("Responde solo con el codigo exacto que te di antes.", ("lima742",)),
                (
                    "En una sola linea resume los cuatro datos que guardaste antes.",
                    ("laura", "medellin", "botox", "lima742"),
                ),
            ]

        return [
            ("Hola", None),
            ("Clinica de Los olivos", ("olivos", "clinicalosolivos.com")),
            ("Siii somos nosotros", None),
            ("te puedo enviar un pdf, te sirve?", None),
            ("y si te mando un audio lo entiendes?", None),
            ("vale, hagamos una demo como cliente", None),
            ("hola buenas tardes", None),
            ("me interesa botox pero me da miedo quedar exagerada", None),
            ("si quiero cita como seguimos?", None),
            ("antes de seguir, dime con qué negocio estamos haciendo esta demo", ("olivos",)),
        ]

    def run_test_mode(self) -> Dict[str, Any]:
        scenario = self._build_test_scenario()

        checks: List[Dict[str, Any]] = []
        failures: List[Dict[str, Any]] = []
        for index, (message, expected_bits) in enumerate(scenario, start=1):
            reply = self.send(message)
            response = reply.response
            passed = True
            missing: List[str] = []
            if expected_bits:
                lowered = response.lower()
                for expected in expected_bits:
                    token = expected.lower()
                    if token not in lowered:
                        passed = False
                        missing.append(expected)
            checks.append(
                {
                    "turn": index,
                    "message": message,
                    "response": response,
                    "expected": list(expected_bits or []),
                    "passed": passed,
                    "missing": missing,
                }
            )
            if not passed:
                failures.append(checks[-1])

        user_turns = [
            turn
            for turn in self.store.get_history(self.session_id)
            if turn.role == "user"
        ]
        if len(user_turns) < 10:
            failures.append(
                {
                    "turn": "count",
                    "message": "",
                    "response": "",
                    "expected": [">=10 user turns"],
                    "passed": False,
                    "missing": [f"found={len(user_turns)}"],
                }
            )

        result = {
            "success": not failures,
            "session_id": self.session_id,
            "runtime_user_id": self.runtime_user_id,
            "turns": len(user_turns),
            "checks": checks,
            "failures": failures,
            "log_path": str(self.logger.path),
        }
        self.logger.write("system", json.dumps(result, ensure_ascii=False))
        if failures:
            first_failure = failures[0]
            raise RuntimeError(
                f"Context check failed on turn {first_failure['turn']}. Missing: {', '.join(first_failure['missing'])}"
            )
        return result


def resolve_master_key(env_path: Path) -> str:
    env_data = load_env_file(env_path)
    return os.getenv("MASTER_API_KEY", env_data.get("MASTER_API_KEY", ""))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="melissa_bridge")
    parser.add_argument("--url", default=DEFAULT_URL, help="Base URL de Melissa")
    parser.add_argument("--transport", choices=("auto", "http", "local"), default="auto",
                        help="Modo de conexión con Melissa")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="Ruta a melissa.db")
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH), help="Ruta al .env")
    parser.add_argument("--master-key", default="", help="MASTER_API_KEY opcional")
    parser.add_argument("--session-id", default="", help="Session id fijo")
    parser.add_argument("--user-id", default="", help="Runtime user_id fijo")
    parser.add_argument("--log-path", default="", help="Ruta fija del log de evidencia")
    parser.add_argument("--message", action="append", default=[], help="Mensaje no interactivo")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Timeout HTTP en segundos")
    parser.add_argument("--test-mode", action="store_true", help="Corre la sesion automatica de contexto")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    db_path = Path(args.db_path).expanduser().resolve()
    env_path = Path(args.env_path).expanduser().resolve()
    logs_dir = DEFAULT_LOGS_DIR
    log_path = Path(args.log_path).expanduser().resolve() if args.log_path else build_log_path(logs_dir)
    master_key = args.master_key or resolve_master_key(env_path)

    store = BridgeStore(db_path)
    logger = BridgeLogger(log_path)
    transport: Transport
    if args.transport == "local":
        transport = LocalMelissaTransport()
    elif args.transport == "http":
        transport = MelissaTransport(args.url, master_key=master_key, timeout=args.timeout)
    else:
        try:
            transport = LocalMelissaTransport()
        except Exception:
            transport = MelissaTransport(args.url, master_key=master_key, timeout=args.timeout)
    bridge = MelissaBridge(
        store,
        transport,
        logger,
        session_id=args.session_id or None,
        runtime_user_id=args.user_id or None,
        logs_dir=logs_dir,
    )

    try:
        if args.test_mode:
            try:
                result = bridge.run_test_mode()
            except Exception as exc:
                error_payload = {
                    "success": False,
                    "error": str(exc),
                    "session_id": bridge.session_id,
                    "runtime_user_id": bridge.runtime_user_id,
                    "log_path": str(logger.path),
                }
                print(json.dumps(error_payload, ensure_ascii=False, indent=2))
                return 1
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.message:
            return bridge.run_messages(args.message)
        if not sys.stdin.isatty():
            return bridge.run_messages(sys.stdin)
        return bridge.run_interactive()
    finally:
        if hasattr(transport, "close"):
            transport.close()  # type: ignore[attr-defined]
        logger.close()


if __name__ == "__main__":
    raise SystemExit(main())
