"""Tests for melissa_voice.py — no robot patterns in output."""
import sys
sys.path.insert(0, ".")

from melissa_voice import MelissaVoice, ROBOT_PATTERNS


def test_removes_ai_self_reference():
    voice = MelissaVoice()
    text = "Como IA, no tengo la capacidad de procesar eso"
    result = voice.humanize(text)
    assert "como ia" not in result.lower()
    assert "no tengo la capacidad" not in result.lower()


def test_removes_bot_greeting():
    voice = MelissaVoice()
    text = "Hola! Soy Melissa, tu asistente virtual. En qué te puedo ayudar?"
    result = voice.humanize(text)
    assert "soy melissa" not in result.lower()
    assert "asistente virtual" not in result.lower()


def test_limits_exclamation_marks():
    voice = MelissaVoice()
    text = "Perfecto! Genial! Maravilloso! Te agendo ya!"
    result = voice.humanize(text)
    assert result.count("!") <= 1


def test_removes_por_supuesto():
    voice = MelissaVoice()
    text = "Por supuesto, te agendo la cita para mañana"
    result = voice.humanize(text)
    assert "por supuesto" not in result.lower()


def test_response_not_starting_with_melissa():
    voice = MelissaVoice()
    text = "Melissa, aquí te confirmo la cita"
    result = voice.humanize(text)
    assert not result.lower().startswith("melissa")


def test_no_robot_patterns_in_sample_responses():
    voice = MelissaVoice()
    samples = [
        "Te agendo la cita para el martes a las 3pm",
        "El precio depende de la valoración personalizada",
        "Con gusto te ayudo con eso, dame un momento",
        "Perfecto, tu nombre completo por favor",
        "Listo, quedó agendado. Nos vemos el jueves",
    ]
    for sample in samples:
        result = voice.humanize(sample)
        found = voice.check_robot_patterns(result)
        assert not found, f"Robot pattern found in: {result} -> {found}"


def test_thinking_block_injection():
    voice = MelissaVoice()
    prompt = "Eres una recepcionista de clinica"
    result = voice.inject_thinking_block(prompt, lang="es")
    assert "INSTRUCCIÓN INTERNA" in result
    assert prompt in result


def test_split_long_response():
    voice = MelissaVoice()
    text = "Primera oracion completa. Segunda oracion completa. Tercera oracion que es mas larga para ver como se divide. Cuarta oracion para completar el test de splitting correctamente."
    bubbles = voice.split_long_response(text, max_chars=100)
    assert len(bubbles) >= 2
    assert all(len(b) <= 200 for b in bubbles)  # reasonable sizes
