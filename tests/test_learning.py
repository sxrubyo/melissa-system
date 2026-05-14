"""Tests for melissa_learning.py"""
import sys
import asyncio
import tempfile
import shutil
sys.path.insert(0, ".")


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_learn_from_admin():
    from melissa_learning import RealTimeLearningEngine
    tmpdir = tempfile.mkdtemp()
    engine = RealTimeLearningEngine(base_dir=tmpdir)
    engine._teachings_dir = __import__("pathlib").Path(tmpdir) / "teachings"
    engine._teachings_dir.mkdir()
    result = _run(engine.learn_from_admin(
        "test_instance", "cuanto vale el botox", "Desde 800.000 COP", "admin1"
    ))
    assert "Aprendido" in result
    teachings = _run(engine.get_teachings("test_instance"))
    assert len(teachings) == 1
    assert "botox" in teachings[0]["question"]
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_build_teachings_prompt():
    from melissa_learning import RealTimeLearningEngine
    engine = RealTimeLearningEngine()
    teachings = [
        {"question": "cuanto vale", "answer": "80.000 COP"},
        {"question": "horario", "answer": "L-V 8am-6pm"},
    ]
    prompt = engine.build_teachings_prompt(teachings)
    assert "INFORMACIÓN APRENDIDA" in prompt
    assert "80.000" in prompt


def test_learn_from_turn_positive():
    from melissa_learning import RealTimeLearningEngine
    tmpdir = tempfile.mkdtemp()
    engine = RealTimeLearningEngine(base_dir=tmpdir)
    _run(engine.learn_from_turn(
        "test_instance",
        user_msg="quiero una cita",
        bot_response="Te agendo para mañana a las 3pm",
        user_reply="perfecto gracias"
    ))
    # Should have reinforced
    idir = engine._instance_dir("test_instance")
    assert (idir / "reinforced.jsonl").exists()
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_learn_from_turn_negative():
    from melissa_learning import RealTimeLearningEngine
    tmpdir = tempfile.mkdtemp()
    engine = RealTimeLearningEngine(base_dir=tmpdir)
    _run(engine.learn_from_turn(
        "test_instance",
        user_msg="cuanto vale",
        bot_response="No tengo esa información",
        user_reply="eso no me sirve, ya te pregunté lo mismo"
    ))
    idir = engine._instance_dir("test_instance")
    assert (idir / "failures.jsonl").exists()
    shutil.rmtree(tmpdir, ignore_errors=True)
