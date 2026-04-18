# ⚡ Omni Cheat Sheet - Referencia Rápida

## Comandos Rápidos (Copiar & Pegar)

```
/status                    # Ver estado de todas las instancias
/alerts                    # Ver alertas pendientes
/ack                       # Reconocer todas las alertas
/help                      # Ver todos los comandos

/conversations             # Ver TODOS los chats activos
/conversations clinica    # Ver chats de una instancia específica
/enter ch_001             # Entrar en una conversación
/list                     # Volver a listar conversaciones
```

## Comandos Mega Inteligentes

```
/analyze clinica-bella                  # Análisis profundo: satisfacción, temas, anomalías
/what-happened clinica-bella 6          # Qué pasó en las últimas 6 horas
/root-cause latency_spike               # Análisis de causa raíz
```

## Lenguaje Natural (Ejemplos)

Puedes simplemente escribir cosas como:

```
"Muéstrame los chats activos"
"¿Quién está esperando respuesta?"
"¿Cómo va clinica-bella?"
"Reinicia el restaurante"
"¿Hay algo raro?"
"Crea una alerta de latencia > 500ms"
"Compara dos instancias"
```

## Flujo Típico

### 1️⃣ Monitorear Instancias
```
/status
```
→ Ver si todo está online

### 2️⃣ Revisar Alertas
```
/alerts
```
→ Ver qué está fallando

### 3️⃣ Hacer Análisis Profundo
```
/analyze [instancia]
```
→ Entender: satisfacción clientes, temas trending, anomalías, predicciones

### 4️⃣ Ver Conversaciones
```
/conversations
```
→ Ver todos los chats activos, quién está esperando respuesta

### 5️⃣ Entrar en una Conversación
```
/enter [chat_id]
```
→ Ver histórico y contexto del cliente

## Ejemplos Reales

### Clínica Bella tiene latencia alta
```
Santiago: Analiza clinica-bella
Omni: [Muestra análisis MEGA]
Santiago: ¿Quién está esperando?
Omni: [5 chats pendientes]
Santiago: /conversations clinica-bella
Omni: [Detalle de chats de esa instancia]
```

### Restaurante no responde
```
Santiago: ¿Cómo va restaurante-central?
Omni: [Estado + satisfacción de clientes]
Santiago: /status
Omni: [Detalle técnico]
Santiago: Reinicia restaurante-central
Omni: [Reinicia + reporte de éxito]
```

### Monitoreo Diario
```
Santiago: /status
Santiago: /alerts
Santiago: /conversations
Santiago: Si hay algo raro → /analyze [inst]
```

## Información en Listas de Conversaciones

```
📱 CONVERSACIONES ACTIVAS (12 totales)

👤 Maria Garcia (ID: `ch_001`)         ← Nombre y ID
   Último: "¿A qué hora mañana?"      ← Último mensaje del cliente
   Hace: Hace 2m                       ← Cuándo fue el último mensaje
```

## Información en Detalle de Conversación

```
📱 CONVERSACIÓN CON MARIA GARCIA
ID: `ch_001`

Histórico (últimos 5 mensajes):
  Maria: "Hola, ¿están?"
  Melissa: "Hola Maria! ✨"
  ...

Acciones:
  /reply ch_001 [msg]   - Responder (próximamente)
  /tag ch_001 vip       - Marcar (próximamente)
  /close ch_001         - Cerrar (próximamente)
```

## Datos que Omni Te Muestra

### En /status
- Online / Total instancias
- Sector (emoji)
- Estado (Online/Offline)
- Plataforma (WhatsApp / Telegram)
- Latencia (ms)

### En /conversations
- Nombre del cliente/paciente
- ID del chat (para copiar)
- Último mensaje del cliente
- Hace cuánto tiempo fue el último mensaje

### En /analyze
- Satisfacción de clientes (%)
- Temas trending
- Anomalías detectadas
- Correlaciones (qué causó esto antes)
- Acciones recomendadas
- Predicciones

### En /alerts
- Timestamp
- Tipo de alerta (latency_spike, offline, etc.)
- Instancia afectada
- Reconocer alertas con /ack

## Sectores & Emojis

```
🏥 Clínicas / Salud
🍽️ Restaurantes
🏨 Hoteles
💪 Gimnasios
👔 Otros
```

## Tips de Profesional

✅ Usa `/status` primero para orientarte  
✅ Si hay alertas, usa `/analyze` en esa instancia  
✅ Usa `/conversations` para ver si hay clientes esperando respuesta  
✅ Si algo es raro, pregunta naturalmente: "¿Hay algo raro?"  
✅ Omni aprende de tus acciones → próximas veces da mejores recomendaciones  

⚠️ Cosas que NO puedes hacer aún:
- Responder mensajes directamente (próx)
- Derivar conversaciones (próx)
- Marcar conversaciones como VIP (próx)
- Ver análisis de sentimiento por chat (próx)

## Combinaciones Poderosas

### Stack de Diagnóstico Completo
```
Santiago: /status                     # Ver qué está down
Santiago: /alerts                     # Ver detalle de alertas
Santiago: /analyze [inst]             # Análisis profundo
Santiago: /what-happened [inst] 6     # Historiar últimas 6h
Santiago: /root-cause [evento]        # Causa raíz
```

### Atención al Cliente
```
Santiago: /conversations              # Ver chats activos
Santiago: ¿Quién está esperando?     # Ver pendientes
Santiago: /enter ch_001               # Ver detalles
Santiago: [Próximamente responder]
```

### Reportería
```
Santiago: /status
Santiago: /analyze [inst]             # Satisfacción, anomalías
Santiago: /what-happened [inst] 24    # Últimas 24h
```

---

## Emergency Commands (Próximamente)

```
/scale [inst] [workers]     # Escalar instancia
/restart [inst]             # Reiniciar instancia  
/backup [inst]              # Backup de data
/send-message [inst] [id]   # Enviar mensaje manual
```

---

**Omni v2.1 Ultra - Tu Centro de Mando Melissa**  
Escrito para Santiago | Enero 2025
