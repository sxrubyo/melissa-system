import sys
import types
import uuid
from pathlib import Path

import pytest


ROOT = Path("/home/ubuntu/melissa")
sys.path.insert(0, str(ROOT))

from melissa_nuke_robot_phrases import apply_patch, strip_robot_phrases
from melissa_send_guard import guard_response, is_cut_response


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("hola, quiero saber el precio del botox", "hola, quiero saber el precio del botox"),
        ("si te sirve, como inteligencia artificial suena muy raro en whatsapp", "si te sirve, como inteligencia artificial suena muy raro en whatsapp"),
        ("te lo digo claro: mis capacidades incluyen disciplina y enfoque", "te lo digo claro: mis capacidades incluyen disciplina y enfoque"),
        ("como modelo de lenguaje corporal, la postura importa mucho", "como modelo de lenguaje corporal, la postura importa mucho"),
        ("ese cierre de saludos cordiales me suena a correo", "ese cierre de saludos cordiales me suena a correo"),
        ("la palabra atentamente me parece demasiado formal", "la palabra atentamente me parece demasiado formal"),
        ("cuando alguien dice soy tu asistente virtual, se siente falso", "cuando alguien dice soy tu asistente virtual, se siente falso"),
        ("quiero un tono directo, no uno que diga mis limitaciones son tantas", "quiero un tono directo, no uno que diga mis limitaciones son tantas"),
        ("como inteligencia emocional, esa respuesta se siente más humana", "como inteligencia emocional, esa respuesta se siente más humana"),
        ("sin más por el momento quiero comparar dos opciones", "sin más por el momento quiero comparar dos opciones"),
    ],
)
def test_strip_robot_phrases_preserves_diverse_normal_prompts(prompt: str, expected: str) -> None:
    assert strip_robot_phrases(prompt) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Como inteligencia artificial, no puedo agendar por ti.", "No puedo agendar por ti."),
        ("Te paso opciones, saludos cordiales", "Te paso opciones"),
        ("Soy tu asistente virtual. ¿Qué necesitas?", "¿Qué necesitas?"),
    ],
)
def test_strip_robot_phrases_removes_only_boundary_robot_clauses(text: str, expected: str) -> None:
    assert strip_robot_phrases(text) == expected


def test_apply_patch_monkey_patches_runtime_filters() -> None:
    module_name = f"dummy_robot_patch_{uuid.uuid4().hex}"
    dummy_module = types.ModuleType(module_name)

    class DummyGenerator:
        def _postprocess(self, response: str, personality) -> str:
            return response

    class DummyAntiRobot:
        FORBIDDEN_HARD = {"como inteligencia artificial", "saludos cordiales"}

        def _remove_forbidden_exact(self, text: str) -> str:
            return text

    dummy_module.DummyGenerator = DummyGenerator
    dummy_module.DummyAntiRobot = DummyAntiRobot
    sys.modules[module_name] = dummy_module

    try:
        assert apply_patch() is True
        assert dummy_module.DummyGenerator()._postprocess(
            "Como inteligencia artificial, agenda una cita.",
            None,
        ) == "Agenda una cita."
        assert dummy_module.DummyAntiRobot()._remove_forbidden_exact(
            "Te paso opciones, saludos cordiales"
        ) == "Te paso opciones"
    finally:
        sys.modules.pop(module_name, None)


def test_send_guard_detects_real_cut_and_ignores_complete_short_sentence() -> None:
    assert is_cut_response("Entendido, vol")[0] is True
    assert is_cut_response("Te escribo luego.")[0] is False
    assert guard_response("Te escribo luego.", context="demo") == "Te escribo luego."
