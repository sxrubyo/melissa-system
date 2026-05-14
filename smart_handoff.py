"""
smart_handoff.py — Sistema de Escala Inteligente Admin v1.1
════════════════════════════════════════════════════════════════════════════════

BUG-3:
  - Persiste el contexto completo del handoff en SQLite
  - Devuelve el ack al cliente sin esperar la notificación al admin
  - Evita loops cuando llegan ecos o acuses del admin
  - Expira tickets a los 10 minutos con fallback elegante

INTEGRACIÓN ACTUAL EN melissa.py:
  `try_intercept_admin_reply(...)` y `trigger(...)` ya se llaman.

INTEGRACIÓN ADICIONAL NECESARIA PARA EL TIMEOUT AUTOMÁTICO:
  Melissa todavía no pasa un sender de cliente al `trigger(...)`, por eso el
  timeout puede persistirse y marcarse como expirado, pero no podrá empujar el
  fallback al paciente hasta integrar exactamente estas llamadas:

      async def _handoff_send_to_client(cid: str, msg: str):
          await mcp_manager.execute(
              "whatsapp_v1",
              "send_message",
              {"chat_id": cid, "message": msg},
          )

      handoff_manager.register_client_sender(_handoff_send_to_client)
      await handoff_manager.resume_pending_timeouts(
          send_to_client_fn=_handoff_send_to_client,
      )

      _hold_msgs, _was_escalated = await handoff_manager.trigger(
          ...,
          send_to_admin_fn=_handoff_notify_admin,
          send_to_client_fn=_handoff_send_to_client,
      )
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("melissa.handoff")

AsyncMessageSender = Callable[[str, str], Awaitable[None]]
AsyncLLMFn = Callable[..., Awaitable[str]]


# ════════════════════════════════════════════════════════════════════════════════
# SEÑALES DE INCERTIDUMBRE
# ════════════════════════════════════════════════════════════════════════════════

_UNCERTAINTY_PHRASES = [
    "te confirmo",
    "te averiguo",
    "déjame confirmar",
    "deja me confirmar",
    "te escribo en un momento",
    "te cuento más tarde",
    "no tengo ese dato",
    "no tengo esa información",
    "no cuento con ese dato",
    "voy a confirmar",
    "en cuanto sepa te escribo",
    "te lo confirmo",
    "te digo",
    "averiguo y te cuento",
    "ahorita no tengo",
    "no lo tengo a mano",
    "no tengo acceso a eso",
    "eso no lo sé",
    "no sé eso",
    "voy a preguntar",
    "tengo que confirmar",
    "lo reviso y te digo",
]

_UNCERTAINTY_PATTERNS = [
    r"no\s+(?:tengo|cuento\s+con|tengo\s+acceso\s+a)\s+(?:ese|esa|el|la)\s+dato",
    r"te\s+(?:confirmo|averiguo|cuento|digo)\s+(?:más\s+tarde|luego|después|ahorita|ya)",
    r"(?:voy\s+a|déjame|deja\s+me)\s+(?:confirmar|averiguar|preguntar|revisar)",
]

_ADMIN_ACK_ONLY = {
    "ok",
    "ok.",
    "oki",
    "dale",
    "listo",
    "listo.",
    "gracias",
    "gracias.",
    "recibido",
    "recibido.",
    "enterado",
    "entendido",
    "👍",
    "👌",
}


# ════════════════════════════════════════════════════════════════════════════════
# SQLITE
# ════════════════════════════════════════════════════════════════════════════════

_DB_PATH = "melissa_handoff.db"
_SCHEMA_READY: set[str] = set()

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS handoff_queue (
    id                  TEXT PRIMARY KEY,
    client_chat_id      TEXT NOT NULL,
    admin_chat_id       TEXT DEFAULT '',
    admin_chat_ids_json TEXT DEFAULT '[]',
    client_message      TEXT NOT NULL,
    context_json        TEXT DEFAULT '{}',
    clinic_name         TEXT DEFAULT '',
    clinic_json         TEXT DEFAULT '{}',
    llm_output          TEXT DEFAULT '',
    hold_message        TEXT DEFAULT '',
    fallback_message    TEXT DEFAULT '',
    status              TEXT DEFAULT 'pending',   -- pending | replied | expired
    admin_raw_reply     TEXT DEFAULT '',
    melissa_reply       TEXT DEFAULT '',
    uncertainty_why     TEXT DEFAULT '',
    created_at          REAL NOT NULL,
    expires_at          REAL NOT NULL,
    replied_at          REAL DEFAULT 0,
    expired_at          REAL DEFAULT 0,
    fallback_sent_at    REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS handoff_learnings (
    id              TEXT PRIMARY KEY,
    clinic_key      TEXT NOT NULL,
    question_norm   TEXT NOT NULL,
    admin_raw       TEXT NOT NULL,
    melissa_polish  TEXT NOT NULL,
    learned_at      REAL NOT NULL,
    times_used      INTEGER DEFAULT 0
);
"""

_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_hq_client         ON handoff_queue(client_chat_id, status);
CREATE INDEX IF NOT EXISTS idx_hq_admin          ON handoff_queue(admin_chat_id, status);
CREATE INDEX IF NOT EXISTS idx_hq_status_expires ON handoff_queue(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_hl_clinic         ON handoff_learnings(clinic_key);
"""

_LEGACY_MIGRATIONS = {
    "admin_chat_ids_json": "ALTER TABLE handoff_queue ADD COLUMN admin_chat_ids_json TEXT DEFAULT '[]'",
    "clinic_json": "ALTER TABLE handoff_queue ADD COLUMN clinic_json TEXT DEFAULT '{}'",
    "llm_output": "ALTER TABLE handoff_queue ADD COLUMN llm_output TEXT DEFAULT ''",
    "hold_message": "ALTER TABLE handoff_queue ADD COLUMN hold_message TEXT DEFAULT ''",
    "fallback_message": "ALTER TABLE handoff_queue ADD COLUMN fallback_message TEXT DEFAULT ''",
    "expires_at": "ALTER TABLE handoff_queue ADD COLUMN expires_at REAL DEFAULT 0",
    "expired_at": "ALTER TABLE handoff_queue ADD COLUMN expired_at REAL DEFAULT 0",
    "fallback_sent_at": "ALTER TABLE handoff_queue ADD COLUMN fallback_sent_at REAL DEFAULT 0",
}


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_CREATE_TABLES)
    cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(handoff_queue)").fetchall()
    }
    for column, ddl in _LEGACY_MIGRATIONS.items():
        if column not in cols:
            conn.execute(ddl)
    conn.executescript(_CREATE_INDEXES)
    conn.commit()


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if _DB_PATH not in _SCHEMA_READY:
        _ensure_schema(conn)
        _SCHEMA_READY.add(_DB_PATH)
    return conn


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


# ════════════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class HandoffTicket:
    id: str
    client_chat_id: str
    admin_chat_id: str
    client_message: str
    context: List[Dict[str, Any]]
    clinic_name: str
    status: str
    uncertainty_why: str
    admin_chat_ids: List[str] = field(default_factory=list)
    clinic_snapshot: Dict[str, Any] = field(default_factory=dict)
    llm_output: str = ""
    hold_message: str = ""
    fallback_message: str = ""
    admin_raw_reply: str = ""
    melissa_reply: str = ""
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    replied_at: float = 0.0
    expired_at: float = 0.0
    fallback_sent_at: float = 0.0


@dataclass
class HandoffLearning:
    id: str
    clinic_key: str
    question_norm: str
    admin_raw: str
    melissa_polish: str
    learned_at: float
    times_used: int = 0


# ════════════════════════════════════════════════════════════════════════════════
# MENSAJES
# ════════════════════════════════════════════════════════════════════════════════

_HOLD_MESSAGES = [
    "Permíteme un momento, te confirmo eso ya",
    "Dame un segundito, me aseguro de darte el dato exacto",
    "Ya te confirmo eso, un momento",
    "Permíteme verificar eso contigo en un momento",
    "Un segundito, voy a asegurarme de darte la info correcta",
    "Dame un momentico, te confirmo",
]

_TIMEOUT_FALLBACKS = [
    "Gracias por esperar. Sigo validando ese dato con la clínica y prefiero no inventarte información. Dejé tu solicitud priorizada y apenas tenga confirmación te escribo por aquí.",
    "Gracias por la paciencia. Todavía estoy revisando ese dato con la clínica para darte algo exacto. Lo dejé escalado y te escribo por aquí apenas me respondan.",
]


def _pick_hold_message() -> str:
    return random.choice(_HOLD_MESSAGES)


def _pick_timeout_fallback() -> str:
    return random.choice(_TIMEOUT_FALLBACKS)


def _format_admin_notification(ticket: HandoffTicket) -> str:
    lines = [
        "⚡ *Melissa necesita tu ayuda*",
        "",
        f"*Cliente:* `{ticket.client_chat_id}`",
        f"*Clínica:* {ticket.clinic_name or 'N/A'}",
        "*Preguntó:*",
        f"_{ticket.client_message}_",
        "",
    ]

    if ticket.context:
        lines.append("*Últimos mensajes:*")
        for turn in ticket.context[-4:]:
            role_label = "Cliente" if turn.get("role") == "user" else "Melissa"
            content = str(turn.get("content", ""))[:160]
            lines.append(f"  [{role_label}] {content}")
        lines.append("")

    lines += [
        f"*Motivo:* {ticket.uncertainty_why}",
        f"*Expira en:* 10 minutos",
        "",
        "*Respóndeme con el dato o la instrucción.*",
        "Yo le aviso al cliente en mi estilo.",
        "",
        f"📌 Ticket: `{ticket.id[:8]}`",
    ]
    return "\n".join(lines)


def _build_context_payload(ticket: HandoffTicket) -> Dict[str, Any]:
    return {
        "version": 2,
        "history": ticket.context,
        "clinic_snapshot": ticket.clinic_snapshot,
        "llm_output": ticket.llm_output,
        "admin_chat_ids": ticket.admin_chat_ids,
        "hold_message": ticket.hold_message,
        "fallback_message": ticket.fallback_message,
        "uncertainty_why": ticket.uncertainty_why,
    }


def _looks_like_handoff_system_echo(text: str) -> bool:
    normalized = (text or "").strip().lower()
    return normalized.startswith("⚡ *melissa necesita tu ayuda*".lower()) or normalized.startswith(
        "✅ listo, le dije al cliente:".lower()
    )


def _is_admin_ack_only(text: str) -> bool:
    return (text or "").strip().lower() in _ADMIN_ACK_ONLY


def _format_expired_admin_notice(ticket: HandoffTicket) -> str:
    age_min = max(10, int((time.time() - ticket.created_at) / 60))
    return (
        "⏱️ Ese ticket ya expiró y no reenvié tu mensaje al cliente automáticamente.\n"
        f"Cliente: `{ticket.client_chat_id}`\n"
        f"Ticket: `{ticket.id[:8]}`\n"
        f"Edad: {age_min} min"
    )


# ════════════════════════════════════════════════════════════════════════════════
# DETECTOR DE INCERTIDUMBRE
# ════════════════════════════════════════════════════════════════════════════════

def detect_uncertainty(
    llm_output: str,
    user_msg: str,
    clinic: Dict[str, Any],
    *,
    intent_confidence: float = 1.0,
) -> Optional[str]:
    out_low = (llm_output or "").lower()
    user_low = (user_msg or "").lower()

    for phrase in _UNCERTAINTY_PHRASES:
        if phrase in out_low:
            return f"LLM expresó incertidumbre: '{phrase}'"

    for pattern in _UNCERTAINTY_PATTERNS:
        if re.search(pattern, out_low):
            return "Patrón de incertidumbre detectado en output"

    prices_text = json.dumps(clinic.get("prices", {}) or {}).lower()
    schedule_text = json.dumps(clinic.get("schedule", {}) or {}).lower()

    if any(kw in user_low for kw in ["precio", "costo", "cuánto", "cuanto", "tarifa", "valor"]):
        if not prices_text or prices_text in ("null", "{}", "[]", '""'):
            return "Cliente pregunta precio pero clinic no tiene 'prices' configurado"

    if any(kw in user_low for kw in ["horario", "hora", "cuando abren", "cuándo abren"]):
        if not schedule_text or schedule_text in ("null", "{}", "[]", '""'):
            return "Cliente pregunta horario pero clinic no tiene 'schedule' configurado"

    if intent_confidence < 0.45:
        return f"Confianza de intención baja: {intent_confidence:.2f}"

    return None


# ════════════════════════════════════════════════════════════════════════════════
# PULIDOR ADMIN → MELISSA
# ════════════════════════════════════════════════════════════════════════════════

async def _polish_admin_reply(
    admin_raw: str,
    client_message: str,
    clinic: Dict[str, Any],
    llm_fn: AsyncLLMFn,
) -> str:
    clinic_name = (clinic.get("name") or "la clínica").strip()
    system = f"""Eres Melissa, la recepcionista virtual de {clinic_name}.
Un administrador te dio esta instrucción sobre cómo responder a un cliente.
Transforma esa instrucción en un mensaje natural, cálido y en tu estilo.

REGLAS:
- Escribe como si le hablaras directamente al cliente en WhatsApp
- Tono conversacional colombiano, sin sonar a robot
- Sin inventar datos que el admin no dio
- Máximo 2-3 oraciones
- No menciones que hubo una consulta interna al admin

Responde SOLO con el mensaje final para el cliente."""

    user_prompt = (
        f'Pregunta del cliente: "{client_message}"\n'
        f'Instrucción del admin: "{admin_raw}"\n\n'
        "Transforma en respuesta natural de Melissa:"
    )

    try:
        result = await llm_fn(system, user_prompt, temp=0.75, max_t=300, model_tier="fast")
        cleaned = (result or "").strip().strip('"').strip("'").strip()
        if cleaned and len(cleaned) > 5:
            return cleaned
    except Exception as exc:
        log.warning(f"[handoff] Error puliendo respuesta admin: {exc}")

    return admin_raw.strip()


# ════════════════════════════════════════════════════════════════════════════════
# LEARNINGS
# ════════════════════════════════════════════════════════════════════════════════

def _normalize_question(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[áàä]", "a", text)
    text = re.sub(r"[éèë]", "e", text)
    text = re.sub(r"[íìï]", "i", text)
    text = re.sub(r"[óòö]", "o", text)
    text = re.sub(r"[úùü]", "u", text)
    text = re.sub(r"ñ", "n", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    stops = {
        "me",
        "puedes",
        "puede",
        "decir",
        "dices",
        "hay",
        "tiene",
        "tienen",
        "cuanto",
        "cual",
        "como",
        "cuando",
        "donde",
        "que",
        "es",
        "son",
        "una",
        "un",
        "la",
        "el",
        "los",
        "las",
    }
    return " ".join(token for token in text.split() if token not in stops)


def find_learned_answer(
    user_msg: str,
    clinic_key: str,
    threshold: float = 0.65,
) -> Optional[str]:
    try:
        conn = _get_db()
        rows = conn.execute(
            "SELECT * FROM handoff_learnings WHERE clinic_key = ? ORDER BY times_used DESC LIMIT 50",
            (clinic_key,),
        ).fetchall()
        conn.close()
    except Exception as exc:
        log.warning(f"[handoff] Error buscando learnings: {exc}")
        return None

    q_norm = set(_normalize_question(user_msg).split())
    if not q_norm:
        return None

    best_score = 0.0
    best_answer = None

    for row in rows:
        stored = set((row["question_norm"] or "").split())
        if not stored:
            continue
        union = q_norm | stored
        score = len(q_norm & stored) / len(union) if union else 0.0
        if score > best_score:
            best_score = score
            best_answer = row["melissa_polish"]

    if best_score >= threshold and best_answer:
        log.info(f"[handoff] Learning encontrado (score={best_score:.2f})")
        return best_answer

    return None


# ════════════════════════════════════════════════════════════════════════════════
# MANAGER
# ════════════════════════════════════════════════════════════════════════════════

class SmartAdminHandoff:
    TICKET_TTL = 60 * 10

    def __init__(self, db_path: str = _DB_PATH):
        global _DB_PATH
        _DB_PATH = db_path
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        conn.close()
        _SCHEMA_READY.add(_DB_PATH)
        self._pending_admin_map: Dict[str, str] = {}
        self._timeout_tasks: Dict[str, asyncio.Task[Any]] = {}
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._default_client_sender: Optional[AsyncMessageSender] = None

    def register_client_sender(self, send_to_client_fn: AsyncMessageSender) -> None:
        self._default_client_sender = send_to_client_fn

    async def resume_pending_timeouts(
        self,
        *,
        send_to_client_fn: Optional[AsyncMessageSender] = None,
    ) -> int:
        sender = send_to_client_fn or self._default_client_sender
        expired = await self.expire_due_tickets(send_to_client_fn=sender)
        for ticket in self.get_pending_tickets():
            self._schedule_timeout(ticket, sender)
        return len(expired)

    def detect_uncertainty(
        self,
        llm_output: str,
        user_msg: str,
        clinic: Dict[str, Any],
        intent_confidence: float = 1.0,
    ) -> Optional[str]:
        return detect_uncertainty(llm_output, user_msg, clinic, intent_confidence=intent_confidence)

    async def trigger(
        self,
        *,
        client_chat_id: str,
        user_msg: str,
        history: List[Dict[str, Any]],
        clinic: Dict[str, Any],
        llm_output: str = "",
        admin_chat_ids: List[str],
        send_to_admin_fn: AsyncMessageSender,
        send_to_client_fn: Optional[AsyncMessageSender] = None,
        intent_confidence: float = 1.0,
    ) -> Tuple[List[str], bool]:
        sender = send_to_client_fn or self._default_client_sender
        self._schedule_background(self.expire_due_tickets(send_to_client_fn=sender))

        clinic_key = str(clinic.get("id") or clinic.get("name") or "default")
        learned = find_learned_answer(user_msg, clinic_key)
        if learned:
            return [learned], False

        reason = detect_uncertainty(llm_output, user_msg, clinic, intent_confidence=intent_confidence)
        if not reason:
            return [], False

        existing = self._get_pending_ticket_for_client(client_chat_id)
        if existing:
            self._schedule_timeout(existing, sender)
            return [existing.hold_message or _pick_hold_message()], True

        now = time.time()
        hold_message = _pick_hold_message()
        ticket = HandoffTicket(
            id=str(uuid.uuid4()),
            client_chat_id=client_chat_id,
            admin_chat_id=admin_chat_ids[0] if admin_chat_ids else "",
            admin_chat_ids=list(admin_chat_ids or []),
            client_message=user_msg,
            context=list(history or []),
            clinic_name=str(clinic.get("name") or ""),
            clinic_snapshot=dict(clinic or {}),
            llm_output=llm_output or "",
            hold_message=hold_message,
            fallback_message=_pick_timeout_fallback(),
            status="pending",
            uncertainty_why=reason,
            created_at=now,
            expires_at=now + self.TICKET_TTL,
        )

        self._save_ticket(ticket)
        self._schedule_background(self._notify_admins(ticket, send_to_admin_fn))
        self._schedule_timeout(ticket, sender)
        log.info(f"[handoff] Ticket {ticket.id[:8]} creado para {client_chat_id}")

        return [hold_message], True

    async def try_intercept_admin_reply(
        self,
        *,
        admin_chat_id: str,
        admin_text: str,
        clinic: Dict[str, Any],
        llm_fn: AsyncLLMFn,
        send_to_client_fn: AsyncMessageSender,
    ) -> Tuple[bool, List[str]]:
        await self.expire_due_tickets(send_to_client_fn=self._default_client_sender or send_to_client_fn)

        text = (admin_text or "").strip()
        if text.startswith("/"):
            return False, []

        ticket_id = self._pending_admin_map.get(admin_chat_id)
        if not ticket_id:
            ticket_id = self._find_pending_ticket_by_admin(admin_chat_id)
        if not ticket_id:
            return False, []

        ticket = self._load_ticket(ticket_id)
        if not ticket:
            self._pending_admin_map.pop(admin_chat_id, None)
            return False, []

        if ticket.status == "expired":
            self._clear_ticket_mappings(ticket)
            return True, [_format_expired_admin_notice(ticket)]

        if ticket.status != "pending":
            self._pending_admin_map.pop(admin_chat_id, None)
            return False, []

        if _looks_like_handoff_system_echo(text):
            return True, []

        if not text or _is_admin_ack_only(text):
            return True, ["Recibido. Cuando tengas la respuesta para el cliente, escríbemela aquí y yo se la paso."]

        polished = await _polish_admin_reply(
            admin_raw=text,
            client_message=ticket.client_message,
            clinic=clinic,
            llm_fn=llm_fn,
        )

        try:
            await send_to_client_fn(ticket.client_chat_id, polished)
        except Exception as exc:
            log.error(f"[handoff] Error enviando al cliente: {exc}")
            return True, [f"⚠️ Error enviando al cliente: {exc}"]

        # Melissa aprende de la respuesta del admin (V9)
        try:
            from knowledge_base import kb as _kb
            if _kb and _kb.has_content():
                # Obtenemos el mensaje original del paciente del ticket
                with self._conn() as c:
                    row = c.execute("SELECT patient_raw FROM handoff_queue WHERE id=?", (ticket_id,)).fetchone()
                    if row:
                        _kb.save_learned_fact(row["patient_raw"], polished, source="admin_handoff")
                        log.info(f"[handoff] Aprendizaje registrado para ticket {ticket_id}")
        except Exception as e:
            log.warning(f"[handoff] Error guardando aprendizaje: {e}")

        self._mark_replied(ticket_id, admin_raw=text, melissa_reply=polished)
        self._cancel_timeout(ticket_id)
        self._clear_ticket_mappings(ticket)
        self._save_learning(
            clinic_key=str(clinic.get("id") or clinic.get("name") or "default"),
            question=ticket.client_message,
            admin_raw=text,
            melissa_polish=polished,
        )

        return True, [
            "✅ Listo, le dije al cliente:\n"
            f"_{polished}_\n\n"
            "📚 Aprendido para la próxima vez que alguien pregunte algo similar."
        ]

    async def expire_due_tickets(
        self,
        *,
        send_to_client_fn: Optional[AsyncMessageSender] = None,
    ) -> List[HandoffTicket]:
        due = self._list_due_tickets()
        if not due:
            return []

        sender = send_to_client_fn or self._default_client_sender
        expired: List[HandoffTicket] = []

        for ticket in due:
            if not self._mark_expired(ticket.id):
                continue

            ticket = self._load_ticket(ticket.id) or ticket
            self._cancel_timeout(ticket.id)
            self._clear_ticket_mappings(ticket)
            expired.append(ticket)

            if sender and not ticket.fallback_sent_at:
                try:
                    await sender(ticket.client_chat_id, ticket.fallback_message)
                    self._mark_fallback_sent(ticket.id)
                except Exception as exc:
                    log.warning(f"[handoff] Error enviando fallback de timeout {ticket.id[:8]}: {exc}")

        return expired

    def get_learnings(self, clinic_key: str) -> List[HandoffLearning]:
        try:
            conn = _get_db()
            rows = conn.execute(
                "SELECT * FROM handoff_learnings WHERE clinic_key = ? ORDER BY learned_at DESC",
                (clinic_key,),
            ).fetchall()
            conn.close()
            return [
                HandoffLearning(
                    id=row["id"],
                    clinic_key=row["clinic_key"],
                    question_norm=row["question_norm"],
                    admin_raw=row["admin_raw"],
                    melissa_polish=row["melissa_polish"],
                    learned_at=row["learned_at"],
                    times_used=row["times_used"],
                )
                for row in rows
            ]
        except Exception as exc:
            log.warning(f"[handoff] Error leyendo learnings: {exc}")
            return []

    def delete_learning(self, learning_id: str) -> bool:
        try:
            conn = _get_db()
            conn.execute("DELETE FROM handoff_learnings WHERE id = ?", (learning_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as exc:
            log.warning(f"[handoff] Error borrando learning {learning_id}: {exc}")
            return False

    def get_pending_tickets(self) -> List[HandoffTicket]:
        self._expire_due_tickets_sync()
        try:
            conn = _get_db()
            rows = conn.execute(
                "SELECT * FROM handoff_queue WHERE status = 'pending' ORDER BY created_at DESC"
            ).fetchall()
            conn.close()
            return [self._row_to_ticket(row) for row in rows]
        except Exception as exc:
            log.warning(f"[handoff] Error listando tickets: {exc}")
            return []

    async def _notify_admins(
        self,
        ticket: HandoffTicket,
        send_to_admin_fn: AsyncMessageSender,
    ) -> None:
        if not ticket.admin_chat_ids:
            return

        async def _notify_one(admin_id: str) -> None:
            try:
                outbound_ticket = self._clone_ticket(ticket, admin_chat_id=admin_id)
                await send_to_admin_fn(admin_id, _format_admin_notification(outbound_ticket))
                self._pending_admin_map[admin_id] = ticket.id
            except Exception as exc:
                log.warning(f"[handoff] Error notificando admin {admin_id}: {exc}")

        await asyncio.gather(*(_notify_one(admin_id) for admin_id in ticket.admin_chat_ids))

    def _clone_ticket(self, ticket: HandoffTicket, *, admin_chat_id: Optional[str] = None) -> HandoffTicket:
        return HandoffTicket(
            id=ticket.id,
            client_chat_id=ticket.client_chat_id,
            admin_chat_id=admin_chat_id if admin_chat_id is not None else ticket.admin_chat_id,
            client_message=ticket.client_message,
            context=list(ticket.context),
            clinic_name=ticket.clinic_name,
            status=ticket.status,
            uncertainty_why=ticket.uncertainty_why,
            admin_chat_ids=list(ticket.admin_chat_ids),
            clinic_snapshot=dict(ticket.clinic_snapshot),
            llm_output=ticket.llm_output,
            hold_message=ticket.hold_message,
            fallback_message=ticket.fallback_message,
            admin_raw_reply=ticket.admin_raw_reply,
            melissa_reply=ticket.melissa_reply,
            created_at=ticket.created_at,
            expires_at=ticket.expires_at,
            replied_at=ticket.replied_at,
            expired_at=ticket.expired_at,
            fallback_sent_at=ticket.fallback_sent_at,
        )

    def _schedule_background(self, coro: Awaitable[Any]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        def _start() -> None:
            task = loop.create_task(coro)
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        # Desacopla la creación real del task del request actual para que
        # trigger() no quede penalizado por el primer await del envío al admin.
        loop.call_soon(_start)

    def _schedule_timeout(
        self,
        ticket: HandoffTicket,
        send_to_client_fn: Optional[AsyncMessageSender],
    ) -> None:
        if not send_to_client_fn:
            return

        self._cancel_timeout(ticket.id)

        delay = max(0.0, ticket.expires_at - time.time())

        async def _timeout_worker() -> None:
            try:
                await asyncio.sleep(delay)
                await self.expire_due_tickets(send_to_client_fn=send_to_client_fn)
            except asyncio.CancelledError:
                raise

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        task = loop.create_task(_timeout_worker())
        self._timeout_tasks[ticket.id] = task
        task.add_done_callback(lambda _: self._timeout_tasks.pop(ticket.id, None))

    def _cancel_timeout(self, ticket_id: str) -> None:
        task = self._timeout_tasks.pop(ticket_id, None)
        if task and not task.done():
            task.cancel()

    def _clear_ticket_mappings(self, ticket: HandoffTicket) -> None:
        for admin_id in set(ticket.admin_chat_ids + ([ticket.admin_chat_id] if ticket.admin_chat_id else [])):
            if self._pending_admin_map.get(admin_id) == ticket.id:
                self._pending_admin_map.pop(admin_id, None)

    def _save_ticket(self, ticket: HandoffTicket) -> None:
        try:
            conn = _get_db()
            conn.execute(
                """
                INSERT INTO handoff_queue (
                    id, client_chat_id, admin_chat_id, admin_chat_ids_json,
                    client_message, context_json, clinic_name, clinic_json,
                    llm_output, hold_message, fallback_message, status,
                    uncertainty_why, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    ticket.id,
                    ticket.client_chat_id,
                    ticket.admin_chat_id,
                    _json_dumps(ticket.admin_chat_ids),
                    ticket.client_message,
                    _json_dumps(_build_context_payload(ticket)),
                    ticket.clinic_name,
                    _json_dumps(ticket.clinic_snapshot),
                    ticket.llm_output,
                    ticket.hold_message,
                    ticket.fallback_message,
                    ticket.uncertainty_why,
                    ticket.created_at,
                    ticket.expires_at,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            log.warning(f"[handoff] Error guardando ticket: {exc}")

    def _load_ticket(self, ticket_id: str) -> Optional[HandoffTicket]:
        try:
            conn = _get_db()
            row = conn.execute(
                "SELECT * FROM handoff_queue WHERE id = ?",
                (ticket_id,),
            ).fetchone()
            conn.close()
            return self._row_to_ticket(row) if row else None
        except Exception as exc:
            log.warning(f"[handoff] Error cargando ticket {ticket_id}: {exc}")
            return None

    def _row_to_ticket(self, row: sqlite3.Row) -> HandoffTicket:
        payload = _json_loads(row["context_json"], {})
        if isinstance(payload, list):
            history = payload
            payload = {}
        else:
            history = payload.get("history") or payload.get("context") or []

        admin_chat_ids = _json_loads(row["admin_chat_ids_json"], payload.get("admin_chat_ids", []))
        if not isinstance(admin_chat_ids, list):
            admin_chat_ids = []

        clinic_snapshot = _json_loads(row["clinic_json"], payload.get("clinic_snapshot", {}))
        if not isinstance(clinic_snapshot, dict):
            clinic_snapshot = {}

        return HandoffTicket(
            id=row["id"],
            client_chat_id=row["client_chat_id"],
            admin_chat_id=row["admin_chat_id"] or "",
            admin_chat_ids=admin_chat_ids,
            client_message=row["client_message"],
            context=history if isinstance(history, list) else [],
            clinic_name=row["clinic_name"] or "",
            clinic_snapshot=clinic_snapshot,
            llm_output=row["llm_output"] or payload.get("llm_output", ""),
            hold_message=row["hold_message"] or payload.get("hold_message", ""),
            fallback_message=row["fallback_message"] or payload.get("fallback_message", ""),
            status=row["status"],
            uncertainty_why=row["uncertainty_why"] or payload.get("uncertainty_why", ""),
            admin_raw_reply=row["admin_raw_reply"] or "",
            melissa_reply=row["melissa_reply"] or "",
            created_at=row["created_at"],
            expires_at=row["expires_at"] or 0.0,
            replied_at=row["replied_at"] or 0.0,
            expired_at=row["expired_at"] or 0.0,
            fallback_sent_at=row["fallback_sent_at"] or 0.0,
        )

    def _mark_replied(self, ticket_id: str, admin_raw: str, melissa_reply: str) -> None:
        try:
            conn = _get_db()
            conn.execute(
                """
                UPDATE handoff_queue
                SET status = 'replied',
                    admin_raw_reply = ?,
                    melissa_reply = ?,
                    replied_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (admin_raw, melissa_reply, time.time(), ticket_id),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            log.warning(f"[handoff] Error actualizando ticket {ticket_id}: {exc}")

    def _mark_expired(self, ticket_id: str) -> bool:
        try:
            conn = _get_db()
            cur = conn.execute(
                """
                UPDATE handoff_queue
                SET status = 'expired',
                    expired_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (time.time(), ticket_id),
            )
            conn.commit()
            changed = cur.rowcount > 0
            conn.close()
            return changed
        except Exception as exc:
            log.warning(f"[handoff] Error expirando ticket {ticket_id}: {exc}")
            return False

    def _mark_fallback_sent(self, ticket_id: str) -> None:
        try:
            conn = _get_db()
            conn.execute(
                "UPDATE handoff_queue SET fallback_sent_at = ? WHERE id = ?",
                (time.time(), ticket_id),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            log.warning(f"[handoff] Error marcando fallback enviado {ticket_id}: {exc}")

    def _get_pending_ticket_for_client(self, client_chat_id: str) -> Optional[HandoffTicket]:
        self._expire_due_tickets_sync()
        try:
            conn = _get_db()
            row = conn.execute(
                """
                SELECT * FROM handoff_queue
                WHERE client_chat_id = ? AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (client_chat_id,),
            ).fetchone()
            conn.close()
            return self._row_to_ticket(row) if row else None
        except Exception as exc:
            log.warning(f"[handoff] Error buscando ticket cliente: {exc}")
            return None

    def _find_pending_ticket_by_admin(self, admin_chat_id: str) -> Optional[str]:
        self._expire_due_tickets_sync()
        try:
            conn = _get_db()
            rows = conn.execute(
                """
                SELECT * FROM handoff_queue
                WHERE status = 'pending'
                ORDER BY created_at DESC
                LIMIT 50
                """
            ).fetchall()
            conn.close()
        except Exception as exc:
            log.warning(f"[handoff] Error buscando ticket por admin: {exc}")
            return None

        for row in rows:
            ticket = self._row_to_ticket(row)
            if admin_chat_id == ticket.admin_chat_id or admin_chat_id in ticket.admin_chat_ids:
                return ticket.id
        return None

    def _list_due_tickets(self) -> List[HandoffTicket]:
        try:
            conn = _get_db()
            rows = conn.execute(
                """
                SELECT * FROM handoff_queue
                WHERE status = 'pending'
                  AND expires_at > 0
                  AND expires_at <= ?
                ORDER BY created_at ASC
                """,
                (time.time(),),
            ).fetchall()
            conn.close()
            return [self._row_to_ticket(row) for row in rows]
        except Exception as exc:
            log.warning(f"[handoff] Error listando expirados: {exc}")
            return []

    def _expire_due_tickets_sync(self) -> None:
        due = self._list_due_tickets()
        for ticket in due:
            if self._mark_expired(ticket.id):
                self._cancel_timeout(ticket.id)
                self._clear_ticket_mappings(ticket)

    def _save_learning(
        self,
        clinic_key: str,
        question: str,
        admin_raw: str,
        melissa_polish: str,
    ) -> None:
        q_norm = _normalize_question(question)
        try:
            conn = _get_db()
            existing = conn.execute(
                "SELECT id FROM handoff_learnings WHERE clinic_key = ? AND question_norm = ?",
                (clinic_key, q_norm),
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE handoff_learnings
                    SET admin_raw = ?, melissa_polish = ?, learned_at = ?
                    WHERE id = ?
                    """,
                    (admin_raw, melissa_polish, time.time(), existing["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO handoff_learnings
                    (id, clinic_key, question_norm, admin_raw, melissa_polish, learned_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), clinic_key, q_norm, admin_raw, melissa_polish, time.time()),
                )

            conn.commit()
            conn.close()
        except Exception as exc:
            log.warning(f"[handoff] Error guardando learning: {exc}")


# ════════════════════════════════════════════════════════════════════════════════
# INSTANCIA GLOBAL
# ════════════════════════════════════════════════════════════════════════════════

handoff_manager = SmartAdminHandoff()


# ════════════════════════════════════════════════════════════════════════════════
# COMANDOS ADMIN
# ════════════════════════════════════════════════════════════════════════════════

async def handle_handoff_admin_command(
    cmd: str,
    clinic: Dict[str, Any],
) -> Optional[List[str]]:
    cmd = (cmd or "").strip().lower()
    clinic_key = str(clinic.get("id") or clinic.get("name") or "default")

    if cmd in ("/handoff", "/handoffs", "/escalaciones"):
        tickets = handoff_manager.get_pending_tickets()
        if not tickets:
            return ["No hay tickets pendientes ahora mismo."]
        lines = [f"📬 *{len(tickets)} ticket(s) pendiente(s):*\n"]
        for ticket in tickets[:10]:
            age_min = int((time.time() - ticket.created_at) / 60)
            lines.append(
                f"• `{ticket.id[:8]}` | {ticket.client_chat_id} | hace {age_min}min\n"
                f"  _{ticket.client_message[:80]}_"
            )
        return ["\n".join(lines)]

    if cmd in ("/handoff-aprendizajes", "/handoff-learnings", "/lo-que-aprendi"):
        learnings = handoff_manager.get_learnings(clinic_key)
        if not learnings:
            return ["Melissa aún no ha aprendido nada vía handoff para esta clínica."]
        lines = [f"📚 *{len(learnings)} aprendizaje(s):*\n"]
        for learning in learnings[:10]:
            lines.append(
                f"• `{learning.id[:8]}` (usado {learning.times_used}x)\n"
                f"  Pregunta: _{learning.question_norm[:60]}_\n"
                f"  Respuesta: _{learning.melissa_polish[:80]}_"
            )
        return ["\n".join(lines)]

    if cmd.startswith("/handoff-borrar "):
        learning_id_prefix = cmd.split("/handoff-borrar ", 1)[1].strip()
        learnings = handoff_manager.get_learnings(clinic_key)
        match = next((learning for learning in learnings if learning.id.startswith(learning_id_prefix)), None)
        if not match:
            return [f"No encontré un learning con ID `{learning_id_prefix}`."]
        handoff_manager.delete_learning(match.id)
        return [f"✅ Learning `{match.id[:8]}` borrado."]

    return None
