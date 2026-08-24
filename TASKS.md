# SE Global Outreach Agent - Implementation Task List

## Phase 0: Project Setup & Configuration
- [x] Create project structure and folder layout
- [x] Create `.env.example` with all required configuration
- [x] Create `requirements.txt` with all dependencies
- [x] Create `.gitignore`
- [x] Create `configure_email.py` GUI for email configuration
- [x] Create SQLite database schema in `ingest_service.py`
- [x] Create `README.md` with comprehensive documentation

## Phase 1: Trigger & Ingestion (ingest_service.py)
- [x] IMAP client setup for polling Drafts folder
- [x] Draft detection with CSV attachment filtering (filename `leads_` or subject `[NEW LEADS]`)
- [x] CSV parsing and lead insertion into SQLite
- [x] Duplicate prevention via `processed_messages` table
- [x] Move processed drafts to "Processed" folder
- [x] Unit tests for ingestion logic

## Phase 2: Scraping & Enrichment (scraper.py + pipeline.py)
- [x] Website fetching with requests + BeautifulSoup
- [x] Email extraction (regex + mailto links + /contact fallback)
- [x] Business context extraction (visible text summary)
- [x] Playwright fallback for JavaScript-heavy sites (optional)
- [x] `enrich_new_leads` function in pipeline
- [x] Status updates: `new` → `new` (with email) or `no_email_found`
- [x] Unit tests for scraper

## Phase 3: AI-Personalized Email Drafting (llm.py + main_service.py)
- [x] Ollama wrapper with `generate_pitch_email()`
- [x] `generate_followup_reply()` for replies
- [x] `generate_weekly_report()` for reports
- [x] `classify_reply_intent()` for intent classification
- [x] SMTP sender with dry-run, rate limiting, daily cap
- [x] Proper email threading headers (Message-ID, In-Reply-To, References)
- [x] Opt-out instruction appended to every email
- [x] Real sender identity (From header with name)
- [x] `send_initial_outreach()` in main_service
- [x] Status update: `new` → `emailed` with `thread_id` and `last_contacted_at`

## Phase 4: Reply Handling & Conversation (main_service.py + pipeline.py)
- [x] IMAP polling of INBOX for replies
- [x] Thread matching via In-Reply-To/References headers
- [x] **Opt-out detection FIRST** (hard requirement) - `contains_opt_out()`
- [x] LLM intent classification: curious / objecting / ready-to-talk / neutral
- [x] `ready-to-talk` → `handed_off` + WhatsApp handoff message
- [x] Other intents → AI-generated contextual reply
- [x] `handed_off` leads never automated again (hard stop)
- [x] Conversation logging to `conversation_log` table
- [x] `classify_inbound()` in pipeline handles all intent types

## Phase 5: Follow-Up Automation (main_service.py + pipeline.py)
- [x] `due_followup_status()` with correct timing:
  - Follow-up 1: 2 days after initial
  - Follow-up 2: 2 days after follow-up 1 (4 days total)
  - Archive: 24 hours after follow-up 2 (5 days total)
- [x] `process_followups()` scheduled hourly
- [x] Follow-up 1 and 2 generated via LLM with context
- [x] Archive logic marks `archived_no_response`
- [x] Unsubscribe check before every send
- [x] Status transitions tracked in database

## Phase 6: Weekly Reporting (main_service.py + llm.py)
- [x] Scheduled job: Sunday 23:00 UTC
- [x] Stats aggregation from SQLite (past 7 days)
  - Total leads, emails sent, replies, handoffs, unsubscribes, archived
  - Reply rate, handoff rate
  - Follow-up effectiveness
  - Top companies by replies
- [x] LLM generates performance summary with benchmarks + improvements
- [x] Report emailed to sender

## Scheduling & Orchestration (main_service.py)
- [x] APScheduler background scheduler
- [x] Hourly follow-up job
- [x] Weekly report job (cron)
- [x] `run_cycle()` runs every 10 minutes in foreground
- [x] Signal handlers for graceful shutdown
- [x] `run_foreground()` entry point

## Guardrails & Compliance
- [x] Opt-out handling checked BEFORE any other reply logic
- [x] Opt-out is permanent (`unsubscribed` status never contacted again)
- [x] Real sender identity in every email
- [x] Rate limiting: 3s minimum delay, 30 emails/day cap
- [x] Human handoff hard stop (`handed_off` never automated)
- [x] Dry-run mode default (`DRY_RUN=true`)
- [x] Opt-out instruction in every email ("Reply STOP to opt out any time")
- [x] Compliance note in README (CAN-SPAM, GDPR, NDPR)

## Testing
- [x] Import tests (`test_imports.py`)
- [x] Ingestion tests (`test_ingest_service.py`)
- [x] Pipeline tests (`test_pipeline.py`) - all 5 tests passing
- [x] All unit tests pass (`python -m unittest -v`)

## Remaining / Future Work (Deferred per build prompt)
- [ ] Always-on hosting / deployment (config in env vars for easy lift-and-shift)
- [ ] Google Sheets synchronization
- [ ] Multi-channel follow-up (LinkedIn) beyond email + WhatsApp
- [ ] Playwright-based scraper for JavaScript-heavy sites
- [ ] More sophisticated personalization angle extraction
- [ ] End-to-end dry run with test leads (user to execute)
- [ ] Production launch with real small batch (user to execute)

## Known Issues / Refinements Needed
- [ ] Verify scraper works with real business websites (not just example.com)
- [ ] Test with real email accounts (user needs to configure .env)
- [ ] Validate LLM prompts produce quality output with llama3.1:8b
- [ ] Consider adding personalization_angle extraction from scraped content
- [ ] Add more robust error handling for network/IMAP/SMTP failures
- [ ] Add logging configuration file
- [ ] Consider adding health check / monitoring endpoint
