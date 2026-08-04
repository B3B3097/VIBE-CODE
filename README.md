<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=200&section=header&text=VIBE-CODE&fontSize=80&fontColor=fff&animation=twinkling&fontAlignY=35&desc=Multi-Agent%20AI%20Code%20Platform&descAlignY=60&descSize=20" width="100%"/>

<br/>

[![GitHub Actions](https://img.shields.io/badge/Powered%20by-GitHub%20Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![Ollama](https://img.shields.io/badge/Runtime-Ollama-FF6B35?style=for-the-badge&logo=ollama&logoColor=white)](https://ollama.ai)
[![Qwen 2.5](https://img.shields.io/badge/Planner-Qwen%202.5-7C3AED?style=for-the-badge&logo=openai&logoColor=white)](https://qwenlm.github.io)
[![Bonsai 27B](https://img.shields.io/badge/Coder-Bonsai%2027B-06B6D4?style=for-the-badge&logo=huggingface&logoColor=white)](https://huggingface.co/prism-ml)
[![APIs](https://img.shields.io/badge/Internet%20APIs-40%2B-22C55E?style=for-the-badge&logo=plug&logoColor=white)](#-api-integrations)
[![License](https://img.shields.io/badge/License-MIT-F59E0B?style=for-the-badge)](LICENSE)

<br/>

> **Write a prompt. Watch two AI agents plan, code, review, and ship — automatically.**
>
> VIBE-CODE runs entirely on GitHub's free CI infrastructure using local LLMs via Ollama.  
> No cloud AI bills. No API quotas. Just raw, local intelligence.

<br/>

[🚀 Quick Start](#-quick-start) · [🧠 How It Works](#-how-it-works) · [🔌 API Integrations](#-api-integrations) · [⚙️ Configuration](#%EF%B8%8F-configuration) · [📸 Screenshots](#-screenshots)

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🧠 Multi-Agent Architecture
Two specialized models work in tandem:
- **Qwen 2.5** — Planner/Architect: decomposes tasks, reviews code, writes release notes
- **Prism Bonsai 27B** — Coder/Executor: implements plans, writes production-ready code
- Automatic review loop (up to 2 iterations) with score-based approval

</td>
<td width="50%">

### 🌐 Internet-Connected (40+ APIs)
The AI agents can fetch real-world data before coding:
- 🔍 Search the web, Wikipedia, GitHub
- 🌤 Get weather, news, financial data
- ⚡ Run code sandboxed in 50+ languages
- 🎨 Generate images, text-to-speech, translations
- 📡 Notify via Telegram, Slack, Discord

</td>
</tr>
<tr>
<td width="50%">

### 🔀 Deep Git Integration
- Auto-reads your target repository as context
- Creates a dedicated branch per run
- Commits all generated files
- Opens Pull Requests automatically
- Generates human-readable Release Notes from diffs

</td>
<td width="50%">

### 💬 Nested Chat Hierarchy
- Parent/child workspaces with context inheritance
- Each chat remembers its repo, mode, and history
- Sub-chats inherit parent settings automatically
- Full generation history with agent trace viewer

</td>
</tr>
</table>

---

## 🧠 How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                        VIBE-CODE v2 Flow                        │
└─────────────────────────────────────────────────────────────────┘

  Your Prompt
       │
       ▼
  ┌─────────┐    Fetches real data    ┌────────────────────────┐
  │ToolRouter│ ──────────────────────▶│  40+ Public/Premium    │
  │ (Auto)   │ ◀──────────────────── │  APIs (Web, Weather,   │
  └─────────┘    Enriched context    │  Code, AI, Finance…)   │
       │                             └────────────────────────┘
       │ Context
       ▼
  ┌─────────────────────┐
  │  Qwen 2.5 Planner   │  Analyzes repo + prompt → JSON execution plan
  │  (Architect)  🧠    │  with files, steps, dependencies, risks
  └─────────────────────┘
       │ Plan
       ▼
  ┌─────────────────────┐
  │  Bonsai 27B Coder   │  Implements every step → complete, production
  │  (Executor)   ⚡    │  ready files with error handling & docs
  └─────────────────────┘
       │ Code
       ▼
  ┌─────────────────────┐    Score ≥ 7 → approve
  │  Qwen 2.5 Reviewer  │    Score < 7 → feedback to Coder (max 2x)
  │  (Quality Gate) 🔍  │
  └─────────────────────┘
       │ Approved code
       ▼
  ┌───────────┐    ┌──────────────┐    ┌─────────────────┐
  │  GitHub   │    │  Auto PR     │    │  Release Notes  │
  │  Commit   │───▶│  Creation    │───▶│  from git diff  │
  │  🔗       │    │  (optional)  │    │  📝             │
  └───────────┘    └──────────────┘    └─────────────────┘
```

---

## 🚀 Quick Start

### 1. Fork this repository

```bash
gh repo fork B3B3097/VIBE-CODE --clone
```

### 2. Open the frontend

The `index.html` is a fully self-contained SPA. Open it in your browser:

```bash
open index.html
```

Or serve it:
```bash
python3 -m http.server 8080
# → http://localhost:8080
```

### 3. Add your GitHub token

In the **Settings panel** (right sidebar), paste a GitHub Personal Access Token with:
- ✅ `repo` scope
- ✅ `workflow` scope

### 4. Pre-warm the model cache (recommended)

Run the **"Keep Model Cache Warm"** workflow once manually to download and cache the models:

```
GitHub → Actions → 🔥 Keep Model Cache Warm → Run workflow
```

This downloads Bonsai 27B (~3.6 GB) and Qwen 2.5 into the Actions cache. Subsequent runs use the cache and skip the download.

### 5. Run your first generation

Select a repo, type a prompt, hit **Send** ↵

```
Build a FastAPI REST service with JWT authentication, 
PostgreSQL via SQLAlchemy, and full CRUD for a User model
```

---

## 🤖 Agent Modes

| Mode | Models | Best For |
|------|--------|----------|
| **Single** | Any Ollama model | Fast generation, simple tasks |
| **Multi-Agent** | Qwen 2.5 + Bonsai 27B | Complex features, architecture changes, PR-ready code |

### Multi-Agent State Machine

```
IDLE → FETCHING → PLANNING → CODING → REVIEWING ──┐
                                    ↑              │ score ≥ 7
                                    └── CODING ←──┘ score < 7
                                         │
                               COMMITTING → RELEASING → DONE
```

---

## 🔌 API Integrations

VIBE-CODE includes **40+ API integrations** available to the AI agents via the **ToolRouter**. Before coding, the Planner automatically decides which APIs to call for enriched context.

### 🟢 Free — No Key Required

| API | What it does |
|-----|-------------|
| 🦆 DuckDuckGo | Web search instant answers |
| 📖 Wikipedia | Encyclopedia summaries |
| 🌡 Open-Meteo | 7-day weather forecast |
| ⛅ wttr.in | Current weather |
| ▶ Piston | Run code in 50+ languages |
| 🦎 CoinGecko | Live crypto prices |
| 💱 ExchangeRate | Currency conversion |
| 🌍 Nominatim | Address geocoding (OpenStreetMap) |
| 📚 Free Dictionary | Word definitions |
| ▦ QR Code API | Generate QR codes |
| 🕐 World Time API | Current time in any timezone |
| 👤 Random User | Fake user data for testing |
| 🐙 GitHub API | Public repo info & code search |
| 📦 PyPI / NPM | Package metadata |
| 🤗 HuggingFace | Inference on public models |

### 🔑 Premium — API Key Required

<details>
<summary><strong>Search & AI</strong></summary>

| API | Free Tier | Key |
|-----|-----------|-----|
| 🔍 Serper.dev | 2,500 searches/mo | `SERPER_API_KEY` |
| 🦁 Brave Search | 2,000 queries/mo | `BRAVE_API_KEY` |
| 🤖 OpenAI | Pay-per-use | `OPENAI_API_KEY` |
| 🧠 Anthropic Claude | Pay-per-use | `ANTHROPIC_API_KEY` |
| ⚡ Groq | Free tier (6k RPD) | `GROQ_API_KEY` |
| 🔗 Together AI | $1 free credit | `TOGETHER_API_KEY` |
| 🌀 Cohere | Free tier | `COHERE_API_KEY` |
| 💨 Mistral AI | Free tier | `MISTRAL_API_KEY` |
| 🔄 Replicate | Pay-per-use | `REPLICATE_API_KEY` |

</details>

<details>
<summary><strong>Data & Media</strong></summary>

| API | Free Tier | Key |
|-----|-----------|-----|
| 🌤 OpenWeatherMap | 1M calls/mo | `OPENWEATHER_API_KEY` |
| 📰 NewsAPI | 100 req/day | `NEWS_API_KEY` |
| 📈 Alpha Vantage | 25 req/day | `ALPHAVANTAGE_API_KEY` |
| 🖼 Unsplash | 50 req/hr | `UNSPLASH_API_KEY` |
| 📷 Pexels | 200 req/hr | `PEXELS_API_KEY` |
| 🎨 Stability AI | Pay-per-use | `STABILITY_API_KEY` |
| 🎙 ElevenLabs | 10k chars/mo | `ELEVENLABS_API_KEY` |
| 🧮 Wolfram Alpha | 2k calls/mo | `WOLFRAM_API_KEY` |
| 🌐 DeepL | 500k chars/mo | `DEEPL_API_KEY` |

</details>

<details>
<summary><strong>Communication & Productivity</strong></summary>

| API | Free Tier | Key |
|-----|-----------|-----|
| ✈ Telegram Bot | Free | `TELEGRAM_BOT_TOKEN` |
| 💬 Discord Webhook | Free | `DISCORD_WEBHOOK_URL` |
| 🔔 Slack Webhook | Free | `SLACK_WEBHOOK_URL` |
| 📓 Notion | Free tier | `NOTION_API_KEY` |
| 📊 Airtable | 1k records free | `AIRTABLE_API_KEY` |
| ⚡ Supabase | Free tier | `SUPABASE_API_KEY` |

</details>

### Adding API Keys

**Via the UI** — Click the **🔌 APIs** tab in the right panel, find the service, click 🔑, paste your key. Keys are stored in your browser's `localStorage` and passed to GitHub Actions automatically.

**Via GitHub Secrets** — For permanent storage, add keys as repository secrets with the same names shown above.

---

## ⚙️ Configuration

### Workflow Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `prompt` | — | What to build (required) |
| `agent_mode` | `single` | `single` or `multi` |
| `enable_tools` | `true` | Let agents call APIs |
| `model_planner` | `qwen2.5:7b` | Planner model |
| `model_coder` | `bonsai-27b` | Coder model |
| `target_repo` | — | Repo to read context from / commit to |
| `auto_pr` | `false` | Create PR automatically |
| `auto_notes` | `true` | Generate release notes |
| `max_tokens` | `4096` | Max tokens per model call |

### Model Cache

The **"🔥 Keep Model Cache Warm"** workflow runs automatically every 5 days to prevent the 7-day cache expiry. You can also trigger it manually.

```
Why not store Bonsai 27B in the repo?
  → File size is 3.6 GB.
  → GitHub limit: 100 MB per file (LFS max 2 GB).
  → Solution: Actions cache (persists 7 days per run) + scheduled warmer.
  → First cold run downloads once; all subsequent runs use the cache.
```

---

## 📁 Project Structure

```
VIBE-CODE/
├── 📄 index.html              # Full SPA frontend (zero dependencies)
├── 🐍 generate.py             # Multi-agent backend
│   ├── APIToolkit             #   40+ API integrations
│   ├── ToolRouter             #   Auto-selects APIs per prompt
│   ├── PlannerAgent           #   Qwen 2.5 (decompose + review)
│   ├── CoderAgent             #   Bonsai 27B (implement + refactor)
│   ├── GitIntegration         #   GitHub API wrapper
│   ├── ReleaseNotesGenerator  #   Changelog from git diff
│   └── Orchestrator           #   State machine coordinator
├── 🐍 read_repo.py            # Reads target repo context
├── .github/workflows/
│   ├── ⚡ generate.yml        # Main generation workflow
│   └── 🔥 warm_cache.yml     # Scheduled model cache warmer
└── 📂 results/                # Auto-generated output artifacts
```

---

## 🎨 Frontend

The `index.html` is a **zero-dependency dark glassmorphism SPA**:

- **Left panel** — Nested chat tree with parent/child hierarchy
- **Center** — Chat interface with markdown rendering and code highlighting
- **Agent status bar** — Live status of Planner / Coder / Git agents + token counter
- **Right panel** with 5 tabs:
  - ⚙️ **Settings** — models, repo, automation toggles
  - 🔌 **APIs (Beta)** — 45 integration cards with key management
  - 📝 **Release Notes** — auto-generated changelog
  - 🔍 **Agent Trace** — step-by-step execution log
  - 📚 **History** — all previous generations

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| CI/CD | GitHub Actions (ubuntu-latest) |
| LLM Runtime | [Ollama](https://ollama.ai) |
| Planner LLM | [Qwen 2.5 7B](https://qwenlm.github.io) |
| Coder LLM | [Prism Bonsai 27B](https://huggingface.co/prism-ml) (1-bit GGUF) |
| Code Sandbox | [Piston](https://github.com/engineer-man/piston) |
| Frontend | Vanilla HTML/CSS/JS (no framework) |
| Persistence | GitHub repo + browser `localStorage` |

---

## 🗺 Roadmap

- [ ] WebSocket real-time streaming from workflow logs
- [ ] Voice input via browser speech API
- [ ] Multi-file upload & diff viewer
- [ ] Agent memory across chat sessions
- [ ] Docker self-hosted mode (no GitHub Actions needed)
- [ ] Plugin system for custom API integrations
- [ ] Team workspaces with shared chat history

---

## 🤝 Contributing

```bash
# 1. Fork & clone
gh repo fork B3B3097/VIBE-CODE --clone && cd VIBE-CODE

# 2. Make changes to index.html or generate.py

# 3. Test via GitHub Actions
git add . && git commit -m "feat: your feature" && git push

# 4. Open a PR — VIBE-CODE will review its own PR 🔄
```

---

<div align="center">

**Built with ❤️ using GitHub Actions + Ollama + local LLMs**

*No cloud AI bills. No vendor lock-in. Just vibes.*

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=100&section=footer" width="100%"/>

</div>
