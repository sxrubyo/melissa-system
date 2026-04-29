<div align="center">
  <img src="brand-assets/melissa-logo.png" alt="Melissa AI" width="400"/>

### 💜 **The AI Receptionist Engine Built for Agencies & Resellers**

*Train once. Deploy unlimited. Your clients pay monthly. You keep the margin.*

[![NPM Version](https://img.shields.io/npm/v/melissa-ai.svg?style=for-the-badge&color=9333ea&logo=npm&logoColor=white)](https://www.npmjs.com/package/melissa-ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-9333ea.svg?style=for-the-badge)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-9333ea.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Production Ready](https://img.shields.io/badge/PRODUCTION-READY-9333ea?style=for-the-badge&logo=checkmarx&logoColor=white)](https://github.com/sxrubyo/melissa)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-READY-25D366?style=for-the-badge&logo=whatsapp&logoColor=white)](https://github.com/sxrubyo/melissa)
[![Telegram](https://img.shields.io/badge/Telegram-READY-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://github.com/sxrubyo/melissa)

</div>

---

## 💰 Turn AI Assistants Into Recurring Revenue

**Melissa** isn't just another chatbot framework.
It's a **white-label AI receptionist platform** that lets you sell branded conversational AI to restaurants, clinics, salons, real estate agencies, e-commerce stores — **any business with a phone number.**

<div align="center">

| Your Client's Pain | What They Pay You For |
|:---|:---|
| 📞 Missed calls = lost revenue | 🤖 24/7 AI receptionist that never sleeps |
| 💬 Slow WhatsApp & Telegram response | ⚡ Instant replies with context memory |
| 📝 Answering the same questions manually | 🧠 AI trained on their FAQ, services, prices |
| 🔄 Hiring, training, managing staff | 🚀 Deploy once, forget about it |

</div>

---

## 🚀 Your Business Model (The Melissa Way)

```
┌─────────────────────────────────────────────────────────────┐
│  1. Install Melissa (5 minutes)                             │
│     npm install -g melissa-ai                               │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  2. Train ONE agent with a prompt (15 minutes)              │
│     "You are Maria, receptionist for a dental clinic.       │
│      Book appointments, answer FAQ, send price list."       │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Clone to unlimited client instances (1 command)         │
│     melissa sync --add /opt/melissa-client-restaurant       │
│     melissa sync --add /opt/melissa-client-salon            │
│     melissa sync --add /opt/melissa-client-realestate       │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Each client gets their own isolated instance            │
│     ✅ WhatsApp Business API integration                    │
│     ✅ Telegram bot (optional)                              │
│     ✅ Custom personality via personas/                     │
│     ✅ Isolated database & credentials                      │
│     ✅ Their own .env — you never touch it again            │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  5. Charge $97–$497/month per client                        │
│     They manage their WhatsApp number                       │
│     They update their FAQ via simple .txt files             │
│     You maintain the core and sync updates in 1 command     │
└─────────────────────────────────────────────────────────────┘
```

<div align="center">

| Clients | Monthly Fee | Your MRR |
|:---:|:---:|:---:|
| 10 clients | $197/mo | **$1,970/mo** |
| 50 clients | $197/mo | **$9,850/mo** |
| 100 clients | $197/mo | **$19,700/mo** |

**Your cost:** $5–15/mo per client (OpenAI API + server)
**Your margin:** 85–95% 🚀

</div>

---

## 🎯 Why Melissa Destroys the Competition

<table>
<tr>
<th width="20%">Solution</th>
<th width="40%">Their Reality</th>
<th width="40%">Melissa Reality</th>
</tr>
<tr>
<td><strong>Voiceflow / Botpress</strong></td>
<td>❌ $99–$625/mo per bot<br>❌ Vendor lock-in<br>❌ You pay per conversation</td>
<td>✅ Open source, MIT license<br>✅ Unlimited instances<br>✅ You control pricing</td>
</tr>
<tr>
<td><strong>n8n / Make / Zapier</strong></td>
<td>❌ Complex workflow builders<br>❌ No memory between sessions<br>❌ Breaks with API changes</td>
<td>✅ Zero external dependencies<br>✅ Built-in memory engine<br>✅ 1 command to update all clients</td>
</tr>
<tr>
<td><strong>Hiring a Dev Team</strong></td>
<td>❌ $5,000–$20,000 upfront<br>❌ 3–6 months development<br>❌ Single-client solution</td>
<td>✅ Install in 5 minutes<br>✅ Deploy client in 10 minutes<br>✅ One core, infinite clients</td>
</tr>
<tr>
<td><strong>Custom Python Script</strong></td>
<td>❌ No state management<br>❌ Security nightmare<br>❌ Dies when you restart</td>
<td>✅ Production-grade FastAPI<br>✅ Zero-trust architecture<br>✅ Systemd + Docker ready</td>
</tr>
</table>

---

## ⚡ Start Selling in 3 Steps

### Step 1 — Install Melissa

```bash
npm install -g melissa-ai
melissa --version
```

### Step 2 — Create Your First Agent

```bash
melissa persona create restaurant-receptionist
```

Edit `personas/restaurant-receptionist.txt`:

```
You are Sofia, the AI receptionist for "La Cucina Bella" Italian restaurant.

Your job:
- Answer questions about menu, hours, location
- Take reservations (collect: name, phone, date, time, party size)
- Send the menu PDF when asked
- Be warm, friendly, professional

Hours: Mon–Sun 11am–10pm
Location: 123 Main St, Miami, FL

When someone wants to book:
"Perfect! I'll need your name, phone number, preferred date & time, and party size."

Never confirm reservations — say "I'll pass this to our manager to confirm."
```

### Step 3 — Deploy to Client

```bash
melissa sync --add /opt/melissa-restaurant-bella
cd /opt/melissa-restaurant-bella
cp .env.example .env
nano .env
python3 melissa.py
```

**Done.** Their WhatsApp now has a 24/7 AI receptionist. You never touch their credentials again.

---

## 🏗️ Architecture

```
                  ┌──────────────────────────┐
                  │    Your Development Core  │
                  │      ~/melissa-dev/       │
                  └────────────┬─────────────┘
                               │  melissa sync
                  ┌────────────┼────────────┐
                  │            │            │
         ┌────────▼───┐ ┌──────▼─────┐ ┌───▼────────┐
         │  Client A  │ │  Client B  │ │  Client C  │
         │ Restaurant │ │   Salon    │ │ Real Estate│
         ├────────────┤ ├────────────┤ ├────────────┤
         │ .env       │ │ .env       │ │ .env       │
         │ persona    │ │ persona    │ │ persona    │
         │ database   │ │ database   │ │ database   │
         │ WhatsApp   │ │ Telegram   │ │ WhatsApp   │
         └────────────┘ └────────────┘ └────────────┘
```

| Module | Purpose |
|:---|:---|
| **`melissa.py`** | FastAPI orchestrator — webhooks, routing, concurrency |
| **`melissa_brain_v10.py`** | Memory layer — context normalization, conversation history |
| **`melissa_domino.py`** | Quality control — validates responses before delivery |
| **`melissa_core/`** | Shared conversation logic and state retention |
| **`melissa_agents/`** | Pluggable skills — calendar, CRM, payments, custom functions |
| **`personas/`** | Personality configs — tone, language, brand voice per client |

---

## 🔄 Core vs. Instance State

<table>
<tr>
<td width="50%">

### ✅ Synced to all instances

```
melissa.py               # Main engine
melissa_brain_v10.py     # Memory system
melissa_domino.py        # Quality control
melissa_core/            # Shared logic
melissa_agents/          # Skills & integrations
personas/                # Personality templates
requirements.txt         # Dependencies
```

</td>
<td width="50%">

### ❌ Never synced (instance-specific)

```
.env                     # API keys, secrets
*.db                     # Conversation history
auth_info_*.txt          # WhatsApp sessions
logs/                    # Instance logs
backups/                 # Local backups
```

</td>
</tr>
</table>

**Updates are safe.** Sync the engine without ever touching client credentials or data.

---

## 🎮 CLI Reference

```bash
npm install -g melissa-ai          # Install globally
melissa --version                  # Check version

melissa sync --list                # List all client instances
melissa sync --add /opt/client     # Register new client
melissa sync --remove /opt/client  # Remove client
melissa sync -y                    # Push updates to all clients

melissa persona create <name>      # New personality template
melissa agent list                 # Show available agents
melissa validate                   # Health check — config, deps, files
```

---

## 🛡️ Security by Design

| Risk | Other Platforms | Melissa |
|:---|:---|:---|
| API keys in version control | ❌ Common mistake | ✅ `.env` never synced |
| Shared database across clients | ❌ GDPR violation | ✅ Isolated SQLite per instance |
| Session hijacking | ❌ No isolation | ✅ Separate auth per client |
| Cross-client data contamination | ❌ Possible | ✅ Impossible by design |

---

## 📊 Industry Use Cases

| Industry | What the AI Handles | Suggested Price |
|:---|:---|:---:|
| 🍕 **Restaurants** | Reservations, menu, hours, delivery | $147–$297/mo |
| 💇 **Salons & Spas** | Bookings, services, prices, upsells | $197–$397/mo |
| 🏠 **Real Estate** | Lead qualification, listings, viewings | $297–$597/mo |
| 🦷 **Medical / Dental** | Consultations, forms, reminders | $347–$697/mo |
| 🛒 **E-commerce** | Product questions, order tracking, returns | $197–$497/mo |
| 🏋️ **Gyms & Studios** | Class bookings, schedules, memberships | $197–$397/mo |

---

## 🔥 Production Deployment

### VPS (DigitalOcean, Linode, Vultr — $6/mo)

```bash
npm install -g melissa-ai
melissa sync --add /opt/client-001
cd /opt/client-001
cp .env.example .env && nano .env
```

**Systemd service (auto-restart on crash):**

```ini
[Unit]
Description=Melissa AI — Client 001
After=network.target

[Service]
WorkingDirectory=/opt/client-001
ExecStart=/usr/bin/python3 /opt/client-001/melissa.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable melissa-client-001
sudo systemctl start melissa-client-001
```

### Docker

```bash
docker run -d \
  --name melissa-client-001 \
  -p 8000:8000 \
  -v /opt/client-001:/app \
  --env-file /opt/client-001/.env \
  melissa-ai:latest
```

---

## 🗺️ Roadmap

- [ ] Web dashboard for clients (no-code persona editor)
- [ ] Multi-language personas (auto-switch by locale)
- [ ] Built-in analytics — conversation metrics per instance
- [ ] Voice support — Telegram voice → transcription → AI response
- [ ] Redis-backed session sharing for horizontal scaling
- [ ] Plugin marketplace — community agents and skills
- [ ] Edge deployment — Cloudflare Workers / Vercel Edge

---

## 🎓 What You DON'T Need

❌ n8n workflows &nbsp;&nbsp; ❌ Zapier subscriptions &nbsp;&nbsp; ❌ Voiceflow licenses  
❌ AWS Lambda complexity &nbsp;&nbsp; ❌ Kubernetes &nbsp;&nbsp; ❌ Redis (unless 500+ clients)  
❌ PostgreSQL &nbsp;&nbsp; ❌ Docker Swarm &nbsp;&nbsp; ❌ A dev team

**Melissa runs on a $6/mo VPS. One server. Dozens of clients.**

---

<div align="center">

## 💜 Ready to Build?

[![Install Now](https://img.shields.io/badge/📦_Install_Now-npm_install_-g_melissa--ai-9333ea?style=for-the-badge&logo=npm&logoColor=white)](https://www.npmjs.com/package/melissa-ai)
[![GitHub Issues](https://img.shields.io/badge/🐛_Issues-Report_Here-9333ea?style=for-the-badge&logo=github)](https://github.com/sxrubyo/melissa/issues)
[![Discussions](https://img.shields.io/badge/💬_Community-GitHub_Discussions-9333ea?style=for-the-badge&logo=github)](https://github.com/sxrubyo/melissa/discussions)

---

**Built for agencies. Designed for profit. Engineered for scale.**

No vendor lock-in · No recurring SaaS fees · You own the code · You set the price

**Created by [sxrubyo](https://github.com/sxrubyo)** · MIT License · Open Source

</div>
