#!/usr/bin/env python3
"""
melissa_patch.py — Aplica todos los fixes de producción a melissa.py

Fixes:
  1. Presencia online al recibir mensaje (soluciona checkmark gris)
  2. Typing más humano con presencia antes de cada burbuja  
  3. Comando /token para generar códigos de activación desde el chat
  4. Comando /activar para activar instancia sin API externa
  5. Help actualizado con nuevos comandos
  
Uso: python3 melissa_patch.py /home/ubuntu/melissa/melissa.py
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

if len(sys.argv) < 2:
    print("Uso: python3 melissa_patch.py /ruta/a/melissa.py")
    sys.exit(1)

target = Path(sys.argv[1])
if not target.exists():
    print(f"Error: {target} no existe")
    sys.exit(1)

# Backup
backup = target.with_suffix(f".py.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
shutil.copy2(target, backup)
print(f"Backup: {backup}")

src = target.read_text(encoding="utf-8")
original_len = len(src)

# ══════════════════════════════════════════════════════════════════════════════
# PATCH 1 — _typing_action: agregar presencia available antes del typing
# Soluciona el checkmark gris — WA necesita saber que estamos online
# ══════════════════════════════════════════════════════════════════════════════

OLD_TYPING = '''            elif platform == "whatsapp":
                if Config.WHATSAPP_BRIDGE_URL:
                    async with httpx.AsyncClient(timeout=8.0) as client:
                        # Solo typing — el /read se dispara por separado con delay natural
                        await client.post(
                            f"{Config.WHATSAPP_BRIDGE_URL}/typing",
                            json={"to": chat_id, "duration": duration}
                        )'''

NEW_TYPING = '''            elif platform == "whatsapp":
                if Config.WHATSAPP_BRIDGE_URL:
                    async with httpx.AsyncClient(timeout=8.0) as client:
                        # 1. Aparecer online ANTES de typing — soluciona checkmark gris
                        # WhatsApp solo entrega mensajes cuando el remitente está online
                        try:
                            await client.post(
                                f"{Config.WHATSAPP_BRIDGE_URL}/presence",
                                json={"status": "available", "timeout": 120000},
                                timeout=3.0
                            )
                        except Exception:
                            pass
                        # 2. Typing proporcional al mensaje
                        await client.post(
                            f"{Config.WHATSAPP_BRIDGE_URL}/typing",
                            json={"to": chat_id, "duration": duration}
                        )'''

if OLD_TYPING in src:
    src = src.replace(OLD_TYPING, NEW_TYPING)
    print("✓ PATCH 1 aplicado: presencia online antes de typing")
else:
    print("⚠ PATCH 1 no encontrado — puede que ya esté aplicado")

# ══════════════════════════════════════════════════════════════════════════════
# PATCH 2 — webhook WhatsApp: marcar presencia available al recibir mensaje
# Esto hace que Melissa aparezca online inmediatamente cuando llega un mensaje
# ══════════════════════════════════════════════════════════════════════════════

OLD_WEBHOOK_WA = '''    if not chat_id:
        return {"ok": True}

    if audio_id:
        await melissa._typing_action(chat_id)'''

NEW_WEBHOOK_WA = '''    if not chat_id:
        return {"ok": True}

    # Aparecer online al recibir — soluciona checkmark gris y "último vez visto"
    if platform == "whatsapp" and Config.WHATSAPP_BRIDGE_URL:
        async def _go_online():
            try:
                async with httpx.AsyncClient(timeout=3.0) as _hx:
                    await _hx.post(
                        f"{Config.WHATSAPP_BRIDGE_URL}/presence",
                        json={"status": "available", "timeout": 180000}
                    )
            except Exception:
                pass
        asyncio.create_task(_go_online())

    if audio_id:
        await melissa._typing_action(chat_id)'''

if OLD_WEBHOOK_WA in src:
    src = src.replace(OLD_WEBHOOK_WA, NEW_WEBHOOK_WA)
    print("✓ PATCH 2 aplicado: presencia online al recibir mensaje")
else:
    print("⚠ PATCH 2 no encontrado")

# ══════════════════════════════════════════════════════════════════════════════
# PATCH 3 — Comandos /token y /activar en el handler admin
# /token [nombre] → genera un código de activación
# /activar         → activa esta instancia si ya tiene datos
# ══════════════════════════════════════════════════════════════════════════════

OLD_REGLAS_CMD = '''            elif cmd == "/reglas":
                return await self._admin_show_trust_rules()'''

NEW_REGLAS_CMD = '''            elif cmd == "/reglas":
                return await self._admin_show_trust_rules()

            # ── Tokens de activacion ───────────────────────────────────────
            elif cmd == "/token" or cmd.startswith("/token "):
                # /token              → genera token para esta instancia
                # /token Clinica Demo → genera token con ese nombre
                label = cmd.split("/token", 1)[1].strip() if " " in cmd else ""
                if not label:
                    clinic_name = clinic.get("name") or "Mi Negocio"
                    label = clinic_name
                new_token = generate_activation_token(label)
                expires_at = (datetime.now() + timedelta(hours=Config.TOKEN_EXPIRY_HOURS)).isoformat()
                saved = db.create_activation_token(new_token, label, expires_at)
                if saved:
                    return [
                        f"Token de activacion generado para: {label}",
                        f"{new_token}",
                        f"Expira en {Config.TOKEN_EXPIRY_HOURS}h. Enviaselo al administrador del negocio."
                    ]
                return ["No pude generar el token. Intenta de nuevo."]

            elif cmd == "/activar":
                # Activa esta instancia directamente (para instancias ya configuradas)
                clinic_name = clinic.get("name") or ""
                if not clinic_name:
                    db.update_clinic(setup_step="idle")
                    return [
                        "Para activar, primero dime el nombre de tu negocio.",
                        "Escribe el nombre y te configuro de una."
                    ]
                db.update_clinic(setup_done=1)
                admin_ids = clinic.get("admin_chat_ids", [])
                if isinstance(admin_ids, str):
                    try: admin_ids = json.loads(admin_ids) if admin_ids else []
                    except: admin_ids = []
                if chat_id not in admin_ids:
                    admin_ids.append(chat_id)
                    db.update_clinic(admin_chat_ids=json.dumps(admin_ids))
                return [
                    f"Instancia activada.",
                    f"Negocio: {clinic_name}",
                    f"Ya puedo atender pacientes. Escribe /config para ver todo."
                ]'''

if OLD_REGLAS_CMD in src:
    src = src.replace(OLD_REGLAS_CMD, NEW_REGLAS_CMD)
    print("✓ PATCH 3 aplicado: comandos /token y /activar")
else:
    print("⚠ PATCH 3 no encontrado")

# ══════════════════════════════════════════════════════════════════════════════
# PATCH 4 — Help actualizado con nuevos comandos
# ══════════════════════════════════════════════════════════════════════════════

OLD_HELP = '''            elif cmd.startswith("/"):
                return [
                    "Comandos disponibles:\\n\\n"
                    "/citas — citas pendientes\\n"
                    "/chats — ver conversaciones de pacientes\\n"
                    "/chat [id] — conversación completa\\n"
                    "/reglas — lo aprendido del feedback\\n"
                    "/sector — ver/cambiar sector del negocio\\n"
                    "/nova — motor de gobernanza\\n"
                    "/whatsapp — conectar WhatsApp Business\\n"
                    "/agenda — estado del calendario\\n"
                    "/personalidad — ajustar personalidad\\n"
                    "/config — ver configuración\\n"
                    "/metricas — métricas\\n\\n"
                    "V6.0 — Inteligencia:\\n"
                    "/pipeline — leads por temperatura (frío/tibio/caliente)\\n"
                    "/perdidos — por qué se van los clientes\\n"
                    "/coach — feedback de ventas de la semana\\n"
                    "/estilo — clonar tu forma de escribir\\n\\n"
                    "V6.0 — Automatización:\\n"
                    "/reactivar — reactivar clientes 60+ días inactivos\\n"
                    "/seguimiento — estado de follow-ups automáticos\\n"
                    "/reporte — reporte ahora mismo\\n"
                    "/broadcast [msg] — mensaje masivo a pacientes\\n\\n"
                    "V6.0 — Canales y pagos:\\n"
                    "/instagram — conectar DMs de Instagram\\n"
                    "/pagos — pagos desde el chat (Wompi/MercadoPago)\\n"
                    "/preconsulta — formulario pre-cita automático\\n\\n"
                    "O escríbeme en lenguaje natural."
                ]'''

NEW_HELP = '''            elif cmd.startswith("/"):
                return [
                    "Comandos disponibles:\\n\\n"
                    "Atencion:\\n"
                    "/citas — citas pendientes\\n"
                    "/chats — ver conversaciones de pacientes\\n"
                    "/chat [id] — conversacion completa\\n"
                    "/reglas — reglas aprendidas\\n"
                    "/broadcast [msg] — mensaje masivo\\n\\n"
                    "Configuracion:\\n"
                    "/config — ver configuracion\\n"
                    "/sector — ver/cambiar sector\\n"
                    "/personalidad — ajustar personalidad\\n"
                    "/whatsapp — conectar WhatsApp\\n"
                    "/agenda — estado del calendario\\n"
                    "/nova — motor de gobernanza\\n"
                    "/metricas — metricas\\n\\n"
                    "Activacion:\\n"
                    "/token [nombre] — generar codigo de activacion\\n"
                    "/activar — activar esta instancia\\n\\n"
                    "Inteligencia (V7):\\n"
                    "/pipeline — leads por temperatura\\n"
                    "/perdidos — analisis de perdidos\\n"
                    "/coach — feedback de ventas\\n"
                    "/reactivar — reactivar clientes inactivos\\n"
                    "/reporte — reporte inmediato\\n\\n"
                    "O escribe en lenguaje natural."
                ]'''

if OLD_HELP in src:
    src = src.replace(OLD_HELP, NEW_HELP)
    print("✓ PATCH 4 aplicado: help actualizado")
else:
    print("⚠ PATCH 4 no encontrado — ayuda sin cambios")

# ══════════════════════════════════════════════════════════════════════════════
# PATCH 5 — _send_bubbles: marcar offline después de enviar todas las burbujas
# Comportamiento humano: aparece online → escribe → desaparece
# ══════════════════════════════════════════════════════════════════════════════

OLD_SEND_BUBBLES_END = '''            if i < len(bubbles) - 1:
                # Pausa inter-burbuja más humana — evita que WA trate las ráfagas como spam
                inter_pause = random.uniform(1.4, 2.8) if is_wa else random.uniform(0.8, 1.8)
                await asyncio.sleep(inter_pause)'''

NEW_SEND_BUBBLES_END = '''            if i < len(bubbles) - 1:
                # Pausa inter-burbuja más humana — evita que WA trate las ráfagas como spam
                inter_pause = random.uniform(1.4, 2.8) if is_wa else random.uniform(0.8, 1.8)
                await asyncio.sleep(inter_pause)

        # Después de enviar todo: volver a unavailable con delay natural
        # Simula comportamiento humano: escribe, manda, se desconecta
        if is_wa and Config.WHATSAPP_BRIDGE_URL:
            async def _go_offline_delayed():
                await asyncio.sleep(random.uniform(8.0, 18.0))
                try:
                    async with httpx.AsyncClient(timeout=3.0) as _hx:
                        await _hx.post(
                            f"{Config.WHATSAPP_BRIDGE_URL}/presence",
                            json={"status": "unavailable"}
                        )
                except Exception:
                    pass
            asyncio.create_task(_go_offline_delayed())'''

if OLD_SEND_BUBBLES_END in src:
    src = src.replace(OLD_SEND_BUBBLES_END, NEW_SEND_BUBBLES_END)
    print("✓ PATCH 5 aplicado: offline después de enviar (comportamiento humano)")
else:
    print("⚠ PATCH 5 no encontrado")

# ══════════════════════════════════════════════════════════════════════════════
# Escribir resultado
# ══════════════════════════════════════════════════════════════════════════════

target.write_text(src, encoding="utf-8")
new_len = len(src)

print(f"\n{'='*60}")
print(f"Archivo actualizado: {target}")
print(f"Tamaño: {original_len:,} → {new_len:,} chars (+{new_len - original_len:,})")
print(f"Backup guardado en: {backup}")
print(f"\nSiguiente paso:")
print(f"  pm2 restart melissa --update-env")
print(f"  pm2 logs melissa --lines 20 --nostream")
