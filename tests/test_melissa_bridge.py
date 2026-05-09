from pathlib import Path
import json
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import melissa_bridge as bridge_module  # noqa: E402


class FakeTransport:
    def __init__(self) -> None:
        self.state = {}

    def send(self, message: str, user_id: str) -> bridge_module.TransportReply:
        facts = self.state.setdefault(user_id, {})
        lower = message.lower()

        if "nombre de cliente que te di antes" in lower:
            response = facts.get("name", "sin dato")
        elif "ciudad que te dije antes" in lower:
            response = facts.get("city", "sin dato")
        elif "tratamiento de interes que te dije antes" in lower:
            response = facts.get("interest", "sin dato")
        elif "codigo exacto que te di antes" in lower:
            response = facts.get("code", "sin dato")
        elif "resume los cuatro datos" in lower:
            response = (
                f"{facts.get('name', '')} - {facts.get('city', '')} - "
                f"{facts.get('interest', '')} - {facts.get('code', '')}"
            )
        elif "nombre de cliente:" in lower:
            facts["name"] = message.split(":", 1)[1].strip(" .")
            response = "Anotado."
        elif "ciudad:" in lower:
            facts["city"] = message.split(":", 1)[1].strip(" .")
            response = "Ciudad guardada."
        elif "tratamiento de interes:" in lower:
            facts["interest"] = message.split(":", 1)[1].strip(" .")
            response = "Interes guardado."
        elif "codigo exacto:" in lower:
            facts["code"] = message.split(":", 1)[1].strip(" .")
            response = facts["code"]
        else:
            response = "ok"

        return bridge_module.TransportReply(response=response, raw={"response": response})


def build_bridge(tmp_path: Path) -> tuple[bridge_module.MelissaBridge, bridge_module.BridgeStore, Path]:
    db_path = tmp_path / "melissa.db"
    log_path = tmp_path / "logs" / "bridge_20260509_000000.txt"
    store = bridge_module.BridgeStore(db_path)
    logger = bridge_module.BridgeLogger(log_path)
    bridge = bridge_module.MelissaBridge(
        store,
        FakeTransport(),
        logger,
        session_id="bridge_test_session",
        runtime_user_id="bridge_test_user",
        logs_dir=tmp_path / "logs",
    )
    return bridge, store, log_path


def test_bridge_persists_turns_and_exports_session(tmp_path):
    bridge, store, _log_path = build_bridge(tmp_path)

    try:
        assert bridge.process_line("Hola Melissa") == "ok"
        assert bridge.process_line("Guarda este nombre de cliente: Laura Vega.") == "Anotado."

        history = store.get_history("bridge_test_session")
        assert [turn.role for turn in history] == ["user", "assistant", "user", "assistant"]

        export_path = bridge.export_session(tmp_path / "session.json")
        payload = json.loads(export_path.read_text(encoding="utf-8"))
        assert payload["session_id"] == "bridge_test_session"
        assert payload["turn_count"] == 4
        assert payload["turns"][0]["content"] == "Hola Melissa"
    finally:
        bridge.logger.close()


def test_clear_rotates_session_without_erasing_previous_history(tmp_path):
    bridge, store, _log_path = build_bridge(tmp_path)

    try:
        bridge.process_line("Hola")
        old_session = bridge.session_id
        message = bridge.handle_command("/clear")
        assert "old=bridge_test_session" in message
        assert bridge.session_id != old_session

        bridge.process_line("Despues del clear")
        old_history = store.get_history(old_session)
        new_history = store.get_history(bridge.session_id)

        assert any(turn.command == "/clear" for turn in old_history)
        assert [turn.role for turn in new_history] == ["user", "assistant"]
    finally:
        bridge.logger.close()


def test_test_mode_runs_context_checks_and_writes_log(tmp_path):
    bridge, store, log_path = build_bridge(tmp_path)

    try:
        result = bridge.run_test_mode()
        assert result["success"] is True
        assert result["turns"] >= 10
        history = store.get_history("bridge_test_session")
        user_turns = [turn for turn in history if turn.role == "user"]
        assert len(user_turns) >= 10
        assert log_path.exists()
        log_text = log_path.read_text(encoding="utf-8")
        assert "lima742" in log_text
    finally:
        bridge.logger.close()


def test_bridge_sessions_table_is_created_in_sqlite(tmp_path):
    db_path = tmp_path / "melissa.db"
    bridge_module.BridgeStore(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bridge_sessions'"
        ).fetchone()
    finally:
        conn.close()

    assert row == ("bridge_sessions",)
