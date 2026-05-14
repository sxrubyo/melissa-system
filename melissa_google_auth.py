"""melissa_google_auth.py — Google OAuth2 flow via WhatsApp chat."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlencode

import httpx

log = logging.getLogger("melissa.google_auth")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob")

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]

CREDENTIALS_DIR = Path("integrations/vault")


def get_oauth_url(instance_id: str = "default") -> Optional[str]:
    """Generate Google OAuth2 consent URL for the admin to click."""
    if not GOOGLE_CLIENT_ID:
        return None

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": instance_id,
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, instance_id: str = "default") -> Optional[Dict]:
    """Exchange authorization code for access + refresh tokens."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return None

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code.strip(),
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if r.status_code == 200:
            tokens = r.json()
            # Save tokens
            creds_dir = CREDENTIALS_DIR / instance_id
            creds_dir.mkdir(parents=True, exist_ok=True)
            creds_file = creds_dir / "google_calendar.json"
            creds_file.write_text(json.dumps(tokens, indent=2))
            log.info(f"[google_auth] tokens saved for {instance_id}")
            return tokens
        else:
            log.error(f"[google_auth] token exchange failed: {r.status_code} {r.text[:200]}")
            return None


async def refresh_access_token(instance_id: str = "default") -> Optional[str]:
    """Refresh the access token using stored refresh token."""
    creds_file = CREDENTIALS_DIR / instance_id / "google_calendar.json"
    if not creds_file.exists():
        return None

    tokens = json.loads(creds_file.read_text())
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return None

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if r.status_code == 200:
            new_tokens = r.json()
            tokens["access_token"] = new_tokens["access_token"]
            tokens["expires_in"] = new_tokens.get("expires_in", 3600)
            creds_file.write_text(json.dumps(tokens, indent=2))
            return new_tokens["access_token"]
        else:
            log.error(f"[google_auth] refresh failed: {r.status_code}")
            return None


def has_credentials(instance_id: str = "default") -> bool:
    """Check if instance has stored Google credentials."""
    creds_file = CREDENTIALS_DIR / instance_id / "google_calendar.json"
    return creds_file.exists()


def is_oauth_code(text: str) -> bool:
    """Detect if a message looks like a Google OAuth authorization code."""
    t = text.strip()
    # Google auth codes are typically 40-80 char alphanumeric with slashes
    if len(t) >= 20 and len(t) <= 120 and "/" in t:
        return True
    # Or the format 4/0A... that Google uses
    if t.startswith("4/") and len(t) > 30:
        return True
    return False
