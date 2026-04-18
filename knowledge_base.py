"""
knowledge_base.py — Base de conocimiento de la clinica para Melissa

Sistema que permite al admin cargar un documento maestro con toda la info
de la clinica (servicios, precios, contraindicaciones, protocolos, FAQs, etc.)
y que Melissa consulte siempre antes de responder.

Flujo:
  1. Admin termina setup y Melissa le pide el documento maestro
  2. Admin envia texto libre (puede ser muy largo)
  3. Se chunquea y se guarda en DB
  4. Cuando un paciente pregunta algo, se recuperan los chunks relevantes
  5. El contexto del KB se inyecta en el system prompt con maxima prioridad

Schema DB adicional:
  - knowledge_base: texto completo del documento
  - kb_chunks: chunks indexados por palabras clave
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("melissa.kb")

# Tamano de chunks (en caracteres)
CHUNK_SIZE   = 400
CHUNK_OVERLAP = 80

# Cuantos chunks incluir en el contexto del LLM
MAX_CHUNKS_IN_CONTEXT = 4

# Minima relevancia para incluir un chunk (0-1)
MIN_RELEVANCE = 0.15


# ─── Chunking ────────────────────────────────────────────────────────────────

def _split_into_chunks(text: str) -> List[str]:
    """
    Divide el texto en chunks con overlap.
    Intenta partir en parrafos/oraciones completas.
    """
    # Limpiar texto
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    # Primero intentar partir por parrafos
    paragraphs = [p.strip() for p in re.split(r'\n\n+', text) if p.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) < CHUNK_SIZE:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            # Si el parrafo es muy largo, partirlo por oraciones
            if len(para) > CHUNK_SIZE:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                buf = ""
                for s in sentences:
                    if len(buf) + len(s) < CHUNK_SIZE:
                        buf = (buf + " " + s).strip()
                    else:
                        if buf:
                            chunks.append(buf)
                        buf = s
                if buf:
                    current = buf
                else:
                    current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return [c for c in chunks if len(c) > 30]


def _extract_keywords(text: str) -> List[str]:
    """
    Extrae palabras clave de un texto para indexacion.
    Ignora stopwords comunes en espanol.
    """
    STOPWORDS = {
        "el", "la", "los", "las", "un", "una", "unos", "unas",
        "de", "del", "al", "a", "en", "con", "por", "para", "que",
        "como", "cuando", "donde", "cual", "quien", "este", "esta",
        "ese", "esa", "mi", "tu", "su", "y", "o", "pero", "si", "no",
        "mas", "muy", "ya", "es", "son", "era", "fue", "ser", "estar",
        "hay", "han", "hemos", "tienen", "tiene", "hace", "hacer",
        "puede", "pueden", "se", "lo", "le", "les", "me", "te", "nos",
        "sobre", "entre", "hasta", "desde", "durante", "antes", "despues",
        "tambien", "ademas", "aunque", "porque", "sino", "sino", "ni",
        "todo", "toda", "todos", "todas", "cada", "otro", "otra",
    }
    words = re.findall(r'\b[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]{3,}\b', text.lower())
    keywords = [w for w in words if w not in STOPWORDS]
    # Frecuencia
    freq: Dict[str, int] = {}
    for w in keywords:
        freq[w] = freq.get(w, 0) + 1
    # Top palabras por frecuencia
    return sorted(freq, key=freq.get, reverse=True)[:20]


def _score_chunk(chunk_keywords: List[str], query_keywords: List[str]) -> float:
    """
    Calcula relevancia de un chunk para una query.
    Score de 0 a 1.
    """
    if not query_keywords or not chunk_keywords:
        return 0.0
    chunk_set = set(chunk_keywords)
    matches = sum(1 for kw in query_keywords if kw in chunk_set)
    # Bonus por matches exactos de frases
    return min(matches / max(len(query_keywords), 1), 1.0)


# ─── KnowledgeBase Manager ────────────────────────────────────────────────────

class KnowledgeBase:
    """
    Gestor de la base de conocimiento de la clinica.
    Se inicializa con la conexion DB de melissa.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_tables()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self):
        """Crea las tablas KB si no existen (migracion segura)."""
        with self._conn() as c:
            c.executescript("""
            -- Documento maestro de la clinica
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY,
                raw_text TEXT DEFAULT '',
                chunk_count INTEGER DEFAULT 0,
                word_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            INSERT OR IGNORE INTO knowledge_base (id) VALUES (1);

            -- Chunks indexados para recuperacion rapida
            CREATE TABLE IF NOT EXISTS kb_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                keywords TEXT DEFAULT '[]',
                section_hint TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_kb_chunks_id ON kb_chunks(id);
            """)
        log.info("[kb] tablas listas")

    # ─── Ingestion ────────────────────────────────────────────────────────────

    def ingest(self, raw_text: str) -> Dict:
        """
        Procesa y guarda el documento maestro de la clinica.
        Reemplaza cualquier KB anterior.
        Retorna stats del ingestion.
        """
        if not raw_text or not raw_text.strip():
            return {"ok": False, "error": "texto vacio"}

        raw_text = raw_text.strip()
        chunks = _split_into_chunks(raw_text)
        word_count = len(raw_text.split())

        with self._conn() as c:
            # Limpiar chunks anteriores
            c.execute("DELETE FROM kb_chunks")

            # Guardar documento maestro
            c.execute("""
                UPDATE knowledge_base
                SET raw_text=?, chunk_count=?, word_count=?, updated_at=datetime('now')
                WHERE id=1
            """, (raw_text, len(chunks), word_count))

            # Insertar chunks con keywords
            for i, chunk in enumerate(chunks):
                keywords = _extract_keywords(chunk)
                # Detectar hint de seccion (primera linea si parece titulo)
                first_line = chunk.split('\n')[0].strip()
                section_hint = first_line if len(first_line) < 60 and not first_line.endswith('.') else ""

                c.execute("""
                    INSERT INTO kb_chunks (content, keywords, section_hint)
                    VALUES (?, ?, ?)
                """, (chunk, json.dumps(keywords, ensure_ascii=False), section_hint))

        log.info(f"[kb] ingested {len(chunks)} chunks, {word_count} palabras")
        return {
            "ok": True,
            "chunks": len(chunks),
            "words": word_count,
            "chars": len(raw_text),
        }

    def append(self, additional_text: str) -> Dict:
        """Agrega texto al KB existente sin borrar lo anterior."""
        existing = self.get_raw()
        combined = (existing + "\n\n" + additional_text).strip() if existing else additional_text
        return self.ingest(combined)

    # ─── Recuperacion ─────────────────────────────────────────────────────────

    def retrieve(self, query: str, max_chunks: int = MAX_CHUNKS_IN_CONTEXT) -> str:
        """
        Recupera los chunks mas relevantes para una query.
        Retorna contexto listo para inyectar al LLM.
        """
        if not self.has_content():
            return ""

        query_keywords = _extract_keywords(query)
        if not query_keywords:
            # Sin keywords claras: retornar primeros chunks (intro de la clinica)
            return self._get_first_chunks(max_chunks)

        with self._conn() as c:
            rows = c.execute("SELECT id, content, keywords FROM kb_chunks").fetchall()

        # Calcular relevancia de cada chunk
        scored: List[Tuple[float, str]] = []
        for row in rows:
            try:
                chunk_kws = json.loads(row["keywords"] or "[]")
            except Exception:
                chunk_kws = []
            score = _score_chunk(chunk_kws, query_keywords)
            if score >= MIN_RELEVANCE:
                scored.append((score, row["content"]))

        if not scored:
            # Ninguno relevante: dar los primeros (contexto general)
            return self._get_first_chunks(max_chunks)

        # Ordenar por relevancia descendente
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [content for _, content in scored[:max_chunks]]

        return "\n\n---\n\n".join(selected)

    def _get_first_chunks(self, n: int) -> str:
        """Retorna los primeros n chunks (contexto general de la clinica)."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT content FROM kb_chunks ORDER BY id LIMIT ?", (n,)
            ).fetchall()
        return "\n\n---\n\n".join(r["content"] for r in rows)

    def get_raw(self) -> str:
        """Retorna el documento completo."""
        with self._conn() as c:
            row = c.execute("SELECT raw_text FROM knowledge_base WHERE id=1").fetchone()
        return row["raw_text"] if row else ""

    def get_stats(self) -> Dict:
        with self._conn() as c:
            row = c.execute(
                "SELECT chunk_count, word_count, updated_at FROM knowledge_base WHERE id=1"
            ).fetchone()
        if row:
            return {
                "chunks": row["chunk_count"],
                "words":  row["word_count"],
                "updated_at": row["updated_at"],
            }
        return {"chunks": 0, "words": 0, "updated_at": None}

    def has_content(self) -> bool:
        with self._conn() as c:
            row = c.execute(
                "SELECT chunk_count FROM knowledge_base WHERE id=1"
            ).fetchone()
        return bool(row and row["chunk_count"] > 0)

    def clear(self):
        """Borra el KB completo."""
        with self._conn() as c:
            c.execute("DELETE FROM kb_chunks")
            c.execute("""
                UPDATE knowledge_base
                SET raw_text='', chunk_count=0, word_count=0, updated_at=datetime('now')
                WHERE id=1
            """)
        log.info("[kb] KB limpiado")


# ─── Formateo para el LLM ─────────────────────────────────────────────────────

def format_kb_context(kb_text: str) -> str:
    """
    Envuelve el contexto del KB en un bloque claro para el LLM.
    """
    if not kb_text:
        return ""
    return (
        "=== BASE DE CONOCIMIENTO DE LA CLINICA ===\n"
        "(Esta es informacion oficial de la clinica. Usala con maxima prioridad "
        "antes de buscar en internet o inventar datos.)\n\n"
        f"{kb_text}\n"
        "=== FIN BASE DE CONOCIMIENTO ==="
    )
