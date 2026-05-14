"""melissa_google_auth.py — Google OAuth2 flow via WhatsApp chat.
OpenClaw-inspired: credentials live in vault files, NOT in .env.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlencode

import httpx

log = logging.getLogger("melissa.google_auth")

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]

VAULT_DIR = Path("integrations/vault")


def _load_google_creds(instance_id: str = "default") -> Dict[str, str]:
    """Load Google credentials from vault (OpenClaw pattern: vault > env)."""
    # Priority 1: Vault file (uploaded by admin)
    creds_file = VAULT_DIR / instance_id / "google_credentials.json"
    if creds_file.exists():
        try:
            data = json.loads(creds_file.read_text())
            inner = data.get("installed") or data.get("web") or data
            return {
                "client_id": inner.get("client_id", ""),
                "client_secret": inner.get("client_secret", ""),
                "redirect_uri": inner.get("redirect_uris", ["urn:ietf:wg:oauth:2.0:oob"])[0],
            }
        except Exception:
            pass

    # Priority 2: Environment variables (fallback)
    return {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob"),
    }


def get_oauth_url(instance_id: str = "default") -> Optional[str]:
    """Generate Google OAuth2 consent URL."""
    creds = _load_google_creds(instance_id)
    if not creds["client_id"]:
        return None

    params = {
        "client_id": creds["client_id"],
        "redirect_uri": creds["redirect_uri"],
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": instance_id,
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, instance_id: str = "default") -> Optional[Dict]:
    """Exchange authorization code for access + refresh tokens."""
    creds = _load_google_creds(instance_id)
    if not creds["client_id"] or not creds["client_secret"]:
        return None

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code.strip(),
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
                "redirect_uri": creds["redirect_uri"],
                "grant_type": "authorization_code",
            },
        )
        if r.status_code == 200:
            tokens = r.json()
            tokens_dir = VAULT_DIR / instance_id
            tokens_dir.mkdir(parents=True, exist_ok=True)
            (tokens_dir / "google_tokens.json").write_text(json.dumps(tokens, indent=2))
            log.info(f"[google_auth] tokens saved for {instance_id}")
            return tokens
        else:
            log.error(f"[google_auth] exchange failed: {r.status_code} {r.text[:200]}")
            return None


async def refresh_access_token(instance_id: str = "default") -> Optional[str]:
    """Refresh access token using stored refresh token."""
    tokens_file = VAULT_DIR / instance_id / "google_tokens.json"
    if not tokens_file.exists():
        return None

    tokens = json.loads(tokens_file.read_text())
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return None

    creds = _load_google_creds(instance_id)

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if r.status_code == 200:
            new_tokens = r.json()
            tokens["access_token"] = new_tokens["access_token"]
            tokens["expires_in"] = new_tokens.get("expires_in", 3600)
            tokens_file.write_text(json.dumps(tokens, indent=2))
            return new_tokens["access_token"]
        else:
            log.error(f"[google_auth] refresh failed: {r.status_code}")
            return None


async def get_access_token(instance_id: str = "default") -> Optional[str]:
    """Get a valid access token (refresh if needed)."""
    tokens_file = VAULT_DIR / instance_id / "google_tokens.json"
    if not tokens_file.exists():
        return None
    tokens = json.loads(tokens_file.read_text())
    # Always refresh to ensure valid token
    refreshed = await refresh_access_token(instance_id)
    return refreshed or tokens.get("access_token")


def has_credentials(instance_id: str = "default") -> bool:
    """Check if instance has Google OAuth credentials configured."""
    creds = _load_google_creds(instance_id)
    return bool(creds["client_id"])


def has_tokens(instance_id: str = "default") -> bool:
    """Check if instance has completed OAuth (has tokens)."""
    return (VAULT_DIR / instance_id / "google_tokens.json").exists()


def is_oauth_code(text: str) -> bool:
    """Detect if a message looks like a Google OAuth authorization code."""
    t = text.strip()
    if t.startswith("4/") and len(t) > 30:
        return True
    if len(t) >= 30 and len(t) <= 120 and "/" in t and " " not in t:
        return True
    return False
