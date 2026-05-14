"""Tests for melissa_nova_proxy.py"""
import sys
import asyncio
sys.path.insert(0, ".")

from melissa_nova_proxy import NovaLLMProxy


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class MockLLM:
    """Mock LLM engine for testing."""
    async def complete(self, messages, **kwargs):
        user_msg = ""
        for m in messages:
            if m["role"] == "user":
                user_msg = m["content"]
        return f"Respuesta a: {user_msg[:50]}", {"provider": "mock", "model": "test"}


class MockGuard:
    """Mock Nova guard that approves everything."""
    async def should_send(self, message, **kwargs):
        return True, "mock_approved", ""


class MockBlockingGuard:
    """Mock Nova guard that blocks everything."""
    async def should_send(self, message, **kwargs):
        return False, "mock_blocked", "ledger_123"


def test_proxy_calls_llm():
    proxy = NovaLLMProxy(MockLLM())
    response, meta = _run(proxy.complete(
        [{"role": "user", "content": "hola"}],
        inject_memory=False,
        inject_thinking=False,
        apply_voice=False,
    ))
    assert "Respuesta a: hola" in response
    assert meta["proxy"] is True


def test_proxy_with_guard_approves():
    proxy = NovaLLMProxy(MockLLM(), nova_guard=MockGuard())
    response, meta = _run(proxy.complete(
        [{"role": "user", "content": "quiero una cita"}],
        inject_memory=False,
        inject_thinking=False,
        apply_voice=False,
    ))
    assert response  # Should have content
    assert meta.get("nova_verdict") == "approved"


def test_proxy_with_guard_blocks():
    proxy = NovaLLMProxy(MockLLM(), nova_guard=MockBlockingGuard())
    response, meta = _run(proxy.complete(
        [{"role": "user", "content": "test"}],
        inject_memory=False,
        inject_thinking=False,
        apply_voice=False,
    ))
    assert meta.get("nova_verdict") == "blocked"
    assert meta.get("nova_fallback") is True
    assert "verificar" in response.lower() or "agend" in response.lower()


def test_proxy_stats():
    proxy = NovaLLMProxy(MockLLM())
    _run(proxy.complete([{"role": "user", "content": "test"}],
                        inject_memory=False, inject_thinking=False, apply_voice=False))
    _run(proxy.complete([{"role": "user", "content": "test2"}],
                        inject_memory=False, inject_thinking=False, apply_voice=False))
    stats = proxy.get_stats()
    assert stats["total_calls"] == 2
    assert stats["blocked"] == 0


def test_proxy_without_llm():
    proxy = NovaLLMProxy(None)
    response, meta = _run(proxy.complete(
        [{"role": "user", "content": "hola"}],
        inject_memory=False, inject_thinking=False, apply_voice=False,
    ))
    assert response == ""
    assert "error" in meta
