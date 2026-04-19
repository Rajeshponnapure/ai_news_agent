# 🛠️ Setup Guide — AI News Agent

This guide walks you through setting up the AI News Agent from scratch. Follow each step carefully and you'll have a fully autonomous AI news digest running in under 10 minutes.

---

## 📋 Prerequisites

Before you begin, make sure you have:

| Requirement | Version | How to Check |
|-------------|---------|-------------|
| **Python** | 3.11 or higher | `python --version` |
| **pip** | Latest | `pip --version` |
| **Git** | Any | `git --version` |
| **Gmail Account** | With 2FA enabled | [myaccount.google.com](https://myaccount.google.com) |

> ⚠️ **Windows Users**: Make sure Python is added to your system PATH during installation.

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/your-username/ainews_agent.git
cd ainews_agent
```

Or if you downloaded a ZIP:
```bash
cd path/to/ainews_agent
```

---

## Step 2: Create a Virtual Environment

It's **strongly recommended** to use a virtual environment to avoid dependency conflicts.

### Windows
```bash
python -m venv agent_env
agent_env\Scripts\activate
```

### macOS / Linux
```bash
python3 -m venv agent_env
source agent_env/bin/activate
```

You should see `(agent_env)` appear in your terminal prompt.

---

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs the following packages:

| Package | Purpose |
|---------|---------|
| `httpx` | HTTP client for fetching RSS, APIs, blogs |
| `feedparser` | RSS/Atom feed parsing |
| `beautifulsoup4` + `lxml` | HTML scraping for blog pages |
| `APScheduler` | Scheduling ingestion + daily digest |
| `python-dotenv` | Loading `.env` configuration |
| `fpdf2` | PDF report generation (Unicode support) |
| `Pillow` | Image processing (used by fpdf2) |
| `fastapi` + `uvicorn` | Optional REST API |

---

## Step 4: Configure Email (Required)

The agent sends your daily digest via email. You need a **Gmail App Password** — this is different from your regular Gmail password.

### 4a. Enable 2-Step Verification on Gmail

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Under "How you sign in to Google", click **2-Step Verification**
3. Follow the steps to enable it (if not already enabled)

### 4b. Generate a Gmail App Password

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. If prompted, sign in to your Google account
3. Under "Select app", choose **Mail**
4. Under "Select device", choose **Windows Computer** (or your OS)
5. Click **Generate**
6. Google will show you a **16-character password** like: `abcd efgh ijkl mnop`
7. **Copy this password** — you'll need it in the next step

> ⚠️ **Important**: This is NOT your Gmail login password. It's a separate app-specific password. Keep it safe and don't share it.

### 4c. Edit the `.env` File

Open the `.env` file in the project root and fill in your email details:

```env
# ── Email (SMTP) — Primary Delivery ──────────────
EMAIL_ENABLED=true
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SENDER=your-email@gmail.com              # ← Your Gmail address
EMAIL_PASSWORD=abcd efgh ijkl mnop              # ← Your 16-char App Password
EMAIL_RECIPIENT=recipient-email@gmail.com       # ← Where to receive the digest
```

> 💡 **Tip**: The sender and recipient can be the same email address if you want to send the digest to yourself.

---

## Step 5: Configure NewsAPI (Recommended)

NewsAPI provides access to 50,000+ news sources worldwide. The free tier gives you **100 requests/day**, which is more than enough.

### 5a. Get a Free API Key

1. Go to [newsapi.org/register](https://newsapi.org/register)
2. Sign up for a free account
3. Copy your API key from the dashboard

### 5b. Add to `.env`

```env
# ── NewsAPI.org (free tier: 100 requests/day) ─────
NEWS_API_KEY=your_api_key_here
```

> 💡 Without a NewsAPI key, the agent will still work using RSS feeds, blog scraping, and GitHub monitoring. But NewsAPI significantly increases the breadth of coverage.

---

## Step 6: Configure GitHub Token (Optional)

A GitHub token raises the API rate limit from 60 to 5,000 requests/hour.

### 6a. Generate a Token

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Give it a name like "AI News Agent"
4. Select scope: `public_repo` (read-only access to public repos)
5. Click **Generate token**
6. Copy the token

### 6b. Add to `.env`

```env
# ── GitHub (optional, raises rate limit) ──────────
GITHUB_TOKEN=ghp_your_token_here
```

> 💡 Without a token, the agent still works but may get rate-limited during heavy ingestion cycles. This mainly affects GitHub release monitoring.

---

## Step 7: Customize Schedule (Optional)

By default, the agent ingests every 12 minutes and sends the digest at 6:00 AM IST.

```env
# ── Scheduler ─────────────────────────────────────
INGESTION_INTERVAL_MINUTES=12     # How often to fetch new updates
COMPILE_TIME_IST=05:55            # When to start compiling the digest
SEND_TIME_IST=06:00               # When to send the email digest
```

**To receive the digest at a different time**, just change `SEND_TIME_IST`. For example:
- `SEND_TIME_IST=08:00` → receive at 8:00 AM IST
- `SEND_TIME_IST=22:00` → receive at 10:00 PM IST

---

## Step 8: Run the Agent

### Option A: Run as Autonomous Agent (Recommended)

```bash
python main.py
```

This starts the agent in the foreground. It will:
1. Run initial ingestion immediately
2. Continue ingesting every 12 minutes
3. Send a PDF digest email at the configured time daily
4. Keep running until you press `Ctrl+C`

You should see output like:
```
2026-04-19 09:00:00 [INFO] ai_agent: Database initialized at data/ai_updates.db
2026-04-19 09:00:00 [INFO] ai_agent: Running initial ingestion...
2026-04-19 09:00:05 [INFO] ingestion.rss_ingestor: Ingesting RSS for OpenAI
2026-04-19 09:00:06 [INFO] ingestion.rss_ingestor:   → 3 relevant entries from OpenAI
...
2026-04-19 09:00:45 [INFO] ingestion.manager: New entries stored: 47
2026-04-19 09:00:45 [INFO] ai_agent: 🤖 AI Update Agent is running. Press Ctrl+C to stop.
```

### Option B: Send a Digest Right Now (Manual)

```bash
python send_pdf_digest.py
```

This immediately:
1. Fetches updates from the database (runs ingestion if empty)
2. Processes and categorizes all updates
3. Generates a professional PDF report
4. Sends an email with HTML body + PDF attachment

### Option C: Start the REST API

```bash
uvicorn api:app --reload --port 8000
```

Then visit `http://localhost:8000/docs` for the interactive API documentation.

---

## ✅ Verify Everything Works

### Quick Test Checklist

| Step | Command | Expected Result |
|------|---------|-----------------|
| 1. Imports | `python -c "from config.settings import settings; print('OK')"` | Prints `OK` |
| 2. Database | `python -c "from database.db import get_db; db = get_db(); print('DB OK')"` | Prints `DB OK` |
| 3. Ingestion | `python -c "from ingestion.manager import IngestionManager; m = IngestionManager(); c = m.run(); m.close(); print(f'{c} entries')"` | Prints entry count |
| 4. PDF | `python -c "from reporting.pdf_generator import generate_pdf_report; p = generate_pdf_report([{'id':'t','title':'Test','company':'Test','summary':'Test','impact_level':'high','source_url':'','timestamp':'2026-01-01'}]); print(f'PDF: {p}')"` | Prints PDF path |
| 5. Email | `python send_pdf_digest.py` | Sends email to your inbox |

---

## 🔧 Troubleshooting

### "ModuleNotFoundError: No module named 'xyz'"

Make sure your virtual environment is activated:
```bash
# Windows
agent_env\Scripts\activate

# macOS/Linux
source agent_env/bin/activate

# Then reinstall
pip install -r requirements.txt
```

### "Email send failed: (535, 'Authentication failed')"

- Make sure you're using a **Gmail App Password**, not your regular password
- Verify 2-Step Verification is enabled on your Gmail account
- Make sure there are no extra spaces in `EMAIL_PASSWORD`
- Try generating a new App Password

### "No updates found in last 24h"

First run? The database is empty. The agent will automatically run ingestion:
```bash
python -c "from ingestion.manager import IngestionManager; m = IngestionManager(); print(m.run(), 'entries ingested'); m.close()"
```

### "NewsAPI returned 0 articles"

- Check that `NEWS_API_KEY` is set correctly in `.env`
- The free tier has a 100 requests/day limit — you might have exceeded it
- The agent works without NewsAPI (uses RSS, blogs, and GitHub instead)

### "GitHub releases fetch failed: 403"

- You've hit the GitHub API rate limit (60 requests/hour without a token)
- Add a `GITHUB_TOKEN` to `.env` for 5,000 requests/hour

### PDF is empty or very small

- This was a known bug (now fixed). If you're on an old version, pull the latest
- The fix: we register system Unicode fonts (Arial on Windows) so special characters don't crash the PDF generator

---

## 🔄 Running as a Background Service

### Windows — Task Scheduler

1. Open **Task Scheduler** (search in Start menu)
2. Click **Create Basic Task**
3. Name: "AI News Agent"
4. Trigger: **When the computer starts**
5. Action: **Start a program**
   - Program: `C:\path\to\agent_env\Scripts\python.exe`
   - Arguments: `main.py`
   - Start in: `C:\path\to\ainews_agent`
6. Check **"Run with highest privileges"** in Properties

### Windows — As a Batch Script

Create a file `start_agent.bat`:
```batch
@echo off
cd /d "C:\path\to\ainews_agent"
call agent_env\Scripts\activate
python main.py
pause
```

### Linux — systemd Service

Create `/etc/systemd/system/ainews-agent.service`:
```ini
[Unit]
Description=AI News Agent
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/ainews_agent
ExecStart=/path/to/ainews_agent/agent_env/bin/python main.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable ainews-agent
sudo systemctl start ainews-agent
sudo systemctl status ainews-agent
```

---

## 📊 Complete `.env` Reference

Here is a fully documented `.env` file with all available settings:

```env
# ══════════════════════════════════════════════════════
#  AI NEWS AGENT — Configuration
# ══════════════════════════════════════════════════════

# ── Database ──────────────────────────────────────────
DB_ENGINE=sqlite                              # sqlite | postgres
SQLITE_PATH=data/ai_updates.db                # Relative to project root
# POSTGRES_DSN=postgresql://user:pass@localhost:5432/ai_updates

# ── Email (SMTP) — Primary Delivery ──────────────────
EMAIL_ENABLED=true                            # Enable/disable email sending
EMAIL_SMTP_HOST=smtp.gmail.com                # SMTP server hostname
EMAIL_SMTP_PORT=587                           # 587 for TLS, 465 for SSL
EMAIL_SENDER=your-email@gmail.com             # Sender email address
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx            # Gmail App Password (16 chars)
EMAIL_RECIPIENT=recipient@gmail.com           # Where to send the digest

# ── Scheduler ─────────────────────────────────────────
INGESTION_INTERVAL_MINUTES=12                 # Fetch cycle interval
COMPILE_TIME_IST=05:55                        # When to start compiling
SEND_TIME_IST=06:00                           # When to send email (IST)

# ── GitHub (optional) ────────────────────────────────
GITHUB_TOKEN=                                 # Raises rate limit to 5000/hr

# ── NewsAPI.org (free: 100 req/day) ──────────────────
NEWS_API_KEY=                                 # Get at newsapi.org/register

# ── Notification Settings ────────────────────────────
MAX_RETRIES=3                                 # Email retry attempts
RETRY_DELAY_SECONDS=5                         # Delay between retries
```

---

## 🎯 What Happens After Setup

Once the agent is running, here's the daily flow:

```
Every 12 minutes:
  → Fetch RSS feeds (20+ sources)
  → Scrape company blogs (25+ sites)
  → Check GitHub releases (30+ repos)
  → Query NewsAPI (50,000+ sources)
  → Store new entries in SQLite
  → Deduplicate and filter noise

Daily at 06:00 AM IST:
  → Run final ingestion
  → Process all unsent entries
  → Assign impact levels (HIGH/MEDIUM/LOW)
  → Generate professional PDF report
  → Build rich HTML email
  → Send email with PDF attachment
  → Mark all entries as sent
  → Clean up entries older than 7 days
```

**You don't need to do anything after setup.** The agent runs autonomously and you'll receive your AI digest in your inbox every morning.

---

> **Need help?** Open an issue on GitHub or check the [Troubleshooting](#-troubleshooting) section above.
