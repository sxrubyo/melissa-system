"""Tests for melissa_memory_engine.py"""
import sys
import asyncio
import tempfile
import shutil

sys.path.insert(0, ".")

from melissa_memory_engine import MelissaMemoryEngine


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_ingest_and_recall_roundtrip():
    tmpdir = tempfile.mkdtemp()
    try:
        engine = MelissaMemoryEngine(base_dir=tmpdir)
        messages = [
            {"role": "user", "content": "Hola, quiero agendar una cita de botox"},
            {"role": "assistant", "content": "Claro, te puedo agendar. Que dia te queda bien?"},
            {"role": "user", "content": "El martes a las 3pm"},
            {"role": "assistant", "content": "Perfecto, agendado para el martes a las 3pm"},
        ]
        _run(engine.ingest_conversation("test_instance", "chat_001", messages))

        results = _run(engine.recall_context("test_instance", "quiero una cita de botox"))
        assert len(results) > 0
        assert results[0]["score"] > 0.05
        assert results[0]["chat_id"] == "chat_001"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_entity_extraction():
    tmpdir = tempfile.mkdtemp()
    try:
        engine = MelissaMemoryEngine(base_dir=tmpdir)
        messages = [
            {"role": "user", "content": "Me llamo Santiago, mi telefono es 3124348669 y mi correo es santiago@test.com"},
            {"role": "assistant", "content": "Perfecto Santiago, te agendo"},
        ]
        _run(engine.ingest_conversation("test_instance", "chat_002", messages))

        # Check entities were extracted
        import json
        from pathlib import Path
        ent_file = Path(tmpdir) / "test_instance" / "semantic" / "entities.json"
        assert ent_file.exists()
        entities = json.loads(ent_file.read_text())
        assert "3124348669" in entities.get("phones", {})
        assert "santiago@test.com" in entities.get("emails", {})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_faq_frequency_tracking():
    tmpdir = tempfile.mkdtemp()
    try:
        engine = MelissaMemoryEngine(base_dir=tmpdir)
        messages = [
            {"role": "user", "content": "Cuanto cuesta el botox?"},
            {"role": "assistant", "content": "El precio depende de la valoracion"},
        ]
        _run(engine.ingest_conversation("test_instance", "chat_003", messages))
        _run(engine.ingest_conversation("test_instance", "chat_004", messages))

        faqs = _run(engine.get_top_faqs("test_instance"))
        assert len(faqs) > 0
        assert faqs[0]["frequency"] >= 2
        assert "botox" in faqs[0]["question"].lower()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_empty_recall_returns_empty():
    tmpdir = tempfile.mkdtemp()
    try:
        engine = MelissaMemoryEngine(base_dir=tmpdir)
        results = _run(engine.recall_context("nonexistent", "hola"))
        assert results == []
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
