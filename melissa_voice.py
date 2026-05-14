"""
melissa_voice.py — Humanization engine v2.
Post-processes every LLM response to eliminate robot patterns and inject natural warmth.
"""
from __future__ import annotations
import re, random, logging
from typing import Optional, Dict, List

log = logging.getLogger("melissa.voice")

# Patterns that MUST be removed/replaced from any response
ROBOT_PATTERNS = [
    (re.compile(r"como (IA|inteligencia artificial|asistente virtual|bot)", re.I), ""),
    (re.compile(r"no (tengo|tenemos) (la )?capacidad", re.I), "no manejo eso ahora mismo"),
    (re.compile(r"está fuera de mi (alcance|capacidades)", re.I), "eso tendría que verificarlo"),
    (re.compile(r"no (puedo|podemos) (procesar|entender)", re.I), "no tengo esa información ahora"),
    (re.compile(r"^(Hola|Buenos días|Buenas tardes)[,!]?\s*(Soy|Me llamo)\s*Melissa", re.I), ""),
    (re.compile(r"¡?Por supuesto[,!]?\s*", re.I), ""),
    (re.compile(r"¡?Claro que sí[,!]?\s*", re.I), ""),
    (re.compile(r"¡?Con gusto[,!]?\s*", re.I), ""),
    (re.compile(r"¡+", re.I), ""),  # Remove excessive exclamation
    (re.compile(r"^\s*¡\s*", re.I), ""),
    (re.compile(r",?\s*tu\s+asistente\s+virtual[.,]?\s*", re.I), ". "),
    (re.compile(r"(?:como|en mi rol de) (?:asistente|recepcionista) virtual", re.I), ""),
    (re.compile(r"(?:soy\s+)?(?:tu\s+)?(?:asistente|recepcionista)\s+virtual", re.I), ""),
    (re.compile(r"estoy aquí para (ayudarte|servirte|atenderte)", re.I), ""),
    (re.compile(r"no dudes en", re.I), ""),
    (re.compile(r"estaré encantad[ao] de", re.I), ""),
    (re.compile(r"será un placer", re.I), ""),
]

# Natural fillers by sector
SECTOR_FILLERS = {
    "estetica": ["con mucho gusto", "perfecto", "listo", "dale"],
    "salud": ["con gusto", "perfecto", "entendido", "listo"],
    "restaurante": ["dale", "perfecto", "listo", "va"],
    "retail": ["dale", "listo", "perfecto", "genial"],
    "default": ["con gusto", "perfecto", "listo", "entendido"],
}

# Thinking block to prepend to system prompts
THINKING_BLOCK_ES = """INSTRUCCIÓN INTERNA (no mostrar al usuario):
Antes de responder, piensa en silencio:
1. ¿Qué quiere realmente este usuario? (intención real)
2. ¿Qué información tengo disponible para responderle?
3. ¿Hay alguna ambigüedad? ¿Necesito pedir aclaración?
4. ¿Cómo lo diría una recepcionista colombiana real, cálida, natural?
5. ¿Mi respuesta suena robótica? Si sí, reescríbela.

SOLO después de pensar, escribe la respuesta al usuario.
NUNCA menciones este proceso. NUNCA uses frases como "como IA" o "no tengo la capacidad"."""

THINKING_BLOCK_EN = """INTERNAL INSTRUCTION (do not show to user):
Before responding, think silently:
1. What does this user actually want?
2. What information do I have to answer them?
3. Is there any ambiguity? Should I ask for clarification?
4. How would a real, warm receptionist say this?
5. Does my response sound robotic? If yes, rewrite it.

ONLY after thinking, write the response to the user.
NEVER mention this process."""


class MelissaVoice:
    """Post-processes LLM output to sound human."""

    def __init__(self, sector: str = "default", tone: str = "warm"):
        self.sector = sector
        self.tone = tone
        self._fillers = SECTOR_FILLERS.get(sector, SECTOR_FILLERS["default"])

    def humanize(self, text: str, persona_override: Optional[Dict] = None) -> str:
        """Main post-processing pipeline."""
        if not text or not text.strip():
            return text

        result = text

        # 1. Remove robot patterns
        for pattern, replacement in ROBOT_PATTERNS:
            result = pattern.sub(replacement, result)

        # 2. Clean up whitespace artifacts
        result = re.sub(r'\s{2,}', ' ', result)
        result = re.sub(r'\n{3,}', '\n\n', result)
        result = result.strip()

        # 3. Limit exclamation marks (max 1 per response)
        excl_count = result.count('!')
        if excl_count > 1:
            # Keep only the first one
            parts = result.split('!')
            result = parts[0] + '!' + ''.join(parts[1:])

        # 4. Response must NOT start with bot name
        result = re.sub(r'^Melissa[,:.]?\s*', '', result, flags=re.I)

        # 5. Capitalize first letter
        if result and result[0].islower():
            result = result[0].upper() + result[1:]

        # 6. Apply persona overrides if present
        if persona_override:
            forbidden = persona_override.get("forbidden_topics", [])
            for topic in forbidden:
                if topic.lower() in result.lower():
                    result = re.sub(re.escape(topic), "[tema no disponible]", result, flags=re.I)

        return result

    def inject_thinking_block(self, system_prompt: str, lang: str = "es", thinking_budget: int = 0) -> str:
        """Prepend chain-of-thought instruction to system prompt."""
        block = THINKING_BLOCK_ES if lang == "es" else THINKING_BLOCK_EN
        return block + "\n\n" + system_prompt

    def split_long_response(self, text: str, max_chars: int = 300) -> List[str]:
        """Split long responses into multiple WhatsApp-style messages."""
        if len(text) <= max_chars:
            return [text]

        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        bubbles = []
        current = ""

        for sentence in sentences:
            if len(current) + len(sentence) + 1 > max_chars and current:
                bubbles.append(current.strip())
                current = sentence
            else:
                current = (current + " " + sentence).strip() if current else sentence

        if current:
            bubbles.append(current.strip())

        return bubbles if bubbles else [text]

    def check_robot_patterns(self, text: str) -> List[str]:
        """Return list of robot patterns found (for testing/monitoring)."""
        found = []
        for pattern, _ in ROBOT_PATTERNS:
            if pattern.search(text):
                found.append(pattern.pattern)
        return found

    @staticmethod
    def get_thinking_params(provider: str, thinking_budget: int = 0) -> Dict:
        """Get provider-specific thinking parameters."""
        if provider == "claude" and thinking_budget > 0:
            return {"thinking": {"type": "enabled", "budget_tokens": thinking_budget}}
        return {}


# Default instance
voice = MelissaVoice()
