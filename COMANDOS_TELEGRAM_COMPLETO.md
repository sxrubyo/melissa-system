# 📱 LISTA COMPLETA DE COMANDOS TELEGRAM - OMNI v2.1

## 🔴 COMANDOS RÁPIDOS (Sin parámetros)

| Comando | Descripción |
|---------|-------------|
| `/status` | Ver estado de TODAS las instancias (online/offline, latencia, memoria) |
| `/alerts` | Ver alertas pendientes (no reconocidas) con timestamp |
| `/ack` | Reconocer TODAS las alertas pendientes automáticamente |
| `/help` | Mostrar esta lista de comandos |
| `/conversations` | Ver chats activos de TODAS las instancias (top 10) |
| `/chats` | Alias para `/conversations` |
| `/list` | Listar conversaciones activas nuevamente |

---

## 🟠 COMANDOS CON PARÁMETROS

### `/analyze [instancia]`
```
/analyze clinica-bella
/analyze restaurante-central
```
**Qué hace:** Análisis PROFUNDO y MEGA inteligente de una instancia
**Muestra:**
- Satisfacción de clientes (porcentaje)
- Temas trending en conversaciones
- Anomalías detectadas
- Correlaciones históricas
- Acciones recomendadas
- Predicciones

---

### `/what-happened [instancia] [horas]`
```
/what-happened clinica-bella 6
/what-happened restaurante-central 24
/what-happened hotel-paradise      (default 6h)
```
**Qué hace:** Histórico de eventos en las últimas N horas
**Parámetros:**
- `instancia`: nombre de la instancia (obligatorio)
- `horas`: número de horas atrás (default: 6 si no especificas)
**Muestra:**
- Eventos cronológicos
- Cambios de estado
- Alertas
- Causalidad entre eventos

---

### `/root-cause [evento]`
```
/root-cause latency_spike
/root-cause offline_restaurant
/root-cause high_error_rate
```
**Qué hace:** Análisis de CAUSA RAÍZ - por qué pasó algo
**Muestra:**
- Qué causó el problema
- Cuándo pasó algo similar antes
- Cómo se resolvió la última vez
- Probabilidad de la causa identificada

---

### `/conversations [instancia]`
```
/conversations                (TODOS los chats de todas instancias)
/conversations clinica-bella  (Chats de solo esa instancia)
/conversations restaurante    (Filtra por nombre)
```
**Qué hace:** Ver chats activos (todos o de una instancia)
**Muestra:**
- Nombre del cliente/paciente
- ID del chat (entre backticks)
- Último mensaje (preview de 60 caracteres)
- Hace cuánto fue el último mensaje

---

### `/enter [chat_id]`
```
/enter ch_001
/enter ch_abc123
/enter patient_maria_123
```
**Qué hace:** Entrar en una conversación específica
**Parámetros:**
- `chat_id`: ID del chat (obtenlo de `/conversations`)
**Muestra:**
- Nombre del cliente/paciente
- ID del chat
- Histórico de últimos 5 mensajes
- Sender de cada mensaje (quién escribió)
- Acciones disponibles

---

## 💬 LENGUAJE NATURAL

Omni entiende preguntas naturales en español. NO NECESITAS COMANDOS si hablas naturalmente.

### Sobre Estado de Instancias
```
"¿Cómo va clinica-bella?"
"¿Cómo está el restaurante?"
"Dame el estado del hotel"
"¿Qué pasó hoy?"
"¿Por qué subió la latencia?"
"¿Hay algo raro en restaurante?"
"¿Hay anomalías?"
```

### Sobre Conversaciones
```
"Muéstrame los chats activos"        → Ejecuta /conversations automático
"¿Quién está esperando?"             → Muestra top 5 clientes pendientes
"Dame una lista de chats"            → /conversations
"Chats de clinica-bella"             → /conversations clinica-bella
"¿Cuáles son los clientes nuevos?"   → /conversations
"¿Qué pacientes no han respondido?"  → /conversations
"Clientes que necesitan atención"    → /conversations
```

### Sobre Acciones
```
"Reinicia el restaurante"            → Ejecuta reinicio
"Reinicia clinica-bella"             → Ejecuta reinicio
"Crea una alerta de latencia > 500ms" → Crea alert automática
"Reinicia todas las instancias"      → Ejecuta reinicio múltiple
```

### Sobre Análisis
```
"¿Hay algo raro?"                    → Análisis de anomalías
"Dame un resumen"                    → /analyze de instancia
"¿Qué predicciones hay?"             → Predicciones
"Compara dos instancias"             → Análisis comparativo
"Analiza clinica-bella"              → /analyze clinica-bella
```

---

## 📊 TABLA RESUMEN RÁPIDO

| Comando | Parámetro | Función |
|---------|-----------|---------|
| `/status` | — | Estado de todas instancias |
| `/alerts` | — | Ver alertas pendientes |
| `/ack` | — | Reconocer todas alertas |
| `/help` | — | Mostrar comandos |
| `/conversations` | — | Todos los chats |
| `/conversations [i]` | instancia | Chats de una instancia |
| `/chats` | — | Alias conversaciones |
| `/list` | — | Re-listar chats |
| `/enter [id]` | chat_id | Detalles de chat |
| `/analyze [i]` | instancia | Análisis profundo |
| `/what-happened [i] [h]` | inst + horas | Histórico |
| `/root-cause [evt]` | evento | Causa raíz |

**TOTAL: 12 comandos + lenguaje natural infinito**

---

## 🎯 CASOS DE USO

### Monitoreo Diario (Mañana)
```
/status              ← Verificar online
/alerts              ← Ver si hay problemas
/conversations       ← Ver clientes nuevos
/help                ← Recordar comandos si necesitas
```

### Cuando Algo Falla
```
/alerts                     ← Qué está roto
/analyze [inst]             ← Entender por qué
/root-cause [evento]        ← Causa raíz específica
/what-happened [inst] 6     ← Qué pasó en últimas 6h
/conversations [inst]       ← Clientes esperando
```

### Gestionar Clientes
```
/conversations              ← Ver todos los chats
"¿Quién está esperando?"    ← Ver pendientes
/enter [chat_id]            ← Ver detalles del chat
```

### Investigación Profunda
```
/analyze [inst]             ← Análisis completo
/what-happened [inst] 24    ← Últimas 24 horas
/root-cause [evento]        ← Por qué pasó
Preguntas naturales         ← Omni entiende contexto
```

---

## 💡 TIPS PROFESIONALES

✅ **Siempre comienza con `/status`** para orientarte  
✅ **Si hay alertas, usa `/analyze [inst]`** para entender  
✅ **Pregunta en español natural** - Omni entiende perfectamente  
✅ **`/conversations` es tu nuevo mejor amigo** - úsalo constantemente  
✅ **`/help` te muestra todo nuevamente** si lo olvidas  
✅ **Los parámetros van sin corchetes:** `/analyze clinica` (NO `/analyze [clinica]`)  
✅ **Los chat_ids aparecen entre backticks:** `ch_001` - cópialos así  
✅ **Omni aprende de tus acciones** - próximas veces mejora automáticamente  

---

## 🔤 EJEMPLOS REALES COMPLETOS

### EJEMPLO 1: Monitoreo Matutino
```
Santiago: /status
Omni: 📊 Estado Rápido (09:30)
      Online: 4/4
      🏥 Clinica Bella (45ms)
      🍽️  Restaurante Central (32ms)
      🏨 Hotel Paradise (67ms)
      💪 Gimnasio Fit (28ms)

Santiago: /alerts
Omni: ✅ No hay alertas pendientes

Santiago: /conversations
Omni: 📱 CONVERSACIONES ACTIVAS (12 totales)
      👤 Maria Garcia (ID: `ch_001`)
      Último: "¿A qué hora me atiendes?"
      Hace: Hace 2m
      ...
```

### EJEMPLO 2: Problema de Latencia
```
Santiago: /analyze clinica-bella
Omni: [Muestra análisis profundo con satisfacción, temas, anomalías]

Santiago: Latencia está alta, ¿por qué?
Omni: Probablemente por el backup de las 2pm. Pasó ayer igual.

Santiago: /root-cause latency_spike
Omni: [Análisis: 95% causado por backup, se resolvió en 3min]
```

### EJEMPLO 3: Cliente Esperando
```
Santiago: "¿Quién está esperando?"
Omni: ⏳ CHATS PENDIENTES
      👤 Maria: "¿A qué hora mañana?"
      👤 Carlos: "Confirmé la cita"
      👤 Ana: "¿Qué precio tienen?"
      ... y 2 más

Santiago: /enter ch_001
Omni: 📱 CONVERSACIÓN CON MARIA GARCIA
      ID: `ch_001`
      
      Histórico (últimos 5 mensajes):
      Maria: "Hola, ¿están?"
      Melissa: "Hola Maria! ✨"
      Maria: "¿A qué hora me atiendes mañana?"
      Melissa: "Te atenderemos a las 3:00 PM"
      Maria: "¿Y qué precio?"
```

### EJEMPLO 4: Investigación Histórica
```
Santiago: /what-happened clinica-bella 24
Omni: [Muestra eventos de las últimas 24h cronológicamente]

Santiago: ¿Por qué estuvo offline a las 2pm?
Omni: Backup automático de database. Tomó 8 minutos.

Santiago: /root-cause offline
Omni: [Análisis: Backup de 2pm, causa conocida, sin acción requerida]
```

---

## 📞 SI NECESITAS AYUDA

### Comando directo
```
/help         ← Ver todos los comandos nuevamente
```

### Pregunta natural
```
"Ayuda, ¿cuáles son los comandos?"
"¿Cómo funciona esto?"
"¿Qué puedo hacer?"
"¿Cómo entro en un chat?"
```

Omni entiende cualquier pregunta en español y te da la respuesta.

---

## 🚀 ACCESOS RÁPIDOS

Copiar & pegar para usar:

```
/status
/alerts
/ack
/help
/conversations
/conversations clinica-bella
/enter ch_001
/analyze clinica-bella
/what-happened clinica-bella 6
/root-cause latency_spike
```

---

## 🎊 RESUMEN

**Tienes 12 comandos + lenguaje natural infinito:**

- 7 comandos sin parámetros (rápidos)
- 5 comandos con parámetros (análisis)
- Lenguaje natural en español (preguntas)

**Usa lo que sea más rápido para ti.**

---

**Omni v2.1 Ultra - El Ojo Superinteligente que Todo lo Ve**

*Para cualquier pregunta, solo pregunta naturalmente en Telegram. Omni entiende español perfectamente.*
