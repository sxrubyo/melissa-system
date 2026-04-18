# Melissa en Producción

Guía corta para operar Melissa esta noche sin mezclar promesas con realidad.

## Qué está conectado

- `Telegram` funciona con router compartido y ruteo por `chat_id`.
- `WhatsApp` funciona por bridge o por la plataforma configurada en cada instancia.
- El comportamiento base ya distingue `admin` y `paciente`.
- El buffer agrupa burbujas para que no responda como robot.
- El cambio de modelo se puede hacer por comando y por lenguaje natural.
- Las imágenes, logos y documentos de marca se guardan en un `Brand Vault` por instancia.

## Brand Vault

Cada instancia tiene su propia carpeta persistente de marca en `BRAND_ASSETS_BASE_DIR`.

Se usa para guardar:

- logos
- manuales
- PDFs
- textos de marca
- documentos de identidad visual

Qué hacer:

- envía los archivos al chat de admin de la instancia
- usa `/brand` para ver el estado del vault
- evita reenviar el mismo material en chats distintos si quieres mantener una sola fuente de verdad

Lo importante:

- Melissa conserva el archivo original y el texto extraído cuando aplica
- la carpeta se copia con `melissa new`, `melissa clone` y `melissa sync`

## Multi-canal

### Telegram

- La base puede actuar como router compartido.
- Las instancias hijas no deben pelear por el webhook.
- El enrutado correcto se define con `melissa pair`.

Comandos útiles:

```bash
melissa pair list
melissa pair default clinica-de-las-americas
melissa pair clinica-de-las-americas 123456789
melissa pair detach 123456789
```

### WhatsApp

- WhatsApp entra por el bridge o por la plataforma que ya esté configurada.
- El flujo ideal es uno solo por instancia.
- Si el bridge falla, primero revisa la sesión y el webhook antes de tocar el modelo.

## Tono: admin vs paciente

### Paciente

- tono cálido, corto y claro
- una sola pregunta útil por turno
- no sonar como manual ni call center
- si el mensaje trae ruido, responde solo lo útil

### Admin / dueño

- trato directo y profesional
- respetuoso, sin excesiva formalidad
- si el admin pide cambio de tono, Melissa debe ajustarse
- si algo no se entiende, debe pedir una aclaración corta

## Burbujas y buffering

Melissa no responde una burbuja por una burbuja cuando el contexto llega partido.

Comportamiento esperado:

- agrupa mensajes cercanos en una sola respuesta
- espera un poco antes de responder cuando hay mensajes seguidos
- mantiene el ritmo humano en varias burbujas

Variables relevantes:

- `BUFFER_WAIT_MIN`
- `BUFFER_WAIT_MAX`
- `BUBBLE_PAUSE_MIN`
- `BUBBLE_PAUSE_MAX`

Valores operativos actuales:

- `BUFFER_WAIT_MIN=8`
- `BUFFER_WAIT_MAX=18`
- `BUBBLE_PAUSE_MIN=0.8`
- `BUBBLE_PAUSE_MAX=2.5`

## Cambio de modelo

Se puede cambiar por:

- `/modelo`
- `/modelo gemini-flash`
- `/modelo claude-sonnet`
- `/modelo reset`

También entiende frases como:

- `usa gemini 2.5 flash`
- `cambia el modelo a claude sonnet`
- `ponte en gemini flash`

Modelos base recomendados hoy:

- `LLM_REASONING=google/gemini-2.5-flash`
- `LLM_FAST=google/gemini-2.5-flash`
- `LLM_LITE=google/gemini-2.5-flash-lite-preview-06-17`

## Crear nuevas instancias

Flujo recomendado:

```bash
melissa new
melissa pair default <instancia>
melissa sync
```

Si la instancia va por Telegram compartido:

- usa un solo bot token para el router base
- la instancia hija debe quedar enlazada por `chat_id`
- no le pongas un webhook propio si está bajo el router compartido

## Autocuración de instancia

Si una instancia vieja arranca con la base de datos incompleta pero sí tiene
`instance.json`, Melissa ahora rellena automáticamente:

- nombre del negocio
- servicios
- horario base
- `setup_done`
- memoria permanente mínima
- ruta del `Brand Vault`

Eso evita que una clínica existente quede viva pero aparezca como `sin configurar`.

## Qué sí y qué no

### Sí

- canalizar Telegram y WhatsApp
- guardar marca y documentos por instancia
- mantener conversaciones más humanas
- cambiar de modelo sin drama
- distinguir admin de paciente

### No todavía

- no asumir que Melissa ve todo tu historial de Gmail si no existe integración explícita
- no asumir que un archivo de marca explica por sí solo la identidad si no se carga bien al vault
- no vender la deduplicación de correo como real si la instancia no tiene acceso a la fuente correcta
- no levantar a la vez el `whatsapp-bridge` de PM2 y otro bridge Docker usando la misma carpeta de sesión o el mismo número

## Verificación rápida

```bash
pm2 ls
curl http://127.0.0.1:8003/health
curl http://127.0.0.1:8003/brand/status
melissa pair list
```

Si todo eso responde, la base está lista para operar y ajustar sobre la marcha.
