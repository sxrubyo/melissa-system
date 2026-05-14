"""melissa_audio_learn.py — Transcribe admin audio → auto-learn."""
from __future__ import annotations
import logging, os, tempfile, base64
from pathlib import Path
from typing import Optional
import httpx

log = logging.getLogger("melissa.audio_learn")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


async def transcribe_audio(audio_data: bytes, mime_type: str = "audio/ogg") -> Optional[str]:
    """Transcribe audio bytes using Groq Whisper API."""
    if not GROQ_API_KEY:
        # Fallback: try reading from .env at runtime
        key = os.getenv("GROQ_API_KEY", "")
        if not key:
            log.warning("[audio_learn] no GROQ_API_KEY")
            return None
    else:
        key = GROQ_API_KEY

    ext = {"audio/ogg": ".ogg", "audio/mp4": ".m4a", "audio/mpeg": ".mp3",
           "audio/wav": ".wav", "audio/webm": ".webm"}.get(mime_type, ".ogg")

    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp.write(audio_data)
    tmp.close()

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(tmp.name, "rb") as f:
                r = await client.post(
                    GROQ_WHISPER_URL,
                    headers={"Authorization": f"Bearer {key}"},
                    files={"file": (f"audio{ext}", f, mime_type)},
                    data={"model": "whisper-large-v3", "language": "es"},
                )
            if r.status_code == 200:
                text = r.json().get("text", "").strip()
                log.info(f"[audio_learn] transcribed {len(audio_data)} bytes → {len(text)} chars")
                return text
            else:
                log.error(f"[audio_learn] Groq returned {r.status_code}: {r.text[:200]}")
                return None
    except Exception as e:
        log.error(f"[audio_learn] transcription error: {e}")
        return None
    finally:
        os.unlink(tmp.name)


async def process_admin_audio(audio_data: bytes, mime_type: str, instance_id: str, chat_id: str) -> Optional[str]:
    """Full pipeline: transcribe → save to soul + teachings."""
    text = await transcribe_audio(audio_data, mime_type)
    if not text or len(text) < 10:
        return None

    # Save to soul
    soul_dir = Path(f"soul/{instance_id}")
    soul_dir.mkdir(parents=True, exist_ok=True)
    soul_file = soul_dir / "knowledge.md"
    from datetime import datetime
    with open(soul_file, "a") as f:
        f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] [audio del admin]\n{text[:2000]}\n")

    # Save to teachings (split into sentences for better retrieval)
    teachings_dir = Path("teachings")
    teachings_dir.mkdir(exist_ok=True)
    import json
    teachings_file = teachings_dir / f"{instance_id}.jsonl"
    with open(teachings_file, "a") as f:
        f.write(json.dumps({
            "ts": datetime.now().isoformat(),
            "question": "[audio del admin] " + text[:100],
            "answer": text[:500],
            "taught_by": chat_id,
            "source": "audio_transcription",
        }, ensure_ascii=False) + "\n")

    log.info(f"[audio_learn] saved audio teaching for {instance_id}: {text[:60]}...")
    return text
