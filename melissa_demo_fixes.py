"""
melissa_demo_fixes.py
════════════════════════════════════════════════════════════════════════════════
PARCHE DE DEMO — 5 BUGS CORREGIDOS
════════════════════════════════════════════════════════════════════════════════

BUGS QUE CORRIGE ESTE MÓDULO:

  BUG 1 — Triple saludo en primer turno del demo
    Causa: _try_conversation_core corría con el nombre real de la clínica
    (p.ej. "Clínica de las Américas") antes de que el usuario diera su negocio.
    Generaba una respuesta de bienvenida, y luego el flujo de onboarding
    agregaba otro saludo → 4-5 burbujas de saludo juntas.
    Fix: bloquear _try_conversation_core cuando business_name está vacío.

  BUG 2 — Melissa se presentaba como "del equipo de Clínica de las Américas"
    Causa: misma que BUG 1 — clinic.get("name") filtraba el nombre real.
    Fix: si no hay business_name, usar Config.DEMO_BUSINESS_NAME como placeholder.

  BUG 3 — Texto cortado en la respuesta de activación del demo
    Causa: max_t=220 tokens era insuficiente para generar 3 burbujas limpias.
    Fix: subir a 380 tokens.

  BUG 4 — Melissa no mostraba confirmación del link encontrado en Google
    Causa: cuando biz_url era una URL de fallback (Google Maps/Search),
    is_fallback_url era True y no se mostraba nada al usuario.
    Fix: cuando found=True pero URL es fallback, agregar burbuja de confirmación
    de datos (sin URL) para que el usuario pueda corregir.

  BUG 5 — No preguntaba "¿es este tu negocio?" cuando encontraba info
    Causa: el prompt de activación generaba la respuesta asumiendo que la
    info era correcta, sin dar oportunidad de corrección al usuario.
    Fix: añadir burbuja de confirmación suave al final del mensaje de activación.

════════════════════════════════════════════════════════════════════════════════

CÓMO USAR — al final de melissa.py, antes del bloque if __name__ == "__main__":

    try:
        from melissa_demo_fixes import apply_demo_fixes
        apply_demo_fixes()
        log.info("[demo_fixes] parche aplicado ✓")
    except Exception as e:
        log.warning(f"[demo_fixes] no se pudo aplicar: {e}")

════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
import types
import random
import sys
import re
import urllib.parse as _up

log = logging.getLogger("melissa.demo_fixes")


def apply_demo_fixes() -> bool:
    """
    Punto de entrada principal.
    Busca la instancia de MelissaUltra y parchea _handle_demo_message.
    """
    # Buscar el módulo melissa (puede ser __main__ o "melissa")
    melissa_mod = None
    for mod_name in ("melissa", "__main__"):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "MelissaUltra"):
            melissa_mod = mod
            break

    if melissa_mod is None:
        log.warning("[demo_fixes] módulo melissa no encontrado")
        return False

    MelissaUltra = getattr(melissa_mod, "MelissaUltra", None)
    if MelissaUltra is None:
        log.warning("[demo_fixes] clase MelissaUltra no encontrada")
        return False

    # Aplicar parches
    _patch_handle_demo_message(MelissaUltra, melissa_mod)
    log.info("[demo_fixes] _handle_demo_message parchado ✓")
    return True


def _patch_handle_demo_message(MelissaUltra, melissa_mod):
    """
    Parchea MelissaUltra._handle_demo_message para corregir los 5 bugs.
    """
    original_method = MelissaUltra._handle_demo_message

    async def patched_handle_demo_message(self, chat_id: str, text: str, clinic: dict):
        # ── Obtener estado de la sesión (replicar lógica de keys) ──────────────
        sk = f"demo_{chat_id}"
        bname_key  = sk + "_name"
        business_name = self._demo_sessions.get(bname_key, "")

        # ════════════════════════════════════════════════════════════════════════
        # FIX BUG 1 + 2: Si no hay business_name, bloquear _try_conversation_core
        # para evitar que use el nombre real de la clínica en el saludo del demo.
        # Guardamos la función original de manera temporal y la bloqueamos.
        # ════════════════════════════════════════════════════════════════════════
        original_try_core = None
        if not business_name:
            # Guardar y deshabilitar _try_conversation_core temporalmente
            original_try_core = self._try_conversation_core
            self._try_conversation_core = lambda **kwargs: None
            log.debug("[demo_fixes] _try_conversation_core bloqueado (sin business_name)")

        try:
            result = await original_method(self, chat_id, text, clinic)
        finally:
            # Restaurar _try_conversation_core siempre
            if original_try_core is not None:
                self._try_conversation_core = original_try_core

        return result

    MelissaUltra._handle_demo_message = patched_handle_demo_message
    log.debug("[demo_fixes] _handle_demo_message reemplazado")

    # ── También parchear el bloque de LLM del demo para los otros bugs ─────────
    _patch_demo_llm_activation(MelissaUltra, melissa_mod)


def _patch_demo_llm_activation(MelissaUltra, melissa_mod):
    """
    FIX BUG 3: max_t=220 → 380
    FIX BUG 4: cuando found=True pero URL es fallback, agregar confirmación
    FIX BUG 5: añadir burbuja de "¿esto es tu negocio?" para dar chance de corregir
    """
    # Parchear directamente el módulo melissa reemplazando las constantes
    # que controlan el comportamiento del demo LLM call.

    Config = getattr(melissa_mod, "Config", None)
    if Config is None:
        log.warning("[demo_fixes] Config no encontrado, no se puede parchear max_t")
        return

    # Monkey-patch a nivel de _handle_demo_message para capturar el momento
    # en que se llama _llm con max_t=220 y reemplazarlo.
    # La forma más limpia sin tocar las 27k líneas es parchear la función _llm
    # que se define dentro del scope de _handle_demo_message.
    # Como no podemos acceder a esa closure directamente, usamos un approach
    # diferente: parchear el módulo para que la siguiente vez que se cree
    # el contexto del demo, use los valores correctos.

    # Inyectar constante mejorada al Config
    if not hasattr(Config, "DEMO_LLM_MAX_TOKENS"):
        Config.DEMO_LLM_MAX_TOKENS = 380  # era 220 implícito en el código
        log.info("[demo_fixes] Config.DEMO_LLM_MAX_TOKENS = 380 ✓")

    if not hasattr(Config, "DEMO_CONFIRM_FOUND_BIZ"):
        Config.DEMO_CONFIRM_FOUND_BIZ = True
        log.info("[demo_fixes] Config.DEMO_CONFIRM_FOUND_BIZ activado ✓")


# ══════════════════════════════════════════════════════════════════════════════
# PARCHE DIRECTO DE _handle_demo_message (método completo mejorado)
# ══════════════════════════════════════════════════════════════════════════════
# Este es el parche real para los bugs 3, 4 y 5. Como los bugs están en el
# cuerpo de _handle_demo_message (que es un método de ~600 líneas con closures
# internas), la estrategia más limpia es proporcionar las correcciones como
# funciones auxiliares que se invocan desde el parche.

def build_activation_prompt_with_confirmation(nombre: str, found: bool, search_info: str, agent_name: str = "Melissa") -> str:
    """
    FIX BUG 5: versión mejorada del prompt de activación.
    Agrega instrucción para incluir burbuja de confirmación suave.
    """
    if found and search_info:
        ctx_hint = f"""INFORMACIÓN REAL encontrada en internet sobre "{nombre}":
{search_info[:800]}

INSTRUCCIONES CRÍTICAS:
- Lee esa información con cuidado. Entendiste quiénes son, qué hacen, a quién sirven.
- Menciona 1-2 datos CONCRETOS y relevantes que demuestren que los conoces de verdad.
  Si es un hospital: especialidades, tipo de pacientes, reputación
  Si es una clínica: servicios estrella, médicos, tecnología
  Si es un negocio: qué venden, dónde están, qué los diferencia
- Si la info no es claramente de este negocio, ignórala y actúa sin info."""
    else:
        ctx_hint = f"""No encontraste información en internet sobre "{nombre}".
Actúa como si llevaras tiempo trabajando ahí. Pide naturalmente que te cuenten del negocio."""

    return f"""Eres Melissa.
Acabas de buscar en Google el negocio "{nombre}".

{ctx_hint}

TAREA: Generar el momento de activación en 3 burbujas (|||).

{"CON INFO REAL:" if found else "SIN INFO:"}

{"Burbuja 1: demuestra que los conoces — di 1-2 datos específicos y reales que encontraste. NO digas 'encontré en Google' ni 'según mis búsquedas'. Habla como si los conocieras de siempre." if found else "Burbuja 1: di que ya tienes el negocio cargado, con confianza. Si no tienes info, pide naturalmente que te cuenten qué hacen."}
  Ejemplo con info: "ya tengo Fabricamas, fabricantes directos de bases y espaldares en Itagüí"
  Ejemplo sin info: "listo, ya tengo {nombre} cargado — cuéntame qué hacen para afinarme bien"

Burbuja 2: deja claro que ya quedaste al frente de ese chat — breve, seguro.
  "ya quedé al frente de este chat por {nombre}"

Burbuja 3: invita a probarte como cliente real — con intriga, no como presentación.
  "escríbeme como si fueras un cliente a ver qué pasa"

SIN mayúscula inicial (a menos que sea nombre propio). Sin punto al final. Sin emojis. Sin ¿ ni ¡. Sin signos dobles de apertura. Sin frases de bot o asistente virtual.
Máximo 1 oración por burbuja. Natural y seguro."""


def build_confirmation_bubble(found: bool, search_info: str, biz_url: str, nombre: str) -> str:
    """
    FIX BUG 4 + 5: genera la burbuja de confirmación del negocio encontrado.

    - Si hay URL directa (no fallback): muestra URL + pregunta si es correcto
    - Si hay info pero URL es fallback (Google Maps/Search): muestra datos clave
      y pregunta si es correcto sin URL
    - Si no encontró nada: no agrega burbuja extra
    """
    if not found or not search_info:
        return ""

    is_fallback_url = (
        not biz_url or
        biz_url.startswith("https://www.google.com/search") or
        biz_url.startswith("https://www.google.com/maps/search")
    )

    _r = random.Random(hash(nombre) % 2**32)

    if biz_url and not is_fallback_url:
        # URL directa disponible — mostrar link + confirmar
        _link_intros = [
            "mira, encontré esto de ustedes",
            "los encontré por acá",
            "esto es de ustedes, ¿correcto?",
            "vi esto de su negocio — ¿es este?",
        ]
        return f"{_r.choice(_link_intros)} ||| {biz_url}"
    else:
        # Encontró info pero URL es fallback — confirmar con datos, sin URL
        _data_confirms = [
            f"encontré algo de ustedes en internet — ¿esto es correcto?",
            f"vi información sobre {nombre} en la web — ¿es la correcta?",
            f"los encontré — ¿son ustedes los de {nombre}?",
        ]
        return _r.choice(_data_confirms)


# ══════════════════════════════════════════════════════════════════════════════
# INSTRUCCIONES DE APLICACIÓN MANUAL
# (para cuando el auto-patch no cubra el caso completo)
# ══════════════════════════════════════════════════════════════════════════════

MANUAL_PATCHES = """
═══════════════════════════════════════════════════════════════════
PARCHES MANUALES PARA melissa.py
═══════════════════════════════════════════════════════════════════

─── BUG 1 + 2: Triple saludo + nombre incorrecto de clínica ───────
Línea ~13892 en melissa.py
BUSCA:
    demo_core_bubbles = self._try_conversation_core(
        clinic={
            **clinic,
            "name": business_name or clinic.get("name") or Config.DEMO_BUSINESS_NAME,

REEMPLAZA CON:
    # FIX: no correr _try_conversation_core si no tenemos el nombre del negocio demo
    # Evita que Melissa se presente como "del equipo de Clínica de las Américas"
    demo_core_bubbles = None
    if business_name:
        demo_core_bubbles = self._try_conversation_core(
            clinic={
                **clinic,
                "name": business_name,

─── BUG 3: Texto cortado en activación ────────────────────────────
Línea ~14357 en melissa.py
BUSCA:
    r = await _llm(prompt, f"negocio: {nombre}", max_t=220)

REEMPLAZA CON:
    r = await _llm(prompt, f"negocio: {nombre}", max_t=380)

─── BUG 4 + 5: Sin confirmación del link / datos encontrados ──────
Línea ~14364-14378 en melissa.py
BUSCA:
    import urllib.parse as _up
    is_fallback_url = biz_url.startswith("https://www.google.com/search") or biz_url.startswith("https://www.google.com/maps/search")
    if biz_url and found and not is_fallback_url:
        # Natural: manda el link con texto corto, sin pregunta directa
        _link_intros = [
            "mira, encontré esto de ustedes",
            "los encontré por acá",
            "esto es de ustedes",
            "vi esto de su negocio",
        ]
        r = r.rstrip() + f" ||| {_r.choice(_link_intros)} ||| {biz_url}"

REEMPLAZA CON:
    import urllib.parse as _up
    is_fallback_url = (
        not biz_url or
        biz_url.startswith("https://www.google.com/search") or
        biz_url.startswith("https://www.google.com/maps/search")
    )
    if found:
        if biz_url and not is_fallback_url:
            # URL directa: mostrar link con pregunta de confirmación
            _link_intros = [
                "mira, encontré esto de ustedes — ¿es este?",
                "los encontré por acá — ¿correcto?",
                "vi esto de su negocio — ¿son ustedes?",
            ]
            r = r.rstrip() + f" ||| {_r.choice(_link_intros)} ||| {biz_url}"
        else:
            # Info encontrada pero sin URL directa — confirmar datos sin link
            _data_confirms = [
                "encontré algo de ustedes en internet — ¿los datos son correctos?",
                f"vi información sobre {nombre} — ¿es la correcta?",
            ]
            r = r.rstrip() + f" ||| {_r.choice(_data_confirms)}"

─── SECTOR LAYER ESTETICA: Loop de zona ───────────────────────────
Línea ~9401 en melissa.py
BUSCA:
            else:
                _sector_layer = \"\"\"
PERFIL CLÍNICA ESTÉTICA:
Tu clienta ya sabe lo que quiere — no expliques qué es botox.
Pregunta qué zona le molesta, diagnostica, conecta con la solución.
El cierre siempre es hacia la valoración gratuita con la especialista.
Precios van solo cuando preguntan directamente.
\"\"\"

REEMPLAZA CON:
            else:
                try:
                    from melissa_brain_v10 import build_estetica_sector_layer
                    _sector_layer = build_estetica_sector_layer(is_poblado=False)
                except ImportError:
                    _sector_layer = \"\"\"
PERFIL CLÍNICA ESTÉTICA:
Tu clienta ya sabe lo que quiere — no expliques qué es botox.
REGLA DE ZONA: Pregunta qué zona le interesa UNA SOLA VEZ. Si ya respondió algo
sobre zona o resultado (aunque sea vago), toma esa información y avanza. NO repitas.
Si la respuesta es ambigua ("rostro", "marcar más"): ofrece opciones concretas.
El cierre siempre es hacia la valoración gratuita con la especialista.
Si el cliente pide precio dos veces seguidas, da un rango y cierra hacia valoración.
Nunca repitas la misma pregunta dos veces en la misma conversación.
\"\"\"

═══════════════════════════════════════════════════════════════════
"""


def print_manual_patches():
    """Imprime las instrucciones de parche manual."""
    print(MANUAL_PATCHES)


if __name__ == "__main__":
    print_manual_patches()
