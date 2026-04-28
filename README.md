```markdown
# 
```
███╗   ███╗███████╗██╗     ██╗███████╗███████╗ █████╗ 
████╗ ████║██╔════╝██║     ██║██╔════╝██╔════╝██╔══██╗
██╔████╔██║█████╗  ██║     ██║███████╗███████╗███████║
██║╚██╔╝██║██╔══╝  ██║     ██║╚════██║╚════██║██╔══██║
██║ ╚═╝ ██║███████╗███████╗██║███████║███████║██║  ██║
╚═╝     ╚═╝╚══════╝╚══════╝╚═╝╚══════╝╚══════╝╚═╝  ╚═╝
```

**Deploy production-ready AI receptionists on WhatsApp and Telegram — in minutes, not weeks.**

[![NPM Version](https://img.shields.io/npm/v/melissa-ai.svg?color=9333ea)](https://www.npmjs.com/package/melissa-ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-9333ea.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-9333ea.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Docker-lightgrey)](https://github.com/sxrubyo/melissa)
[![Status](https://img.shields.io/badge/status-production-brightgreen)](https://github.com/sxrubyo/melissa)

---

## What is Melissa?

**Melissa** is a high-performance runtime engine for deploying intelligent AI receptionists that handle real customer conversations on **WhatsApp** and **Telegram**.

It's not a chatbot framework. It's not a low-code platform.  
**Melissa is the production core** — memory, routing, context retention, multi-instance orchestration, and secure state isolation — built for businesses that need AI assistants running 24/7 without breaking.

```
Traditional Chatbot                    Melissa AI
─────────────────                      ───────────
● Stateless                            ● Persistent memory per conversation
● Single bot = single server           ● Multi-instance sync from one core
● Hardcoded flows                      ● Modular agents + skill injection
● No context between sessions          ● Cross-session normalization
● Credentials in repo (security risk)  ● Zero-trust state isolation
```

---

## Why Melissa?

| Problem | Melissa's Solution |
|---------|-------------------|
| **"Every chatbot lives on a different server"** | One core syncs to unlimited production instances |
| **"Conversation memory resets every session"** | `melissa_brain_v10` — persistent short-term memory |
| **"We need different personalities per brand"** | Drop-in `personas/` config files — same engine, different tone |
| **"Our credentials leaked in Git"** | `.env`, sessions, and databases **never** touch version control |
| **"Scaling means copy-pasting code"** | `melissa sync` — propagate updates to all instances safely |

---

## Quick Start

### Install via npm (Recommended)
```bash
npm install -g melissa-ai
melissa --help
```

### Install via Script
```bash
curl -fsSL https://raw.githubusercontent.com/sxrubyo/melissa/main/install.sh | bash
```

### Run Locally (Development)
```bash
git clone https://github.com/sxrubyo/melissa.git
cd melissa
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # configure your API keys
python3 melissa.py
```

Server starts at `http://localhost:8000` with hot reload enabled.

---

## Core Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    melissa.py (FastAPI)                  │
│              High-concurrency message router             │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
   ┌────▼───┐   ┌───▼────┐  ┌────▼─────┐
   │ Brain  │   │ Domino │  │  Agents  │
   │  v10   │   │Control │  │  Skills  │
   │Memory  │   │Quality │  │Functions │
   └────────┘   └────────┘  └──────────┘
        │            │            │
        └────────────┼────────────┘
                     │
            ┌────────▼─────────┐
            │ Instance State   │
            │ • Sessions       │
            │ • Credentials    │
            │ • Local DB       │
            └──────────────────┘
```

| Module | Purpose |
|--------|---------|
| **`melissa.py`** | FastAPI orchestrator — handles webhooks, routing, concurrency |
| **`melissa_brain_v10.py`** | Memory layer — context normalization, conversation history |
| **`melissa_domino.py`** | Quality control — validates responses before delivery |
| **`melissa_core/`** | Shared conversation logic and state retention |
| **`melissa_agents/`** | Pluggable skills — calendar, CRM, payments, custom functions |
| **`personas/`** | Personality configs — tone, language, brand voice |

---

## CLI Commands

```bash
melissa                          # Start the runtime server
melissa sync                     # Sync core updates to all linked instances
melissa sync --list              # Show all registered instances
melissa sync --add <path>        # Register a new production instance
melissa sync --remove <path>     # Unlink an instance
melissa validate                 # Health check — core files, dependencies, config
melissa persona create <name>    # Scaffold a new personality profile
melissa agent list               # Show available agent modules
melissa --version                # Show installed version
```

---

## What Gets Synced (Core) vs. What Stays Local (Instance State)

### ✅ Synced to all instances (the **core runtime**)
```
melissa.py                    # Main engine
melissa_brain_v10.py          # Memory system
melissa_domino.py             # Quality control
melissa_core/                 # Shared logic
melissa_agents/               # Skills and integrations
personas/                     # Personality templates
requirements.txt              # Python dependencies
```

### ❌ Never synced (stays **instance-specific**)
```
.env                          # API keys, tokens, secrets
*.db                          # SQLite conversation history
auth_info_*.txt               # WhatsApp session data
logs/                         # Instance-specific logs
backups/                      # Local database backups
```

This separation means:
- **Updates are safe** — sync the engine without touching production credentials
- **Secrets stay isolated** — each instance has its own `.env` and database
- **One codebase, many deployments** — same core, different customers/brands

---

## Instance Management

### Create a new production instance
```bash
# 1. Clone the core to a new location
git clone https://github.com/sxrubyo/melissa.git /opt/melissa-client-abc

# 2. Link it to your development core for future updates
melissa sync --add /opt/melissa-client-abc

# 3. Configure instance-specific secrets
cd /opt/melissa-client-abc
cp .env.example .env
nano .env  # add API keys, phone numbers, etc.

# 4. Start the instance
python3 melissa.py
```

### Update all instances from core
```bash
cd ~/melissa-dev  # your main development repo
git pull origin main
melissa sync -y   # pushes updates to all linked instances
```

**No credentials or session data is touched.** Only core runtime files are updated.

---

## Security & Production Guidelines

Melissa is built **Zero-Trust** from day one.

### ✅ Do This
- Use `.env.example` as the contract for required variables
- Keep `.env`, `*.db`, and session files in `.gitignore`
- Run `git status` before every commit from a production machine
- Use separate `.env` per instance — never share credentials
- Enable file integrity monitoring on production instances

### ❌ Never Do This
- Commit a real `.env` file
- Store API tokens in code or comments
- Push database files to version control
- Share session files between instances
- Run `git add .` blindly from a production server

---

## Roadmap

- [ ] **Plugin marketplace** — community-contributed agents and skills
- [ ] **Multi-language personas** — auto-switch based on customer locale
- [ ] **Built-in analytics dashboard** — conversation metrics without external tools
- [ ] **Edge deployment mode** — run Melissa on Cloudflare Workers / Vercel Edge
- [ ] **Voice support** — Telegram voice messages → transcription → AI response
- [ ] **Horizontal scaling** — Redis-backed session sharing for multi-server deployments

---

## Community & Support

- **Documentation**: [docs.melissa-ai.com](https://docs.melissa-ai.com) *(coming soon)*
- **Issues**: [GitHub Issues](https://github.com/sxrubyo/melissa/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sxrubyo/melissa/discussions)
- **npm**: [melissa-ai](https://www.npmjs.com/package/melissa-ai)

Built for production. Optimized for scale. Designed for privacy.

---

**Built by [sxrubyo](https://github.com/sxrubyo)** · MIT License · Production-Ready · Open Source
```
