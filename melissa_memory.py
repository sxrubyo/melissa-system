#!/usr/bin/env python3
"""
melissa_memory.py — Persistent memory system for Melissa multi-tenant instances.
Inspired by OpenClaw memory architecture, built for business use.

File structure per instance:
  instances/{instance_id}/
    knowledge/
      MEMORY.md       ← master memory (loaded on every conversation)
      servicios.md    ← what the business offers
      precios.md      ← pricing
      faqs.md         ← frequently asked questions
      objeciones.md   ← objections heard + resolutions
      sector.md       ← industry context and tone rules
    learned/
      escalaciones/
        {YYYY-MM-DD}/
          {timestamp}.md   ← each escalation
      patrones/
        {YYYY-MM}.md       ← monthly patterns
    persona/
      tono.md              ← tone rules
      personalidad.md      ← persona config
    session_cache/
      {chat_id}.json       ← last 20 messages per contact
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("melissa.memory")


class MelissaMemory:

    def __init__(self, instance_id: str = "default"):
        self.instance_id = instance_id
        self.base = Path(f"instances/{instance_id}")
        self.memory_file = self.base / "knowledge" / "MEMORY.md"
        self.knowledge_dir = self.base / "knowledge"
        self.learned_dir = self.base / "learned"
        self.persona_dir = self.base / "persona"
        self.cache_dir = self.base / "session_cache"

    def load_context(self) -> str:
        """Load everything Melissa needs at the start of every conversation."""
        sections = []

        if self.memory_file.exists():
            sections.append(self.memory_file.read_text())

        if self.knowledge_dir.exists():
            for f in sorted(self.knowledge_dir.glob("*.md")):
                if f.name == "MEMORY.md":
                    continue
                try:
                    content = f.read_text().strip()
                    if content:
                        sections.append(f"## {f.stem.replace('_', ' ').title()}\n{content}")
                except Exception as e:
                    log.warning(f"[memory] read error {f}: {e}")

        escalations = sorted(
            (self.learned_dir / "escalaciones").rglob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:10]
        if escalations:
            parts = []
            for e in escalations:
                try:
                    parts.append(e.read_text().strip())
                except Exception:
                    pass
            if parts:
                sections.append("## Respuestas aprendidas\n" + "\n\n---\n\n".join(parts))

        return "\n\n---\n\n".join(sections) if sections else ""

    def save_escalation(
        self,
        client_msg: str,
        admin_response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Save an admin escalation so Melissa learns it."""
        now = datetime.now()
        folder = self.learned_dir / "escalaciones" / now.strftime("%Y-%m-%d")
        folder.mkdir(parents=True, exist_ok=True)
        ts = now.strftime("%H%M%S")
        content = (
            f"# Escalación {ts}\n"
            f"Pregunta del cliente: {client_msg}\n"
            f"Respuesta del admin: {admin_response}\n"
            f"Fecha: {now.isoformat()}\n"
        )
        if context:
            content += f"\nContexto:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n"
        (folder / f"{ts}.md").write_text(content)
        self._append_to_memory(
            f"- Aprendido {now.strftime('%Y-%m-%d')}: "
            f"'{client_msg[:60]}' → '{admin_response[:120]}'"
        )
        log.info(f"[memory] escalation saved: {client_msg[:40]}")

    def update_knowledge(self, file: str, content: str) -> None:
        """Admin updates a knowledge file."""
        safe = file.replace("..", "").replace("/", "").strip()
        target = self.knowledge_dir / f"{safe}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        log.info(f"[memory] knowledge updated: {safe}")

    def read_knowledge(self, file: str) -> str:
        """Read a knowledge file."""
        safe = file.replace("..", "").replace("/", "").strip()
        target = self.knowledge_dir / f"{safe}.md"
        if target.exists():
            return target.read_text()
        return ""

    def get_session_cache(self, chat_id: str) -> List[Dict[str, str]]:
        """Get last 20 messages for a chat."""
        cache_file = self.cache_dir / f"{chat_id}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except Exception:
                pass
        return []

    def save_session_cache(self, chat_id: str, messages: List[Dict[str, str]]) -> None:
        """Save session cache, keeping last 20."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.cache_dir / f"{chat_id}.json"
        cache_file.write_text(json.dumps(messages[-20:], ensure_ascii=False))

    def append_to_cache(self, chat_id: str, role: str, content: str) -> None:
        """Append one message to session cache."""
        cache = self.get_session_cache(chat_id)
        cache.append({"role": role, "content": content})
        self.save_session_cache(chat_id, cache)

    def get_persona_tone(self) -> str:
        """Load persona tone file."""
        tone = self.persona_dir / "tono.md"
        if tone.exists():
            return tone.read_text()
        return ""

    def save_persona_tone(self, content: str) -> None:
        """Save persona tone."""
        self.persona_dir.mkdir(parents=True, exist_ok=True)
        (self.persona_dir / "tono.md").write_text(content)

    def save_pattern(self, pattern_type: str, content: str) -> None:
        """Save monthly pattern."""
        now = datetime.now()
        folder = self.learned_dir / "patrones"
        folder.mkdir(parents=True, exist_ok=True)
        month_file = folder / f"{now.strftime('%Y-%m')}.md"
        with open(month_file, "a") as f:
            f.write(f"\n## {now.strftime('%Y-%m-%d')} [{pattern_type}]\n{content}")

    def get_patterns(self, months: int = 2) -> str:
        """Get recent patterns."""
        folder = self.learned_dir / "patrones"
        if not folder.exists():
            return ""
        parts = []
        now = datetime.now()
        for i in range(months):
            dt = now.replace(day=1)
            m = now.month - i
            while m <= 0:
                m += 12
            dt = dt.replace(month=((m - 1) % 12) + 1)
            if m > now.month:
                dt = dt.replace(year=dt.year - 1)
            f = folder / f"{dt.strftime('%Y-%m')}.md"
            if f.exists():
                parts.append(f.read_text())
        return "\n\n".join(parts)

    def _append_to_memory(self, line: str) -> None:
        """Append line to MEMORY.md."""
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        with open(self.memory_file, "a") as f:
            f.write(f"\n{line}")

    def init_instance(self) -> None:
        """Create all directories for a new instance."""
        for d in (
            self.knowledge_dir,
            self.learned_dir / "escalaciones",
            self.learned_dir / "patrones",
            self.persona_dir,
            self.cache_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
        if not self.memory_file.exists():
            self.memory_file.write_text(
                f"# MEMORY.md — {self.instance_id}\n"
                f"# Inicializado: {datetime.now().isoformat()}\n\n"
                "## Lo que sé de este negocio:\n(vacío)\n"
            )


_memory_cache: Dict[str, "MelissaMemory"] = {}


def get_memory(instance_id: str = "default") -> "MelissaMemory":
    if instance_id not in _memory_cache:
        _memory_cache[instance_id] = MelissaMemory(instance_id)
    return _memory_cache[instance_id]