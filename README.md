# 🤖 Melissa — AI Receptionist Runtime

Melissa is a high-performance AI receptionist runtime you run on your own servers. It answers your customers on the channels you already use. It can process context and memory, and orchestrate multiple instances. The Core is just the engine — the product is the receptionist. 

If you want a scalable, multi-instance virtual assistant that feels fast, secure, and always-on, this is it.

Supported channels include: **WhatsApp, Telegram**.

Preferred setup: run `melissa` onboard in your terminal. Works seamlessly with `npm`.

[![NPM Version](https://img.shields.io/npm/v/melissa-ai.svg)](https://www.npmjs.com/package/melissa-ai)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ⚡ Core Philosophy

* **Decoupled Architecture:** The core stays clean. State, sessions, and secrets live only in your deployment instances.
* **Integrated Memory Layer:** Built-in short-term memory and context normalization (`melissa_brain_v10`).
* **Intelligent Routing:** High-concurrency main router powered by FastAPI (`melissa.py`).
* **Sync CLI:** Built-in tool to clone, create, and sync the base code across multiple instances (`melissa sync`).
* **Security Defaults:** Credentials, logs, and databases are strictly excluded from version control. Zero-trust environment out of the box.

## 🚀 Quickstart

### Global Installation via NPM (Recommended)
Melissa is packaged in npm for rapid deployment on servers or local environments.

```bash
# Install globally
npm install -g melissa-ai

# Verify installation and view options
melissa --help
```

*Alternative via script:*
```bash
bash install.sh --user
```

### Local Development Environment
To modify the core or run integration tests:

```bash
# 1. Clone the repository
git clone https://github.com/sxrubyo/melissa.git
cd melissa

# 2. Configure environment variables (Base contract)
cp .env.example .env

# 3. Create and activate an isolated virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Start the FastAPI runtime
python3 melissa.py
```

## ⚙️ Instance Management (CLI)

Melissa CLI maintains a single source of truth for the runtime. This allows you to propagate core updates to active instances without touching sensitive configurations.

```bash
# Sync the updated core to all linked instances
python3 melissa_cli.py sync -y
```

## 🛡️ Security & DevOps

We maintain a Zero-Trust environment in the repository. Treat inbound messages as untrusted input. If you are operating on production servers, follow these rules:

* **Configuration Contract:** Only use `.env.example` to declare new variables. **Never** commit a real `.env` file.
* **Data Isolation:** SQLite databases, API tokens, conversation histories, and local logs must be covered by `.gitignore`.
* **Commit Auditing:** Run `git status` and review the working tree before pushing from any production machine.

## 🏗️ Core Structure

| Module / File | Primary Function |
| :--- | :--- |
| `melissa.py` | Main FastAPI API and runtime orchestrator. |
| `melissa_brain_v10.py` | Memory layer and first-turn normalization. |
| `melissa_domino.py` | Structural control to ensure high-quality responses. |
| `melissa_core/` | Shared conversational logic and context retention. |
| `melissa_agents/` | Specialized agents, skills, and external integrations. |
| `personas/` | Bot personality and tone configuration files. |

## 🧪 Automated Testing

Continuous validation of core regressions and CLI flows. Run tests before opening a Pull Request:

```bash
# Run the complete test suite
pytest -q

# Specific verification of the sync engine
pytest -q tests/test_sync_runtime.py
```

## 🗺️ Open Source Roadmap

- [ ] Decrease monolith coupling in `melissa.py`.
- [ ] Improve the separation boundary between the shared core and instance state.
- [ ] Publish official guide for deploying new *Zero-Touch* instances over sensitive code.

---
*Built to scale. Optimized for production.*
