# Changelog

## 8.1.1 - 2026-05-10

- corregido el flujo demo-owner en inglés para no tomar frases como `Just English sorry` o `I don't talk Spanish` como nombre de negocio
- endurecida la detección de idioma para mantener el inglés durante confirmaciones, correcciones y preguntas meta del dueño
- localizado el binding del negocio, confirmaciones de URL, correcciones y resets para que respeten el idioma activo del dueño
- afinados los heurísticos de nombre de negocio para distinguir mejor entre lenguaje/meta y nombres reales
- añadidas pruebas para onboarding demo en inglés, corrección de match equivocado y preservación del idioma en sesión

## 8.1.0 - 2026-05-09

- corrigido el filtro de frases robóticas para que deje de truncar salidas válidas del LLM
- invertida la prioridad de respuesta en demo/chat: el LLM decide primero y los fallbacks quedan como último recurso real
- endurecido el flujo demo para no rebinder confirmaciones como si fueran nuevos negocios y para mantener modo owner/admin sin secuestros
- productizado `smart_handoff.py` con persistencia completa de contexto, ack inmediato, timeout de 10 minutos y reanudación limpia
- añadido `melissa_bridge.py` con memoria SQLite, `/history`, `/clear`, `/export` y prueba automatizada de continuidad
- añadido modo `melissa_cli.py --non-interactive` para validación scripted del runtime
- reducidos `bare except` en `melissa.py` y cubiertos con pruebas nuevas de bridge, handoff y filtros
- incluido el nuevo runtime auxiliar en el paquete npm
