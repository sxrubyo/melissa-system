# Melissa Architecture Map

## Qué es Melissa

Melissa es un runtime base para recepcionistas IA orientadas a WhatsApp y Telegram. El repo público contiene el core reusable: conversación, memoria corta, personalidad, canales, API, CLI y sincronización hacia instancias de negocio. El estado vivo de cada negocio queda fuera del repo.

## Entry points reales

- `melissa.py`
  Runtime principal. Levanta FastAPI, webhooks, router de mensajes, memoria, base SQLite, auth de admin, conectores de canal, bridge de calendario y capa LLM.
- `melissa_cli.py`
  CLI operativo. Crea instancias, sincroniza runtime, inspecciona estado, administra webhooks, expone `bb`, hace doctor y orquesta despliegue local.
- `npm/melissa.js`
  Launcher global para `melissa-ai`.

## Núcleo conversacional

- `melissa_core/persona_registry.py`
  Carga personas desde YAML y resuelve la persona efectiva por clínica/sector/canal.
- `melissa_core/conversation_engine.py`
  Router conversacional liviano para casos que no necesitan gastar LLM: probe de identidad, meta-followups y algunos primeros turnos contextuales.
- `melissa_core/first_turn_ops.py`
  Helpers puros de primer turno, saludo, normalización y browser admin de conversaciones.
- `melissa_brain_v10.py`
  Memoria corta y anti-loop. Extrae señales del historial reciente para evitar repreguntas y elevar calidad contextual.

## Personalidad y voz

- `personas/melissa/base/default.yaml`
  Contrato base de voz.
- `personas/melissa/base/estetica_whatsapp.yaml`
  Override específico para estética/WhatsApp.
- `melissa.py`
  Sigue concentrando el `prompt building` pesado del runtime:
  - `_build_compact_system_prompt`
  - `_build_system_prompt`
  - `_apply_output_pipeline`
  - `_retry_until_human`

## Canales y entrega

- `melissa.py`
  Expone los webhooks HTTP y la lógica de entrada/salida por:
  - Telegram
  - WhatsApp Cloud
  - bridges compartidos
- `WhatsAppConnector`
  Integración con envío/salida de mensajes.
- `CalendarBridge`
  Resuelve disponibilidad o notifica al admin cuando la agenda no está integrada.

## Datos y persistencia

- `DatabaseManager` en `melissa.py`
  Es la capa de persistencia real. Administra clínica, pacientes, conversaciones, feedback, admins, tokens, reglas de confianza, playbooks y memoria operativa.
- `melissa.db`
  Base local de desarrollo o runtime local. No debe vivir en el repo público.

## Operación

- `melissa_cli.py`
  El CLI tiene cuatro dominios mezclados en un solo archivo:
  - lifecycle de instancias
  - health/doctor/logs
  - `bb` y entrenamiento operativo
  - sync/runtime propagation

## Tamaño real del problema

- `melissa.py`: ~28.5k líneas
- `melissa_cli.py`: ~11k líneas

El principal cuello de botella de mantenimiento no es el runtime en sí, sino el acoplamiento de demasiadas responsabilidades en esos dos archivos.

## Qué ya está separado

- persona registry
- conversation engine
- first-turn helpers
- memoria corta v10

## Qué falta separar

### Fase 1

- mover `prompt building` de `ResponseGenerator` a `melissa_core/prompt_ops.py`
- dejar `ResponseGenerator` como orquestador, no como contenedor de prosa gigante

### Fase 2

- mover browser admin de conversaciones a `melissa_admin/conversation_review_ops.py`
- separar auth/admin lifecycle de `melissa.py`

### Fase 3

- partir `melissa_cli.py` en:
  - `melissa_cli_instances.py`
  - `melissa_cli_bb.py`
  - `melissa_cli_runtime.py`
  - `melissa_cli_common.py`

## Cómo usar Melissa hoy

### Runtime local

```bash
python3 melissa.py
```

### CLI local

```bash
python3 melissa_cli.py --help
python3 melissa_cli.py guide
python3 melissa_cli.py bb config
```

### Global

```bash
npm install -g melissa-ai
melissa --help
```

## Riesgos actuales

- `melissa.py` todavía mezcla HTTP, DB, LLM, prompts, canales y helpers de negocio.
- `melissa_cli.py` todavía mezcla UX, PM2, bridge, sync, config y entrenamiento.
- el `conversation_engine` y `ResponseGenerator` todavía comparten parte del territorio del primer turno; ya no es crítico, pero aún no está completamente consolidado.
