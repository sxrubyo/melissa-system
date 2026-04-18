"""
search.py — Motor de busqueda para Melissa v2
SerpAPI (primario) → Brave Search (secundario) → Apify (fallback de emergencia)

Incluye:
  - Cache en memoria con TTL configurable
  - Busqueda medica/estetica especializada con answer_box de Google
  - Deteccion automatica de procedimientos y edad en el texto
  - Autodiscovery de clinicas
  - SearchEngine compatible con melissa.py
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from typing import Dict, List, Optional, Tuple

import httpx

log = logging.getLogger("melissa.search")

# ─── API Keys ────────────────────────────────────────────────────────────────
SERP_API_KEY  = os.getenv("SERP_API_KEY",  "")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")

# ─── Cache en memoria ────────────────────────────────────────────────────────
_search_cache: Dict[str, Tuple[str, float]] = {}
_CACHE_TTL = 1800   # 30 min


def _cache_key(query: str) -> str:
    return hashlib.md5(query.lower().strip().encode()).hexdigest()[:16]


def _cache_get(query: str) -> Optional[str]:
    k = _cache_key(query)
    if k in _search_cache:
        result, ts = _search_cache[k]
        if time.time() - ts < _CACHE_TTL:
            log.debug(f"[cache hit] {query[:50]}")
            return result
    return None


def _cache_set(query: str, result: str):
    k = _cache_key(query)
    _search_cache[k] = (result, time.time())
    if len(_search_cache) > 500:
        oldest = sorted(_search_cache.items(), key=lambda x: x[1][1])[:100]
        for key, _ in oldest:
            del _search_cache[key]


# ─── SerpAPI (primario) ──────────────────────────────────────────────────────

async def serp_search(query: str, count: int = 5,
                      location: str = "Medellin, Colombia") -> List[Dict]:
    """
    Busqueda via SerpAPI (Google results reales).
    Captura answer_box y knowledge_graph ademas de resultados organicos.
    """
    if not SERP_API_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                "https://serpapi.com/search",
                params={
                    "engine":   "google",
                    "q":        query,
                    "api_key":  SERP_API_KEY,
                    "hl":       "es",
                    "gl":       "co",
                    "location": location,
                    "num":      count,
                    "safe":     "active",
                },
            )
            r.raise_for_status()
            data = r.json()

        results = []

        # Answer box — respuesta directa de Google (mejor fuente para preguntas medicas)
        ab = data.get("answer_box", {})
        if ab:
            snippet = (
                ab.get("answer") or
                ab.get("snippet") or
                ab.get("result") or ""
            )
            if snippet:
                results.append({
                    "title":       ab.get("title", "Respuesta directa"),
                    "url":         ab.get("link", ""),
                    "description": snippet.strip()[:700],
                    "source":      "answer_box",
                })

        # Knowledge graph — para procedimientos/tratamientos reconocidos
        kg = data.get("knowledge_graph", {})
        if kg and kg.get("description"):
            results.append({
                "title":       kg.get("title", ""),
                "url":         kg.get("website", ""),
                "description": kg["description"][:500],
                "source":      "knowledge_graph",
            })

        # Resultados organicos
        for res in data.get("organic_results", [])[:count]:
            desc = res.get("snippet", "").strip()
            if desc:
                results.append({
                    "title":       res.get("title", ""),
                    "url":         res.get("link", ""),
                    "description": desc[:400],
                    "source":      "organic",
                })

        log.info(f"[serp] {len(results)} resultados — {query[:60]}")
        return results

    except Exception as e:
        log.warning(f"[serp] error: {e}")
        return []


# ─── Brave Search (secundario) ───────────────────────────────────────────────

async def brave_search(query: str, count: int = 5) -> List[Dict]:
    if not BRAVE_API_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept":               "application/json",
                    "Accept-Encoding":      "gzip",
                    "X-Subscription-Token": BRAVE_API_KEY,
                },
                params={"q": query, "count": count, "search_lang": "es", "country": "CO"},
            )
            r.raise_for_status()
            return [
                {"title": res.get("title", ""), "url": res.get("url", ""),
                 "description": res.get("description", ""), "source": "brave"}
                for res in r.json().get("web", {}).get("results", [])
                if res.get("description")
            ]
    except Exception as e:
        log.warning(f"[brave] error: {e}")
        return []


# ─── Apify (fallback de emergencia) ─────────────────────────────────────────

async def apify_search(query: str, count: int = 5) -> List[Dict]:
    if not APIFY_API_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.post(
                "https://api.apify.com/v2/acts/apify~google-search-scraper/run-sync-get-dataset-items",
                headers={"Authorization": f"Bearer {APIFY_API_KEY}"},
                json={"queries": query, "maxPagesPerQuery": 1,
                      "resultsPerPage": count, "languageCode": "es", "countryCode": "co"},
                params={"timeout": 20, "memory": 256},
            )
            items = r.json()
            if not items or not isinstance(items, list):
                return []
            results = []
            for item in items[:1]:
                for res in item.get("organicResults", [])[:count]:
                    if res.get("description"):
                        results.append({"title": res.get("title", ""),
                                        "url": res.get("url", ""),
                                        "description": res["description"],
                                        "source": "apify"})
            return results
    except Exception as e:
        log.warning(f"[apify] error: {e}")
        return []


# ─── Motor unificado con fallback automatico ─────────────────────────────────

async def web_search(query: str, count: int = 5) -> List[Dict]:
    """SerpAPI → Brave → Apify. Retorna lista de resultados."""
    results = await serp_search(query, count=count)
    if results:
        return results
    log.info(f"[search] SerpAPI vacio, probando Brave")
    results = await brave_search(query, count=count)
    if results:
        return results
    log.info(f"[search] Brave vacio, probando Apify")
    return await apify_search(query, count=count)


async def search_context(query: str, context: str = "", count: int = 5,
                         max_chars: int = 1400) -> str:
    """
    Busqueda y construccion de contexto para el LLM.
    Prioriza answer_box (respuestas directas de Google) sobre resultados organicos.
    """
    cache_key = f"{context}|{query}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    full_query = f"{context} {query}".strip() if context else query
    results = await web_search(full_query, count=count)
    if not results:
        _cache_set(cache_key, "")
        return ""

    # Ordenar: answer_box primero (es la respuesta directa de Google)
    priority = {"answer_box": 0, "knowledge_graph": 1, "organic": 2, "brave": 3, "apify": 4}
    results.sort(key=lambda r: priority.get(r.get("source", "organic"), 5))

    lines = []
    for r in results:
        desc = r.get("description", "").strip()
        title = r.get("title", "").strip()
        if desc:
            lines.append(f"• {title}: {desc}" if title else f"• {desc}")

    result_str = "\n".join(lines)[:max_chars]
    _cache_set(cache_key, result_str)
    return result_str


# ─── Busqueda medica/estetica especializada ───────────────────────────────────

# Aliases de procedimientos para construir queries ricas
PROCEDURE_QUERIES: Dict[str, str] = {
    "botox":              "toxina botulinica botox beneficios edad resultados duracion quien puede",
    "bichectomia":        "bichectomia extraccion bolas bichat resultados recuperacion candidatos",
    "rellenos":           "rellenos acido hialuronico labios mejillas volumizacion resultados duracion",
    "hilos":              "hilos tensores lifting facial resultados contraindicaciones edad candidatos",
    "prp":                "plasma rico plaquetas PRP piel facial rejuvenecimiento beneficios",
    "laser":              "laser rejuvenecimiento piel tipos sesiones resultados contraindicaciones",
    "ipl":                "luz pulsada intensa IPL manchas piel rosácea tratamiento sesiones",
    "radiofrecuencia":    "radiofrecuencia facial corporal colageno flacidez resultados sesiones",
    "ultrasonido":        "HIFU ultrasonido focalizado lifting sin cirugia resultados candidatos",
    "lipolisis":          "lipolisis inyectable grasa localizada papada abdomen resultados",
    "cavitacion":         "cavitacion ultrasonido adipocitos celulitis resultados sesiones",
    "limpieza":           "limpieza facial profunda tipos piel combinada grasa seca beneficios pasos",
    "microdermoabrasion": "microdermoabrasion cristales diamante cicatrices manchas poros beneficios",
    "peelings":           "peeling quimico acidos TCA AHA BHA tipos piel recuperacion resultados",
    "dermapen":           "dermapen microagujas colágeno elastina cicatrices poros resultados sesiones",
    "mesoterapia":        "mesoterapia capilar caida cabello vitaminas resultados sesiones",
    "presoterapia":       "presoterapia drenaje linfático retención líquidos celulitis beneficios",
}

# Keywords para detectar procedimientos en texto del paciente
PROCEDURE_KEYWORDS: Dict[str, List[str]] = {
    "botox":              ["botox", "toxina", "botulinica", "bótox"],
    "bichectomia":        ["bichectomia", "bichat", "bolas de grasa", "mejillas grandes"],
    "rellenos":           ["relleno", "hialuronico", "labio", "pomulo", "mejilla", "ácido"],
    "hilos":              ["hilo", "lifting", "tensor"],
    "prp":                ["prp", "plasma", "plaqueta"],
    "laser":              ["laser", "láser"],
    "ipl":                ["ipl", "luz pulsada"],
    "radiofrecuencia":    ["radiofrecuencia", "rf facial", "rf corporal"],
    "ultrasonido":        ["hifu", "ultrasonido focalizado", "sin cirugia"],
    "lipolisis":          ["lipolisis", "lipólisis", "grasa localizada", "papada"],
    "cavitacion":         ["cavitacion", "cavitación", "celulitis"],
    "limpieza":           ["limpieza facial", "limpieza de piel", "limpiar la piel"],
    "microdermoabrasion": ["microdermoabrasion", "dermabrasion"],
    "peelings":           ["peeling", "exfoliacion quimica", "acido en la cara"],
    "dermapen":           ["dermapen", "microagujas", "microaguja"],
    "mesoterapia":        ["mesoterapia", "coctel capilar", "caida de cabello"],
    "presoterapia":       ["presoterapia", "drenaje linfatico", "drenaje linfático"],
}


def detect_procedure(text: str) -> Optional[str]:
    """Detecta si el texto menciona un procedimiento estetico. Retorna nombre canonico."""
    text_lower = text.lower()
    for procedure, keywords in PROCEDURE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return procedure
    return None


def extract_age(text: str) -> Optional[int]:
    """Extrae edad mencionada en el texto del paciente."""
    m = re.search(r'\b(\d{2})\s*(años?|a[ñn]os?)', text.lower())
    if m:
        age = int(m.group(1))
        if 15 <= age <= 90:
            return age
    return None


async def medical_search(procedure: str, question: str = "",
                         patient_age: Optional[int] = None,
                         clinic_services: Optional[List[str]] = None) -> str:
    """
    Busqueda medica especializada para un procedimiento especifico.
    Construye queries ricas considerando edad del paciente y servicios de la clinica.
    Retorna contexto rico para el LLM.
    """
    proc_lower = procedure.lower().strip()
    base_query = PROCEDURE_QUERIES.get(proc_lower, f"{procedure} tratamiento estetico")

    # Ajustar query segun edad
    age_suffix = ""
    if patient_age:
        if patient_age >= 60:
            age_suffix = "mayores 60 años contraindicaciones seguridad efectividad adultos mayores"
        elif patient_age >= 50:
            age_suffix = "50 años menopausia cambios hormonales beneficios anti-edad"
        elif patient_age >= 40:
            age_suffix = "40 años manchas flacidez rejuvenecimiento preventivo"
        elif patient_age >= 30:
            age_suffix = "30 años prevencion primeras lineas expresion"
        else:
            age_suffix = "jovenes 20 años preventivo acne cicatrices"

    # Query principal
    main_query = f"{base_query} {age_suffix} {question}".strip()

    # Query de precios locales — siempre util para el paciente
    price_query = f"{procedure} precio costo Medellin Colombia clinica estetica 2024"

    # Buscar en paralelo para no perder tiempo
    main_ctx, price_ctx = await asyncio.gather(
        search_context(main_query, count=5, max_chars=1000),
        search_context(price_query, count=3, max_chars=400),
    )

    parts = []
    if main_ctx:
        parts.append(f"INFORMACION DEL PROCEDIMIENTO:\n{main_ctx}")
    if price_ctx:
        parts.append(f"PRECIOS DE REFERENCIA EN COLOMBIA:\n{price_ctx}")

    return "\n\n".join(parts) if parts else ""


# ─── Autodiscovery de clinica ────────────────────────────────────────────────

async def discover_clinic(clinic_name: str, city: str = "Medellin") -> str:
    """
    Busca info real de la clinica en Google y retorna contexto crudo.
    """
    queries = [
        f"{clinic_name} {city} servicios precios horario telefono",
        f'"{clinic_name}" clinica estetica {city}',
    ]

    snippets = []
    for q in queries:
        cached = _cache_get(q)
        if cached is not None:
            snippets.append(cached)
        else:
            results = await web_search(q, count=5)
            if results:
                block = "\n".join(
                    f"- {r['title']}: {r['description']}"
                    for r in results if r.get("description")
                )[:800]
                _cache_set(q, block)
                snippets.append(block)

        if snippets and len(snippets[0]) > 200:
            break

    return "\n".join(snippets)[:2000]


# ─── Clase compatible con melissa.py ─────────────────────────────────────────

class SearchEngine:
    """
    Interfaz compatible con WebSearchEngine en melissa.py.
    Drop-in replacement con capacidades medicas adicionales.
    """

    async def search(self, query: str, context: str = "") -> str:
        return await search_context(query, context=context)

    async def discover(self, clinic_name: str, city: str = "Medellin") -> str:
        return await discover_clinic(clinic_name, city)

    async def medical(self, procedure: str, question: str = "",
                      patient_age: Optional[int] = None,
                      clinic_services: Optional[List[str]] = None) -> str:
        return await medical_search(procedure, question, patient_age, clinic_services)

    def detect_procedure(self, text: str) -> Optional[str]:
        return detect_procedure(text)

    def extract_age(self, text: str) -> Optional[int]:
        return extract_age(text)
