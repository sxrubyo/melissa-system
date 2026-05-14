"""melissa_demo_voice.py — Voice cascade with ElevenLabs for demo mode."""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import List, Optional, Tuple

import httpx

log = logging.getLogger("melissa.demo_voice")

# Cascade of API keys — if first fails, try second
API_KEYS = [
    os.getenv("ELEVENLABS_API_KEY", "sk_e200c93fe4787b44dae55fdfe4e938d1f07ebbd2b0a67bb7"),
    os.getenv("ELEVENLABS_API_KEY_2", "sk_199e6c73c2adbdeedd746de08fbb3ec7e9067259c7210c50"),
]

# Female voices ranked by how natural/warm they sound in Spanish
# All free tier, tested for WhatsApp voice note quality
VOICE_CASCADE: List[Tuple[str, str]] = [
    ("cgSgspJ2msm6clMCkdW9", "Jessica"),   # Playful, Bright, Warm — young (best for Colombian)
    ("EXAVITQu4vr4xnSDxMaL", "Sarah"),     # Mature, Confident — young (backup)
    ("FGY2WhTYpPnrIDTdsKH5", "Laura"),      # Enthusiast, quirky — young (energetic)
    ("hpp4J3VqNfWAUOO0d1Us", "Bella"),      # Professional, Warm — middle_aged (formal fallback)
]

# Default: Jessica (most natural for Colombian Spanish)
DEFAULT_VOICE = VOICE_CASCADE[0][0]


async def generate_demo_audio(text: str, voice_idx: int = 0) -> Optional[str]:
    """Generate audio with cascade: try key1 → key2, voice1 → voice2 → voice3."""
    if not any(API_KEYS):
        return None

    # Try each API key
    for key in API_KEYS:
        if not key:
            continue
        # Try voices in order
        for vid, vname in VOICE_CASCADE[voice_idx:voice_idx + 2]:
            result = await _try_generate(text, key, vid)
            if result:
                log.info(f"[demo_voice] generated with {vname} ({vid[:8]}...)")
                return result
            log.debug(f"[demo_voice] {vname} failed with key ...{key[-6:]}, trying next")

    log.warning("[demo_voice] all keys/voices exhausted")
    return None


async def _try_generate(text: str, api_key: str, voice_id: str) -> Optional[str]:
    """Single attempt to generate audio."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": "eleven_flash_v2_5",
                    "voice_settings": {
                        "stability": 0.35,          # Lower = more natural variation
                        "similarity_boost": 0.70,
                        "style": 0.25,              # Subtle expressiveness
                        "use_speaker_boost": True,
                    },
                },
            )
            if r.status_code == 200 and len(r.content) > 1000:
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp.write(r.content)
                tmp.close()
                return tmp.name
            elif r.status_code == 401:
                log.debug(f"[demo_voice] key unauthorized")
                return None
            elif r.status_code == 429:
                log.debug(f"[demo_voice] rate limited")
                return None
            else:
                log.debug(f"[demo_voice] HTTP {r.status_code}: {r.text[:100]}")
                return None
    except Exception as e:
        log.debug(f"[demo_voice] error: {e}")
        return None


def should_send_voice_in_demo(text: str, turn_number: int, has_business_name: bool) -> bool:
    """Decide when to send voice in demo — strategic moments only."""
    # First greeting: ALWAYS voice (immediate wow)
    if turn_number <= 1:
        return True

    # After getting business name and entering character
    if has_business_name and turn_number <= 4:
        return True

    # Patient simulation responses (showing the product)
    if turn_number >= 3 and len(text) < 150:
        return True

    # Never spam voice — max every 3 turns
    if turn_number > 5 and turn_number % 3 != 0:
        return False

    return False


# Conversion hooks for demo closing
DEMO_CLOSING_TRIGGERS = [
    "como activo", "cómo activo", "como lo contrato", "cómo contrato",
    "cuanto cuesta", "cuánto cuesta", "precio", "planes",
    "me interesa", "lo quiero", "activar", "contratar",
]


def detect_buying_intent(text: str) -> bool:
    """Detect if prospect wants to buy."""
    return any(t in text.lower() for t in DEMO_CLOSING_TRIGGERS)


def get_closing_response() -> str:
    """When prospect wants to buy, close with Santiago's contact."""
    return (
        "me alegra que te haya gustado la demo! |||"
        " para activarlo en tu negocio, Santiago te explica todo: 3124348669 |||"
        " la activación es rápida, en menos de 5 minutos ya estoy respondiendo tu WhatsApp"
    )
