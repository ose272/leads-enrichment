# Outreach Agent

Automated cold outreach system with email scraping, AI-powered drafting, sending, reply detection, follow-ups, and weekly reporting. Runs on GitHub Actions for free.

## Architecture

```
src/
├── main.py         # Orchestration & CLI entry point
├── tracker.py      # SQLite database (leads, status, follow-up timing)
├── scraper.py      # Email scraping with rate limiting & retries
├── llm_client.py   # Groq API wrapper (llama-3.3-70b-versatile)
├── drafter.py      # Personalized email generation
├── mailer.py       # SMTP sending + IMAP reply checking
└── reporter.py     # Weekly CSV/HTML/email reports
```

## Features

- **CSV Ingestion** - Load websites, deduplicate, validate URLs
- **Email Scraping** - Homepage + contact/about pages with rate limiting & retries
- **AI Drafting** - Personalized cold emails via Groq (free tier)
- **Email Sending** - SMTP with CAN-SPAM/GDPR footer
- **Reply Detection** - IMAP polling + LLM sentiment classification
- **Follow-ups** - Automated 2-day/4-day follow-ups (max 2)
- **Positive Handoff** - Auto-reply with WhatsApp link for positive replies
- **Weekly Reports** - CSV + HTML + email summary
- **GitHub Actions** - Free daily/weekly scheduled runs

## Quick Start (Local)

```bash
git clone <your-repo-url>
cd outreach-agent
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python -m src.main --mode upload --csv leads.csv
python -m src.main --mode daily
```

## Configuration (.env)

```env
# Required: Groq API (free at console.groq.com)
GROQ_API_KEY=your_key

# Required: SMTP for sending (Gmail app password or Resend/Brevo)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SENDER_NAME=Your Company

# Required: IMAP for reply checking
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=your_app_password

# Optional
LOG_LEVEL=INFO
DRY_RUN=false
```

## CSV Format

```csv
website
https://example.com
example2.com
https://example3.com/about
```

## CLI Modes

| Mode | Description |
|------|-------------|
| `daily` | Full cycle: scrape → draft → send → check replies → follow-ups |
| `report` | Generate weekly report (CSV + HTML + email) |
| `scrape` | Only scrape emails for new leads |
| `draft` | Only draft emails for scraped leads |
| `send` | Only send drafted emails |
| `followup` | Only send due follow-ups |
| `replies` | Only check for replies |
| `upload` | Upload CSV of websites (requires `--csv`) |

## GitHub Actions Deployment (Free)

1. Push to GitHub
2. Add secrets in Settings → Secrets → Actions:
   - `GROQ_API_KEY`
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SENDER_NAME`
   - `IMAP_HOST`, `IMAP_PORT`, `IMAP_USER`, `IMAP_PASSWORD`
3. Workflows run automatically:
   - **Daily** at 9:00 UTC (`.github/workflows/daily_run.yml`)
   - **Weekly** Monday 9:00 UTC (`.github/workflows/weekly_report.yml`)

## Database Schema (SQLite)

```sql
leads (
  id INTEGER PRIMARY KEY,
  website TEXT NOT NULL,
  contact_email TEXT,
  status TEXT,  -- new/scraped/drafted/sent/replied/follow_up_1/follow_up_2/closed_handoff
  first_contacted_date TEXT,
  last_contacted_date TEXT,
  follow_up_count INTEGER DEFAULT 0,
  reply_text TEXT,
  reply_sentiment TEXT,  -- positive/neutral/negative
  notes TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

## Lead Status Flow

```
new → scraped → drafted → sent → replied → closed_handoff (positive)
                    ↓
              follow_up_1 → follow_up_2
```

## Phase 6: Hosted Database (Optional)

For persistent storage across GitHub Actions runs, configure Supabase:
1. Create free Supabase project
2. Run schema in SQL editor
3. Add `SUPABASE_URL` and `SUPABASE_KEY` to secrets
4. Update `tracker.py` to use Supabase client

## License

MIT
# SE Global Lead Enrichment Dashboard

Streamlit Cloud-compatible web app for enriching lead lists with email guesses.

## Features
- CSV Upload - Drag & drop leads CSV (requires website column)
- Domain Deduplication - Keep one lead per unique domain
- Email Enrichment - Pattern-based (free) or LLM-powered (Groq/OpenAI/Anthropic)
- Results Preview - Interactive table with confidence scores
- CSV Download - Full results or filtered (only leads with emails)

## Quick Start (Local)
`ash
git clone <your-repo-url>
cd AUTOMATION-1
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
`

## Deploy to Streamlit Cloud
1. Push to GitHub
2. Connect at share.streamlit.io
3. Main file: streamlit_app.py
4. Add secrets in Settings > Secrets

## Secrets
LLM_PROVIDER = groq
GROQ_API_KEY = your-key

## CSV Format
Required: website
Optional: company, first_name, last_name

## Limitations
- No persistent DB -> Use Supabase/Neon
- No background jobs -> Use GitHub Actions
- No local writes -> Use st.download_button
- No Ollama -> Use cloud API
- No SMTP -> Use SendGrid/Mailgun

## License
MIT
