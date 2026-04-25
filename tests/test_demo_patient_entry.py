import sys


sys.path.insert(0, "/home/ubuntu/melissa")
from melissa import MelissaUltra  # noqa: E402


def test_demo_patient_like_messages_are_detected() -> None:
    runtime = MelissaUltra.__new__(MelissaUltra)

    assert runtime._demo_should_use_patient_chat_path("hola")
    assert runtime._demo_should_use_patient_chat_path("quien eres")
    assert runtime._demo_should_use_patient_chat_path("quiero una cita para botox")

    assert not runtime._demo_should_use_patient_chat_path("quiero una demo")
    assert not runtime._demo_should_use_patient_chat_path("tengo un negocio")
    assert not runtime._demo_should_use_patient_chat_path("me dejaron probarte")


def test_demo_patient_clinic_uses_runtime_sector_and_drops_nova_label() -> None:
    runtime = MelissaUltra.__new__(MelissaUltra)

    clinic = runtime._build_demo_patient_clinic({"name": "Nova", "sector": "otro"})

    assert clinic["name"] == ""
    assert clinic["sector"] == "estetica"


def test_demo_patient_path_ignores_demo_history_when_no_business_loaded() -> None:
    runtime = MelissaUltra.__new__(MelissaUltra)
    seen = {}

    def fake_try_conversation_core(**kwargs):
        seen.update(kwargs)
        return ["Hola, soy Melissa."]

    runtime._try_conversation_core = fake_try_conversation_core

    history = [
        {"role": "assistant", "content": "Sigo siendo Melissa, la recepcionista virtual."},
        {"role": "assistant", "content": "dime cómo se llama tu negocio"},
    ]

    result = runtime._try_conversation_core(
        clinic=runtime._build_demo_patient_clinic({"name": "Nova", "sector": "otro"}),
        user_msg="quiero una cita para botox",
        history=[],
        is_admin=False,
        channel="whatsapp",
    )

    assert result == ["Hola, soy Melissa."]
    assert seen["history"] == []
    assert history[0]["content"].startswith("Sigo siendo Melissa")
