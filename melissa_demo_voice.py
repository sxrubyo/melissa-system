"""melissa_demo_voice.py — Voice-enhanced demo mode for maximum conversion."""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Optional

log = logging.getLogger("melissa.demo_voice")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")  # Bella - warm female


async def generate_demo_audio(text: str) -> Optional[str]:
    """Generate audio for demo using ElevenLabs. Returns path to mp3 or None."""
    api_key = ELEVENLABS_API_KEY or os.getenv("ELEVENLABS_API_KEY", "")
    if not api_key:
        return None

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": "eleven_flash_v2_5",
                    "voice_settings": {
                        "stability": 0.40,
                        "similarity_boost": 0.75,
                        "style": 0.30,
                        "use_speaker_boost": True,
                    },
                },
            )
            if r.status_code == 200:
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp.write(r.content)
                tmp.close()
                log.info(f"[demo_voice] generated audio: {len(r.content)} bytes")
                return tmp.name
            else:
                log.warning(f"[demo_voice] ElevenLabs {r.status_code}: {r.text[:100]}")
                return None
    except Exception as e:
        log.error(f"[demo_voice] error: {e}")
        return None


def should_send_voice_in_demo(text: str, turn_number: int, has_business_name: bool) -> bool:
    """Decide if this demo message should be sent as audio for maximum impact."""
    # First greeting: ALWAYS voice (wow factor)
    if turn_number <= 1:
        return True

    # When Melissa shows she understood the business: voice (personalization wow)
    if has_business_name and turn_number <= 3:
        return True

    # Simulated patient response: voice (shows how real it sounds)
    if "como si fuera" in text.lower() or "simul" in text.lower():
        return True

    # Short impactful messages
    if len(text) < 100 and turn_number <= 5:
        return True

    return False


# Demo conversion hooks - messages designed to close
DEMO_HOOKS = {
    "after_name": [
        "ya busqué tu negocio en internet y vi de qué se trata",
        "listo, ya me metí en personaje",
        "escríbeme como si fueras un cliente tuyo y te muestro cómo respondo",
    ],
    "after_simulation": [
        "eso es exactamente lo que recibiría tu cliente real",
        "y eso fue sin entrenarme — imagínate cuando me pases tus precios y horarios",
        "quieres ver más o hablamos de cómo activarlo para tu negocio?",
    ],
    "closing": [
        "la activación es inmediata — en 5 minutos ya estoy respondiendo tu WhatsApp",
        "Santiago te puede contar los planes: 3124348669",
        "o si quieres, le digo a Santiago que te escriba?",
    ],
}
