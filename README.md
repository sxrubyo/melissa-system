# Melissa

Melissa es el runtime base de una recepcionista IA para WhatsApp y Telegram. Este árbol contiene la lógica compartida, el router principal, la capa de memoria y los módulos de conversación que luego se clonan o sincronizan hacia instancias específicas.

El objetivo de este repo es abrir el core sin exponer estado de producción. No incluye `.env` reales, bases locales, historiales de chats, logs ni credenciales.

## Qué hay aquí

- `melissa.py`: runtime principal y API FastAPI.
- `melissa_brain_v10.py`: capa de memoria corta y normalización mínima del primer turno.
- `melissa_domino.py`: guía estructural para respuestas de mayor calidad.
- `melissa_core/`: piezas compartidas de conversación y contexto.
- `melissa_agents/`, `melissa_skills/`, `melissa_integrations/`: módulos auxiliares del runtime.
- `personas/`: configuración base de personalidad y tono.
- `tests/`: regresiones del core y del flujo de sincronización.

## Estado del repo

Este repo está pensado como base reusable. Las instancias activas de negocio, sus sesiones, sus bases y sus secretos viven fuera del repositorio.

## Requisitos

- Python 3.11+
- `pip`
- Un `.env` derivado de `.env.example`

## Arranque local

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 melissa.py
```

Si usas el CLI local:

```bash
python3 melissa_cli.py --help
```

## Instalación global

Con npm:

```bash
npm install -g melissa-ai
melissa --help
```

Con el instalador local:

```bash
bash install.sh --user
```

## Tests

```bash
pytest -q
```

Para una verificación rápida del runtime sincronizable:

```bash
pytest -q tests/test_sync_runtime.py
```

## Sincronización de instancias

El CLI mantiene un manifiesto único de runtime para que `melissa new`, `melissa clone` y `melissa sync` copien la misma base compartida hacia las instancias.

```bash
python3 melissa_cli.py sync -y
```

## Seguridad

- No subas `.env`, tokens, bases SQLite, logs ni backups.
- Usa `.env.example` como contrato público de configuración.
- Revisa el árbol antes de cada push si vienes de una máquina de producción.

## Próximo paso de open source

- separar mejor el core compartido del estado de instancia
- bajar acoplamiento del monolito `melissa.py`
- publicar una guía clara para crear instancias nuevas sin tocar código sensible
