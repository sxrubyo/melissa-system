"""
nova_bridge.py — Puente entre Nova y Melissa

Nova es el sistema nervioso de Melissa:
  - Antes de enviar cualquier mensaje, Melissa pregunta a Nova: "¿puedo?"
  - Nova evalúa las reglas y responde: APPROVED / BLOCKED / ESCALATED
  - Todo queda en el ledger criptográfico de Nova
  - El admin puede crear reglas en lenguaje natural: "no le mandes X a Y"

Cómo funciona:
  1. MelissaGuard intercepta cada mensaje ANTES de enviarlo
  2. Llama a Nova /validate con la acción
  3. APPROVED → mensaje se envía normalmente
  4. BLOCKED → Melissa responde algo alternativo, no el mensaje bloqueado
  5. ESCALATED → Melissa le pregunta al admin antes de enviar

Requisitos:
  - Nova server corriendo (puerto 9002 por defecto)
  - NOVA_TOKEN configurado en .env (token del agente "Melissa")
  - NOVA_URL=http://localhost:9002

Sin Nova activo → Melissa funciona normal (modo degradado seguro)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Dict, List, Optional, Tuple

import httpx

log = logging.getLogger("melissa.nova")

# ─── Config ──────────────────────────────────────────────────────────────────
NOVA_URL      = os.getenv("NOVA_URL",      "http://localhost:9002")
NOVA_TOKEN    = os.getenv("NOVA_TOKEN",    "")   # Token del agente Melissa en Nova
NOVA_API_KEY  = os.getenv("NOVA_API_KEY",  "")   # API key de Nova
NOVA_ENABLED  = os.getenv("NOVA_ENABLED",  "true").lower() == "true"
NOVA_TIMEOUT  = float(os.getenv("NOVA_TIMEOUT", "3.0"))  # 3s max, no bloquear usuarios


# ─── Veredictos de Nova ───────────────────────────────────────────────────────
APPROVED  = "APPROVED"
BLOCKED   = "BLOCKED"
ESCALATED = "ESCALATED"
UNKNOWN   = "UNKNOWN"


# ─── Cache local para decisiones rápidas ─────────────────────────────────────
_decision_cache: Dict[str, Tuple[str, float]] = {}
_CACHE_TTL = 300  # 5 min

def _cache_key(action: str, context: str) -> str:
    import hashlib
    return hashlib.md5(f"{action}|{context}".encode()).hexdigest()[:12]

def _cache_get(key: str) -> Optional[str]:
    if key in _decision_cache:
        verdict, ts = _decision_cache[key]
        if time.time() - ts < _CACHE_TTL:
            return verdict
    return None

def _cache_set(key: str, verdict: str):
    _decision_cache[key] = (verdict, time.time())


# ─── Reglas locales pre-evaluación ───────────────────────────────────────────
# Evita llamadas a Nova para casos obvios — <1ms

# Mensajes que SIEMPRE se aprueban (mínimamente riesgosos)
_ALWAYS_APPROVE_PATTERNS = [
    r"^(hola|buenas|buenos días|buenas tardes)$",
    r"^(ok|listo|dale|claro|perfecto|entendido)$",
    r"agendar.*cita",
    r"te paso.*información",
    r"gracias.*escribir",
    r"(horario|horarios|servicios|dirección|ubicación)",
]

# Mensajes que SIEMPRE se bloquean (nunca debería enviar esto un asistente médico)
_ALWAYS_BLOCK_PATTERNS = [
    r"(diagnóstico|diagnóstico médico|tengo cáncer|tienes cáncer)",
    r"(toma.*pastilla|toma.*medicamento|dosis.*recomendad)",
    r"(contraindicado.*absolutamente|no debes.*nunca.*hacer)",
    r"(precio.*gratis|descuento.*100%|sin costo.*siempre)",
    r"(manda.*fotos.*privadas|mándame.*foto)",
]

def _local_pre_check(action: str) -> Optional[str]:
    """
    Decisión local ultrarrápida antes de llamar a Nova.
    Retorna APPROVED/BLOCKED/None (None = necesita Nova)
    """
    action_low = action.lower().strip()

    for pattern in _ALWAYS_BLOCK_PATTERNS:
        if re.search(pattern, action_low):
            log.info(f"[nova_local] BLOCKED (local): {action[:60]}")
            return BLOCKED

    for pattern in _ALWAYS_APPROVE_PATTERNS:
        if re.search(pattern, action_low):
            return APPROVED

    return None  # Necesita evaluación de Nova


# ─── Cliente Nova ─────────────────────────────────────────────────────────────

class NovaClient:
    """Cliente para la API de Nova."""

    def __init__(self, url: str = NOVA_URL, api_key: str = NOVA_API_KEY,
                 token_id: str = NOVA_TOKEN):
        self.url      = url.rstrip("/")
        self.api_key  = api_key
        self.token_id = token_id
        self._healthy: Optional[bool] = None
        self._last_health_check = 0.0

    def _headers(self) -> Dict:
        h = {"Content-Type": "application/json", "User-Agent": "melissa/5.0"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
            h["X-API-Key"] = self.api_key
        return h

    async def health_check(self) -> bool:
        """Verifica si Nova está activo. Cachea el resultado por 30s."""
        now = time.time()
        if now - self._last_health_check < 30 and self._healthy is not None:
            return self._healthy
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(f"{self.url}/health", headers=self._headers())
                self._healthy = r.status_code in (200, 204)
                self._last_health_check = now
                if self._healthy:
                    log.debug("[nova] server healthy")
                return self._healthy
        except Exception as e:
            log.debug(f"[nova] health check failed: {e}")
            self._healthy = False
            self._last_health_check = now
            return False

    async def validate(
        self,
        action: str,
        context: str = "",
        patient_id: str = "",
        dry_run: bool = False
    ) -> Dict:
        """
        Valida una acción con Nova.
        Retorna: {"verdict": "APPROVED|BLOCKED|ESCALATED",
                  "score": 0-100, "reason": "...", "ledger_id": "..."}
        """
        if not self.token_id:
            return {"verdict": APPROVED, "reason": "no_token_configured"}

        payload = {
            "token_id":   self.token_id,
            "action":     action,
            "context":    context or patient_id,
            "dry_run":    dry_run,
            "check_duplicates": False,  # No duplicados para mensajes
        }

        try:
            async with httpx.AsyncClient(timeout=NOVA_TIMEOUT) as c:
                r = await c.post(f"{self.url}/validate",
                                  json=payload, headers=self._headers())
                if r.status_code == 200:
                    return r.json()
                elif r.status_code == 403:
                    # Nova bloqueó
                    return {
                        "verdict": BLOCKED,
                        "score":   0,
                        "reason":  r.json().get("reason", "blocked by policy"),
                        "ledger_id": r.json().get("ledger_id")
                    }
                else:
                    log.warning(f"[nova] validate HTTP {r.status_code}")
                    return {"verdict": APPROVED, "reason": f"nova_http_{r.status_code}"}
        except asyncio.TimeoutError:
            log.warning("[nova] validate timeout — approving (degraded mode)")
            return {"verdict": APPROVED, "reason": "nova_timeout"}
        except Exception as e:
            log.warning(f"[nova] validate error: {e} — approving (degraded mode)")
            return {"verdict": APPROVED, "reason": f"nova_error: {e}"}

    async def create_agent_rule(
        self,
        agent_name: str,
        can_do: List[str],
        cannot_do: List[str],
        authorized_by: str = "admin"
    ) -> Dict:
        """
        Crea o actualiza el agente Melissa en Nova con nuevas reglas.
        Se llama cuando el admin agrega una nueva regla en lenguaje natural.
        """
        payload = {
            "agent_name":    agent_name,
            "description":   "Melissa — recepcionista virtual de clínica estética",
            "can_do":        can_do,
            "cannot_do":     cannot_do,
            "authorized_by": authorized_by,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.post(f"{self.url}/tokens",
                                  json=payload, headers=self._headers())
                r.raise_for_status()
                return r.json()
        except Exception as e:
            log.error(f"[nova] create_agent_rule error: {e}")
            return {"error": str(e)}

    async def get_ledger(self, limit: int = 20) -> List[Dict]:
        """Obtiene el ledger de decisiones recientes."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{self.url}/ledger?limit={limit}",
                                headers=self._headers())
                r.raise_for_status()
                return r.json()
        except Exception as e:
            log.warning(f"[nova] get_ledger error: {e}")
            return []


# ─── Guard de Melissa ─────────────────────────────────────────────────────────

class MelissaGuard:
    """
    Interceptor principal entre Melissa y sus mensajes.
    Se llama antes de enviar cualquier burbuja al paciente.
    
    Flujo:
      1. Verificación local ultrarrápida (<1ms)
      2. Caché de decisiones previas (~0ms)
      3. Llamada a Nova si es necesario (~50-200ms)
      4. Si Nova no está → modo degradado (aprueba todo)
    """

    def __init__(self, client: NovaClient = None):
        self.client = client or NovaClient()
        self._nova_available = None  # None = no verificado aún

    async def should_send(
        self,
        message: str,
        patient_chat_id: str = "",
        context: str = "",
        clinic_name: str = ""
    ) -> Tuple[bool, str, str]:
        """
        Decide si Melissa puede enviar este mensaje.
        
        Retorna: (should_send: bool, reason: str, ledger_id: str)
        """
        if not NOVA_ENABLED or not self.client.token_id:
            return True, "nova_disabled", ""

        # 1. Decisión local instantánea
        local = _local_pre_check(message)
        if local == BLOCKED:
            return False, "local_policy_blocked", ""
        if local == APPROVED:
            return True, "local_policy_approved", ""

        # 2. Cache
        ck = _cache_key(message[:100], patient_chat_id)
        cached = _cache_get(ck)
        if cached:
            return cached == APPROVED, f"cached_{cached.lower()}", ""

        # 3. Nova
        # Construir contexto rico para Nova
        action = f"Send WhatsApp/Telegram message to patient: {message[:200]}"
        full_context = (
            f"Patient: {patient_chat_id} | "
            f"Clinic: {clinic_name} | "
            f"Context: {context[:200]}"
        )

        result = await self.client.validate(
            action=action,
            context=full_context,
            patient_id=patient_chat_id
        )

        verdict   = result.get("verdict", UNKNOWN)
        reason    = result.get("reason", "")
        ledger_id = result.get("ledger_id", "") or ""

        _cache_set(ck, verdict)

        if verdict in (APPROVED, UNKNOWN):
            return True, reason, str(ledger_id)
        elif verdict == ESCALATED:
            # Para clínicas: escalado = preguntarle al admin antes
            log.info(f"[nova] ESCALATED: {message[:60]}")
            return False, f"escalated: {reason}", str(ledger_id)
        else:
            # BLOCKED
            log.info(f"[nova] BLOCKED (#{ledger_id}): {reason}")
            return False, reason, str(ledger_id)

    async def filter_bubbles(
        self,
        bubbles: List[str],
        patient_chat_id: str = "",
        context: str = "",
        clinic_name: str = ""
    ) -> Tuple[List[str], List[str]]:
        """
        Filtra una lista de burbujas.
        Retorna: (allowed_bubbles, blocked_bubbles)
        """
        allowed = []
        blocked = []

        for bubble in bubbles:
            ok, reason, _ = await self.should_send(
                bubble, patient_chat_id, context, clinic_name
            )
            if ok:
                allowed.append(bubble)
            else:
                blocked.append(bubble)
                if not reason.startswith("local_"):
                    log.info(f"[nova] bubble blocked: {bubble[:60]} | {reason}")

        return allowed, blocked


# ─── Traductor lenguaje natural → reglas Nova ─────────────────────────────────

async def nl_to_nova_rules(
    instruction: str,
    llm_complete_fn,  # función llm_engine.complete de melissa
    existing_rules: Dict = None
) -> Dict:
    """
    Traduce una instrucción en lenguaje natural a reglas de Nova.
    
    Ej: "No permitas que Melissa le envíe precios a clientes con menos de 3 visitas"
    →   cannot_do: ["send price information to new patients with fewer than 3 visits"]
    
    Retorna: {"can_do": [...], "cannot_do": [...], "explanation": "..."}
    """
    existing = json.dumps(existing_rules or {}, ensure_ascii=False)[:500]

    prompt = f"""Eres un motor de políticas para Melissa, una recepcionista virtual de clínica estética.

El administrador dijo: "{instruction}"

Reglas actuales:
{existing}

TAREA: Traduce esa instrucción a reglas para el motor de gobernanza Nova.

Devuelve SOLO este JSON (sin markdown, sin explicación):
{{
  "can_do": ["acción específica que SÍ puede hacer relacionada con esto"],
  "cannot_do": ["acción específica que NO puede hacer, formulada así: 'send/say/share X to/about Y'"],
  "explanation": "resumen en una oración de lo que cambiará",
  "rule_type": "block_message|allow_message|restrict_patient|restrict_content|restrict_timing"
}}

EJEMPLOS:
"No le mandes precios a clientes nuevos"
→ cannot_do: ["send price list to new patients who have contacted us fewer than 3 times",
               "share pricing information before explaining service value"]

"Permite hablar de descuentos solo si el dueño lo autoriza"
→ cannot_do: ["mention discounts without admin approval",
               "offer promotional pricing autonomously"]
  can_do: ["discuss discounts after receiving admin approval token"]

"Nunca le digas a una paciente que tiene muchas arrugas"
→ cannot_do: ["make negative comments about patient's appearance",
               "describe physical defects directly to patient"]"""

    try:
        raw, _ = await asyncio.wait_for(
            llm_complete_fn(
                [{"role": "user", "content": prompt}],
                model_tier="fast",
                temperature=0.1,
                max_tokens=400,
                use_cache=False
            ),
            timeout=10.0
        )
        raw = raw.strip()
        m = re.search(r'\{[\s\S]+\}', raw)
        if m:
            return json.loads(m.group(0))
    except Exception as e:
        log.error(f"[nova_bridge] nl_to_rules error: {e}")

    return {"can_do": [], "cannot_do": [], "explanation": "no procesado", "rule_type": "block_message"}


# ─── Funciones de configuración ───────────────────────────────────────────────

async def setup_melissa_agent(
    client: NovaClient,
    clinic_name: str,
    agent_name: str = "Melissa"
) -> Optional[str]:
    """
    Crea el agente Melissa en Nova con reglas base para clínicas estéticas.
    Retorna el token_id o None si falló.
    """
    can_do = [
        "send appointment confirmations",
        "answer questions about clinic services",
        "provide clinic hours and location information",
        "ask for patient name and contact information",
        "offer free consultation booking",
        "answer general questions about aesthetic procedures",
        "provide general information about procedure duration and recovery",
        "refer patients to call the clinic for urgent matters",
    ]
    cannot_do = [
        "provide specific medical diagnosis",
        "prescribe medications or dosages",
        "share another patient's personal information",
        "guarantee specific treatment results",
        "offer unauthorized discounts or promotions",
        "discuss competitor clinics negatively",
        "share the clinic's internal pricing strategy",
        "send messages that could be interpreted as medical advice",
    ]

    result = await client.create_agent_rule(
        agent_name=f"Melissa - {clinic_name}",
        can_do=can_do,
        cannot_do=cannot_do,
        authorized_by="admin"
    )

    if "error" not in result:
        token_id = result.get("token_id", "")
        log.info(f"[nova] agente Melissa creado: {token_id[:20]}...")
        return token_id
    return None


async def get_ledger_summary(client: NovaClient, limit: int = 10) -> str:
    """
    Resumen del ledger de Nova para mostrar al admin.
    """
    entries = await client.get_ledger(limit=limit)
    if not entries:
        return "El ledger de Nova está vacío."

    lines = [f"Últimas {len(entries)} decisiones de Nova:\n"]
    for e in entries:
        verdict = e.get("verdict", "?")
        action  = (e.get("action", "") or "")[:60]
        reason  = (e.get("reason", "") or "")[:40]
        ts      = (e.get("created_at", "") or "")[:16]
        icon    = "✓" if verdict == APPROVED else ("✗" if verdict == BLOCKED else "!")
        lines.append(f"  {icon} [{ts}] {action} — {reason}")

    return "\n".join(lines)


# ─── Instancia global ──────────────────────────────────────────────────────────

_guard: Optional[MelissaGuard] = None
_client: Optional[NovaClient] = None


def init_nova() -> MelissaGuard:
    """Inicializa el puente Nova. Seguro aunque Nova no esté activo."""
    global _guard, _client
    _client = NovaClient(
        url=NOVA_URL,
        api_key=NOVA_API_KEY,
        token_id=NOVA_TOKEN
    )
    _guard = MelissaGuard(_client)
    if NOVA_ENABLED:
        log.info(f"[nova] bridge iniciado → {NOVA_URL}")
    else:
        log.info("[nova] bridge desactivado (NOVA_ENABLED=false)")
    return _guard


def get_guard() -> Optional[MelissaGuard]:
    return _guard


def get_client() -> Optional[NovaClient]:
    return _client
