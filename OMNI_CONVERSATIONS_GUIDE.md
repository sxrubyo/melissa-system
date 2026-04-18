# 📱 Guía de Gestión de Conversaciones - Melissa Omni v2.1

## Resumen

Omni ahora es tu **Centro de Mando de Conversaciones**. Puedes ver todos los chats activos, entrar en conversaciones específicas y responder a pacientes/clientes directamente desde Telegram.

---

## Comandos Disponibles

### 🔍 Ver Conversaciones Activas

```
/conversations          # Ver chats de TODAS las instancias
/conversations [inst]   # Ver chats de una instancia específica
/chats                  # Alias corto para /conversations
/list                   # Listar conversaciones activas
```

**Ejemplo:**
```
Santiago: /conversations
Omni: 📱 CONVERSACIONES ACTIVAS (12 totales)

👤 Maria Garcia (ID: `ch_001`)
   Último: "¿A qué hora me atiendes mañana?"
   Hace: Hace 2m

👤 Carlos López (ID: `ch_002`)
   Último: "Gracias por la cita, nos vemos"
   Hace: Hace 15m

... y 10 más
```

### 🪟 Entrar en una Conversación

```
/enter [chat_id]   # Entrar en una conversación específica
```

**Ejemplo:**
```
Santiago: /enter ch_001
Omni: 📱 CONVERSACIÓN CON MARIA GARCIA
ID: `ch_001`

Histórico (últimos 5 mensajes):
  Maria: "Hola, ¿están?"
  Melissa: "Hola Maria! Clínica Bella aquí ✨"
  Maria: "¿A qué hora me atiendes mañana?"
  Melissa: "Te atenderemos a las 3:00 PM"
  Maria: "Perfecto!"

Acciones:
  /reply ch_001 [mensaje] - Responder
  /tag ch_001 vip - Marcar como VIP
  /close ch_001 - Cerrar conversa
  /list - Volver a lista
```

---

## Lenguaje Natural

Omni entiende preguntas naturales sobre conversaciones:

### Ver Chats
```
"Muéstrame los chats activos"
"Dame una lista de conversaciones"
"¿Cuáles son los chats abiertos?"
"Quiero ver los mensajes"
```
→ **Automáticamente ejecuta:** `/conversations`

### Ver Clientes Pendientes
```
"¿Quién está esperando respuesta?"
"¿Qué pacientes tienen chats sin responder?"
"¿Cuáles son los chats pendientes?"
"Muéstrame clientes que necesitan atención"
```
→ **Automáticamente muestra:** Los 5 chats más recientes

### Entrar en Conversación
```
"Entra en el chat con María"
"Quiero ver la conversación con el cliente X"
"Abre el chat de Carlos"
```
→ **Omni te sugiere:** `/enter [chat_id]`

---

## Ejemplos de Uso Completo

### Escenario 1: Monitoreo Rápido
```
Santiago: Muéstrame los chats activos
Omni: [Muestra lista de 12 chats]
Santiago: ¿Quién está esperando?
Omni: [Muestra 5 chats más recientes con últimos mensajes]
Santiago: /enter ch_005
Omni: [Muestra conversación con María]
Santiago: /reply ch_005 Te atendemos en 5 minutos
Omni: [Mensaje enviado ✅]
```

### Escenario 2: Responder a Clientes Múltiples
```
Santiago: /conversations clinica-bella
Omni: [Muestra 10 chats de la clínica]
Santiago: /enter ch_002
Omni: [Detalle del chat]
Santiago: /reply ch_002 Hola! ¿En qué te puedo ayudar?
Omni: ✅ Mensaje enviado a Carlos López
Santiago: /list
Omni: [Vuelve a mostrar lista]
```

### Escenario 3: Análisis Inteligente
```
Santiago: Analiza clinica-bella
Omni: [Análisis MEGA: satisfacción 89%, temas trending, anomalías, etc.]
Santiago: ¿Quién está esperando?
Omni: [5 chats pendientes]
Santiago: Pero qué pasa con la conversación ch_003?
Omni: [LLM entiende el contexto y te da insight específico]
```

---

## Funcionalidades Avanzadas

### Información en Conversación

Cuando ves una conversación, Omni te muestra:
- **Nombre del cliente/paciente**
- **ID único del chat**
- **Últimos 5 mensajes** (histórico)
- **Acciones disponibles**

### Próximas Integraciones (Roadmap)

```
❌ /reply [chat_id] [msg]        # Responder mensajes
❌ /tag [chat_id] [tag]          # Marcar conversación
❌ /close [chat_id]              # Cerrar conversación
❌ /forward [chat_id] [user]     # Derivar a otro agente
❌ /summary [chat_id]            # Resumen IA de conversación
```

---

## Tips & Tricks

✅ **Usa /conversations sin parámetros** para ver TODAS las instancias  
✅ **Usa /conversations [inst]** para filtrar por instancia  
✅ **Las conversaciones se ordenan** por más recientes primero  
✅ **Omni entiende preguntas naturales** en español  
✅ **El chat_id aparece en la lista** para copiar/pegar rápidamente  

⚠️ **Limitaciones actuales:**
- Solo muestra últimos 10 chats en la lista (máx 50 en backend)
- Los históricos muestran últimos 5 mensajes
- Las acciones de /reply aún no están implementadas (próximamente)

---

## Problemas Comunes

**P: ¿Cómo copio el chat_id?**  
R: Aparece entre backticks, ej: `ch_001`. Selecciona y copia.

**P: ¿Puedo responder directamente?**  
R: No todavía. Próximamente con `/reply`. Ahorita ves el contexto.

**P: ¿Por qué solo veo 10 chats?**  
R: Es un límite de UI para no saturar. El backend carga 50.

**P: ¿Las conversaciones se actualizan en tiempo real?**  
R: No. Refrescar con `/list` o `/conversations` nuevamente.

---

## Arquitectura Interna

### Nuevas Funciones en Melissa-Omni

```python
async def get_active_conversations(instance: str = None)
    → Obtiene conversaciones activas de 1 o todas las instancias

async def get_recent_conversations(port: int, master_key: str, limit: int = 10)
    → Conecta a melissa.py y trae últimas N conversaciones

def format_active_conversations(conversations: List[Dict], instance: str = None)
    → Formatea lista bonita para mostrar a Santiago

def format_conversation_detail(conversation: Dict)
    → Formatea detalle de una conversación con histórico

async def handle_telegram_message(chat_id: str, text: str)
    → Detecta intención natural sobre conversaciones + ejecuta
```

### Flujo de Datos

```
Telegram (Santiago)
    ↓
handle_telegram_message()
    ↓
Detecta: /conversations, /enter, /list O intención natural
    ↓
get_active_conversations() → melissa.py API
    ↓
format_active_conversations() → respuesta bonita
    ↓
send_telegram() → Santiago ve el resultado
```

---

## Próximos Pasos

Santiago puede ya ahora:
✅ Ver todos los chats activos  
✅ Ver detalle de una conversación  
✅ Entender preguntas naturales  

Próximamente:
- ❌ Responder a clientes desde Omni
- ❌ Derivar conversaciones a agentes  
- ❌ Análisis de sentimiento por chat  
- ❌ Alertas cuando hay chats sin responder > X tiempo
- ❌ Estadísticas de tiempo de respuesta

---

**v2.1 - Enero 2025 | Melissa Omni Ultra**
