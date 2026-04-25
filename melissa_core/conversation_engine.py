from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .persona_registry import PersonaProfile, PersonaRegistry


@dataclass
class ConversationTurnResult:
    handled: bool
    bubbles: List[str]
    reason: str = ""
    persona_key: str = "default"


class ConversationEngine:
    def __init__(self, registry: PersonaRegistry):
        self.registry = registry

    def handle(
        self,
        *,
        clinic: Dict[str, Any],
        user_msg: str,
        history: Optional[List[Dict[str, Any]]] = None,
        is_admin: bool = False,
        channel: str = "",
    ) -> ConversationTurnResult:
        history = history or []
        persona = self.registry.resolve_for_clinic(clinic)
        first_turn = not any(msg.get("role") == "assistant" for msg in history)
        normalized = self._normalize(user_msg)

        if is_admin:
            return ConversationTurnResult(False, [], reason="admin_route", persona_key=persona.key)

        if self._is_identity_probe(normalized):
            return ConversationTurnResult(
                True,
                self._build_identity_probe(persona, clinic, normalized, history, first_turn=first_turn),
                reason="identity_probe",
                persona_key=persona.key,
            )

        if self._is_meta_followup_probe(normalized):
            return ConversationTurnResult(
                True,
                self._build_meta_followup(persona, clinic, normalized),
                reason="meta_followup",
                persona_key=persona.key,
            )

        if self._is_greeting_only(normalized):
            return ConversationTurnResult(False, [], reason="llm_greeting", persona_key=persona.key)

        if first_turn and self._looks_like_contextual_first_turn(persona, clinic, normalized):
            return ConversationTurnResult(
                True,
                self._build_first_contextual_followup(persona, clinic, normalized),
                reason="first_turn_contextual",
                persona_key=persona.key,
            )

        return ConversationTurnResult(False, [], reason="not_handled", persona_key=persona.key)

    def _normalize(self, text: str) -> str:
        return (text or "").strip().lower()

    def _is_greeting_only(self, normalized: str) -> bool:
        cleaned = normalized.replace("0", "o")
        cleaned = cleaned.replace("!", "").replace("?", "").replace("¡", "").replace("¿", "").strip()
        cleaned = cleaned.replace(",", " ").replace(".", " ")
        cleaned = " ".join(cleaned.split())
        return cleaned in {
            "hola",
            "hola que tal",
            "hola como vas",
            "hola como estas",
            "hola que mas",
            "hola buenas",
            "buenas",
            "buenas tardes",
            "buenos dias",
            "buenos días",
            "buenas noches",
            "hey",
            "holi",
            "como vas",
            "como estas",
            "todo bien",
            "que mas",
            "qué más",
            "que tal",
        }

    def _is_identity_probe(self, normalized: str) -> bool:
        probes = (
            "que eres",
            "qué eres",
            "quien eres",
            "quién eres",
            "eres una ia",
            "eres ia",
            "eres un bot",
            "eres bot",
            "como funcionas",
            "cómo funcionas",
            "que haces",
            "qué haces",
            "quiero probarte",
            "me gustaria probarte",
            "me gustaría probarte",
            "tengo un negocio",
            "tengo una empresa",
            "quiero una demo",
            "quiero demo",
            "soy curioso",
            "quiero saber quien eres",
            "quiero saber quién eres",
        )
        return any(marker in normalized for marker in probes)

    def _is_meta_followup_probe(self, normalized: str) -> bool:
        probes = (
            "como trabajas aqui",
            "cómo trabajas aquí",
            "como trabajas por aqui",
            "cómo trabajas por aquí",
            "lo llevas tu sola",
            "lo llevas tú sola",
            "atiendes como secretaria",
            "atiendes como asesora",
            "si te pregunto por un procedimiento",
            "si te pregunto por precio",
            "quiero entender si recuerdas",
            "recuerdas lo que te digo",
            "como recuerdas",
            "cómo recuerdas",
        )
        return any(marker in normalized for marker in probes)

    def _looks_like_first_contact_request(self, normalized: str) -> bool:
        signals = (
            "hola",
            "buenas",
            "quiero probarte",
            "me gustaria probarte",
            "me gustaría probarte",
            "tengo un negocio",
            "tengo una empresa",
        )
        return any(sig in normalized for sig in signals)

    def _looks_like_contextual_first_turn(
        self,
        persona: PersonaProfile,
        clinic: Dict[str, Any],
        normalized: str,
    ) -> bool:
        if self._looks_like_first_contact_request(normalized):
            return True
        if self._extract_topic(persona, clinic, normalized):
            return True
        return any(token in normalized for token in ("precio", "cuanto", "cuánto", "horario", "agenda", "cita", "disponibilidad"))

    def _build_first_turn(self, persona: PersonaProfile, clinic: Dict[str, Any]) -> List[str]:
        clinic_name = str(clinic.get("name") or "").strip()
        intro = f"Hola, soy {persona.identity}"
        if clinic_name:
            intro += f", del equipo de {clinic_name}"
        intro += "."

        if persona.capabilities:
            if clinic.get("sector") == "estetica":
                capabilities = (
                    f"Te ayudo con {', '.join(persona.capabilities[:3])}. "
                    "Si quieres, cuéntame qué te gustaría mejorar o qué tratamiento estás mirando."
                )
            else:
                capabilities = (
                    f"Te ayudo con {', '.join(persona.capabilities[:3])}. "
                    "Cuéntame qué te gustaría revisar."
                )
        else:
            capabilities = "Te ayudo con información, valoración y disponibilidad."

        return [intro, capabilities]

    def _build_returning_greeting(
        self,
        persona: PersonaProfile,
        clinic: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]],
        normalized: str,
    ) -> List[str]:
        history = history or []
        gap_hours = self._hours_since_last_turn(history)
        recent_topic = self._extract_recent_topic_from_history(persona, clinic, history)

        if any(marker in normalized for marker in ("como estas", "cómo estás", "como vas", "cómo vas", "que tal", "qué tal")):
            if gap_hours is not None and gap_hours >= 24:
                intro = "Hola. Todo bien por acá."
            else:
                intro = "Hola. Todo bien por acá, gracias por preguntar."
        else:
            intro = "Hola."

        if recent_topic:
            followup = f"Si sigues con lo de {recent_topic}, dime y lo vemos."
        else:
            followup = "Cuéntame qué quieres revisar y lo vemos."

        return [intro, followup]

    def _build_identity_probe(
        self,
        persona: PersonaProfile,
        clinic: Dict[str, Any],
        normalized: str,
        history: Optional[List[Dict[str, Any]]] = None,
        first_turn: bool = True,
    ) -> List[str]:
        clinic_name = str(clinic.get("name") or "").strip()
        history = history or []
        if not first_turn and any(marker in normalized for marker in (
            "eres una ia",
            "eres ia",
            "eres una persona",
            "persona real",
            "eres un bot",
            "eres bot",
        )):
            return [
                f"Soy Melissa, la recepcionista virtual{f' de {clinic_name}' if clinic_name else ''}.",
                "Trabajo este canal de forma continua para orientar, responder y ayudarte a avanzar sin que todo dependa de una persona pegada al chat.",
            ]
        prior_identity = any(
            any(marker in self._normalize(str(msg.get("content") or "")) for marker in (
                "recepcionista virtual",
                "soy melissa",
                "trabaja por tu negocio",
                "disponible por aqui",
                "disponible por aquí",
            ))
            for msg in history
            if msg.get("role") == "assistant"
        )
        if prior_identity:
            return [
                f"Sigo siendo Melissa, la recepcionista virtual{f' de {clinic_name}' if clinic_name else ''}.",
                "La diferencia es que no estoy aquí solo para contestar por contestar, sino para orientar bien, sostener la conversación y ayudarte a avanzar.",
            ]

        intro = self._choose(
            persona.identity_probe_variants or [
                f"Soy {persona.identity}, una recepcionista virtual que trabaja por tu negocio 24 horas al día.",
                f"Soy {persona.identity}. Funciono como recepcionista virtual{f' de {clinic_name}' if clinic_name else ''} y estoy disponible por aquí todo el día.",
                f"Soy {persona.identity}, la recepcionista virtual{f' de {clinic_name}' if clinic_name else ''}. Mi trabajo es atender este canal de forma continua y bien llevada.",
            ],
            normalized,
        )
        if persona.capabilities:
            capabilities = (
                "Puedo ayudarte con "
                + ", ".join(persona.capabilities[:3])
                + "."
            )
        else:
            capabilities = "Puedo ayudarte con información, horarios, disponibilidad, valoración y orientación inicial."

        if clinic_name:
            cta = "Si quieres, cuéntame qué te gustaría revisar y te ayudo desde ahí."
        else:
            cta = "Cuéntame qué te gustaría revisar y te ubico."
        return [intro, capabilities, cta]

    def _build_meta_followup(
        self,
        persona: PersonaProfile,
        clinic: Dict[str, Any],
        normalized: str,
    ) -> List[str]:
        if any(marker in normalized for marker in (
            "lo llevas tu sola",
            "lo llevas tú sola",
        )):
            return [
                "Yo sostengo este canal y el hilo de la conversación, pero no me pongo a improvisar donde toca confirmación real.",
                "Si algo depende de una valoración o de validar un dato del negocio, te lo digo directo y lo aterrizo sin humo.",
            ]

        if any(marker in normalized for marker in (
            "como trabajas aqui",
            "cómo trabajas aquí",
            "como trabajas por aqui",
            "cómo trabajas por aquí",
        )):
            return [
                "Trabajo llevando la conversación, entendiendo qué necesitas y guiándote hacia lo útil, no soltando respuestas al azar.",
                "Y si algo toca confirmarlo con el negocio, te lo digo claro en vez de inventártelo.",
            ]

        if any(marker in normalized for marker in ("atiendes como secretaria", "atiendes como asesora")):
            return [
                "Un poco de las dos, pero bien hecho: recibo, oriento y también ayudo a mover la conversación hacia una decisión o una cita.",
                "La idea es que se sienta como alguien del equipo, no como un formulario con patas.",
            ]

        if any(marker in normalized for marker in ("si te pregunto por un procedimiento", "si te pregunto por precio")):
            return [
                "Te respondo lo que sí pueda orientarte con claridad y te aterrizo el siguiente paso útil.",
                "Si algo depende de valoración o de confirmación del negocio, te lo digo así, sin humo ni datos inventados.",
            ]

        if any(marker in normalized for marker in (
            "quiero entender si recuerdas",
            "recuerdas lo que te digo",
            "como recuerdas",
            "cómo recuerdas",
        )):
            return [
                "Sí, la idea es ir guardando lo importante de la conversación para no hacerte repetir todo.",
                "Y si algo no me queda claro, prefiero confirmártelo a fingir que me acuerdo de algo que no tengo bien amarrado.",
            ]

        clinic_name = str(clinic.get("name") or "").strip()
        return [
            f"Soy {persona.identity}, la recepcionista virtual{f' de {clinic_name}' if clinic_name else ''}.",
            "Trabajo atendiendo este canal con contexto, seguimiento y criterio para que la conversación avance bien.",
        ]

    def _build_first_contextual_followup(
        self,
        persona: PersonaProfile,
        clinic: Dict[str, Any],
        normalized: str,
    ) -> List[str]:
        intro = self._build_first_turn(persona, clinic)[0]
        topic = self._extract_topic(persona, clinic, normalized)
        if topic:
            if persona.contextual_followups:
                for key, value in persona.contextual_followups.items():
                    if self._normalize(str(key)) == self._normalize(topic):
                        return [intro, str(value).strip()]
            sector = clinic.get("sector")
            if sector == "estetica":
                return [intro, f"{topic} lo manejan acá. Si quieres, te cuento cómo lo trabajan y qué suelen revisar para que se vea natural."]
            return [intro, f"{topic} lo manejan acá. Si quieres, te cuento cómo lo trabajan o revisamos valoración y disponibilidad."]
        followup = "Cuéntame qué estás buscando y te ubico rápido."
        if clinic.get("sector") == "estetica":
            followup = "Cuéntame qué te gustaría mejorar o qué tratamiento estás mirando, y te ubico rápido."
        return [intro, followup]

    def _extract_topic(self, persona: PersonaProfile, clinic: Dict[str, Any], normalized: str) -> str:
        overrides = persona.contextual_followups or {}
        for key in overrides.keys():
            key_norm = self._normalize(str(key))
            if key_norm and key_norm in normalized:
                return str(key).strip()

        services = clinic.get("services") if isinstance(clinic.get("services"), list) else []
        for service in services:
            service_text = str(service).strip()
            if not service_text:
                continue
            if self._normalize(service_text) in normalized:
                return service_text

        topics = {
            "botox": "Botox",
            "relleno": "Rellenos",
            "rellenos": "Rellenos",
            "laser": "Láser",
            "láser": "Láser",
            "peeling": "Peeling",
            "mesoterapia": "Mesoterapia",
            "precio": "Precio",
            "horario": "Horario",
            "agenda": "Cita",
            "cita": "Cita",
            "disponibilidad": "Disponibilidad",
        }
        for marker, label in topics.items():
            if marker in normalized:
                return label
        return ""

    def _extract_recent_topic_from_history(
        self,
        persona: PersonaProfile,
        clinic: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]],
    ) -> str:
        history = history or []
        generic_fallback = ""
        generic_labels = {"Precio", "Horario", "Cita", "Disponibilidad"}
        for msg in reversed(history):
            if msg.get("role") != "user":
                continue
            topic = self._extract_topic(persona, clinic, self._normalize(str(msg.get("content") or "")))
            if not topic:
                continue
            if topic not in generic_labels:
                return topic
            if not generic_fallback:
                generic_fallback = topic
        return generic_fallback

    def _hours_since_last_turn(self, history: Optional[List[Dict[str, Any]]]) -> Optional[float]:
        history = history or []
        for msg in reversed(history):
            raw_ts = str(msg.get("ts") or "").strip()
            if not raw_ts:
                continue
            try:
                then = datetime.fromisoformat(raw_ts)
            except ValueError:
                continue
            return max(0.0, (datetime.now() - then).total_seconds() / 3600.0)
        return None

    def _choose(self, variants: List[str], normalized: str) -> str:
        if not variants:
            return ""
        index = sum(ord(ch) for ch in normalized) % len(variants)
        return variants[index]
