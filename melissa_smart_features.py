"""melissa_smart_features.py — 10 power features for human-like intelligence."""
from __future__ import annotations
import json, logging, re, time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("melissa.smart")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CROSS-SESSION MEMORY — Remember patients by phone number
# ═══════════════════════════════════════════════════════════════════════════════

class CrossSessionMemory:
    """Remember patient context across multiple conversations."""

    def __init__(self, instance_id: str = "default"):
        self._dir = Path(f"memory_store/{instance_id}/patients")
        self._dir.mkdir(parents=True, exist_ok=True)

    def remember_patient(self, chat_id: str, data: Dict):
        """Store patient data (name, preferences, last topic)."""
        file = self._dir / f"{self._safe_id(chat_id)}.json"
        existing = json.loads(file.read_text()) if file.exists() else {}
        existing.update(data)
        existing["last_seen"] = datetime.now().isoformat()
        existing["visit_count"] = existing.get("visit_count", 0) + 1
        file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

    def recall_patient(self, chat_id: str) -> Dict:
        """Recall everything we know about this patient."""
        file = self._dir / f"{self._safe_id(chat_id)}.json"
        if file.exists():
            return json.loads(file.read_text())
        return {}

    def get_context_for_prompt(self, chat_id: str) -> str:
        """Build a prompt section with patient memory."""
        data = self.recall_patient(chat_id)
        if not data:
            return ""
        parts = []
        if data.get("name"):
            parts.append(f"Se llama {data['name']}")
        if data.get("last_topic"):
            parts.append(f"La última vez habló de: {data['last_topic']}")
        if data.get("visit_count", 0) > 1:
            parts.append(f"Ya ha escrito {data['visit_count']} veces")
        if data.get("preferences"):
            parts.append(f"Preferencias: {data['preferences']}")
        return "\n".join(parts) if parts else ""

    def _safe_id(self, chat_id: str) -> str:
        return chat_id.replace("@", "_").replace(".", "_")[:50]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. FOLLOW-UP ENGINE — Re-engage abandoned conversations
# ═══════════════════════════════════════════════════════════════════════════════

class FollowUpEngine:
    """Schedule and manage follow-up messages."""

    def __init__(self, instance_id: str = "default"):
        self._file = Path(f"memory_store/{instance_id}/followups.jsonl")
        self._file.parent.mkdir(parents=True, exist_ok=True)

    def schedule_followup(self, chat_id: str, reason: str, delay_hours: int = 24):
        """Schedule a follow-up message."""
        entry = {
            "chat_id": chat_id,
            "reason": reason,
            "send_after": (datetime.now() + timedelta(hours=delay_hours)).isoformat(),
            "sent": False,
        }
        with open(self._file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_pending_followups(self) -> List[Dict]:
        """Get all follow-ups that are due."""
        if not self._file.exists():
            return []
        now = datetime.now().isoformat()
        pending = []
        for line in open(self._file):
            try:
                entry = json.loads(line)
                if not entry.get("sent") and entry.get("send_after", "") <= now:
                    pending.append(entry)
            except Exception:
                continue
        return pending

    def generate_followup_message(self, reason: str) -> str:
        """Generate a natural follow-up message."""
        templates = {
            "pricing": "hola! ayer estuvimos hablando de precios, te quedó alguna duda?",
            "booking": "hey! me quedé pensando en tu cita, quieres que te ayude a agendar?",
            "info": "hola de nuevo! por si te sirve, aquí estoy para lo que necesites",
            "default": "hola! hace rato no hablamos, necesitas algo?",
        }
        return templates.get(reason, templates["default"])


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SENTIMENT TRACKER — Detect emotional state per turn
# ═══════════════════════════════════════════════════════════════════════════════

class SentimentTracker:
    """Track patient sentiment across conversation turns."""

    FRUSTRATED = ["no entiendo", "ya le dije", "otra vez", "no me sirve", "eso no",
                  "qué lento", "cuánto más", "pésimo", "malo", "horrible"]
    HAPPY = ["gracias", "perfecto", "genial", "excelente", "increíble", "súper",
             "te amo", "la mejor", "mil gracias", "buenísimo"]
    URGENT = ["urgente", "emergencia", "ayuda", "ya", "rápido", "ahora mismo",
              "sangre", "dolor", "grave", "auxilio"]

    def analyze(self, text: str) -> Dict[str, float]:
        """Return sentiment scores."""
        t = text.lower()
        return {
            "frustration": sum(1 for w in self.FRUSTRATED if w in t) / max(len(self.FRUSTRATED), 1),
            "happiness": sum(1 for w in self.HAPPY if w in t) / max(len(self.HAPPY), 1),
            "urgency": sum(1 for w in self.URGENT if w in t) / max(len(self.URGENT), 1),
        }

    def should_escalate(self, text: str, history: List[Dict] = None) -> Tuple[bool, str]:
        """Determine if conversation should escalate to human."""
        scores = self.analyze(text)
        if scores["urgency"] > 0.2:
            return True, "urgency_detected"
        if scores["frustration"] > 0.15:
            # Check if frustrated for multiple turns
            if history and len(history) >= 4:
                recent_frustration = sum(
                    self.analyze(m.get("content", ""))["frustration"]
                    for m in history[-4:] if m.get("role") == "user"
                )
                if recent_frustration > 0.3:
                    return True, "sustained_frustration"
        return False, ""


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PREDICTIVE INTENT — Know what returning patients want
# ═══════════════════════════════════════════════════════════════════════════════

class PredictiveIntent:
    """Predict what a returning patient wants."""

    def predict(self, patient_memory: Dict, current_msg: str) -> Optional[str]:
        """Predict intent based on history."""
        last_topic = patient_memory.get("last_topic", "")
        visit_count = patient_memory.get("visit_count", 0)

        msg_low = current_msg.lower().strip()

        # Simple greeting from returning patient → probably wants to continue
        if msg_low in ("hola", "buenas", "hey", "hola buenas") and visit_count > 1:
            if last_topic == "pricing":
                return "returning_for_booking"
            if last_topic == "booking":
                return "checking_appointment"

        return None

    def get_proactive_opener(self, prediction: str, patient_name: str = "") -> Optional[str]:
        """Get a proactive opening based on prediction."""
        name = patient_name or ""
        openers = {
            "returning_for_booking": f"hola{' ' + name if name else ''}! la otra vez estuvimos mirando precios, quieres que agendemos?",
            "checking_appointment": f"hola{' ' + name if name else ''}! vienes por lo de tu cita?",
        }
        return openers.get(prediction)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. TIME AWARENESS — Greet appropriately for Colombian time
# ═══════════════════════════════════════════════════════════════════════════════

def get_time_greeting() -> str:
    """Return appropriate greeting for current Colombian time (UTC-5)."""
    from datetime import timezone
    now = datetime.now(timezone(timedelta(hours=-5)))
    hour = now.hour
    if 5 <= hour < 12:
        return "buenos días"
    elif 12 <= hour < 18:
        return "buenas tardes"
    else:
        return "buenas noches"


def is_business_hours() -> bool:
    """Check if it's currently business hours in Colombia."""
    from datetime import timezone
    now = datetime.now(timezone(timedelta(hours=-5)))
    return 8 <= now.hour <= 18 and now.weekday() < 6


# ═══════════════════════════════════════════════════════════════════════════════
# 6. CONVERSATION CLOSER — Detect natural end
# ═══════════════════════════════════════════════════════════════════════════════

CLOSING_SIGNALS = [
    "gracias", "chao", "bye", "hasta luego", "nos vemos",
    "listo", "perfecto gracias", "dale gracias", "ok gracias",
    "bendiciones", "que estés bien", "buena tarde", "buena noche",
]

def is_conversation_ending(text: str) -> bool:
    """Detect if the patient is saying goodbye."""
    t = text.lower().strip()
    return any(signal in t for signal in CLOSING_SIGNALS)

def get_natural_closing(tone: str = "casual") -> str:
    """Generate a natural conversation closing."""
    import random
    closings = {
        "casual": ["dale, cualquier cosa me escribes!", "listo, aquí estoy pa lo que necesites", "chao, que te vaya bien!"],
        "luxury": ["fue un placer atenderle, que tenga un excelente día", "quedamos atentos para servirle, que esté muy bien"],
        "formal": ["con gusto, que tenga buen día", "quedamos pendientes, hasta pronto"],
    }
    options = closings.get(tone, closings["casual"])
    return random.choice(options)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. POST-VISIT FOLLOW-UP — Request reviews after appointment
# ═══════════════════════════════════════════════════════════════════════════════

def generate_review_request(patient_name: str = "", clinic_name: str = "", google_review_link: str = "") -> str:
    """Generate a natural review request message."""
    name = patient_name or ""
    greeting = f"hola{' ' + name if name else ''}!"

    if google_review_link:
        return f"{greeting} cómo te fue en tu cita? espero que todo bien\n\nsi te gustó la atención, nos ayudaría muchísimo una reseñita aquí: {google_review_link}\n\ngracias!"
    return f"{greeting} cómo te fue en tu cita? espero que todo super bien"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. WEEKLY STATS — Count everything
# ═══════════════════════════════════════════════════════════════════════════════

class WeeklyStats:
    """Calculate weekly statistics for an instance."""

    def calculate(self, db_path: str = "melissa.db") -> Dict[str, int]:
        """Get stats for the last 7 days."""
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()

            c.execute("SELECT COUNT(DISTINCT chat_id) FROM conversations WHERE role='user' AND created_at > ?", (week_ago,))
            patients = c.fetchone()[0] or 0

            c.execute("SELECT COUNT(*) FROM conversations WHERE created_at > ?", (week_ago,))
            messages = c.fetchone()[0] or 0

            conn.close()
            return {"patients": patients, "messages": messages, "period": "7d"}
        except Exception:
            return {"patients": 0, "messages": 0, "period": "7d"}


# ═══════════════════════════════════════════════════════════════════════════════
# 9. ADMIN SHADOW MODE — Learn from admin's real responses
# ═══════════════════════════════════════════════════════════════════════════════

class AdminShadowMode:
    """When admin takes over a conversation, learn from their responses."""

    def __init__(self, instance_id: str = "default"):
        self._instance_id = instance_id
        self._shadow_file = Path(f"soul/{instance_id}/shadow_learnings.jsonl")
        self._shadow_file.parent.mkdir(parents=True, exist_ok=True)

    def detect_admin_takeover(self, chat_id: str, admin_ids: List[str], message_sender: str) -> bool:
        """Detect if admin is responding to a patient's chat."""
        # If message is outgoing (fromMe) in a non-admin chat, admin took over
        return message_sender in admin_ids and chat_id not in admin_ids

    def learn_from_admin_response(self, patient_question: str, admin_response: str):
        """Save admin's response as a learning example."""
        entry = {
            "ts": datetime.now().isoformat(),
            "patient_asked": patient_question[:200],
            "admin_responded": admin_response[:500],
            "learned": True,
        }
        with open(self._shadow_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        log.info(f"[shadow] learned from admin: {patient_question[:50]} → {admin_response[:50]}")


# ═══════════════════════════════════════════════════════════════════════════════
# 10. LANGUAGE DETECTOR — Auto-detect and respond in same language
# ═══════════════════════════════════════════════════════════════════════════════

class LanguageDetector:
    """Simple keyword-based language detection."""

    ENGLISH_MARKERS = ["hello", "hi", "good morning", "how are you", "i want", "i need",
                       "please", "thank you", "appointment", "available", "price"]
    PORTUGUESE_MARKERS = ["olá", "bom dia", "boa tarde", "quero", "preciso",
                          "por favor", "obrigado", "consulta", "disponível", "preço"]

    def detect(self, text: str) -> str:
        """Detect language: es, en, or pt."""
        t = text.lower()
        en_score = sum(1 for m in self.ENGLISH_MARKERS if m in t)
        pt_score = sum(1 for m in self.PORTUGUESE_MARKERS if m in t)

        if en_score >= 2:
            return "en"
        if pt_score >= 2:
            return "pt"
        if en_score == 1 and not any(w in t for w in ["hola", "buenas", "quiero"]):
            return "en"
        return "es"

    def get_language_instruction(self, lang: str) -> str:
        """Get system prompt instruction for detected language."""
        if lang == "en":
            return "The patient is writing in English. Respond entirely in English. Natural, warm tone."
        if lang == "pt":
            return "O paciente está escrevendo em português. Responda totalmente em português brasileiro."
        return ""
