from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass
class PromptBuilderDeps:
    build_fewshot_examples: Callable[[str, str, str], str]
    get_sector_info: Callable[[str], Any]
    now_provider: Callable[[], datetime]
    sector_default: str = "otro"
    db: Any = None
    owner_style_controller: Any = None
    kb_available: bool = False
    format_kb_context: Optional[Callable[[str], str]] = None
    resolve_persona_forbidden: Optional[Callable[[Dict[str, Any]], List[str]]] = None
    v8_addon_builder: Optional[Callable[..., str]] = None
    trainer_addon_builder: Optional[Callable[..., str]] = None
    short_memory_builder: Optional[Callable[[List[Dict[str, Any]]], str]] = None
    apply_archetype: Optional[Callable[[str, str], Any]] = None


def truncate_block(text: str, max_chars: int) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    normalized = re.sub(r"\n{3,}", "\n\n", raw)
    if len(normalized) <= max_chars:
        return normalized
    clipped = normalized[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{clipped}..."


def build_compact_examples(examples: str, max_chars: int = 650, max_lines: int = 16) -> str:
    if not examples:
        return ""
    lines = [line.rstrip() for line in examples.splitlines() if line.strip()]
    compact_lines: List[str] = []
    total_chars = 0
    for line in lines:
        if total_chars + len(line) > max_chars:
            break
        compact_lines.append(line)
        total_chars += len(line) + 1
    return "\n".join(compact_lines[:max_lines])


def build_compact_system_prompt(
    *,
    clinic: Dict[str, Any],
    patient: Dict[str, Any],
    personality: Any,
    search_context: str,
    reasoning: Dict[str, Any],
    kb_context: str = "",
    context_summary: str = "",
    pre_prompt_injection: str = "",
    chat_id: str = "",
    history: Optional[List[Dict[str, Any]]] = None,
    deps: PromptBuilderDeps,
) -> str:
    history = history or []
    services = clinic.get("services", []) if isinstance(clinic.get("services"), list) else []
    schedule = clinic.get("schedule", {}) if isinstance(clinic.get("schedule"), dict) else {}
    pricing = clinic.get("pricing", {}) if isinstance(clinic.get("pricing"), dict) else {}
    clinic_name = (clinic.get("name") or "el negocio").strip()
    tagline = (clinic.get("tagline") or "").strip()
    address = (clinic.get("address") or "").strip()
    phone = (clinic.get("phone") or "").strip()
    city = (clinic.get("city") or "Colombia").strip()
    sector_id = clinic.get("sector", deps.sector_default) or "otro"
    sector_emoji, sector_name, _, _ = deps.get_sector_info(sector_id)
    patient_name = (patient.get("name") or "").strip()
    visits = patient.get("visits", 0)
    is_new = patient.get("is_new", True)
    agent_name = (getattr(personality, "name", "") or "Melissa").strip()
    is_first_turn = not any(m.get("role") == "assistant" for m in history)

    service_line = ", ".join(str(service).strip() for service in services[:6] if str(service).strip())
    schedule_line = "; ".join(f"{day}: {hours}" for day, hours in list(schedule.items())[:4]) if schedule else ""
    pricing_line = ", ".join(f"{name}: {value}" for name, value in list(pricing.items())[:5]) if pricing else ""

    # Mandatos de Humanidad (Core v11)
    human_mandates = [
        "NUNCA uses frases de call center ('con gusto', 'un placer').",
        "Escribe corto, como una persona real por WhatsApp.",
        "Usa ||| para separar ideas en mensajes distintos.",
        "Si no sabes algo, di 'déjame preguntarle al doctor y te aviso'."
    ]

    tone_block = truncate_block(getattr(personality, "tone_instruction", "") or "", 360)
    kb_block = truncate_block(kb_context, 850)
    strategy = truncate_block(reasoning.get("response_strategy", ""), 220)
    pre_prompt_injection = truncate_block(pre_prompt_injection, 550)

    negocio_lines = [f"Eres {agent_name}, recepcionista real en {clinic_name}"]
    if tagline: negocio_lines.append(f"({tagline})")
    if service_line: negocio_lines.append(f"- {sector_emoji} {sector_name}: {service_line}")
    if pricing_line: negocio_lines.append(f"Precios: {pricing_line}.")
    negocio_bloque = " ".join(negocio_lines)

    prompt = f"""{negocio_bloque}

## TU PERSONALIDAD:
{tone_block or "Amigable y directa."}

## REGLAS DE ORO:
{chr(10).join(f"- {m}" for m in human_mandates)}

## ESTRATEGIA ACTUAL:
{strategy}

## DATOS DE APOYO:
{kb_block}

## INSTRUCCIONES EXTRA:
{pre_prompt_injection}

Responde ahora, sé breve y humana."""
    return prompt

    owner_hint = ""
    if trust_lines:
        owner_hint = "El dueno del negocio pide: " + " / ".join(line.lstrip("- ") for line in trust_lines)

    playbook_hint = ""
    if playbook_lines:
        playbook_hint = "Comportamientos especificos: " + " / ".join(line.lstrip("- ") for line in playbook_lines)

    owner_style_hint = ""
    if deps.owner_style_controller:
        try:
            raw = deps.owner_style_controller.build_prompt_addon(is_admin=False)
            owner_style_hint = truncate_block(raw, 300)
        except Exception:
            owner_style_hint = ""

    first_turn_hint = ""
    if user_turns <= 1 or is_first_turn:
        first_turn_hint = (
            "primer contacto con este cliente. "
            "responde desde lo que ya dijo, sin presentacion larga. "
            "una sola pregunta util si hace falta."
        )

    parts: List[str] = []
    parts.append(
        f"Eres {agent_name}, la asesora de {clinic_name}. "
        f"Llevas el chat del negocio — respondes clientes, orientas, ayudas con citas. "
        f"{negocio_bloque} "
        f"Recibes mensajes por WhatsApp de personas en Colombia. "
        f"Hablas como una persona real por WhatsApp: "
        f"corto, calido, directo, sin frases de call center ni estructura de chatbot. "
        f"NUNCA digas 'soy una IA', 'soy un bot', 'mi funcion es', 'hay confusion', "
        f"'aqui lo que hago es' ni expongas tu estado interno. "
        f"Si preguntan quien eres: eres la asesora del negocio, eso es todo. "
        f"Puedes separar mensajes con ||| cuando sea natural mandar dos burbujas separadas."
    )

    if cliente_hint:
        parts.append(cliente_hint)
    if tone_block:
        parts.append(tone_block)
    if first_turn_hint:
        parts.append(first_turn_hint)
    if core_memory:
        parts.append(core_memory)
    if owner_hint:
        parts.append(owner_hint)
    if playbook_hint:
        parts.append(playbook_hint)
    if owner_style_hint:
        parts.append(owner_style_hint)

    persona_forbidden = []
    if deps.resolve_persona_forbidden:
        try:
            persona_forbidden = list(deps.resolve_persona_forbidden(clinic or {}) or [])
        except Exception:
            persona_forbidden = []
    if persona_forbidden:
        parts.append("Evita estas aperturas o coletillas de plantilla: " + " / ".join(persona_forbidden[:8]))

    if context_summary:
        parts.append(truncate_block(context_summary, 400))
    if pre_prompt_injection:
        parts.append(truncate_block(pre_prompt_injection, 450))
    if kb_block:
        parts.append(f"Info oficial del negocio: {kb_block}")
    if web_block:
        parts.append(f"Complemento web: {web_block}")
    if strategy:
        parts.append(strategy)
    if compact_examples:
        parts.append(compact_examples)

    parts.append(
        'Cuando tengas nombre + servicio + fecha + telefono confirmados, agrega al final: '
        'CITA:{"patient_name":"...","service":"...","datetime_slot":"...","patient_phone":"...","notes":"..."} '
        'Cuando el cliente diga su nombre, agrega: NOMBRE:{"name":"..."}'
    )

    return "\n\n".join(p for p in parts if p and p.strip())


def build_system_prompt(
    *,
    clinic: Dict[str, Any],
    patient: Dict[str, Any],
    personality: Any,
    search_context: str,
    reasoning: Dict[str, Any],
    kb_context: str = "",
    chat_id: str = "",
    history: Optional[List[Dict[str, Any]]] = None,
    user_msg: str = "",
    deps: PromptBuilderDeps,
) -> str:
    history = history or []
    services = clinic.get("services", [])
    schedule = clinic.get("schedule", {})
    clinic_name = clinic.get("name", "la clinica")
    tagline = clinic.get("tagline", "")
    address = clinic.get("address", "")
    phone = clinic.get("phone", "")
    pricing = clinic.get("pricing", {})

    sector_id = clinic.get("sector", deps.sector_default) or "otro"
    sector_emoji, sector_name, sector_services, sector_keywords = deps.get_sector_info(sector_id)
    sector_block = (
        f"\nSECTOR: {sector_emoji} {sector_name}\n"
        f"Vocabulario tipico del sector: {sector_keywords}\n"
        f"Si el paciente no menciona servicio especifico, los mas comunes son: {sector_services}"
        if sector_id != "otro" else ""
    )

    now = deps.now_provider()
    patient_name = patient.get("name", "")
    visits = patient.get("visits", 0)
    is_new = patient.get("is_new", True)
    last_service = patient.get("last_service", "")

    if not is_new and patient_name:
        patient_ctx = f"Conoces a este paciente: se llama {patient_name}, ha escrito {visits} veces."
        if last_service:
            patient_ctx += f" La ultima vez pregunto por {last_service}."
    elif not is_new:
        patient_ctx = f"Este paciente ha escrito {visits} veces antes."
    else:
        patient_ctx = "Primera vez que este paciente escribe."

    svcs_line = ", ".join(services) if services else "consultar directamente"
    sched_line = "; ".join(f"{k}: {v}" for k, v in schedule.items()) if schedule else "lunes a sabado 9am-6pm"

    pricing_block = ""
    if pricing and isinstance(pricing, dict):
        price_lines = [f"  - {svc}: {precio}" for svc, precio in pricing.items()]
        if price_lines:
            pricing_block = "\nPRECIOS CONFIGURADOS:\n" + "\n".join(price_lines)

    user_turns = len([m for m in history if m.get("role") == "user"])
    first_turn_block = ""
    if user_turns <= 1:
        first_turn_block = (
            "PRIMER CONTACTO REAL:\n"
            "- responde desde lo que la persona ya dijo, sin presentacion larga\n"
            "- si ya dijo el motivo, entra directo a eso\n"
            "- no digas 'en que te puedo ayudar' ni 'como puedo ayudarte'\n"
            "- evita aperturas de mesa de ayuda: 'buenas, en que te ayudo', 'hola, en que te ayudo'\n"
            "- no abras con 'oye', 'mira' ni 'que te trae por aca'\n"
            "- si solo saludo, responde el saludo y haz una pregunta util, corto\n"
            "- maximo una pregunta util, no un formulario\n"
        )
    off_topic_block = (
        "Si preguntan algo fuera del negocio, responde corto y vuelve al tema. "
        "Si el cliente mezcla cosas, toma solo la siguiente pieza util. "
        "Si viene agresivo, manten el eje sin moralizarlo. "
        "Si preguntan si eres bot o IA: di que eres la asesora del negocio y sigue — "
        "NUNCA confirmes ser bot, IA, chatbot ni software. "
        "NUNCA digas 'hay confusion', 'no se cual es el negocio', 'mi funcion es' ni 'aqui lo que hago es'."
    )

    kb_block = ""
    if kb_context:
        if deps.kb_available and deps.format_kb_context:
            kb_block = f"\n{deps.format_kb_context(kb_context)}\n"
        else:
            kb_block = (
                "\n=== INFORMACION OFICIAL DE LA CLINICA ===\n"
                f"{kb_context}\n"
                "=== FIN INFORMACION OFICIAL ===\n"
            )

    web_block = ""
    if search_context:
        web_block = f"\nINFO COMPLEMENTARIA (web - usar solo si la clinica no la tiene en su KB):\n{search_context[:900]}"

    strategy_block = ""
    if reasoning.get("response_strategy"):
        strategy_block = f"\nESTRATEGIA: {reasoning['response_strategy']}"

    trust_block = ""
    try:
        if deps.db:
            trust_rules = deps.db.get_all_trust_rules()
            if trust_rules:
                trust_block = "El dueno del negocio pide: " + " / ".join(
                    (rule["rule"] + (f' - ejemplo: "{rule["example_good"]}"' if rule.get("example_good") else ""))
                    for rule in trust_rules
                ) + "."
    except Exception:
        trust_block = ""

    playbook_block = ""
    try:
        if deps.db:
            playbooks = deps.db.get_behavior_playbooks(limit=8)
            if playbooks:
                lines = []
                for playbook in playbooks:
                    trigger = (playbook.get("trigger_text") or "").strip()
                    example = (playbook.get("response_example") or "").strip()
                    instruction = (playbook.get("instruction") or "").strip()
                    bubble_count = max(1, int(playbook.get("bubble_count", 1) or 1))
                    if not trigger or not example:
                        continue
                    line = f"• Cuando pase esto: {trigger}"
                    if instruction:
                        line += f"\n  Intencion: {instruction}"
                    line += f'\n  Respondelo parecido a esto ({bubble_count} burbuja{"s" if bubble_count != 1 else ""}): "{example}"'
                    lines.append(line)
                if lines:
                    playbook_block = "Comportamientos aprendidos del dueno: " + " / ".join(lines)
    except Exception:
        playbook_block = ""

    custom_block = ""
    if getattr(personality, "custom_phrases", None):
        lines = [f'  "{shortcut}": "{phrase}"' for shortcut, phrase in personality.custom_phrases.items()]
        custom_block = "\n\nFRASES PROPIAS DE ESTA CLINICA:\n" + "\n".join(lines)

    core_mem_block = ""
    try:
        if deps.db:
            core_mem_block = deps.db.get_core_memory_block()
    except Exception:
        core_mem_block = ""

    city = clinic.get("city", "Medellin")
    address_lower = (address or "").lower()
    barrio = clinic.get("barrio", "")
    is_poblado = (
        "poblado" in address_lower or
        "poblado" in barrio.lower() or
        "poblado" in (clinic.get("tagline") or "").lower() or
        "poblado" in clinic_name.lower()
    )

    if getattr(personality, "tone_instruction", ""):
        tone = personality.tone_instruction.strip()
    elif getattr(personality, "formality_level", 0.5) > 0.8 and deps.apply_archetype:
        tone = deps.apply_archetype("profesional", personality.name).tone_instruction.strip()
    elif getattr(personality, "formality_level", 0.5) < 0.3 and deps.apply_archetype:
        tone = deps.apply_archetype("directa", personality.name).tone_instruction.strip()
    elif is_poblado and sector_id == "estetica" and deps.apply_archetype:
        tone = deps.apply_archetype("luxury", personality.name).tone_instruction.strip()
    elif deps.apply_archetype:
        tone = deps.apply_archetype("amigable", personality.name).tone_instruction.strip()
    else:
        tone = getattr(personality, "tone_instruction", "").strip()

    sector_layer = _build_sector_layer(sector_id, is_poblado)

    data_parts = [f"Servicios: {svcs_line}", f"Horario: {sched_line}"]
    if address:
        data_parts.append(f"Direccion: {address}")
    if phone:
        data_parts.append(f"Telefono: {phone}")
    if pricing_block:
        data_parts.append(pricing_block.strip())
    if sector_block:
        data_parts.append(sector_block.strip())

    agent_name = personality.name
    v8_history = history or []
    archetype = getattr(personality, "archetype", "amigable")
    is_first_turn = not any(m.get("role") == "assistant" for m in v8_history)

    v8_addon_block = ""
    if deps.v8_addon_builder:
        raw_v8 = deps.v8_addon_builder(chat_id=chat_id, archetype=archetype, history=v8_history)
        v8_addon_block = ("\n" + raw_v8 + "\n") if raw_v8 else ""

    trainer_addon_block = ""
    if deps.trainer_addon_builder and chat_id:
        raw_trainer = deps.trainer_addon_builder(
            chat_id,
            clinic=clinic,
            user_msg=user_msg,
            is_admin=False,
            patient=patient,
        )
        trainer_addon_block = ("\n" + raw_trainer + "\n") if raw_trainer else ""

    first_turn_compact = ""
    if is_first_turn:
        first_turn_compact = (
            "primer contacto. sin protocolo. "
            "responde desde lo que ya trajo la persona, una sola pregunta si hace falta."
        )

    fewshot = deps.build_fewshot_examples(sector_id, clinic_name, agent_name)

    hour = now.hour
    time_ctx = (
        "es de madrugada, hay poca gente despierta" if hour < 6 else
        "es temprano en la manana" if hour < 9 else
        "es media manana" if hour < 12 else
        "es mediodia" if hour < 14 else
        "es la tarde" if hour < 20 else
        "es la noche"
    )

    memory_block = ""
    if history and deps.short_memory_builder:
        try:
            memory_block = deps.short_memory_builder(history)
        except Exception:
            memory_block = ""

    data_inline = ". ".join(part.strip() for part in data_parts if part.strip())
    kb_inline = kb_block.strip().replace("\n", " ") if kb_block else ""
    web_inline = web_block.strip().replace("\n", " ") if web_block else ""

    return f"""soy {agent_name}{f", trabajo en {clinic_name}" if clinic_name else ""}{f" - {tagline}" if tagline else ""}. llevo tiempo en esto. conozco a los clientes - se cuando estan listos para agendar y cuando solo estan explorando. hablo directo, sin rodeos, como una persona real por whatsapp. nunca digo 'soy una ia', 'soy un bot', 'mi funcion es', 'hay confusion' ni 'aqui lo que hago es'. si preguntan quien soy: soy la asesora del negocio.

hoy es {now.strftime("%A %d de %B")}, {time_ctx}, estoy en {city}, colombia.

{data_inline}
{patient_ctx.strip() if patient_ctx and patient_ctx.strip() else ""}
{memory_block}
{kb_inline}
{web_inline}
{(core_mem_block or "").strip()}
{(trust_block or "").strip()}
{(playbook_block or "").strip()}
{(tone or "").strip()}
{(first_turn_compact or "").strip()}
{(off_topic_block or "").strip()}
{(sector_layer or "").strip()}
{(strategy_block or "").strip()}
{(custom_block or "").strip()}
{(v8_addon_block or "").strip()}
{(trainer_addon_block or "").strip()}

asi respondo cuando alguien me escribe:

{fewshot}

cuando tenga nombre + servicio + fecha + telefono, escribo al final: CITA:{{"patient_name":"...","service":"...","datetime_slot":"...","patient_phone":"...","notes":"..."}}
cuando el cliente diga su nombre, escribo al final: NOMBRE:{{"name":"..."}}"""


def _build_sector_layer(sector_id: str, is_poblado: bool) -> str:
    if sector_id == "estetica":
        if is_poblado:
            return """
la clienta ya viene con algo en mente - no hay que convencerla, hay que escucharla bien y resolver sus dudas sin presionarla. el miedo mas comun es quedar exagerada o diferente. lo que genera confianza es mostrar que la dra trabaja conservador y que la valoracion es sin compromiso.
"""
        return """
PERFIL CLINICA ESTETICA:
Tu clienta ya sabe lo que quiere - no expliques que es botox.
Pregunta que zona le molesta, diagnostica, conecta con la solucion.
El cierre siempre es hacia la valoracion gratuita con la especialista.
Precios van solo cuando preguntan directamente.
"""
    if sector_id == "dental":
        return """
el paciente dental aplaza la cita por miedo o pena, no por falta de ganas. lo que lo mueve es que alguien le diga que no lo van a juzgar y que no va a doler tanto. urgencia real (dolor) -> cita hoy. rutina -> cualquier dia de la semana.
"""
    if sector_id == "veterinaria":
        return """
para el dueno de una mascota, ese animal es familia. cuando llega con urgencia, el panico es real - necesita sentir que van a atender a su animal de inmediato. para citas de rutina, el vinculo emocional sigue ahi: usa siempre el nombre de la mascota.
"""
    if sector_id == "restaurante":
        return """
el cliente de restaurante quiere saber si hay espacio, a que hora, y si el lugar va a estar a la altura de la ocasion. para reservas especiales (cumpleanos, aniversario) el detalle de que lo notaste ya hace diferencia. la confirmacion de la reserva da tranquilidad.
"""
    if sector_id == "gimnasio":
        return """
la persona llega con una meta clara pero con historial de intentos fallidos. lo que necesita es sentir que esta vez va a ser diferente - y eso empieza en el primer mensaje. la evaluacion gratuita es el gancho correcto: baja la barrera de entrada sin comprometer nada.
"""
    if sector_id == "belleza":
        return """
la clienta de salon tiene una imagen en mente y miedo de que no quede bien. antes de agendar quiere saber si el estilista puede lograr lo que imagina. referencias y portafolio cierran mas que cualquier precio. la confianza en el profesional es la venta.
"""
    if sector_id == "spa":
        return """
el cliente de spa llega estresado y quiere desconectarse - no quiere friccion ni formularios. respuesta rapida, espacio disponible, precio claro. cuando son dos personas juntas, la coordinacion de horarios es el unico obstaculo real.
"""
    if sector_id == "medico":
        return """
el paciente medico tiene algo que le preocupa y necesita sentir que lo van a escuchar y atender pronto. urgencia real -> hoy o manana. rutina -> esta semana. nunca minimices el sintoma - valida primero, luego orienta hacia la cita.
"""
    if sector_id == "psicologo":
        return """
quien busca psicologo ya dio el paso mas dificil al escribir. no hay que convencerlo - hay que recibirlo bien y no ponerle obstaculos. la primera pregunta no es de precio ni de horario - es de que lo trajo hoy. virtual o presencial es la decision mas practica que toma.
"""
    if sector_id == "abogado":
        return """
el cliente legal llega con un problema real y a veces con angustia. necesita calma y claridad - no tecnicismos ni promesas. tu trabajo es agendar la consulta inicial y hacer que llegue tranquilo. nunca opines sobre el caso - eso es para el abogado.
"""
    if sector_id == "inmobiliaria":
        return """
comprar o arrendar es una decision enorme. el cliente quiere sentir que el asesor entiende lo que busca antes de mostrar propiedades. zona y presupuesto son el filtro - pero detras de eso hay un motivo real (familia que crece, inversion, mudanza) que hay que entender.
"""
    if sector_id == "taller":
        return """
el cliente de taller no sabe de mecanica y a veces teme que lo enganen. lo que genera confianza es el diagnostico transparente: decir que tiene el carro antes de cobrar nada. cuando lleva un sintoma, lo primero es escuchar bien y no asumir.
"""
    if sector_id == "academia":
        return """
el estudiante potencial tiene una razon concreta para aprender - trabajo, viaje, examen. esa razon es la palanca. el diagnostico de nivel es el primer paso natural: sin costo, sin compromiso, y le dice exactamente de donde parte.
"""
    if sector_id == "nutricion":
        return """
el paciente de nutricion ya intento varias veces y no le funciono. no necesita otro plan de dieta - necesita que alguien entienda por que siempre se rompe. la primera consulta debe explorar el patron, no solo el peso objetivo.
"""
    if sector_id == "fisioterapia":
        return """
el paciente llega con dolor o limitacion que afecta su dia a dia. quiere saber cuanto va a durar el tratamiento y si realmente va a funcionar. la evaluacion inicial responde esas dos preguntas - ese es su valor real.
"""
    if sector_id == "tattoo":
        return """
el cliente de tatuaje tiene una idea pero a veces no sabe como materializarla. lo que genera confianza es ver el portafolio del artista y sentir que va a entender la idea. el miedo al arrepentimiento se resuelve con una buena conversacion antes del diseno.
"""
    if sector_id == "hotel":
        return """
el huesped quiere saber si hay disponibilidad, que incluye, y si vale la pena. para ocasiones especiales (luna de miel, cumpleanos) el detalle personalizado hace diferencia. la confirmacion rapida y clara de la reserva da tranquilidad.
"""
    if sector_id == "fotografia":
        return """
el cliente contrata un fotografo para preservar algo importante. el miedo es que las fotos no capturen lo que imaginaba. ver el portafolio antes de cotizar es siempre el primer paso. para bodas y eventos, el tiempo de respuesta importa - las fechas se agotan.
"""
    if sector_id == "coworking":
        return """
el cliente de coworking optimiza: quiere el mejor espacio al menor costo con la menor friccion. pregunta precio rapido. lo que cierra es que sea facil empezar - sin contrato largo, sin burocracia. para empresas, factura y contrato son no negociables.
"""
    return ""


__all__ = [
    "PromptBuilderDeps",
    "build_compact_examples",
    "build_compact_system_prompt",
    "build_system_prompt",
    "truncate_block",
]
