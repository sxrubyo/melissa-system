"""
Melissa Uncertainty Detector — Identifies knowledge gaps and alerts admins.

Detects when Melissa is uncertain about her answers and logs gaps
for future training / admin intervention.
"""

import re
import json
import logging
import asyncio
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

log = logging.getLogger("melissa.uncertainty")

UNCERTAINTY_MARKERS_ES = [
    "no sé",
    "no tengo información",
    "no estoy segura",
    "no puedo ayudar",
    "no cuento con",
    "no manejo esa información",
    "no tengo datos",
    "desconozco",
    "no sabría decirte",
    "tendría que consultar",
    "no tengo acceso",
    "no dispongo de",
]

UNCERTAINTY_MARKERS_EN = [
    "i don't know",
    "i'm not sure",
    "i can't help with that",
    "i don't have that information",
    "let me check",
]


class UncertaintyDetector:
    def __init__(self, threshold: float = 0.4):
        self.threshold = threshold
        self._gaps_dir = Path("knowledge_gaps")
        self._gaps_dir.mkdir(exist_ok=True)

    def detect_uncertainty_markers(self, text: str) -> bool:
        """Return True if the text contains any uncertainty marker."""
        text_low = text.lower()
        return any(
            marker in text_low
            for marker in UNCERTAINTY_MARKERS_ES + UNCERTAINTY_MARKERS_EN
        )

    def confidence_score(self, response: str, user_msg: str, history: list) -> float:
        """Score confidence 0.0-1.0. Detects evasion, not just explicit uncertainty."""
        score = 1.0
        text_low = response.lower()
        user_low = user_msg.lower()

        # Penalty for uncertainty markers
        marker_count = sum(
            1
            for m in UNCERTAINTY_MARKERS_ES + UNCERTAINTY_MARKERS_EN
            if m in text_low
        )
        score -= marker_count * 0.35

        # Extra penalty if response IS the uncertainty (very short + marker)
        if len(response.split()) < 8 and marker_count > 0:
            score -= 0.15

        # Penalty for very short responses to complex questions
        if len(user_msg.split()) > 8 and len(response.split()) < 10:
            score -= 0.2

        # Penalty for deflection patterns
        deflection = ["pregunta al", "consulta con", "contacta a", "llama a"]
        if any(d in text_low for d in deflection):
            score -= 0.15

        # === NEW: Detect PRICE evasion ===
        # User asked about price but response has no numbers/amounts
        price_signals = ["cuanto", "cuánto", "precio", "vale", "cuesta", "cobran", "tarifa", "costo", "promo"]
        user_asked_price = any(s in user_low for s in price_signals)
        response_has_price = bool(re.search(r'\$?\d[\d.,]+', response)) or any(
            w in text_low for w in ("gratis", "sin costo", "incluido")
        )
        if user_asked_price and not response_has_price:
            score -= 0.45  # Heavy penalty: user asked price, we don't know it

        # === NEW: Detect SERVICE evasion ===
        # User asked about specific service but response says "we don't do that" or redirects
        service_denial = [
            "no manejamos", "no ofrecemos", "no realizamos", "no hacemos",
            "no contamos con", "nuestra especialidad es", "solo manejamos",
            "solo ofrecemos", "no tenemos ese",
        ]
        if any(d in text_low for d in service_denial):
            score -= 0.3  # She might be wrong — she doesn't actually know the full service list

        # === NEW: Detect "depende" evasion ===
        vague_deflectors = [
            "depende del servicio", "depende de la valoración", "depende del caso",
            "te confirmo", "déjame verificar", "let me check",
        ]
        if any(d in text_low for d in vague_deflectors) and user_asked_price:
            score -= 0.35  # Vague + user wanted specifics = she doesn't know

        # Bonus for specific information (contains numbers/concrete data)
        if any(c.isdigit() for c in response):
            score += 0.1

        return max(0.0, min(1.0, score))

    async def log_gap(
        self,
        instance_id: str,
        user_msg: str,
        bot_response: str,
        confidence: float,
        chat_id: str = "",
    ):
        """Log a knowledge gap to JSONL file."""
        today = datetime.now().strftime("%Y-%m-%d")
        gap_file = self._gaps_dir / f"{today}.jsonl"
        entry = {
            "ts": datetime.now().isoformat(),
            "instance_id": instance_id,
            "chat_id": chat_id,
            "user_msg": user_msg,
            "bot_response": bot_response,
            "confidence": round(confidence, 3),
        }
        with open(gap_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        log.info(
            f"[uncertainty] gap logged for {instance_id}: confidence={confidence:.2f}"
        )

    async def alert_admin(
        self,
        instance_id: str,
        user_msg: str,
        bot_response: str,
        confidence: float,
        send_fn=None,
    ):
        """Send WhatsApp alert to admin when confidence is low."""
        alert_text = (
            f"Hola, soy Melissa de {instance_id}. "
            f"Un paciente preguntó: '{user_msg[:200]}' "
            f"y no supe responderle bien (confianza: {confidence:.0%}). "
            f"¿Me puedes dar la información correcta para aprender?"
        )
        if send_fn:
            try:
                await send_fn(alert_text)
            except Exception as e:
                log.error(f"[uncertainty] failed to alert admin: {e}")
        return alert_text


# Singleton
uncertainty_detector = UncertaintyDetector()
