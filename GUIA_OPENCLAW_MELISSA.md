# Melissa + OpenClaw

## Qué se aplicó

Melissa ya soporta un patrón inspirado en `Openclaw` para Telegram:

- un solo `TELEGRAM_TOKEN` en la Melissa base
- un solo webhook público para ese token
- routing interno por `chat_id`
- instancias hijas que reciben el update ya encaminado

Esto permite que varias instancias hablen usando el mismo bot sin pelearse el webhook.

## Arquitectura

### Router base

La Melissa base puede actuar como router compartido si en su `.env` tiene:

```env
TELEGRAM_SHARED_ROUTER=true
TELEGRAM_DEFAULT_INSTANCE=clinica-de-las-americas
BASE_URL=https://tu-dominio
TELEGRAM_TOKEN=...
```

En ese modo, la base registra el webhook en:

`/telegram/shared/{secret}`

y decide a qué instancia mandar cada update.

### Instancia hija

Una instancia hija que quiera usar el token compartido debe tener:

```env
PLATFORM=telegram
TELEGRAM_TOKEN=...
TELEGRAM_SHARED=true
BASE_URL=https://tu-dominio
```

Cuando `TELEGRAM_SHARED=true`, la instancia no intenta registrar su propio webhook. Solo espera updates reenviados por la base.

## Cómo decide el destino

Melissa resuelve el destino en este orden:

1. ruta explícita en `shared_telegram_routes.json`
2. `default_instance`
3. `TELEGRAM_DEFAULT_INSTANCE`
4. si solo existe una instancia compartida, usa esa

Archivo de rutas:

`/home/ubuntu/melissa/shared_telegram_routes.json`

## Comandos CLI útiles

Listar rutas actuales:

```bash
cd /home/ubuntu/melissa
. .venv/bin/activate
python3 melissa_cli.py pair list
```

Asignar un `chat_id` a una instancia:

```bash
python3 melissa_cli.py pair clinica-de-las-americas 123456789
```

Definir la instancia por defecto:

```bash
python3 melissa_cli.py pair default clinica-de-las-americas
```

Quitar una ruta:

```bash
python3 melissa_cli.py pair detach 123456789
```

## Cambio de modelo

Melissa ya acepta cambios de modelo en tres formas:

### Slash command

```text
/modelo
/modelo gemini-flash
/modelo claude-sonnet
/modelo reset
```

### Lenguaje natural

```text
usa gemini 2.5 flash
cambia el modelo a claude sonnet
ponte en gemini flash
dejalo en gemini 2.5 flash
```

### Default recomendado

Hoy el default operativo recomendado quedó así:

- `LLM_REASONING=google/gemini-2.5-flash`
- `LLM_FAST=google/gemini-2.5-flash`
- `LLM_LITE=google/gemini-2.5-flash-lite-preview-06-17`

## Humanización

Se reforzaron estos puntos:

- el primer turno no debe abrir con `hola, en qué te ayudo`
- evita `entiendo perfecto`, `como asistente virtual`, `soy un bot`
- reacciona a lo que la persona ya dijo
- termina con una sola pregunta útil
- menos temperatura en primer contacto para evitar respuestas raras o demasiado perfectas

## Validaciones recomendadas

### Ver que la ruta compartida resuelve bien

```bash
cd /home/ubuntu/melissa
. .venv/bin/activate
python3 - <<'PY'
import melissa
print(melissa._resolve_shared_telegram_target('555123'))
PY
```

### Ver que el parser de modelo entiende lenguaje natural

```bash
cd /home/ubuntu/melissa
. .venv/bin/activate
python3 - <<'PY'
import melissa
tests = [
    'usa gemini 2.5 flash',
    'cambia el modelo a claude sonnet',
    'ponte en gemini flash',
]
for t in tests:
    print(t, '=>', melissa.extract_model_request_from_text(t))
PY
```

### Reiniciar la clínica después de sincronizar

```bash
pm2 restart melissa-clinica-de-las-americas
curl -s http://127.0.0.1:8003/health
```

## Estado actual

- la clínica ya está usando el token compartido
- el router base ya resuelve `clinica-de-las-americas` como destino por defecto
- Gemini 2.5 Flash quedó como modelo efectivo del tier `fast`
- Melissa entiende cambios de modelo en lenguaje natural
- el primer turno quedó más directo y menos bot

## Lo que sigue si quieres llevarlo más lejos

- enrutar varios negocios con el mismo bot usando `pair`
- añadir pruebas E2E con payloads Telegram mockeados
- ajustar tono por sector con más few-shots propios
- guardar preferencias de modelo por admin y por chat de prueba
