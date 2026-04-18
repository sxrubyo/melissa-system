# 🤖 Melissa v5.0 ULTRA - Documentación Técnica Completa

Melissa es un ecosistema de agentes autónomos de recepción diseñados para escalar la atención al cliente y la gestión de citas mediante IA multi-capa.

---

## 🏗️ 1. Arquitectura del Sistema

El sistema opera bajo un modelo de **Orquestación de Instancias**. Existe una "Instancia Base" y múltiples "Instancias de Clientes" que corren de forma independiente pero comparten el mismo núcleo lógico.

### Componentes de Software
1.  **`melissa.py` (Core):** El motor FastAPI que procesa mensajes, gestiona la lógica de citas y conecta con los LLMs.
2.  **`melissa_cli.py` (Gestor):** La interfaz de línea de comandos para crear y administrar la flota de agentes.
3.  **`melissa-omni.py` (Supervisor):** Sistema de monitorización global con auto-healing y dashboard web (Puerto 9001).
4.  **`melissa-chat.py` (Admin Chat):** Interfaz de lenguaje natural para que el dueño (Santiago) gestione el sistema conversando.

---

## 🛠️ 2. Guía de Comandos (CLI)

El comando principal es `melissa`. Estos son todos los comandos disponibles:

### Gestión de Instancias
*   `melissa init`: Configura el entorno, instala dependencias y prepara la base de datos global.
*   `melissa new`: Wizard interactivo para crear un nuevo negocio (Pide nombre, sector, puerto y keys).
*   `melissa list`: Muestra una tabla con todas las instancias, sus puertos y estado en PM2.
*   `melissa status`: Chequeo de salud (Health Check) en tiempo real de cada instancia.
*   `melissa delete <nombre>`: Detiene y borra físicamente la carpeta de la instancia.

### Control de Procesos (vía PM2)
*   `melissa start <nombre>`: Inicia el proceso.
*   `melissa stop <nombre>`: Detiene el proceso.
*   `melissa restart <nombre>`: Reinicia el proceso (útil tras cambios en el .env).
*   `melissa logs <nombre>`: Muestra la salida de consola en vivo.

### Mantenimiento y Backup
*   `melissa backup <nombre>`: Genera un volcado de la base de datos SQLite.
*   `melissa update`: Sincroniza el código base de todas las instancias con la última versión del core.

---

## 🧠 3. Módulos de Inteligencia y Datos

### 📖 Base de Conocimiento (`knowledge_base.py`)
Melissa no solo usa su entrenamiento general, usa RAG (Retrieval-Augmented Generation):
*   **Ingesta:** Los documentos del cliente se dividen en fragmentos (chunks) indexados.
*   **Recuperación:** Ante una duda, Melissa busca los fragmentos más parecidos y los usa como "Manual de consulta" antes de responder.

### 🔍 Motor de Búsqueda (`search.py`)
Cuando el conocimiento local no es suficiente, Melissa navega:
*   **Cascada:** SerpAPI (Google) -> Brave Search -> Apify.
*   **Especialización:** Búsquedas optimizadas para procedimientos médicos y estéticos (precios en Colombia, contraindicaciones por edad).

### 🛡️ Gobernanza Nova (`nova_bridge.py`)
Capa de ética y cumplimiento:
*   Cada mensaje pasa por un filtro de reglas antes de salir.
*   Puede bloquear respuestas que incluyan diagnósticos médicos prohibidos o información sensible.

---

## 👁️ 4. Melissa Omni (Supervisión Global)

Omni corre en el puerto **9001** y ofrece:
*   **Auto-Healing:** Si una clínica se cae, Omni la reinicia automáticamente tras 2 minutos.
*   **Notificaciones Multi-Canal:** Alertas a Telegram, Slack o Email ante errores críticos.
*   **Dashboard:** Interfaz web en `http://localhost:9001/dashboard`.

---

## 📡 5. API y Conectividad

Cada instancia expone endpoints clave:
*   `/health`: Estado del bot y conexión de WhatsApp.
*   `/analytics/summary`: Estadísticas de conversión (requiere `MASTER_API_KEY`).
*   `/appointments`: Gestión de la agenda.
*   `/trust-rules`: Reglas aprendidas del feedback humano (Carpeta de Confianza).

---

## ⚙️ 6. Configuración (.env)

Variables críticas para que una instancia funcione:
*   `TELEGRAM_TOKEN`: El bot de atención al público.
*   `OPENROUTER_API_KEY`: Acceso a la cascada de modelos (Claude, GPT, Llama).
*   `MASTER_API_KEY`: Tu clave maestra para la API.
*   `PORT`: El puerto único asignado (ej. 8005).

---
*Documentación generada para Melissa v5.0 ULTRA - 2026*
