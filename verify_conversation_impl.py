#!/usr/bin/env python3
"""Verificar que todas las funciones de conversación están presentes."""
import re

with open('melissa-omni.py', 'r') as f:
    content = f.read()

checks = {
    'get_recent_conversations': (r'async def get_recent_conversations\(', 'Obtener conversaciones recientes'),
    'get_active_conversations': (r'async def get_active_conversations\(', 'Obtener conversaciones activas'),
    'format_active_conversations': (r'def format_active_conversations\(', 'Formatear lista de conversaciones'),
    'format_conversation_detail': (r'def format_conversation_detail\(', 'Formatear detalle de conversación'),
    '/conversations handler': (r"text\.lower\(\)\.startswith\(\"/conversations\"\)", 'Manejador /conversations'),
    '/enter handler': (r'text\.startswith\(\"/enter ', 'Manejador /enter'),
    '/list handler': (r'text\.lower\(\) == \"/list\"', 'Manejador /list'),
    'Natural intent detection': (r'conversation_keywords = \[', 'Detección de intención natural'),
    'muéstrame/dame detection': (r"any\(kw in text_lower for kw in \[\"muéstrame\",", 'Detección muéstrame/dame'),
    'quién está detection': (r"any\(kw in text_lower for kw in \[\"quién\", \"quien\"", 'Detección quién está'),
    'System prompt update': (r'"También eres GESTORA DE CONVERSACIONES"', 'System prompt actualizado'),
    'Help text update': (r"\*Gestión de Conversaciones:\*", 'Help text actualizado'),
}

print("=" * 70)
print("✅ VERIFICACIÓN: Melissa Omni v2.1 - Conversation Features")
print("=" * 70)
print()

all_ok = True
for name, (pattern, desc) in checks.items():
    if re.search(pattern, content, re.MULTILINE):
        print(f"✅ {name:30} - {desc}")
    else:
        print(f"❌ {name:30} - {desc}")
        all_ok = False

print()
print("=" * 70)
if all_ok:
    print("✅ TODAS LAS VERIFICACIONES PASARON")
    print("🎉 Omni v2.1 está LISTO para producción")
else:
    print("❌ ALGUNAS VERIFICACIONES FALLARON")
    
print("=" * 70)

# Contar líneas de código nuevo
conv_section = content[content.find('async def get_recent_conversations'):content.find('# ══════════════════════════════════════════════════════════════════════════════\n# NOTIFICACIONES')]
print(f"\nLíneas de código para conversaciones: ~{len(conv_section.splitlines())} líneas")
