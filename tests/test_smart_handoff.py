import asyncio
import json
import sqlite3
import sys
import time
from pathlib import Path


sys.path.insert(0, "/home/ubuntu/melissa")
import smart_handoff as sh  # noqa: E402


def _build_manager(tmp_path: Path) -> tuple[sh.SmartAdminHandoff, Path]:
    db_path = tmp_path / "handoff.db"
    manager = sh.SmartAdminHandoff(db_path=str(db_path))
    return manager, db_path


async def _fake_llm(*args, **kwargs) -> str:
    return "Con gusto, mañana te llamamos para confirmarte el dato."


def test_trigger_returns_ack_without_waiting_admin_notification_and_persists_full_context(tmp_path: Path) -> None:
    manager, db_path = _build_manager(tmp_path)
    admin_notifications: list[tuple[str, str]] = []
    history = [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "hola, en qué te ayudo"},
        {"role": "user", "content": "cuál es el precio del botox"},
        {"role": "assistant", "content": "te confirmo eso ya"},
    ]
    clinic = {"id": "clinic-1", "name": "Clínica Serena", "prices": {}, "services": ["Botox"]}

    async def _slow_admin_notify(admin_id: str, message: str) -> None:
        await asyncio.sleep(0.05)
        admin_notifications.append((admin_id, message))

    async def _scenario() -> tuple[list[str], bool, float, int, int]:
        start = time.perf_counter()
        messages, escalated = await manager.trigger(
            client_chat_id="573000000001",
            user_msg="cuál es el precio del botox",
            history=history,
            clinic=clinic,
            llm_output="Te confirmo eso ya",
            admin_chat_ids=["admin-1", "admin-2"],
            send_to_admin_fn=_slow_admin_notify,
        )
        elapsed = time.perf_counter() - start
        immediate_notifications = len(admin_notifications)
        await asyncio.sleep(0.08)
        return messages, escalated, elapsed, immediate_notifications, len(admin_notifications)

    messages, escalated, elapsed, immediate_notifications, total_notifications = asyncio.run(_scenario())

    assert escalated is True
    assert len(messages) == 1
    assert elapsed < 0.04
    assert immediate_notifications == 0
    assert total_notifications == 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM handoff_queue").fetchone()
    conn.close()

    assert row is not None
    payload = json.loads(row["context_json"])
    assert payload["history"] == history
    assert payload["llm_output"] == "Te confirmo eso ya"
    assert json.loads(row["admin_chat_ids_json"]) == ["admin-1", "admin-2"]
    assert json.loads(row["clinic_json"])["name"] == "Clínica Serena"
    assert row["hold_message"] == messages[0]
    assert row["expires_at"] > row["created_at"]


def test_admin_ack_only_is_not_forwarded_to_client(tmp_path: Path) -> None:
    manager, _db_path = _build_manager(tmp_path)
    forwarded: list[tuple[str, str]] = []
    clinic = {"id": "clinic-1", "name": "Clínica Serena", "prices": {}, "services": ["Botox"]}

    async def _admin_notify(admin_id: str, message: str) -> None:
        return None

    async def _send_client(chat_id: str, message: str) -> None:
        forwarded.append((chat_id, message))

    async def _scenario() -> tuple[bool, list[str], str]:
        await manager.trigger(
            client_chat_id="573000000001",
            user_msg="cuál es el precio del botox",
            history=[{"role": "user", "content": "cuál es el precio del botox"}],
            clinic=clinic,
            llm_output="Te confirmo eso ya",
            admin_chat_ids=["admin-1"],
            send_to_admin_fn=_admin_notify,
        )
        await asyncio.sleep(0)
        handled, messages = await manager.try_intercept_admin_reply(
            admin_chat_id="admin-1",
            admin_text="ok",
            clinic=clinic,
            llm_fn=_fake_llm,
            send_to_client_fn=_send_client,
        )
        ticket = manager.get_pending_tickets()[0]
        return handled, messages, ticket.status

    handled, messages, status = asyncio.run(_scenario())

    assert handled is True
    assert forwarded == []
    assert "Cuando tengas la respuesta" in messages[0]
    assert status == "pending"


def test_timeout_expires_ticket_and_sends_fallback(tmp_path: Path) -> None:
    manager, _db_path = _build_manager(tmp_path)
    manager.TICKET_TTL = 0.05
    forwarded: list[tuple[str, str]] = []
    clinic = {"id": "clinic-1", "name": "Clínica Serena", "prices": {}, "services": ["Botox"]}

    async def _admin_notify(admin_id: str, message: str) -> None:
        return None

    async def _send_client(chat_id: str, message: str) -> None:
        forwarded.append((chat_id, message))

    async def _scenario() -> sh.HandoffTicket:
        await manager.trigger(
            client_chat_id="573000000001",
            user_msg="cuál es el precio del botox",
            history=[{"role": "user", "content": "cuál es el precio del botox"}],
            clinic=clinic,
            llm_output="Te confirmo eso ya",
            admin_chat_ids=["admin-1"],
            send_to_admin_fn=_admin_notify,
            send_to_client_fn=_send_client,
        )
        await asyncio.sleep(0.09)
        row_conn = sqlite3.connect(_db_path)
        row_conn.row_factory = sqlite3.Row
        row = row_conn.execute("SELECT id FROM handoff_queue").fetchone()
        row_conn.close()
        assert row is not None
        ticket = manager._load_ticket(row["id"])
        assert ticket is not None
        return ticket

    ticket = asyncio.run(_scenario())

    assert ticket.status == "expired"
    assert ticket.fallback_sent_at > 0
    assert forwarded == [("573000000001", ticket.fallback_message)]


def test_late_admin_reply_after_timeout_is_not_forwarded(tmp_path: Path) -> None:
    manager, db_path = _build_manager(tmp_path)
    manager.TICKET_TTL = 0.05
    forwarded: list[tuple[str, str]] = []
    clinic = {"id": "clinic-1", "name": "Clínica Serena", "prices": {}, "services": ["Botox"]}

    async def _admin_notify(admin_id: str, message: str) -> None:
        return None

    async def _send_client(chat_id: str, message: str) -> None:
        forwarded.append((chat_id, message))

    async def _scenario() -> tuple[bool, list[str], str]:
        await manager.trigger(
            client_chat_id="573000000001",
            user_msg="cuál es el precio del botox",
            history=[{"role": "user", "content": "cuál es el precio del botox"}],
            clinic=clinic,
            llm_output="Te confirmo eso ya",
            admin_chat_ids=["admin-1"],
            send_to_admin_fn=_admin_notify,
            send_to_client_fn=_send_client,
        )
        await asyncio.sleep(0.09)
        row_conn = sqlite3.connect(db_path)
        row_conn.row_factory = sqlite3.Row
        row = row_conn.execute("SELECT id FROM handoff_queue").fetchone()
        row_conn.close()
        assert row is not None
        manager._pending_admin_map["admin-1"] = row["id"]
        handled, messages = await manager.try_intercept_admin_reply(
            admin_chat_id="admin-1",
            admin_text="dile que mañana a las 8am",
            clinic=clinic,
            llm_fn=_fake_llm,
            send_to_client_fn=_send_client,
        )
        ticket = manager._load_ticket(row["id"])
        assert ticket is not None
        return handled, messages, ticket.status

    handled, messages, status = asyncio.run(_scenario())

    assert handled is True
    assert status == "expired"
    assert len(forwarded) == 1
    assert "expiró" in messages[0].lower()
