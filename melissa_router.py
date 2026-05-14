#!/usr/bin/env python3
"""
melissa_router.py — Webhook handlers and command routing.
Extracted from melissa.py for Phase 3 split.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from melissa_config import Config, DEMO_CMD_ALIASES, DEMO_COMMANDS, DEMO_HELP_FULL

log = logging.getLogger("melissa.router")


# ── Platform Detection ─────────────────────────────────────────────────────────

def detect_incoming_platform(body: Dict[str, Any]) -> str:
    """Detect which platform sent the message."""
    if body.get("entry"):
        entry = body["entry"][0] if body["entry"] else {}
        changes = entry.get("changes", [{}])[0] if entry.get("changes") else {}
        value = changes.get("value", {})
        if value.get("messages"):
            return "whatsapp_cloud"
        if value.get("statuses"):
            return "whatsapp_cloud"
    if body.get("message") or body.get("edited_message"):
        return "telegram"
    if body.get("data", {}).get("key", {}).get("fromMe"):
        return "evolution"
    if body.get("iswa"):
        return "whatsapp"
    return "unknown"


# ── Command Detection ──────────────────────────────────────────────────────────

def detect_command(text: str) -> Optional[str]:
    """Detect if text is a command (slash or natural language alias)."""
    if not text:
        return None
    text_norm = text.lower().strip()

    # Slash commands
    if text_norm.startswith("/"):
        return text_norm

    # Natural language aliases
    for alias, cmd in DEMO_CMD_ALIASES.items():
        if text_norm == alias or text_norm == "/" + alias:
            return "/" + cmd

    return None


# ── Full Command Handler (moved from enqueue_message) ────────────────────────

def handle_command(
    chat_id: str,
    text: str,
    demo_sessions: Dict[str, Any],
    send_fn,
) -> Optional[List[str]]:
    """
    Handle commands BEFORE session lookup.
    Returns a list of response strings, or None if not a command.
    """
    cmd = text.strip()
    if not cmd.startswith("/"):
        return None

    # /help — show all commands
    if cmd in ("/help", "/ayuda", "/comandos"):
        bn = demo_sessions.get(chat_id + "_name", "")
        if bn:
            return [DEMO_HELP_FULL]
        return [
            "Comandos: /help | /reset | /bot | /status | /memoria"
        ]

    # /reset
    if cmd in ("/reset", "/reiniciar"):
        keys_del = [k for k in list(demo_sessions) if k.startswith(chat_id + "_") and not k.endswith("_ts")]
        for k in keys_del:
            try:
                del demo_sessions[k]
            except Exception:
                pass
        return ["listo, sesión limpia ||| empezamos de nuevo"]

    # /status
    if cmd in ("/status", "/estado"):
        bn = demo_sessions.get(chat_id + "_name", "")
        return [f"Estado: {'demo activa' if bn else 'en onboarding'} ||| negocio: {bn or 'sin nombre'}"]

    # /bot
    if cmd in ("/bot", "/recepcionista"):
        return ["modo recepcionista ||| háblame como cliente y te respondo en contexto"]

    # /memoria
    if cmd in ("/memoria",):
        return ["no tengo memoria activa todavía ||| en la próxima versión lo tendre"]

    return None


# ── Webhook Parser: Telegram ────────────────────────────────────────────────────

def parse_telegram_message(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse Telegram webhook body into standard message format."""
    msg = body.get("message") or body.get("edited_message")
    if not msg:
        return None

    chat = msg.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    if not chat_id:
        return None

    voice = msg.get("voice") or msg.get("audio")
    audio_id = voice.get("file_id") if voice else None

    document = msg.get("document")
    photos = msg.get("photo") or []
    caption = msg.get("caption", "").strip()

    attachments = []
    if document:
        attachments.append({
            "kind": "document",
            "platform": "telegram",
            "file_id": document.get("file_id", ""),
            "filename": document.get("file_name", "document.bin"),
            "mime_type": document.get("mime_type", "application/octet-stream"),
            "caption": caption,
        })
    if photos:
        photo = photos[-1]
        attachments.append({
            "kind": "image",
            "platform": "telegram",
            "file_id": photo.get("file_id", ""),
            "filename": f"telegram_photo_{photo.get('file_unique_id', 'image')}.jpg",
            "mime_type": "image/jpeg",
            "caption": caption,
        })

    text = msg.get("text", "").strip() or caption

    return {
        "chat_id": chat_id,
        "text": text,
        "audio_id": audio_id,
        "attachments": attachments,
        "platform": "telegram",
    }


# ── Webhook Parser: WhatsApp Cloud ─────────────────────────────────────────────

def parse_whatsapp_cloud_message(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse WhatsApp Cloud API webhook body."""
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        msgs = value.get("messages", [])
        if not msgs:
            return None
        msg = msgs[0]
        chat_id = msg.get("from", "")
        msg_type = msg.get("type", "text")

        attachments = []
        text = None
        audio_id = None

        if msg_type == "text":
            text = msg.get("text", {}).get("body", "").strip()
        elif msg_type in ("audio", "voice"):
            audio_id = msg.get("audio", msg.get("voice", {})).get("id", "")
        elif msg_type == "image":
            attachments.append({
                "kind": "image",
                "platform": "whatsapp_cloud",
                "media_id": msg.get("image", {}).get("id", ""),
                "filename": f"wa_cloud_image_{msg.get('id', 'image')}.jpg",
                "mime_type": msg.get("image", {}).get("mime_type", "image/jpeg"),
                "caption": msg.get("image", {}).get("caption", ""),
            })
            text = msg.get("image", {}).get("caption", "").strip()
        elif msg_type == "document":
            attachments.append({
                "kind": "document",
                "platform": "whatsapp_cloud",
                "media_id": msg.get("document", {}).get("id", ""),
                "filename": msg.get("document", {}).get("filename", f"wa_cloud_{msg.get('id', 'document')}"),
                "mime_type": msg.get("document", {}).get("mime_type", "application/octet-stream"),
                "caption": msg.get("document", {}).get("caption", ""),
            })
            text = msg.get("document", {}).get("caption", "").strip()

        return {
            "chat_id": chat_id,
            "text": text,
            "audio_id": audio_id,
            "attachments": attachments,
            "platform": "whatsapp_cloud",
        }
    except (IndexError, KeyError, TypeError):
        return None


# ── Webhook Parser: WhatsApp Bridge ───────────────────────────────────────────

def parse_whatsapp_bridge_message(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse WhatsApp Bridge (Baileys) webhook body."""
    try:
        chat_id = body.get("key", {}).get("remoteJid", "")
        if not chat_id:
            return None
        if chat_id.endswith("@g.us"):
            return None  # Skip group chats

        attachments = []
        text = body.get("message", {}).get("conversationMessage", {}).get("conversation", "").strip()

        if body.get("isImage") and body.get("imageBase64"):
            attachments.append({
                "kind": "image",
                "platform": "whatsapp",
                "filename": f"wa_bridge_{body.get('messageId', 'image')}.jpg",
                "mime_type": body.get("imageMime", "image/jpeg"),
                "caption": text or "",
                "base64": body.get("imageBase64", ""),
            })
            text = ""

        if body.get("isDocument") and body.get("docBase64"):
            attachments.append({
                "kind": "document",
                "platform": "whatsapp",
                "filename": body.get("docName", f"wa_doc_{body.get('messageId', 'doc')}"),
                "mime_type": body.get("docMime", "application/octet-stream"),
                "caption": text or "",
                "base64": body.get("docBase64", ""),
            })
            text = ""

        audio_id = None
        if body.get("isAudio") and body.get("audioBase64"):
            b64_mime = body.get("audioMime", "audio/ogg")
            audio_id = f"wa_b64:{b64_mime}:{body['audioBase64']}"

        return {
            "chat_id": chat_id,
            "text": text,
            "audio_id": audio_id,
            "attachments": attachments,
            "platform": "whatsapp",
        }
    except Exception:
        return None


# ── Full Webhook Parser ─────────────────────────────────────────────────────────

def parse_webhook(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse any webhook body into standard format."""
    platform = detect_incoming_platform(body)

    if platform == "telegram":
        return parse_telegram_message(body)
    elif platform == "whatsapp_cloud":
        return parse_whatsapp_cloud_message(body)
    elif platform == "whatsapp":
        return parse_whatsapp_bridge_message(body)
    elif platform == "evolution":
        try:
            data = body.get("data", {})
            key = data.get("key", {})
            if key.get("fromMe", False):
                return None
            chat_id = key.get("remoteJid", "")
            msg_data = data.get("message", {})
            conv = msg_data.get("conversationMessage", {}).get("conversation", "").strip()
            ext = msg_data.get("extendedTextMessage", {})
            text = conv or ext.get("text", "").strip() or ""
            return {
                "chat_id": chat_id,
                "text": text,
                "audio_id": None,
                "attachments": [],
                "platform": "evolution",
            }
        except Exception:
            return None

    return None