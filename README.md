# 🚀 AI News Agent

**An autonomous AI intelligence agent that monitors 50+ sources, curates the most relevant AI/tech updates, and delivers a professional PDF digest to your email — every single day, hands-free.**

---

## 🧠 What Does This Agent Do?

The AI News Agent is a fully autonomous system that runs 24/7 on your machine and performs three core jobs:

### 1. 📡 Ingestion — Collects AI News from the Best Sources
The agent monitors **4 types of sources** every 12 minutes:

| Source Type | What It Covers | Examples |
|-------------|---------------|----------|
| **RSS Feeds** | 20+ top tech publications | TechCrunch, VentureBeat, The Verge, Ars Technica, MIT Tech Review, Wired, CNET, Engadget |
| **Blog Scraping** | 25+ company blogs | Anthropic, Google AI, Meta AI, Microsoft AI, Nvidia, Mistral, LangChain, DeepMind |
| **GitHub Releases** | 30+ AI repositories | OpenAI, Hugging Face Transformers, LangChain, vLLM, Ollama, DeepSeek, NVIDIA TensorRT |
| **NewsAPI** | 50,000+ news sources worldwide | Covers AI models, startups, chips, healthcare AI, finance AI, regulation, robotics |

### 2. 🔍 Processing — Filters, Deduplicates, and Ranks
- **Keyword-based relevance filtering** — only AI/ML/tech content passes through
- **Smart deduplication** — normalized title+company matching prevents repeats
- **Impact scoring** — each update is classified as HIGH, MEDIUM, or LOW impact
- **Noise filtering** — removes opinions, job postings, editorials, and irrelevant content

### 3. 📧 Delivery — Professional Email with PDF Report
Every day at **6:00 AM IST**, the agent sends you:
- **Rich HTML email** — beautifully formatted with categorized sections, impact badges, and source links
- **PDF attachment** — a professional multi-page report with cover page, table of contents, and categorized updates for offline reading

---

## 📊 Categories

Updates are automatically organized into these industry categories:

| Category | Coverage |
|----------|----------|
| 💰 **Finance & Business** | AI trading, fintech, startups, funding, acquisitions, enterprise AI |
| 🏥 **Medical & Healthcare** | AI drug discovery, diagnostics, clinical AI, biotech |
| 💻 **Coding & Development** | AI coding tools, SDKs, frameworks, GitHub releases |
| 🤖 **AI Tech & Models** | GPT, Claude, Gemini, LLaMA, benchmarks, training, inference |
| ⚡ **Hardware & Chips** | Nvidia GPUs, TPUs, AI accelerators, data centers |
| 🔧 **Industrial & Manufacturing** | Robotics, automation, IoT, supply chain AI |
| 🚗 **Autonomous & Vehicles** | Self-driving, drones, autonomous delivery |
| 🔬 **Research & Science** | ArXiv papers, academic breakthroughs, quantum AI |
| 📱 **General Tech** | Cloud platforms, SaaS, digital transformation |

**Tech Launches** from major companies (OpenAI, Google, Anthropic, Nvidia, etc.) are automatically **prioritized at the top** of every report.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    AI NEWS AGENT                         │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ RSS Ingestor│  │Blog Scraper │  │GitHub Monitor│     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │              │
│  ┌──────┴──────┐         │         ┌──────┴──────┐     │
│  │NewsAPI      │         │         │Ingestion    │     │
│  │Ingestor     │─────────┴─────────│Manager      │     │
│  └──────┬──────┘                   └──────┬──────┘     │
│         │                                 │              │
│         └──────────────┬──────────────────┘              │
│                        ▼                                 │
│              ┌─────────────────┐                         │
│              │  SQLite Database │                         │
│              │  (ai_updates.db) │                         │
│              └────────┬────────┘                         │
│                       ▼                                  │
│            ┌──────────────────┐                          │
│            │Processing Pipeline│                         │
│            │ • Impact scoring  │                         │
│            │ • Deduplication   │                         │
│            │ • Noise filtering │                         │
│            └────────┬─────────┘                          │
│                     ▼                                    │
│         ┌─────────────────────┐                          │
│         │  PDF Report Generator│                         │
│         │  • Cover page        │                         │
│         │  • Table of contents │                         │
│         │  • Categorized pages │                         │
│         └────────┬────────────┘                          │
│                  ▼                                       │
│         ┌─────────────────┐                              │
│         │  Email Notifier  │                             │
│         │  • HTML body     │                             │
│         │  • PDF attachment│                             │
│         └─────────────────┘                              │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │             APScheduler (Async)                   │   │
│  │  • Ingestion: every 12 min                        │   │
│  │  • Digest: daily at 06:00 IST                     │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
ainews_agent/
├── main.py                  # Entry point — starts the scheduler
├── scheduler.py             # APScheduler: ingestion + daily email digest
├── send_pdf_digest.py       # Manual trigger: generate and email PDF now
├── api.py                   # Optional FastAPI REST API
├── requirements.txt         # Python dependencies
├── .env                     # Configuration (email, API keys)
│
├── config/
│   └── settings.py          # Loads .env and exposes settings
│
├── ingestion/
│   ├── manager.py           # Orchestrates all 4 ingestors
│   ├── rss_ingestor.py      # Fetches 20+ RSS feeds
│   ├── blog_ingestor.py     # Scrapes 25+ company blogs
│   ├── github_ingestor.py   # Monitors 30+ GitHub repos for releases
│   └── newsapi_ingestor.py  # Queries NewsAPI.org (50K+ sources)
│
├── processing/
│   └── pipeline.py          # Impact scoring, dedup, noise filtering
│
├── database/
│   └── db.py                # SQLite storage + dedup logic
│
├── reporting/
│   └── pdf_generator.py     # Professional PDF report with Unicode support
│
├── notifier/
│   └── email_notifier.py    # SMTP email with HTML body + PDF attachment
│
├── utils/
│   └── helpers.py           # Utility functions
│
├── data/
│   └── ai_updates.db        # SQLite database (auto-created)
│
└── reports/
    └── AI_Digest_YYYYMMDD.pdf  # Generated PDF reports
```

---

## ⚡ Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-username/ainews_agent.git
cd ainews_agent

# 2. Create virtual environment
python -m venv agent_env
agent_env\Scripts\activate       # Windows
# source agent_env/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your .env file (see SETUP.md for details)
#    At minimum, set: EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT

# 5. Run the agent
python main.py
```

> 📖 **For detailed setup instructions, see [SETUP.md](SETUP.md)**

---

## 🔧 Configuration

All configuration is done via the `.env` file:

| Variable | Description | Required |
|----------|-------------|----------|
| `EMAIL_SENDER` | Your Gmail address | ✅ Yes |
| `EMAIL_PASSWORD` | Gmail App Password (16 chars) | ✅ Yes |
| `EMAIL_RECIPIENT` | Where to send the digest | ✅ Yes |
| `NEWS_API_KEY` | NewsAPI.org API key | Recommended |
| `GITHUB_TOKEN` | GitHub personal access token | Optional |
| `SEND_TIME_IST` | Daily send time (default: 06:00) | Optional |
| `INGESTION_INTERVAL_MINUTES` | Fetch interval (default: 12) | Optional |

---

## 📬 What You Receive

### Email (HTML Body)
A beautifully formatted email with:
- Header with date and total update count
- Table of contents by category
- Color-coded category sections
- Impact badges (HIGH / MEDIUM / LOW)
- Source links for every update

### PDF Attachment
A professional multi-page PDF report with:
- Cover page with stats
- Table of contents
- Tech launches prioritized first
- Categorized sections with impact badges
- Full summaries and source URLs
- Unicode support (handles all characters)

---

## 🛠️ Manual Commands

```bash
# Start the autonomous agent (runs forever, sends daily digest)
python main.py

# Manually generate and send a PDF digest right now
python send_pdf_digest.py

# Start the optional REST API
uvicorn api:app --reload
```

### API Endpoints (Optional)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/updates` | GET | List recent updates |
| `/ingest` | POST | Trigger manual ingestion |
| `/stats` | GET | Database statistics |

---

## 🧪 Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Database | SQLite (WAL mode) |
| Scheduler | APScheduler (AsyncIO) |
| HTTP Client | httpx |
| RSS Parsing | feedparser |
| HTML Scraping | BeautifulSoup4 + lxml |
| PDF Generation | fpdf2 (Unicode TTF fonts) |
| Email | smtplib (SMTP/TLS) |
| API (optional) | FastAPI + Uvicorn |

---

## 📄 License

This project is open source. Feel free to use, modify, and distribute.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

> **Built with ❤️ for staying on top of the fast-moving AI landscape.**
