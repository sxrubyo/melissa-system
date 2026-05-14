"""melissa_web_search.py — Web search via Brave Search API."""
from __future__ import annotations

import logging
import os
from typing import List, Dict, Optional

import httpx

log = logging.getLogger("melissa.web_search")

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


async def search_web(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Search the web using Brave Search API. Returns list of {title, snippet, url}."""
    if not BRAVE_API_KEY:
        log.debug("[web_search] no BRAVE_API_KEY configured")
        return []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                BRAVE_URL,
                params={"q": query, "count": num_results},
                headers={"X-Subscription-Token": BRAVE_API_KEY, "Accept": "application/json"},
            )
            if r.status_code != 200:
                log.warning(f"[web_search] Brave returned {r.status_code}")
                return []
            data = r.json()
            results = []
            for item in data.get("web", {}).get("results", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("description", ""),
                    "url": item.get("url", ""),
                })
            return results
    except Exception as e:
        log.error(f"[web_search] error: {e}")
        return []


async def search_business(business_name: str, city: str = "Medellín") -> str:
    """Search for a business and return a summary string for LLM context."""
    query = f"{business_name} {city} servicios precios horario"
    results = await search_web(query, num_results=5)
    if not results:
        return ""
    lines = []
    for r in results:
        lines.append(f"- {r['title']}: {r['snippet'][:150]}")
    return "\n".join(lines)


async def search_topic(topic: str) -> str:
    """General topic search, returns formatted results."""
    results = await search_web(topic, num_results=3)
    if not results:
        return ""
    lines = []
    for r in results:
        lines.append(f"- {r['title']}: {r['snippet'][:200]}")
    return "\n".join(lines)
