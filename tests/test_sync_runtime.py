from pathlib import Path
from types import SimpleNamespace
import json
import sqlite3
import sys


sys.path.insert(0, "/home/ubuntu/melissa")
import melissa_cli as cli  # noqa: E402


class DummySpinner:
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def finish(self, *_args, **_kwargs):
        return None


def test_runtime_sync_entries_include_extended_runtime_only(tmp_path):
    source = tmp_path / "base"
    source.mkdir()
    (source / "melissa.py").write_text("base", encoding="utf-8")
    (source / "melissa_brain_v10.py").write_text("brain", encoding="utf-8")
    (source / "melissa_core").mkdir()
    (source / "melissa_core" / "__init__.py").write_text("# core", encoding="utf-8")
    (source / ".env").write_text("SECRET=1", encoding="utf-8")

    entries = cli._runtime_sync_entries(str(source))

    assert "melissa.py" in entries
    assert "melissa_brain_v10.py" in entries
    assert "melissa_core" in entries
    assert ".env" not in entries


def test_clone_runtime_entries_replaces_stale_code_but_preserves_non_manifest_files(tmp_path):
    source = tmp_path / "base"
    source.mkdir()
    (source / "melissa.py").write_text("new melissa", encoding="utf-8")
    (source / "melissa_brain_v10.py").write_text("new brain", encoding="utf-8")
    (source / "melissa_core").mkdir()
    (source / "melissa_core" / "__init__.py").write_text("new core", encoding="utf-8")

    dest = tmp_path / "inst"
    dest.mkdir()
    (dest / "melissa.py").write_text("old melissa", encoding="utf-8")
    (dest / ".env").write_text("KEEP=1", encoding="utf-8")
    (dest / "melissa_core").mkdir()
    (dest / "melissa_core" / "stale.txt").write_text("stale", encoding="utf-8")

    copied = cli._clone_runtime_entries(str(source), str(dest))

    assert "melissa.py" in copied
    assert "melissa_brain_v10.py" in copied
    assert "melissa_core" in copied
    assert (dest / "melissa.py").read_text(encoding="utf-8") == "new melissa"
    assert (dest / "melissa_brain_v10.py").read_text(encoding="utf-8") == "new brain"
    assert (dest / "melissa_core" / "__init__.py").read_text(encoding="utf-8") == "new core"
    assert not (dest / "melissa_core" / "stale.txt").exists()
    assert (dest / ".env").read_text(encoding="utf-8") == "KEEP=1"


def test_cmd_sync_clones_extended_runtime_entries(monkeypatch, tmp_path):
    source = tmp_path / "base"
    source.mkdir()
    (source / "melissa.py").write_text("new melissa", encoding="utf-8")
    (source / "melissa_brain_v10.py").write_text("new brain", encoding="utf-8")
    (source / "search.py").write_text("search", encoding="utf-8")
    (source / "melissa_core").mkdir()
    (source / "melissa_core" / "__init__.py").write_text("new core", encoding="utf-8")

    dest = tmp_path / "instances" / "clinica"
    dest.mkdir(parents=True)
    (dest / "melissa.py").write_text("old melissa", encoding="utf-8")
    (dest / "melissa_core").mkdir()
    (dest / "melissa_core" / "stale.txt").write_text("stale", encoding="utf-8")
    (dest / ".env").write_text("KEEP=1", encoding="utf-8")

    fake_instance = SimpleNamespace(
        is_base=False,
        name="clinica",
        label="Clinica",
        dir=str(dest),
        port=8003,
    )

    monkeypatch.setattr(cli, "MELISSA_DIR", str(source))
    monkeypatch.setattr(cli, "get_instances", lambda: [fake_instance])
    monkeypatch.setattr(cli, "confirm", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli, "pm2", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "health", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(cli, "Spinner", DummySpinner)
    monkeypatch.setattr(cli, "print_logo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "section", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "ok", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "warn", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "dim", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "nl", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "hr", lambda *_args, **_kwargs: None)

    cli.cmd_sync(SimpleNamespace())

    assert (dest / "melissa.py").read_text(encoding="utf-8") == "new melissa"
    assert (dest / "melissa_brain_v10.py").read_text(encoding="utf-8") == "new brain"
    assert (dest / "melissa_core" / "__init__.py").read_text(encoding="utf-8") == "new core"
    assert not (dest / "melissa_core" / "stale.txt").exists()
    assert (dest / ".env").read_text(encoding="utf-8") == "KEEP=1"


def test_cmd_bb_routes_config_to_bb_config(monkeypatch):
    called = []

    monkeypatch.setattr(cli, "cmd_bb_config", lambda args: called.append(("bb", args.name, args.subcommand)))
    monkeypatch.setattr(cli, "cmd_config", lambda args: called.append(("legacy", args.name, args.subcommand)))

    cli.cmd_bb(SimpleNamespace(subcommand="config", name="nova"))

    assert called == [("bb", "nova", "")]


def test_bb_apply_persona_falls_back_to_sqlite_when_instance_is_offline(monkeypatch, tmp_path):
    db_path = tmp_path / "melissa.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE clinic (id INTEGER PRIMARY KEY, persona_config TEXT)")
    conn.execute("INSERT INTO clinic (id, persona_config) VALUES (1, ?)", (json.dumps({"name": "Melissa"}),))
    conn.commit()
    conn.close()

    inst = cli.Instance(
        name="nova",
        label="Nova",
        port=9999,
        dir=str(tmp_path),
        env={"DB_PATH": str(db_path)},
        is_base=False,
    )

    monkeypatch.setattr(cli, "health", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(cli, "Spinner", DummySpinner)
    monkeypatch.setattr(cli, "ok", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "fail", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "warn", lambda *_args, **_kwargs: None)

    assert cli._bb_apply_persona(inst, {"name": "Nova", "tone_instruction": "responde corto"}, spinner_label="x")

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT persona_config FROM clinic WHERE id=1").fetchone()
    conn.close()
    payload = json.loads(row[0])
    assert payload["name"] == "Nova"
    assert payload["tone_instruction"] == "responde corto"
