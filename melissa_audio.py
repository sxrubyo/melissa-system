"""
Módulo de manejo de audio/transcripción para Melissa Ultra.

Contiene la lógica de:
- Transcripción de audio con Gemini 2.0 Flash (primario)
- Fallback a Groq Whisper
- Fallback a OpenRouter Whisper
- Manejo de diferentes plataformas (Telegram, WhatsApp, WhatsApp Cloud)

Este módulo fue extraído de melissa.py para reducir su tamaño y mejorar mantenibilidad.
"""
from __future__ import annotations

import base64
import os
import tempfile
from typing import Optional, Tuple

import httpx

try:
    from melissa_config import Config
except ImportError:
    class Config:
        TELEGRAM_TOKEN = ""
        WA_ACCESS_TOKEN = ""
        GEMINI_API_KEY = ""
        GEMINI_API_KEY_2 = ""
        GEMINI_API_KEY_3 = ""
        GEMINI_API_KEY_4 = ""
        GEMINI_API_KEY_5 = ""
        GEMINI_API_KEY_6 = ""
        GEMINI_API_KEYS = []
        GROQ_API_KEY = ""
        OPENROUTER_API_KEY = ""


class AudioHandler:
    """
    Manejador de audio y transcripción para Melissa Ultra.
    
    Proporciona transcripción de audio con múltiples proveedores:
    - Gemini 2.0 Flash (primario, mayor comprensión de contexto)
    - Groq Whisper (fallback 1)
    - OpenRouter Whisper (fallback 2)
    """
    
    def __init__(self):
        self._audio_cache: dict = {}
    
    def _audio_suffix(self, mime: str) -> str:
        """Mapea mime type a extensión de archivo."""
        mapping = {
            "audio/ogg": ".ogg",
            "audio/oga": ".ogg",
            "audio/opus": ".ogg",
            "audio/mp3": ".mp3",
            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/mp4": ".m4a",
            "audio/x-m4a": ".m4a",
            "audio/webm": ".webm",
        }
        return mapping.get((mime or "").lower(), ".ogg")
    
    async def transcribe_audio(
        self, 
        file_id: str, 
        platform: str = "telegram",
        wa_media_id: str = None
    ) -> str:
        """
        Transcribe audio con Gemini 2.0 Flash (nativo) → fallback Whisper.
        Gemini no solo transcribe — entiende contexto y tono coloquial.
        
        Args:
            file_id: ID del archivo de audio
            platform: Plataforma de origen (telegram, whatsapp, whatsapp_cloud)
            wa_media_id: ID de media de WhatsApp Cloud (si aplica)
            
        Returns:
            Texto transcrito o mensaje de error
        """
        audio_bytes, mime_type = None, "audio/ogg"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if platform == "telegram":
                    r = await client.get(
                        f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/getFile",
                        params={"file_id": file_id}
                    )
                    fp = r.json()["result"]["file_path"]
                    ext = fp.rsplit(".", 1)[-1].lower() if "." in fp else "ogg"
                    mime_type = {
                        "ogg": "audio/ogg", "mp3": "audio/mp3", "wav": "audio/wav",
                        "m4a": "audio/mp4", "oga": "audio/ogg", "opus": "audio/ogg"
                    }.get(ext, "audio/ogg")
                    ar = await client.get(
                        f"https://api.telegram.org/file/bot{Config.TELEGRAM_TOKEN}/{fp}"
                    )
                    audio_bytes = ar.content
                    
                elif platform == "whatsapp_cloud" and wa_media_id:
                    mr = await client.get(
                        f"https://graph.facebook.com/v20.0/{wa_media_id}",
                        headers={"Authorization": f"Bearer {Config.WA_ACCESS_TOKEN}"}
                    )
                    url = mr.json().get("url", "")
                    if url:
                        dl = await client.get(
                            url, 
                            headers={"Authorization": f"Bearer {Config.WA_ACCESS_TOKEN}"}
                        )
                        audio_bytes, mime_type = (
                            dl.content, 
                            mr.json().get("mime_type", "audio/ogg")
                        )

            # WhatsApp Bridge (Baileys) — audio base64 inline
            if platform == "whatsapp" and file_id.startswith("wa_b64:"):
                try:
                    _, mime_part, b64_data = file_id.split(":", 2)
                    mime_type = mime_part or "audio/ogg"
                    audio_bytes = base64.b64decode(b64_data)
                except Exception:
                    return "[no pude escuchar, puedes escribirlo?]"

            if not audio_bytes:
                return "[no pude escuchar, puedes escribirlo?]"

            # Intentar transcripción con Gemini 2.0 Flash
            result = await self._transcribe_gemini(audio_bytes, mime_type)
            if result:
                return result
            
            # Fallback 1: Groq Whisper
            result = await self._transcribe_groq_whisper(audio_bytes, mime_type)
            if result:
                return result
            
            # Fallback 2: OpenRouter Whisper
            result = await self._transcribe_openrouter_whisper(audio_bytes, mime_type)
            if result:
                return result

            return "[no se pudo transcribir el audio]"
            
        except Exception as e:
            import logging
            log = logging.getLogger("melissa_audio")
            log.error(f"[audio] Error: {e}", exc_info=True)
            return "[no pude escuchar, puedes escribirlo?]"
    
    async def _transcribe_gemini(self, audio_bytes: bytes, mime_type: str) -> Optional[str]:
        """Transcribe usando Gemini 2.0 Flash."""
        import logging
        log = logging.getLogger("melissa_audio")
        
        effective_mime = "audio/ogg" if mime_type in ("audio/oga", "audio/opus") else mime_type
        
        gemini_keys = Config.GEMINI_API_KEYS or [
            k for k in [
                Config.GEMINI_API_KEY,
                Config.GEMINI_API_KEY_2,
                Config.GEMINI_API_KEY_3,
                Config.GEMINI_API_KEY_4,
                Config.GEMINI_API_KEY_5,
                Config.GEMINI_API_KEY_6,
            ] if k
        ]
        
        for gkey in gemini_keys:
            try:
                b64 = base64.b64encode(audio_bytes).decode()
                payload = {
                    "contents": [{
                        "parts": [
                            {"inline_data": {"mime_type": effective_mime, "data": b64}},
                            {
                                "text": "Transcribe este mensaje de voz en español exactamente "
                                        "como se dice. Devuelve SOLO el texto transcrito, sin "
                                        "comillas ni comentarios. Mantén el tono coloquial tal como se habla."
                            }
                        ]
                    }],
                    "generationConfig": {"temperature": 0.0, "maxOutputTokens": 500}
                }
                
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/"
                        f"gemini-2.5-flash:generateContent?key={gkey}",
                        json=payload
                    )
                    
                if resp.status_code == 200:
                    parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
                    t = parts[0].get("text", "").strip() if parts else ""
                    if t and len(t) > 2:
                        log.info(f"[audio] Gemini OK: {t[:80]}")
                        return t
                elif resp.status_code in (408, 429, 500, 502, 503, 504):
                    continue  # rotar key
                else:
                    log.warning(f"[audio] Gemini {resp.status_code}: {resp.text[:120]}")
                    continue
                    
            except Exception as eg:
                log.warning(f"[audio] Gemini error: {eg}")
                continue
        
        return None
    
    async def _transcribe_groq_whisper(
        self, 
        audio_bytes: bytes, 
        mime_type: str
    ) -> Optional[str]:
        """Transcribe usando Groq Whisper (fallback 1)."""
        import logging
        log = logging.getLogger("melissa_audio")
        
        if not Config.GROQ_API_KEY:
            return None
        
        tmp_path = None
        try:
            suffix = self._audio_suffix(mime_type)
            filename = f"audio{suffix}"
            
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                with open(tmp_path, "rb") as f:
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}"},
                        files={"file": (filename, f, mime_type)},
                        data={
                            "model": "whisper-large-v3-turbo",
                            "language": "es",
                            "response_format": "json",
                            "temperature": "0",
                            "prompt": "Transcribe este audio en español tal como se dice, sin comentarios adicionales.",
                        },
                    )
            
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
            if resp.status_code == 200:
                payload = resp.json()
                t = (payload.get("text") or "").strip()
                if t:
                    log.info(f"[audio] Groq Whisper OK: {t[:80]}")
                    return t
            else:
                log.warning(f"[audio] Groq Whisper {resp.status_code}: {resp.text[:160]}")
                
        except Exception as eg:
            log.warning(f"[audio] Groq Whisper error: {eg}")
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        
        return None
    
    async def _transcribe_openrouter_whisper(
        self, 
        audio_bytes: bytes, 
        mime_type: str
    ) -> Optional[str]:
        """Transcribe usando OpenRouter Whisper (fallback 2)."""
        import logging
        log = logging.getLogger("melissa_audio")
        
        if not Config.OPENROUTER_API_KEY:
            return None
        
        tmp_path = None
        try:
            suffix = self._audio_suffix(mime_type)
            filename = f"audio{suffix}"
            
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                with open(tmp_path, "rb") as f:
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {Config.OPENROUTER_API_KEY}"},
                        files={"file": (filename, f, mime_type)},
                        data={
                            "model": getattr(Config, "WHISPER_MODEL", "openai/whisper-large-v3"),
                            "language": "es",
                        },
                    )
            
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
            if resp.status_code == 200:
                t = resp.json().get("text", "").strip()
                if t:
                    log.info(f"[audio] Whisper OK: {t[:80]}")
                    return t
            else:
                log.warning(f"[audio] OpenRouter Whisper {resp.status_code}: {resp.text[:160]}")
                
        except Exception as ew:
            log.warning(f"[audio] Whisper error: {ew}")
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        
        return None
    
    def clear_cache(self) -> None:
        """Limpia la caché de audio."""
        self._audio_cache.clear()


async def transcribe_audio(
    file_id: str, 
    platform: str = "telegram",
    wa_media_id: str = None
) -> str:
    """
    Función de conveniencia para transcripción de audio.
    
    Args:
        file_id: ID del archivo de audio
        platform: Plataforma de origen
        wa_media_id: ID de media de WhatsApp Cloud
        
    Returns:
        Texto transcrito o mensaje de error
    """
    handler = AudioHandler()
    return await handler.transcribe_audio(file_id, platform, wa_media_id)