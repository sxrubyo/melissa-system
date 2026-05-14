"""melissa_voice_engine.py — ElevenLabs voice with intelligent audio triggers."""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("melissa.voice_engine")

BOOKING_KEYWORDS = ["confirmad", "agendad", "reservad", "cita quedó", "quedó para"]
EMPATHY_KEYWORDS = ["dolor", "angustia", "urgente", "miedo", "preocup", "asust", "llor", "fiebre", "grave"]
FAREWELL_KEYWORDS = ["chao", "gracias", "hasta luego", "bendiciones", "bye", "adiós", "nos vemos"]


class MelissaVoiceEngine:
    """
    Smart voice engine. Only sends audio when it has high conversion impact.
    Gracefully disabled if no ELEVENLABS_API_KEY is set.
    """

    def __init__(self, instance_id: str = "default"):
        self.instance_id = instance_id
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        self.enabled = bool(self.api_key)
        self._client = None
        self._recent_audio_count = 0

    def _get_client(self):
        if not self._client and self.enabled:
            try:
                from elevenlabs.client import ElevenLabs
                self._client = ElevenLabs(api_key=self.api_key)
            except ImportError:
                log.warning("[voice_engine] elevenlabs package not installed")
                self.enabled = False
        return self._client

    async def should_send_audio(self, response: str, context: Dict, history: List) -> Tuple[bool, str]:
        if not self.enabled:
            return False, "disabled"
        if context.get("user_sent_audio"):
            return True, "reciprocity"
        if self._recent_audio_count >= 1:
            return False, "cooldown"
        if len(response.strip()) < 20:
            return False, "too_short"
        if len(response.strip()) > 300:
            return False, "too_long"

        response_low = response.lower()
        if any(kw in response_low for kw in BOOKING_KEYWORDS):
            return True, "booking_confirmed"

        user_msg = ""
        for m in reversed(history[-5:]):
            if m.get("role") == "user":
                user_msg = m.get("content", "").lower()
                break
        if any(kw in user_msg for kw in EMPATHY_KEYWORDS):
            return True, "empathy_required"
        if any(kw in response_low for kw in FAREWELL_KEYWORDS):
            return True, "farewell"
        if context.get("is_first_turn") and len(history) <= 2:
            return True, "welcome_new_user"

        return False, "no_trigger"

    async def text_to_audio(self, text: str) -> Optional[str]:
        if not self.enabled:
            return None
        client = self._get_client()
        if not client:
            return None
        try:
            from elevenlabs import VoiceSettings
            audio = client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id="eleven_flash_v2_5",
                output_format="mp3_44100_128",
                voice_settings=VoiceSettings(
                    stability=0.45,
                    similarity_boost=0.80,
                    style=0.35,
                    use_speaker_boost=True,
                ),
            )
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            for chunk in audio:
                tmp.write(chunk)
            tmp.close()
            self._recent_audio_count += 1
            return tmp.name
        except Exception as e:
            log.error(f"[voice_engine] TTS error: {e}")
            return None

    async def process_response(self, response: str, context: Dict, history: List,
                               send_text_fn=None, send_audio_fn=None):
        if not self.enabled or not send_audio_fn:
            if send_text_fn:
                await send_text_fn(response)
            return

        send_audio, reason = await self.should_send_audio(response, context, history)
        if send_audio:
            log.info(f"[voice_engine] sending audio [{reason}]: {response[:50]}...")
            audio_path = await self.text_to_audio(response)
            if audio_path:
                await send_audio_fn(audio_path)
                os.unlink(audio_path)
                if send_text_fn:
                    await asyncio.sleep(0.8)
                    await send_text_fn(f"_{response}_")
            elif send_text_fn:
                await send_text_fn(response)
        elif send_text_fn:
            await send_text_fn(response)

    def reset_cooldown(self):
        self._recent_audio_count = 0
