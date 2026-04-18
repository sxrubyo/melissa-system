# Melissa Phase 1 Core And Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extraer el carril de primer turno e identidad de Melissa a un núcleo conversacional reutilizable, versionar la personalidad base en disco y montar un harness de conversación larga para detectar repetición, rigidez y pérdida de contexto.

**Architecture:** Melissa seguirá entrando por `MelissaUltra.process_message`, pero los casos de `greeting`, `identity probe` y `first contextual turn` se resolverán en un nuevo `conversation_engine`. La personalidad base se cargará desde un `persona_registry`, y un runner de conversaciones largas hablará con Melissa por el endpoint real para medir fallos y permitir iterar sin tocar producción a ciegas.

**Tech Stack:** Python 3.12, FastAPI existente, Gemini 2.5 Flash ya configurado, YAML para personas, scripts de prueba locales.

---

### Task 1: Crear estructura mínima del core conversacional

**Files:**
- Create: `/home/ubuntu/melissa/melissa_core/__init__.py`
- Create: `/home/ubuntu/melissa/melissa_core/persona_registry.py`
- Create: `/home/ubuntu/melissa/melissa_core/conversation_engine.py`

- [ ] **Step 1: Crear package y contratos mínimos**

```python
# /home/ubuntu/melissa/melissa_core/__init__.py
from .conversation_engine import ConversationEngine, ConversationTurnResult
from .persona_registry import PersonaRegistry, PersonaProfile
```

- [ ] **Step 2: Crear `PersonaProfile` y carga básica YAML**

```python
@dataclass
class PersonaProfile:
    key: str
    identity: str
    opening_style: str
    capabilities: list[str]
    first_turn_variants: list[str]
    identity_probe_variants: list[str]
    contextual_followups: dict[str, str]
```

- [ ] **Step 3: Crear `ConversationTurnResult`**

```python
@dataclass
class ConversationTurnResult:
    handled: bool
    bubbles: list[str]
    reason: str = ""
```

- [ ] **Step 4: Implementar motor mínimo para**

```python
def handle_first_turn(...):
    ...

def handle_identity_probe(...):
    ...

def handle_first_contextual_turn(...):
    ...
```

- [ ] **Step 5: Validar importación**

Run: `python3 -m py_compile /home/ubuntu/melissa/melissa_core/__init__.py /home/ubuntu/melissa/melissa_core/persona_registry.py /home/ubuntu/melissa/melissa_core/conversation_engine.py`

Expected: sin errores

### Task 2: Versionar la personalidad base en disco

**Files:**
- Create: `/home/ubuntu/melissa/personas/melissa/base/default.yaml`
- Create: `/home/ubuntu/melissa/personas/melissa/base/estetica_whatsapp.yaml`

- [ ] **Step 1: Crear persona base default**

```yaml
key: default
identity: Melissa
opening_style: natural
capabilities:
  - responder dudas
  - orientar
  - mover la conversación
first_turn_variants:
  - "Hola, soy Melissa, del equipo de {clinic_name}."
identity_probe_variants:
  - "Soy Melissa, una recepcionista virtual que trabaja por este negocio 24 horas al día."
```

- [ ] **Step 2: Crear persona estética WhatsApp**

```yaml
key: estetica_whatsapp
identity: Melissa
opening_style: colombia-natural
capabilities:
  - información de tratamientos
  - valoración
  - disponibilidad
contextual_followups:
  botox: "Botox lo manejan acá. Si quieres, te cuento cómo lo trabajan y qué suelen revisar para que se vea natural."
```

- [ ] **Step 3: Validar parseo**

Run: `python3 - <<'PY'\nfrom melissa_core.persona_registry import PersonaRegistry\nregistry = PersonaRegistry('/home/ubuntu/melissa/personas/melissa/base')\nprint(sorted(registry.list_keys()))\nPY`

Expected: `['default', 'estetica_whatsapp']`

### Task 3: Cablear el engine al runtime actual

**Files:**
- Modify: `/home/ubuntu/melissa/melissa.py`
- Modify: `/home/ubuntu/melissa/melissa-instances/clinica-de-las-americas/melissa.py`

- [ ] **Step 1: Importar `ConversationEngine` y `PersonaRegistry`**

```python
from melissa_core import ConversationEngine, PersonaRegistry
```

- [ ] **Step 2: Inicializar registry y engine una sola vez**

```python
persona_registry = PersonaRegistry('/home/ubuntu/melissa/personas/melissa/base')
conversation_engine = ConversationEngine(persona_registry)
```

- [ ] **Step 3: En `process_message`, antes de la generación clásica, enrutar**

```python
turn = conversation_engine.handle(
    clinic=clinic,
    user_msg=text,
    history=history,
    is_admin=is_admin,
)
if turn.handled:
    ...
    return bubbles
```

- [ ] **Step 4: Mantener compatibilidad**

```python
if not turn.handled:
    # seguir al flujo clásico
```

- [ ] **Step 5: Sincronizar instancia clínica**

Run: `cp /home/ubuntu/melissa/melissa.py /home/ubuntu/melissa-instances/clinica-de-las-americas/melissa.py`

Expected: archivo copiado

### Task 4: Crear harness de conversación larga

**Files:**
- Create: `/home/ubuntu/melissa/scripts/long_conversation_harness.py`
- Create: `/home/ubuntu/melissa/scripts/persona_scenarios.yaml`

- [ ] **Step 1: Definir escenarios largos**

```yaml
scenarios:
  - key: curiosa_ia_negocio
    turns:
      - "Hola qué tal"
      - "Qué eres?"
      - "Tengo un negocio"
      - "Pero explícame bien qué haces"
```

- [ ] **Step 2: Implementar runner HTTP contra `/test`**

```python
for turn in scenario["turns"]:
    resp = requests.post(...)
    history.append(...)
```

- [ ] **Step 3: Medir fallos**

```python
checks = {
    "repetition": ...,
    "identity_consistency": ...,
    "context_follow": ...,
    "bot_phrases": ...,
}
```

- [ ] **Step 4: Guardar transcript y score**

```python
json.dump(report, ...)
```

- [ ] **Step 5: Ejecutar mínimo 1 conversación larga**

Run: `python3 /home/ubuntu/melissa/scripts/long_conversation_harness.py --scenario curiosa_ia_negocio --turns 40`

Expected: reporte JSON y transcript guardados

### Task 5: Probar y ajustar en loop

**Files:**
- Modify: `/home/ubuntu/melissa/melissa_core/conversation_engine.py`
- Modify: `/home/ubuntu/melissa/personas/melissa/base/default.yaml`
- Modify: `/home/ubuntu/melissa/personas/melissa/base/estetica_whatsapp.yaml`

- [ ] **Step 1: Correr harness y leer transcript**

Run: `python3 /home/ubuntu/melissa/scripts/long_conversation_harness.py --scenario curiosa_ia_negocio --turns 40`

Expected: identificar repetición y fallos de continuidad

- [ ] **Step 2: Ajustar solo el core o la persona**

```python
# No meter reglas nuevas en melissa.py si el fallo es de opening/identity.
```

- [ ] **Step 3: Repetir hasta que pase**

Run: `python3 /home/ubuntu/melissa/scripts/long_conversation_harness.py --scenario curiosa_ia_negocio --turns 40`

Expected: menor repetición, identidad estable, continuidad mejorada

- [ ] **Step 4: Verificación runtime**

Run: `python3 -m py_compile /home/ubuntu/melissa/melissa.py /home/ubuntu/melissa/melissa_core/conversation_engine.py /home/ubuntu/melissa/melissa_core/persona_registry.py /home/ubuntu/melissa/scripts/long_conversation_harness.py`

Expected: sin errores

- [ ] **Step 5: Reinicio controlado y prueba real**

Run: `pm2 restart melissa-clinica-de-las-americas`

Expected: `online`
