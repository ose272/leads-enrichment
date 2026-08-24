"""
Streamlit Dashboard for SE Global Outreach Agent
Read-only viewer for leads.db with filtering, search, and conversation viewing.
Upload CSV leads (website required) for enrichment and outreach.
Run with: streamlit run dashboard.py
"""

import csv
import io
import sqlite3
import pandas as pd
import streamlit as st

from storage import LeadStore, load_env_file

DB_PATH = "leads.db"


def process_terminal_command(cmd: str) -> list[str]:
    """Process terminal command and return output lines."""
    import os
    from storage import load_env_file
    
    load_env_file()
    parts = cmd.strip().split()
    if not parts:
        return []
    
    command = parts[0].lower()
    args = parts[1:] if len(parts) > 1 else []
    
    output = []
    
    if command == "help":
        output = [
            "Available commands:",
            "  set daily_cap <number>    - Set daily email limit (e.g., 'set daily_cap 100')",
            "  set live_mode <true|false> - Toggle live email sending",
            "  set dry_run <true|false>   - Toggle dry-run mode (opposite of live_mode)",
            "  show                      - Show current settings",
            "  help                      - Show this help",
            "  clear                     - Clear terminal history",
        ]
    
    elif command == "set":
        if len(args) < 2:
            output = ["Usage: set <key> <value>", "Example: set daily_cap 100"]
        else:
            key = args[0].lower()
            value = args[1]
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
            
            if key == "daily_cap":
                try:
                    cap = int(value)
                    if cap < 1 or cap > 1000:
                        output = ["Error: daily_cap must be between 1 and 1000"]
                    else:
                        # Update .env
                        with open(env_path, "r") as f:
                            lines = f.readlines()
                        with open(env_path, "w") as f:
                            found = False
                            for line in lines:
                                if line.startswith("DAILY_EMAIL_CAP="):
                                    f.write(f"DAILY_EMAIL_CAP={cap}\n")
                                    found = True
                                else:
                                    f.write(line)
                            if not found:
                                f.write(f"DAILY_EMAIL_CAP={cap}\n")
                        output = [f"✅ Set DAILY_EMAIL_CAP={cap}", "Restart dashboard/service to apply."]
                except ValueError:
                    output = ["Error: daily_cap must be a number"]
            
            elif key == "live_mode":
                if value.lower() in ("true", "false"):
                    dry_run = "false" if value.lower() == "true" else "true"
                    with open(env_path, "r") as f:
                        lines = f.readlines()
                    with open(env_path, "w") as f:
                        for line in lines:
                            if line.startswith("DRY_RUN="):
                                f.write(f"DRY_RUN={dry_run}\n")
                            else:
                                f.write(line)
                    output = [f"✅ Set DRY_RUN={dry_run} (live_mode={value.lower()})", "Restart dashboard/service to apply."]
                else:
                    output = ["Error: live_mode must be 'true' or 'false'"]
            
            elif key == "dry_run":
                if value.lower() in ("true", "false"):
                    with open(env_path, "r") as f:
                        lines = f.readlines()
                    with open(env_path, "w") as f:
                        for line in lines:
                            if line.startswith("DRY_RUN="):
                                f.write(f"DRY_RUN={value.lower()}\n")
                            else:
                                f.write(line)
                    output = [f"✅ Set DRY_RUN={value.lower()}", "Restart dashboard/service to apply."]
                else:
                    output = ["Error: dry_run must be 'true' or 'false'"]
            
            else:
                output = [f"Error: unknown setting '{key}'. Use 'help' for options."]
    
    elif command == "show":
        daily_cap = os.getenv("DAILY_EMAIL_CAP", "30 (default)")
        dry_run = os.getenv("DRY_RUN", "true")
        live_mode = "true" if dry_run.lower() == "false" else "false"
        output = [
            f"DAILY_EMAIL_CAP={daily_cap}",
            f"DRY_RUN={dry_run}",
            f"LIVE_MODE={live_mode}",
        ]
    
    elif command == "clear":
        output = ["__CLEAR__"]
    
    else:
        output = [f"Unknown command: '{command}'. Type 'help' for available commands."]
    
    # Handle clear command
    if output == ["__CLEAR__"]:
        return ["__CLEAR__"]
    
    return output


def get_connection():
    """Create a read-only connection to the database."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def parse_csv_upload(uploaded_file) -> list[dict]:
    """Parse uploaded CSV file into list of dicts."""
    content = uploaded_file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    return rows


def insert_uploaded_leads(rows: list[dict]) -> tuple[int, list[str]]:
    """Insert uploaded leads into database. Returns (inserted_count, errors)."""
    load_env_file()
    store = LeadStore(DB_PATH)
    try:
        from datetime import datetime, timezone
        batch_id = f"upload_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        inserted = store.insert_leads(batch_id, rows)
        return inserted, []
    except Exception as e:
        return 0, [str(e)]
    finally:
        store.close()


@st.cache_data(ttl=60)
def fetch_leads():
    """Fetch all leads from the database."""
    conn = get_connection()
    query = """
        SELECT
            id,
            company as company_name,
            website,
            email,
            status,
            followup_count,
            last_contacted_at,
            personalization_angle
        FROM leads
        ORDER BY created_at DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=60)
def fetch_status_counts():
    """Fetch count of leads per status."""
    conn = get_connection()
    query = "SELECT status, COUNT(*) as count FROM leads GROUP BY status"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return dict(zip(df['status'], df['count']))


@st.cache_data(ttl=60)
def fetch_conversation(lead_id):
    """Fetch conversation log for a specific lead."""
    conn = get_connection()
    query = """
        SELECT direction, message, timestamp
        FROM conversation_log
        WHERE lead_id = ?
        ORDER BY timestamp ASC
    """
    df = pd.read_sql_query(query, conn, params=(lead_id,))
    conn.close()
    return df


def main():
    st.set_page_config(
        page_title="SE Global Outreach Dashboard",
        page_icon="📊",
        layout="wide"
    )

    st.title("📊 SE Global Outreach Dashboard")

    # Refresh button
    col_refresh, col_spacer = st.columns([1, 10])
    with col_refresh:
        if st.button("🔄 Refresh", type="primary"):
            st.cache_data.clear()
            st.rerun()

    # ===== UPLOAD SECTION =====
    st.subheader("📤 Upload Leads (CSV)")
    st.caption("Upload a CSV with at minimum a 'website' column. Optional: company, email, first_name, last_name, phone.")
    
    with st.expander("📋 CSV Format Guide", expanded=False):
        st.markdown("""
        **Required column:** `website` (or `Website`, `url`, `URL`)
        
        **Optional columns:** `company`, `email`, `first_name`, `last_name`, `phone`
        
        **Example CSV:**
        ```csv
        website,company,first_name,last_name,email,phone
        https://example.com,Example Corp,John,Doe,john@example.com,+1-555-1234
        https://another.com,Another Inc,Jane,Smith,
        ```
        
        - Leads are deduplicated by website (same website won't be inserted twice)
        - If email is provided, it will be used; otherwise the system will scrape the website
        - All leads start with status `new` and go through enrichment → outreach → follow-ups
        """)
    
    uploaded_file = st.file_uploader("Choose CSV file", type=["csv"])
    
    if uploaded_file is not None:
        try:
            rows = parse_csv_upload(uploaded_file)
            st.write(f"Preview: {len(rows)} rows")
            st.dataframe(pd.DataFrame(rows).head(10), use_container_width=True)
            
            if st.button("🚀 Insert Leads", type="primary"):
                with st.spinner("Inserting leads..."):
                    inserted, errors = insert_uploaded_leads(rows)
                if errors:
                    st.error(f"Errors: {errors}")
                else:
                    st.success(f"✅ Inserted {inserted} new leads")
                    st.cache_data.clear()
                    st.rerun()
        except Exception as e:
            st.error(f"Failed to parse CSV: {e}")

    st.divider()
    
    # ===== AUTOMATION TRIGGER =====
    st.subheader("🤖 Run Automation")
    st.caption("Run enrichment (scrape websites for emails) and send initial outreach emails to leads ready for contact.")
    
    # Live Mode Toggle
    col_mode, col_spacer = st.columns([1, 5])
    with col_mode:
        # Read current DRY_RUN from .env
        try:
            from storage import load_env_file
            import os
            load_env_file()
            current_dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        except:
            current_dry_run = True
        
        live_mode = st.toggle(
            "🔴 Live Mode (Send Real Emails)", 
            value=not current_dry_run,
            help="OFF = Dry-run (logs only, no SMTP). ON = Real emails sent via SMTP. Updates .env automatically."
        )
        
        # Update .env if changed
        if live_mode != (not current_dry_run):
            try:
                env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
                with open(env_path, "r") as f:
                    lines = f.readlines()
                with open(env_path, "w") as f:
                    for line in lines:
                        if line.startswith("DRY_RUN="):
                            f.write(f"DRY_RUN={'false' if live_mode else 'true'}\n")
                        else:
                            f.write(line)
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Failed to update .env: {e}")
    
    col_trigger1, col_trigger2, col_trigger3 = st.columns([1, 1, 4])
    
    with col_trigger1:
        if st.button("🔍 Run Enrichment", type="secondary", help="Scrape websites for emails and business summaries"):
            with st.spinner("Enriching leads... This may take a minute."):
                try:
                    from pipeline import enrich_new_leads
                    from storage import LeadStore
                    store = LeadStore("leads.db")
                    count = enrich_new_leads(store)
                    store.close()
                    st.success(f"✅ Enriched {count} leads")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Enrichment failed: {e}")
    
    with col_trigger2:
        if st.button("📧 Send Initial Outreach", type="primary", help="Send first outreach emails to leads with emails"):
            with st.spinner("Sending outreach emails..."):
                try:
                    from main_service import OutreachService
                    from storage import LeadStore, Settings, load_env_file
                    from llm import Ollama
                    from outreach import SmtpSender
                    import os
                    
                    load_env_file()
                    settings = Settings.from_env()
                    store = LeadStore(settings.database_path)
                    llm = Ollama()
                    # Use live_mode toggle: False = dry_run, True = live
                    # Read daily cap from environment variable
                    daily_cap = int(os.getenv("DAILY_EMAIL_CAP", "30"))
                    sender = SmtpSender(dry_run=not live_mode, minimum_delay=3.0, daily_cap=daily_cap)
                    
                    service = OutreachService(settings, store, llm, sender)
                    sent = service.send_initial_outreach()
                    
                    store.close()
                    mode_str = "LIVE" if live_mode else "DRY-RUN"
                    st.success(f"✅ [{mode_str}] Sent {sent} initial outreach emails")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Outreach failed: {e}")
    
    with col_trigger3:
        mode_badge = "🔴 **LIVE MODE** - Real emails will be sent" if live_mode else "🟡 **DRY-RUN MODE** - Logs only, no SMTP"
        st.caption(f"{mode_badge}. Enrichment scrapes websites for emails. Outreach sends personalized first emails to leads with emails.")
    
    st.divider()
    
    # ===== SETTINGS TERMINAL =====
    st.subheader("⚙️ Settings Terminal")
    st.caption("Type commands to configure email limits and other settings. Commands update .env and take effect after restart.")
    
    # Initialize session state for terminal
    if "terminal_history" not in st.session_state:
        st.session_state.terminal_history = []
    if "terminal_input" not in st.session_state:
        st.session_state.terminal_input = ""
    
    # Display terminal output
    terminal_container = st.container()
    with terminal_container:
        if st.session_state.terminal_history:
            for entry in st.session_state.terminal_history:
                if entry.startswith(">"):
                    st.code(entry, language="bash")
                else:
                    st.text(entry)
        else:
            st.text("Welcome to Settings Terminal. Type 'help' for commands.")
    
    # Terminal input
    col_term1, col_term2 = st.columns([5, 1])
    with col_term1:
        cmd = st.text_input(
            ">", 
            value=st.session_state.terminal_input,
            placeholder="Type command (e.g., 'set daily_cap 100')",
            key="terminal_cmd",
            label_visibility="collapsed"
        )
    with col_term2:
        if st.button("Run", type="primary", use_container_width=True):
            if cmd.strip():
                st.session_state.terminal_history.append(f"$ {cmd}")
                process_terminal_command(cmd.strip())
                st.session_state.terminal_input = ""
                st.rerun()
    
    # Quick action buttons
    st.caption("Quick actions:")
    col_q1, col_q2, col_q3 = st.columns(3)
    with col_q1:
        if st.button("📧 Set Daily Cap", use_container_width=True):
            st.session_state.terminal_history.append("$ set daily_cap 100")
            process_terminal_command("set daily_cap 100")
            st.rerun()
    with col_q2:
        if st.button("🔴 Toggle Live Mode", use_container_width=True):
            st.session_state.terminal_history.append("$ set live_mode true")
            process_terminal_command("set live_mode true")
            st.rerun()
    with col_q3:
        if st.button("🗑️ Clear Terminal", use_container_width=True):
            st.session_state.terminal_history = []
            st.rerun()
    
    st.divider()
    
    # ===== EXISTING DASHBOARD =====
    # Fetch data
    leads_df = fetch_leads()
    status_counts = fetch_status_counts()

    # Summary panel at top
    st.subheader("📈 Status Summary")
    if status_counts:
        status_cols = st.columns(len(status_counts))
        for idx, (status, count) in enumerate(sorted(status_counts.items())):
            with status_cols[idx]:
                st.metric(label=status.replace('_', ' ').title(), value=count)
    else:
        st.info("No leads in database yet.")

    st.divider()

    # Filters
    col_search, col_status = st.columns([2, 1])

    with col_search:
        search_term = st.text_input(
            "🔍 Search by company name or email",
            placeholder="Type to filter...",
            key="search_input"
        )

    with col_status:
        all_statuses = sorted(leads_df['status'].unique().tolist()) if not leads_df.empty else []
        selected_statuses = st.multiselect(
            "Filter by status",
            options=all_statuses,
            default=all_statuses,
            key="status_filter"
        )

    # Apply filters
    filtered_df = leads_df.copy()

    if search_term:
        mask = (
            filtered_df['company_name'].str.contains(search_term, case=False, na=False) |
            filtered_df['email'].str.contains(search_term, case=False, na=False)
        )
        filtered_df = filtered_df[mask]

    if selected_statuses:
        filtered_df = filtered_df[filtered_df['status'].isin(selected_statuses)]

    # Display results count
    st.caption(f"Showing {len(filtered_df)} of {len(leads_df)} leads")

    # Main table with expanders for conversation
    if filtered_df.empty:
        st.warning("No leads match the current filters.")
    else:
        for _, row in filtered_df.iterrows():
            with st.expander(f"**{row['company_name'] or 'Unknown Company'}** — {row['email']} — _{row['status']}_", expanded=False):
                # Lead details in columns
                detail_col1, detail_col2 = st.columns(2)

                with detail_col1:
                    st.write(f"**Website:** {row['website'] or '—'}")
                    st.write(f"**Follow-up Count:** {row['followup_count']}")
                    st.write(f"**Last Contacted:** {row['last_contacted_at'] or '—'}")

                with detail_col2:
                    st.write(f"**Status:** {row['status']}")
                    st.write(f"**Personalization Angle:** {row['personalization_angle'] or '—'}")

                # Conversation log
                st.markdown("---")
                st.write("**Conversation History**")
                conv_df = fetch_conversation(row['id'])

                if conv_df.empty:
                    st.caption("No conversation history yet.")
                else:
                    for _, msg in conv_df.iterrows():
                        direction_icon = "📤" if msg['direction'] == 'outbound' else "📥"
                        st.markdown(f"**{direction_icon} {msg['direction'].title()}** — *{msg['timestamp']}*")
                        st.text(msg['message'])
                        st.markdown("")


if __name__ == "__main__":
    main()