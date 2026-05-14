"""Tests for melissa_uncertainty.py"""
import sys
sys.path.insert(0, ".")

from melissa_uncertainty import UncertaintyDetector


def test_confidence_returns_float():
    det = UncertaintyDetector()
    score = det.confidence_score("Claro, te agendo la cita para mañana", "quiero una cita", [])
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_high_confidence_for_specific_response():
    det = UncertaintyDetector()
    score = det.confidence_score(
        "La cita es el martes 14 a las 3pm con el Dr. Lopez",
        "cuando es mi cita",
        []
    )
    assert score >= 0.7


def test_low_confidence_for_uncertain_response():
    det = UncertaintyDetector()
    score = det.confidence_score(
        "No sé, no tengo esa información disponible",
        "cuanto cuesta el botox",
        []
    )
    assert score < 0.6


def test_detect_uncertainty_markers():
    det = UncertaintyDetector()
    assert det.detect_uncertainty_markers("No sé la respuesta a eso")
    assert det.detect_uncertainty_markers("no tengo información sobre eso")
    assert not det.detect_uncertainty_markers("Te agendo la cita para mañana a las 3")


def test_confidence_penalizes_short_response_to_complex_question():
    det = UncertaintyDetector()
    score = det.confidence_score(
        "No sé",
        "cuantos procedimientos de botox realizan al mes y cuales son los precios",
        []
    )
    assert score < 0.4
