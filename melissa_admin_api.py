"""
Melissa Admin API — Multi-tenant runtime configuration endpoints.

Mounted at /admin on the main FastAPI app.
"""

import json
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

log = logging.getLogger("melissa.admin_api")

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _get_admin_key() -> str:
    return os.environ.get("ADMIN_API_KEY") or os.environ.get("MASTER_API_KEY", "")


def _verify_auth(x_admin_key: Optional[str] = None):
    expected = _get_admin_key()
    if not expected:
        raise HTTPException(status_code=500, detail="ADMIN_API_KEY not configured")
    if x_admin_key != expected:
        raise HTTPException(status_code=401, detail="Invalid admin key")


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class PersonaUpdate(BaseModel):
    tone: str = "professional"
    verbosity: str = "concise"
    greeting_style: str = "warm"
    sign_off: str = ""
    forbidden_topics: List[str] = Field(default_factory=list)
    escalation_phrases: List[str] = Field(default_factory=list)


class ModelUpdate(BaseModel):
    provider: str = "anthropic"
    model_id: str = "claude-sonnet-4-20250514"
    temperature: float = 0.7
    max_tokens: int = 1024
    thinking_budget: int = 0


class TeachRequest(BaseModel):
    question: str
    answer: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_DIR = Path(__file__).resolve().parent
_PERSONAS_DIR = _BASE_DIR / "personas"
_MODEL_CONFIG_DIR = _BASE_DIR / "model_configs"
_KNOWLEDGE_GAPS_DIR = _BASE_DIR / "knowledge_gaps"
_TEACHINGS_DIR = _BASE_DIR / "teachings"


def _read_jsonl(path: Path, limit: int = 100) -> list:
    """Read last N lines from a JSONL file."""
    if not path.exists():
        return []
    lines = path.read_text().strip().splitlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/{instance_id}/persona")
async def update_persona(
    instance_id: str,
    body: PersonaUpdate,
    x_admin_key: Optional[str] = Header(None),
):
    """Update personality/persona at runtime for a given instance."""
    _verify_auth(x_admin_key)

    persona_dir = _PERSONAS_DIR / instance_id
    persona_dir.mkdir(parents=True, exist_ok=True)

    override_path = persona_dir / "runtime_override.json"
    payload = body.model_dump()
    payload["updated_at"] = datetime.now().isoformat()

    override_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    log.info(f"[admin] persona updated for {instance_id}")

    return {"ok": True, "applied": payload}


@router.post("/{instance_id}/model")
async def update_model(
    instance_id: str,
    body: ModelUpdate,
    x_admin_key: Optional[str] = Header(None),
):
    """Change LLM provider/model configuration at runtime."""
    _verify_auth(x_admin_key)

    _MODEL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_path = _MODEL_CONFIG_DIR / f"{instance_id}.json"

    payload = body.model_dump()
    payload["updated_at"] = datetime.now().isoformat()

    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    log.info(f"[admin] model config updated for {instance_id}: {body.provider}/{body.model_id}")

    return {"ok": True, "model": payload}


@router.get("/{instance_id}/status")
async def get_status(
    instance_id: str,
    x_admin_key: Optional[str] = Header(None),
):
    """Get current config and recent knowledge gaps for an instance."""
    _verify_auth(x_admin_key)

    # Read persona override
    persona_path = _PERSONAS_DIR / instance_id / "runtime_override.json"
    persona = {}
    if persona_path.exists():
        try:
            persona = json.loads(persona_path.read_text())
        except json.JSONDecodeError:
            persona = {"error": "corrupt persona file"}

    # Read model config
    model_path = _MODEL_CONFIG_DIR / f"{instance_id}.json"
    model = {}
    if model_path.exists():
        try:
            model = json.loads(model_path.read_text())
        except json.JSONDecodeError:
            model = {"error": "corrupt model config file"}

    # Read recent gaps
    today = datetime.now().strftime("%Y-%m-%d")
    gap_file = _KNOWLEDGE_GAPS_DIR / f"{today}.jsonl"
    all_gaps = _read_jsonl(gap_file, limit=200)
    instance_gaps = [g for g in all_gaps if g.get("instance_id") == instance_id][-10:]

    return {
        "instance_id": instance_id,
        "persona": persona,
        "model": model,
        "recent_gaps": instance_gaps,
        "gaps_today": len(instance_gaps),
    }


@router.get("/{instance_id}/gaps")
async def get_gaps(
    instance_id: str,
    x_admin_key: Optional[str] = Header(None),
    limit: int = 50,
):
    """Get knowledge gaps log for an instance."""
    _verify_auth(x_admin_key)

    _KNOWLEDGE_GAPS_DIR.mkdir(parents=True, exist_ok=True)

    # Collect from recent JSONL files
    gap_files = sorted(_KNOWLEDGE_GAPS_DIR.glob("*.jsonl"), reverse=True)[:7]
    all_gaps: list = []

    for gf in gap_files:
        entries = _read_jsonl(gf, limit=500)
        instance_entries = [e for e in entries if e.get("instance_id") == instance_id]
        all_gaps.extend(instance_entries)
        if len(all_gaps) >= limit:
            break

    all_gaps = all_gaps[:limit]

    return {
        "instance_id": instance_id,
        "total": len(all_gaps),
        "gaps": all_gaps,
    }


@router.post("/{instance_id}/teach")
async def teach_fact(
    instance_id: str,
    body: TeachRequest,
    x_admin_key: Optional[str] = Header(None),
):
    """Admin teaches Melissa a new fact (question/answer pair)."""
    _verify_auth(x_admin_key)

    _TEACHINGS_DIR.mkdir(parents=True, exist_ok=True)
    teachings_file = _TEACHINGS_DIR / f"{instance_id}.jsonl"

    entry = {
        "ts": datetime.now().isoformat(),
        "question": body.question,
        "answer": body.answer,
    }

    with open(teachings_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    log.info(f"[admin] new teaching for {instance_id}: Q='{body.question[:60]}'")

    return {
        "ok": True,
        "instance_id": instance_id,
        "taught": entry,
    }
