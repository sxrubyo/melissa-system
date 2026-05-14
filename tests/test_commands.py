"""Tests for melissa_commands.py"""
import sys
import asyncio
sys.path.insert(0, ".")


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_user_help_command():
    from melissa_commands import CommandHandler
    handler = CommandHandler("test")
    result = _run(handler.handle("user123", "/ayuda", is_admin=False))
    assert result is not None
    assert "Comandos disponibles" in result[0]


def test_user_horarios():
    from melissa_commands import CommandHandler
    handler = CommandHandler("test")
    clinic = {"schedule": "L-V 8am-6pm"}
    result = _run(handler.handle("user123", "/horarios", is_admin=False, clinic=clinic))
    assert result is not None
    assert "8am" in result[0]


def test_admin_pausa():
    from melissa_commands import CommandHandler
    handler = CommandHandler("test")
    result = _run(handler.handle("admin1", "/pausa", is_admin=True))
    assert result is not None
    assert handler.is_paused()
    result = _run(handler.handle("admin1", "/reanudar", is_admin=True))
    assert not handler.is_paused()


def test_admin_personalidad():
    from melissa_commands import CommandHandler
    handler = CommandHandler("test_cmd")
    result = _run(handler.handle("admin1", '/personalidad tono=formal nombre="Sofía"', is_admin=True))
    assert result is not None
    assert "actualizada" in result[0].lower()


def test_admin_aprender():
    from melissa_commands import CommandHandler
    handler = CommandHandler("test_learn")
    result = _run(handler.handle("admin1", '/aprender ¿cuánto vale? → $80.000', is_admin=True))
    assert result is not None
    assert "Aprendido" in result[0]


def test_not_a_command():
    from melissa_commands import CommandHandler
    handler = CommandHandler("test")
    result = _run(handler.handle("user123", "hola quiero una cita", is_admin=False))
    assert result is None
