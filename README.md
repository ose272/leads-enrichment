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
