# Melissa WhatsApp Architecture Redesign

Date: 2026-04-02
Owner: Santiago
Scope: Melissa production architecture for WhatsApp-first conversational sales and support

## Why This Exists

Melissa is no longer competing against simple n8n bots or prompt wrappers.
Meta is moving deeper into WhatsApp-native business AI, marketing orchestration, and AI-assisted customer support. At the same time, Gemini 2.5 gives us a strong low-latency reasoning and tool-use base for real-time conversational work.

The problem is not just model quality.
The current Melissa runtime mixes too many concerns in one place, so good model output gets flattened into repetitive, rigid, scripted behavior.

## External Reality

### Meta / WhatsApp Direction

Official Meta signals matter:

- In June 2024, Meta stated it was investing in AI tools to help businesses on WhatsApp answer common questions, help customers discover products, and support purchase flows.
- In July 2025, Meta announced expanded AI support for businesses on WhatsApp, centralized marketing flows in Ads Manager, and future voice/calling support tied to the WhatsApp Business Platform.

Implication:

Melissa cannot win by being "another chat bot".
Melissa has to win by being:

- more business-specific
- more controllable
- more human in first contact
- stronger in multi-turn persuasion
- better integrated into the business memory and sales process

### Gemini 2.5 Direction

Official Google Gemini API signals matter:

- Gemini 2.5 Flash became stable in June 2025.
- Gemini API supports multi-tool use, code execution and search grounding in the same request.
- Gemini 2.5 is positioned as fast, cost-efficient, reasoning-capable, and suitable for high-throughput interactions.

Implication:

Gemini 2.5 Flash should be Melissa's real-time production default for:

- first contact
- short multi-turn handling
- objection handling
- memory-assisted replies

And heavier reasoning should be reserved for:

- synthesis
- policy conflict resolution
- long admin planning
- background scoring or repair loops

## Current State

Melissa is powerful, but structurally overloaded.

The main technical issue is that one runtime handles too many responsibilities inside a single file and a single conversational pass.

Critical concentration points today:

- `melissa.py` `ResponseGenerator`
- `melissa.py` `MelissaUltra.process_message`
- `melissa.py` demo path
- `melissa.py` `ConversationSimulator`
- `melissa.py` `TrainerGateway`
- `melissa.py` `OwnerStyleController`
- `melissa.py` `PromptEvolver`

### Concrete Architectural Problems

1. Multiple layers rewrite the same message.

Current flow is roughly:

input -> analysis -> reasoning -> generation -> first-turn normalization -> anti-robot filter -> owner enforcement -> bubble splitting -> optional second enforcement

This means the model can be right and still sound wrong by the time the user sees the output.

2. Demo and production are not truly one brain.

Melissa has one logic for normal users and another for demo mode. That creates two personalities and two different failure surfaces.

3. "Training" is mostly prompt and rule accumulation.

Today Melissa learns:

- prompt injections
- hard rules
- templates
- trust rules

But she does not yet have a real versioned personality system or a serious evaluation-driven learning loop.

4. First-contact behavior is over-designed and under-generalized.

The system tries to standardize first contact through multiple hard-coded branches. That creates consistency, but it also causes repetitive openings and brittle handling of curiosity messages.

5. Memory is under-structured for persuasion.

Melissa remembers some facts and preferences, but not yet a strong structured view of:

- user type
- trust level
- objection history
- conversion stage
- speaking style
- prior sentiment pattern

6. Admin control is too close to generation.

Admin controls are useful, but they currently function too much like conversation templates rather than policy constraints.

## Product Goal

Melissa must behave like a real business operator, not like a generic AI.

That means:

- she sounds natural on WhatsApp
- she adapts to the business
- she adapts to the user
- she remembers relevant things
- she stays under owner control
- she can be evaluated and improved at scale

## Priority Order

For the next 7 days:

1. First impression
2. Conversation continuity
3. Conversion and closing

Reason:
If first contact fails, nothing else matters.

## Recommended Architecture

### 1. Conversation Core

New module:

- `melissa_core/conversation_engine.py`

Responsibility:

- take one user turn plus context
- decide response intent
- decide response shape
- produce one canonical response object

This module owns:

- first contact
- identity probes
- curiosity handling
- off-topic recovery
- contextual follow-up logic
- transition between discovery, persuasion and booking

It must not own:

- WhatsApp transport
- admin policy enforcement
- prompt evolution persistence
- metrics storage

### 2. Policy Engine

New module:

- `melissa_core/policy_engine.py`

Responsibility:

- enforce owner rules
- enforce channel rules
- enforce formatting boundaries
- enforce forbidden phrases and phrasing constraints

The key design rule:

Policy engine can constrain a response.
It cannot invent the response logic.

That is the difference between policy and conversation.

### 3. Persona Registry

New modules and paths:

- `melissa_core/persona_registry.py`
- `personas/melissa/base/*.yaml`
- `personas/melissa/overlays/*.yaml`
- `personas/clients/*.yaml`

Each Melissa persona must include:

- `identity`
- `tone`
- `opening_strategy`
- `question_style`
- `sales_style`
- `objection_style`
- `followup_style`
- `humor_policy`
- `warmth_range`
- `forbidden_patterns`
- `channel_overrides`

Each client persona must include:

- `curiosity_about_ai`
- `trust_level`
- `purchase_intent`
- `patience`
- `objection_profile`
- `message_density`
- `tone`
- `channel_behavior`

We do not want 100 hand-written prompts.
We want a composable registry and a matrix generator.

### 4. Memory Runtime

New module:

- `melissa_core/memory_runtime.py`

Structured memory should hold:

- confirmed facts
- preferences
- relationship state
- conversion stage
- last unresolved question
- objections already answered
- style profile of the user

Memory must be summarized, typed and queryable.
It should not rely on raw transcript replay.

### 5. Tool Router

New module:

- `melissa_core/tool_router.py`

Responsibility:

- calendar lookup
- pricing lookup
- business knowledge retrieval
- brand vault retrieval
- CRM or logging hooks
- fallback escalation

The goal is to keep tool decisions outside the main conversation-writing logic.

### 6. Simulation Lab

New paths:

- `melissa_lab/scenarios/*.yaml`
- `melissa_lab/personality_matrix.py`
- `melissa_lab/scoring.py`
- `melissa_lab/runner.py`

`ConversationSimulator` should become a runner that executes:

- business persona x client persona x channel x objective

We need batch evaluation across:

- first impression
- conversion progress
- admin obedience
- repetition
- context following
- human feel

### 7. Scoring

The lab should score at least:

- `first_turn_hook_score`
- `humanness_score`
- `context_follow_score`
- `non_repetition_score`
- `conversion_progress_score`
- `admin_obedience_score`
- `channel_naturalness_score`

Only scores that improve should be reinjected into the runtime.

## Runtime Flow

Target flow:

input
-> channel normalization
-> memory snapshot
-> persona selection
-> conversation engine
-> tool router if needed
-> policy engine
-> bubble renderer
-> transport adapter
-> logging + scoring hooks

This replaces the current pattern of:

input
-> many competing branches
-> model
-> multiple rewrite layers
-> filters
-> templates
-> bubbles

## Production Model Strategy

Primary production default:

- Gemini 2.5 Flash

Use cases:

- real-time WhatsApp replies
- objection handling
- first contact
- short multi-turn interaction

Secondary heavy reasoning path:

- Gemini 2.5 Pro or equivalent reasoning tier

Use only for:

- background summarization
- admin planning
- difficult ambiguity resolution
- policy conflict resolution
- improvement and scoring loops

Design rule:

Do not spend heavy model tokens on every user turn.
Spend them where architecture benefits most.

## WhatsApp-Specific Behavior

Melissa must behave like a WhatsApp-native operator.

That means:

- faster conversational turns
- stronger first-message hook
- natural multi-bubble style when useful
- handling stacked short messages
- message aggregation before reply
- strong continuity over multiple short user bubbles
- more human pacing
- optional read/typing presence orchestration at transport layer

WhatsApp behavior must be part of `channel_overrides`, not hard-coded inside the entire conversation stack.

## Migration Strategy

### Phase 1

Create and wire:

- `conversation_engine.py`
- `persona_registry.py`
- `policy_engine.py`

Keep Melissa production working by routing only:

- first contact
- identity probe
- first contextual follow-up

through the new core first.

### Phase 2

Move:

- current first-turn logic
- demo identity logic
- curiosity logic

out of `melissa.py` and into the new core.

### Phase 3

Convert `ConversationSimulator` into lab runner with YAML scenarios.

### Phase 4

Connect scores back into persona versions and controlled overlays.

## Immediate Deliverables

The first implementation cycle should deliver:

1. one single first-contact lane
2. one single identity/curiosity lane
3. persona registry on disk
4. simulation matrix scaffold
5. scoring scaffold for first-turn quality

## Risks

1. Over-refactor risk

If too much moves at once, production can break.
Mitigation: route only first-turn and identity cases through the new core first.

2. Personality explosion

100 personalities can become chaos if unversioned.
Mitigation: persona registry with overlays, tags and scoring.

3. Admin overcontrol

If admin rules keep generating text instead of constraining it, Melissa will keep sounding rigid.
Mitigation: enforce policy-only control semantics.

## Recommendation

Do not keep growing `melissa.py` as the primary innovation surface.

Treat the current file as the compatibility shell.
Put the next six months of advantage into:

- cleaner conversation core
- persona bank
- structured memory
- simulation/scoring lab

That is the path to make Melissa feel less like "code" and more like a real operator.

## Source Notes

Primary source references used for this design:

- Meta newsroom, June 2024: AI tools for businesses on WhatsApp
- Meta newsroom, July 2025: centralized campaigns, expanded AI support and future voice/calling support on WhatsApp Business Platform
- Google Gemini API changelog: Gemini 2.5 Flash stable release and Gemini API tool support
