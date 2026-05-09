# Changelog

## 8.1.0 - 2026-05-09

- corrigido el filtro de frases robóticas para que deje de truncar salidas válidas del LLM
- invertida la prioridad de respuesta en demo/chat: el LLM decide primero y los fallbacks quedan como último recurso real
- endurecido el flujo demo para no rebinder confirmaciones como si fueran nuevos negocios y para mantener modo owner/admin sin secuestros
- productizado `smart_handoff.py` con persistencia completa de contexto, ack inmediato, timeout de 10 minutos y reanudación limpia
- añadido `melissa_bridge.py` con memoria SQLite, `/history`, `/clear`, `/export` y prueba automatizada de continuidad
- añadido modo `melissa_cli.py --non-interactive` para validación scripted del runtime
- reducidos `bare except` en `melissa.py` y cubiertos con pruebas nuevas de bridge, handoff y filtros
- incluido el nuevo runtime auxiliar en el paquete npm
