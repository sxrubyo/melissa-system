"""
melissa_memory_engine.py — Self-learning episodic + semantic memory.
Inspired by OpenClaw's memory pattern.
Per-instance memory with TF-IDF recall, entity extraction, FAQ consolidation.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("melissa.memory")


class MelissaMemoryEngine:
    """Per-instance memory with episodic recall + semantic extraction + procedural learning."""

    def __init__(self, base_dir: str = "memory_store"):
        self._base = Path(base_dir)
        self._base.mkdir(exist_ok=True)
        self._tfidf_cache: Dict[str, Any] = {}

    def _instance_dir(self, instance_id: str) -> Path:
        d = self._base / instance_id
        for sub in ("episodic", "semantic", "procedural", "working"):
            (d / sub).mkdir(parents=True, exist_ok=True)
        return d

    async def ingest_conversation(self, instance_id: str, chat_id: str, messages: List[Dict[str, str]]):
        """After every conversation: store episodic + extract entities + update FAQ frequency."""
        idir = self._instance_dir(instance_id)
        today = datetime.now().strftime("%Y-%m-%d")

        # 1. Store episodic
        ep_file = idir / "episodic" / f"{today}.jsonl"
        entry = {
            "ts": datetime.now().isoformat(),
            "chat_id": chat_id,
            "messages": messages[-20:],
        }
        with open(ep_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # 2. Extract entities
        entities = self._extract_entities(messages)
        if entities:
            ent_file = idir / "semantic" / "entities.json"
            existing = json.loads(ent_file.read_text()) if ent_file.exists() else {}
            for etype, values in entities.items():
                if etype not in existing:
                    existing[etype] = {}
                for val in values:
                    if val in existing[etype]:
                        existing[etype][val]["count"] += 1
                        existing[etype][val]["last_seen"] = datetime.now().isoformat()
                    else:
                        existing[etype][val] = {
                            "count": 1,
                            "last_seen": datetime.now().isoformat(),
                            "chat_id": chat_id,
                        }
            ent_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

        # 3. Update FAQ frequency
        user_questions = [
            m["content"] for m in messages
            if m.get("role") == "user" and "?" in m.get("content", "")
        ]
        if user_questions:
            faq_file = idir / "semantic" / "faqs.json"
            faqs = json.loads(faq_file.read_text()) if faq_file.exists() else {}
            for q in user_questions:
                qhash = hashlib.md5(q.lower().strip().encode()).hexdigest()[:12]
                if qhash in faqs:
                    faqs[qhash]["frequency"] += 1
                    faqs[qhash]["last_asked"] = datetime.now().isoformat()
                else:
                    answer = ""
                    for i, m in enumerate(messages):
                        if m.get("content") == q and i + 1 < len(messages):
                            answer = messages[i + 1].get("content", "")
                            break
                    faqs[qhash] = {
                        "question": q,
                        "answer": answer[:500],
                        "frequency": 1,
                        "first_asked": datetime.now().isoformat(),
                        "last_asked": datetime.now().isoformat(),
                    }
            faq_file.write_text(json.dumps(faqs, ensure_ascii=False, indent=2))

        # Invalidate TF-IDF cache
        self._tfidf_cache.pop(instance_id, None)

    async def recall_context(self, instance_id: str, user_message: str, top_k: int = 5) -> List[Dict]:
        """Before every LLM call: retrieve relevant past exchanges using TF-IDF similarity."""
        idir = self._instance_dir(instance_id)

        # Load episodic entries from last 30 days
        docs: List[Dict] = []
        ep_dir = idir / "episodic"
        cutoff = datetime.now() - timedelta(days=30)

        for f in sorted(ep_dir.glob("*.jsonl"), reverse=True):
            try:
                file_date = datetime.strptime(f.stem, "%Y-%m-%d")
                if file_date < cutoff:
                    break
            except ValueError:
                continue
            with open(f) as fh:
                for line in fh:
                    try:
                        entry = json.loads(line)
                        text = " ".join(
                            m.get("content", "") for m in entry.get("messages", [])
                        )
                        if text.strip():
                            docs.append({"text": text, "entry": entry})
                    except json.JSONDecodeError:
                        continue

        if not docs or not user_message.strip():
            return []

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            corpus = [d["text"] for d in docs] + [user_message]
            vectorizer = TfidfVectorizer(max_features=5000)
            tfidf_matrix = vectorizer.fit_transform(corpus)

            query_vec = tfidf_matrix[-1]
            doc_vecs = tfidf_matrix[:-1]
            similarities = cosine_similarity(query_vec, doc_vecs).flatten()

            top_indices = similarities.argsort()[-top_k:][::-1]
            results = []
            for idx in top_indices:
                if similarities[idx] > 0.05:
                    results.append({
                        "score": float(similarities[idx]),
                        "messages": docs[idx]["entry"].get("messages", [])[-6:],
                        "chat_id": docs[idx]["entry"].get("chat_id", ""),
                        "ts": docs[idx]["entry"].get("ts", ""),
                    })
            return results
        except ImportError:
            log.warning("[memory] scikit-learn not available, skipping recall")
            return []
        except Exception as e:
            log.warning(f"[memory] recall error: {e}")
            return []

    async def get_top_faqs(self, instance_id: str, limit: int = 20) -> List[Dict]:
        """Get most frequently asked questions for system prompt injection."""
        idir = self._instance_dir(instance_id)
        faq_file = idir / "semantic" / "faqs.json"
        if not faq_file.exists():
            return []
        faqs = json.loads(faq_file.read_text())
        sorted_faqs = sorted(faqs.values(), key=lambda x: x.get("frequency", 0), reverse=True)
        return sorted_faqs[:limit]

    async def learn_from_success(self, instance_id: str, chat_id: str,
                                 flow: List[Dict], outcome: str = "booking"):
        """Store successful conversation patterns."""
        idir = self._instance_dir(instance_id)
        success_file = idir / "procedural" / "successful_flows.json"
        existing = json.loads(success_file.read_text()) if success_file.exists() else []
        existing.append({
            "ts": datetime.now().isoformat(),
            "chat_id": chat_id,
            "outcome": outcome,
            "flow_summary": [
                {"role": m["role"], "content": m["content"][:200]}
                for m in flow[-10:]
            ],
        })
        existing = existing[-200:]
        success_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

    async def learn_from_failure(self, instance_id: str, chat_id: str,
                                 flow: List[Dict], reason: str = "escalated"):
        """Store failed conversation patterns for avoidance."""
        idir = self._instance_dir(instance_id)
        fail_file = idir / "procedural" / "failed_flows.json"
        existing = json.loads(fail_file.read_text()) if fail_file.exists() else []
        existing.append({
            "ts": datetime.now().isoformat(),
            "chat_id": chat_id,
            "reason": reason,
            "flow_summary": [
                {"role": m["role"], "content": m["content"][:200]}
                for m in flow[-10:]
            ],
        })
        existing = existing[-100:]
        fail_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

    async def weekly_consolidation(self, instance_id: str):
        """Merge episodic -> semantic, prune duplicates, update FAQ index. Run weekly."""
        idir = self._instance_dir(instance_id)
        log.info(f"[memory] starting weekly consolidation for {instance_id}")

        # 1. Re-scan all episodic for FAQ extraction
        ep_dir = idir / "episodic"
        all_questions: List[Dict] = []
        for f in ep_dir.glob("*.jsonl"):
            with open(f) as fh:
                for line in fh:
                    try:
                        entry = json.loads(line)
                        msgs = entry.get("messages", [])
                        for i, m in enumerate(msgs):
                            if m.get("role") == "user" and "?" in m.get("content", ""):
                                answer = ""
                                if i + 1 < len(msgs) and msgs[i + 1].get("role") == "assistant":
                                    answer = msgs[i + 1]["content"][:500]
                                all_questions.append({"q": m["content"], "a": answer})
                    except Exception:
                        continue

        # 2. Update FAQ index
        faq_file = idir / "semantic" / "faqs.json"
        faqs = json.loads(faq_file.read_text()) if faq_file.exists() else {}

        for qa in all_questions:
            qhash = hashlib.md5(qa["q"].lower().strip().encode()).hexdigest()[:12]
            if qhash in faqs:
                faqs[qhash]["frequency"] += 1
                if qa["a"] and len(qa["a"]) > len(faqs[qhash].get("answer", "")):
                    faqs[qhash]["answer"] = qa["a"]
            else:
                faqs[qhash] = {
                    "question": qa["q"],
                    "answer": qa["a"],
                    "frequency": 1,
                    "first_asked": datetime.now().isoformat(),
                    "last_asked": datetime.now().isoformat(),
                }

        faq_file.write_text(json.dumps(faqs, ensure_ascii=False, indent=2))

        # 3. Prune episodic older than 90 days
        cutoff = datetime.now() - timedelta(days=90)
        for f in ep_dir.glob("*.jsonl"):
            try:
                file_date = datetime.strptime(f.stem, "%Y-%m-%d")
                if file_date < cutoff:
                    f.unlink()
                    log.info(f"[memory] pruned old episodic: {f.name}")
            except Exception:
                continue

        log.info(f"[memory] consolidation complete for {instance_id}: {len(faqs)} FAQs")

    def _extract_entities(self, messages: List[Dict]) -> Dict[str, List[str]]:
        """Simple regex-based entity extraction."""
        entities: Dict[str, List[str]] = {"phones": [], "emails": [], "names": []}
        text = " ".join(
            m.get("content", "") for m in messages if m.get("role") == "user"
        )

        # Colombian phone numbers
        phones = re.findall(r"\b3[0-9]{9}\b", text)
        entities["phones"] = list(set(phones))

        # Emails
        emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        entities["emails"] = list(set(emails))

        # Names after "me llamo", "soy", "mi nombre es"
        name_patterns = [
            r"(?:me llamo|soy|mi nombre es)\s+([A-ZÁÉÍÓÚ][a-záéíóú]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóú]+)?)",
        ]
        for pat in name_patterns:
            matches = re.findall(pat, text)
            entities["names"].extend(matches)
        entities["names"] = list(set(entities["names"]))

        return {k: v for k, v in entities.items() if v}


# Singleton
memory_engine = MelissaMemoryEngine()
