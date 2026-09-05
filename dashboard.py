"""
SE Global Outreach Dashboard
=============================
Real-time monitoring dashboard for the cold outreach automation system.
Connects to actual SQLite database and backend modules.

Features:
- CSV upload for leads
- Pipeline overview (leads by status)
- Email tracking (sent, opened, replied)
- Follow-up management
- Reply sentiment analysis
- Weekly reports
- Manual trigger for daily cycle

Run: streamlit run dashboard.py
"""

import io
import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.tracker import LeadStore
from src.main import (
    run_draft_phase, run_send_phase,
    run_reply_phase, run_followup_phase, run_report_phase
)

st.set_page_config(
    page_title="SE Global Outreach Dashboard",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #007bff;
    }
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .status-new { background: #e0e7ff; color: #3730a3; }
    .status-scraped { background: #dcfce7; color: #166534; }
    .status-drafted { background: #dbeafe; color: #1e40af; }
    .status-sent { background: #fef3c7; color: #92400e; }
    .status-replied { background: #e0e7ff; color: #3730a3; }
    .status-follow_up_1 { background: #fce7f3; color: #9d174d; }
    .status-follow_up_2 { background: #fdf4ff; color: #86198f; }
    .status-closed { background: #fee2e2; color: #991b1b; }
    .status-closed_handoff { background: #dcfce7; color: #166534; }
    .status-no_email { background: #f3f4f6; color: #6b7280; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { padding: 12px 24px; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# DATABASE CONNECTION
# ============================================================
DB_PATH = "outreach.db"

@st.cache_resource
def get_store():
    return LeadStore(DB_PATH)

def get_connection():
    """Get database connection, initializing schema if needed."""
    import os
    db_exists = os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    if not db_exists:
        # Initialize schema on first run
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                website TEXT NOT NULL,
                contact_email TEXT,
                store_name TEXT,
                owner_name TEXT,
                company_name TEXT,
                first_name TEXT,
                last_name TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                first_contacted_date TEXT,
                last_contacted_date TEXT,
                follow_up_count INTEGER NOT NULL DEFAULT 0,
                reply_text TEXT,
                reply_sentiment TEXT,
                notes TEXT,
                last_email_subject TEXT,
                last_email_body TEXT,
                paraphrase_seed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    
    return conn

def load_leads_df():
    """Load all leads as DataFrame"""
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT id, website, contact_email, store_name, owner_name, status, follow_up_count,
               last_contacted_date, first_contacted_date, reply_sentiment,
               created_at, updated_at,
               last_email_subject, last_email_body, notes, paraphrase_seed
        FROM leads
        ORDER BY created_at DESC
    """, conn)
    conn.close()
    return df

def load_stats():
    """Load pipeline statistics"""
    conn = get_connection()
    stats = {}
    
    # Total leads
    stats['total'] = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    
    # By status
    status_counts = conn.execute("""
        SELECT status, COUNT(*) as count FROM leads GROUP BY status
    """).fetchall()
    stats['by_status'] = {row['status']: row['count'] for row in status_counts}
    
    # Recent activity (last 7 days)
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    stats['recent_drafted'] = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE updated_at >= ? AND status IN ('drafted', 'sent', 'replied', 'follow_up_1', 'follow_up_2')",
        (week_ago,)
    ).fetchone()[0]
    stats['recent_sent'] = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE updated_at >= ? AND status IN ('sent', 'replied', 'follow_up_1', 'follow_up_2')",
        (week_ago,)
    ).fetchone()[0]
    stats['recent_replied'] = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE updated_at >= ? AND status = 'replied'",
        (week_ago,)
    ).fetchone()[0]
    stats['positive_replies'] = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE reply_sentiment = 'positive'"
    ).fetchone()[0]
    
    conn.close()
    return stats

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.image("https://via.placeholder.com/200x60/007bff/ffffff?text=SE+Global", width=200)
    st.title("Outreach Dashboard")
    st.caption(f"Connected to: `{DB_PATH}`")
    
    # Refresh button
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    
    # Quick stats in sidebar
    stats = load_stats()
    st.metric("Total Leads", stats['total'])
    st.metric("Sent This Week", stats['recent_sent'])
    st.metric("Replied This Week", stats['recent_replied'])
    st.metric("Positive Replies", stats['positive_replies'])
    
    st.divider()
    
    # Navigation
    page = st.radio(
        "Navigation",
        ["📤 Upload Leads", "📊 Pipeline Overview", "📧 Email Tracking", 
         "🔄 Follow-ups", "💬 Replies & Sentiment", "📈 Reports", "⚙️ Actions"],
        label_visibility="collapsed"
    )

# ============================================================
# MAIN CONTENT
# ============================================================

if page == "📤 Upload Leads":
    st.header("📤 Upload Shopify Store Leads (CSV)")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        **Upload a CSV file with Shopify store owners.** Required column: `email`
        
        Optional columns: `store_name`, `owner_name`, `website`, `context`, `paraphrase_seed`
        
        Example format:
        ```csv
        email,store_name,owner_name,website,context,paraphrase_seed
        john@fitnessgearpro.com,Fitness Gear Pro,John Smith,https://fitnessgearpro.com,"Sells premium fitness equipment",0
        sarah@cozyhomegoods.com,Cozy Home Goods,Sarah Johnson,https://cozyhomegoods.com,"Home decor store",1
        ```
        """)
        
        uploaded_file = st.file_uploader(
            "Choose CSV file",
            type=["csv"],
            help="Upload a CSV with at least an 'email' column"
        )
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.success(f"✅ Loaded {len(df)} rows from CSV")
                
                # Show preview
                st.subheader("Preview")
                st.dataframe(df.head(10), use_container_width=True)
                
                # Validate required column
                if 'email' not in df.columns:
                    st.error("❌ CSV must contain an 'email' column")
                else:
                    if st.button("💾 Import to Database", type="primary", use_container_width=True):
                        with st.spinner("Importing leads..."):
                            store = get_store()
                            imported = 0
                            skipped = 0
                            
                            for _, row in df.iterrows():
                                email = str(row.get('email', '')).strip().lower()
                                if not email:
                                    continue
                                
                                # Check if exists by email
                                existing = store.get_lead_by_email(email)
                                if existing:
                                    skipped += 1
                                    continue
                                
                                # Get optional fields
                                store_name = str(row.get('store_name', '')).strip() or None
                                owner_name = str(row.get('owner_name', '')).strip() or None
                                website = str(row.get('website', '')).strip() or None
                                context = str(row.get('context', '')).strip() or None
                                paraphrase_seed = int(row.get('paraphrase_seed', 0)) if pd.notna(row.get('paraphrase_seed')) else 0
                                
                                # Normalize website
                                if website and not website.startswith(('http://', 'https://')):
                                    website = 'https://' + website
                                
                                # Add lead
                                lead_id = store.add_lead(
                                    website=website or f"shopify-{email.split('@')[0]}",
                                    contact_email=email,
                                    store_name=store_name or "",
                                    owner_name=owner_name or "",
                                    paraphrase_seed=paraphrase_seed
                                )
                                
                                imported += 1
                            
                            st.success(f"✅ Imported {imported} new leads, skipped {skipped} duplicates")
                            st.cache_data.clear()
                            st.rerun()
                            
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
    
    with col2:
        st.subheader("📋 Template")
        template_df = pd.DataFrame({
            'email': ['john@fitnessgearpro.com', 'sarah@cozyhomegoods.com', 'mike@techgadgetstore.com'],
            'store_name': ['Fitness Gear Pro', 'Cozy Home Goods', 'Tech Gadget Store'],
            'owner_name': ['John Smith', 'Sarah Johnson', 'Mike Chen'],
            'website': ['https://fitnessgearpro.com', 'https://cozyhomegoods.com', 'https://techgadgetstore.com'],
            'context': ['Sells premium fitness equipment', 'Home decor and furniture', 'Electronics and accessories'],
            'paraphrase_seed': [0, 1, 0]
        })
        csv = template_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Template CSV",
            data=csv,
            file_name="shopify_leads_template.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        st.info("💡 Tip: Add paraphrase_seed (0, 1, 2...) to generate different email variations for A/B testing.")

elif page == "📊 Pipeline Overview":
    st.header("📊 Pipeline Overview")
    
    df = load_leads_df()
    stats = load_stats()
    
    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Leads", stats['total'])
    with col2:
        st.metric("New (no email)", stats['by_status'].get('new', 0) + stats['by_status'].get('no_email', 0))
    with col3:
        scraped = stats['by_status'].get('scraped', 0) + stats['by_status'].get('drafted', 0)
        st.metric("Ready to Send", scraped)
    with col4:
        st.metric("Active Outreach", stats['by_status'].get('sent', 0) + 
                  stats['by_status'].get('follow_up_1', 0) + 
                  stats['by_status'].get('follow_up_2', 0))
    with col5:
        st.metric("Closed", stats['by_status'].get('closed', 0) + 
                  stats['by_status'].get('closed_handoff', 0))
    
    st.divider()
    
    # Status breakdown chart
    if stats['by_status']:
        st.subheader("Leads by Status")
        status_df = pd.DataFrame(list(stats['by_status'].items()), columns=['Status', 'Count'])
        status_df = status_df.sort_values('Count', ascending=False)
        st.bar_chart(status_df.set_index('Status'))
    
    st.divider()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.multiselect(
            "Filter by Status",
            options=df['status'].unique().tolist() if not df.empty else [],
            default=[]
        )
    with col2:
        has_email = st.selectbox("Email Status", ["All", "Has Email", "No Email"])
    with col3:
        search = st.text_input("🔍 Search store name/website")
    
    # Apply filters
    filtered_df = df.copy()
    if status_filter:
        filtered_df = filtered_df[filtered_df['status'].isin(status_filter)]
    if has_email == "Has Email":
        filtered_df = filtered_df[filtered_df['contact_email'].notna() & (filtered_df['contact_email'] != '')]
    elif has_email == "No Email":
        filtered_df = filtered_df[filtered_df['contact_email'].isna() | (filtered_df['contact_email'] == '')]
    if search:
        filtered_df = filtered_df[
            filtered_df['store_name'].str.contains(search, case=False, na=False) |
            filtered_df['website'].str.contains(search, case=False, na=False) |
            filtered_df['owner_name'].str.contains(search, case=False, na=False)
        ]
    
    # Display table
    st.subheader(f"Leads ({len(filtered_df)} of {len(df)})")
    
    if not filtered_df.empty:
        # Format display
        display_df = filtered_df.copy()
        
        # Status badges
        def status_badge(s):
            return f'<span class="status-badge status-{s}">{s}</span>'
        
        display_df['status'] = display_df['status'].apply(status_badge)
        
        # Truncate long fields
        display_df['website'] = display_df['website'].apply(lambda x: x[:50] + '...' if len(str(x)) > 50 else x)
        display_df['store_name'] = display_df['store_name'].apply(lambda x: x[:40] + '...' if len(str(x)) > 40 else x)
        display_df['last_email_subject'] = display_df['last_email_subject'].apply(
            lambda x: (x[:40] + '...') if x and len(str(x)) > 40 else (x or '')
        )
        
        # Select columns to show
        show_cols = ['id', 'store_name', 'owner_name', 'website', 'contact_email', 'status', 'follow_up_count', 
                     'last_contacted_date', 'reply_sentiment', 'last_email_subject', 'created_at']
        display_df = display_df[show_cols]
        
        st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.info("No leads match the current filters.")

elif page == "📧 Email Tracking":
    st.header("📧 Email Tracking")
    
    df = load_leads_df()
    
    # Filter to leads with email activity
    email_df = df[df['status'].isin(['sent', 'replied', 'follow_up_1', 'follow_up_2', 'closed_handoff'])]
    
    if email_df.empty:
        st.info("No emails sent yet. Run the daily cycle to start outreach.")
    else:
        # Summary
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Emails Sent", len(email_df[email_df['status'].isin(['sent', 'replied', 'follow_up_1', 'follow_up_2', 'closed_handoff'])]))
        with col2:
            st.metric("Replies Received", len(email_df[email_df['status'] == 'replied']))
        with col3:
            st.metric("Follow-ups Sent", len(email_df[email_df['status'].isin(['follow_up_1', 'follow_up_2'])]))
        with col4:
            st.metric("Handoffs", len(email_df[email_df['status'] == 'closed_handoff']))
        
        st.divider()
        
        # Email detail table
        st.subheader("Email History")
        
        display_cols = ['id', 'store_name', 'owner_name', 'website', 'contact_email', 'status', 'follow_up_count',
                        'last_contacted_date', 'reply_sentiment', 'last_email_subject']
        st.dataframe(email_df[display_cols], use_container_width=True, hide_index=True)
        
        # Email content viewer
        st.divider()
        st.subheader("📖 View Email Content")
        
        lead_ids = email_df['id'].tolist()
        selected_id = st.selectbox("Select Lead", lead_ids, format_func=lambda x: f"Lead #{x} - {email_df[email_df['id']==x]['store_name'].values[0]}")
        
        if selected_id:
            lead = email_df[email_df['id'] == selected_id].iloc[0]
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Last Email Subject**")
                st.code(lead['last_email_subject'] or "Not available")
            with col2:
                st.markdown("**Last Email Body**")
                st.text_area("", value=lead['last_email_body'] or "Not available", height=200, disabled=True)
            
            if lead['reply_sentiment']:
                sentiment_color = {"positive": "🟢", "neutral": "🟡", "negative": "🔴"}
                st.markdown(f"**Reply Sentiment:** {sentiment_color.get(lead['reply_sentiment'], '')} {lead['reply_sentiment'].upper()}")

elif page == "🔄 Follow-ups":
    st.header("🔄 Follow-up Management")
    
    df = load_leads_df()
    
    # Follow-up candidates
    followup_df = df[df['status'].isin(['sent', 'follow_up_1'])]
    
    if followup_df.empty:
        st.info("No leads eligible for follow-up.")
    else:
        st.subheader("Follow-up Candidates")
        
        for _, lead in followup_df.iterrows():
            days_since = "N/A"
            if lead['last_contacted_date']:
                try:
                    last_date = datetime.fromisoformat(lead['last_contacted_date'].replace('Z', '+00:00'))
                    days_since = (datetime.now() - last_date.replace(tzinfo=None)).days
                except:
                    pass
            
            next_followup = "Follow-up #1" if lead['status'] == 'sent' else "Follow-up #2"
            
            with st.expander(f"Lead #{lead['id']} - {lead['store_name']} ({next_followup}) - {days_since} days ago"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Email:** {lead['contact_email']}")
                    st.write(f"**Store:** {lead['store_name']}")
                    st.write(f"**Owner:** {lead['owner_name']}")
                    st.write(f"**Status:** {lead['status']}")
                    st.write(f"**Follow-up Count:** {lead['follow_up_count']}")
                    st.write(f"**Last Contacted:** {lead['last_contacted_date']}")
                with col2:
                    if lead['last_email_subject']:
                        st.write("**Last Subject:**")
                        st.code(lead['last_email_subject'])
                    if lead['last_email_body']:
                        st.write("**Last Body:**")
                        st.text(lead['last_email_body'][:300] + "..." if len(lead['last_email_body']) > 300 else lead['last_email_body'])
        
        st.divider()
        
        # Manual follow-up trigger
        st.subheader("Manual Actions")
        if st.button("🔄 Run Follow-up Phase Now", type="secondary"):
            with st.spinner("Running follow-up phase..."):
                store = get_store()
                result = run_followup_phase(store)
                st.success(f"Follow-up complete: {result}")
                st.cache_data.clear()
                st.rerun()

elif page == "💬 Replies & Sentiment":
    st.header("💬 Replies & Sentiment Analysis")
    
    df = load_leads_df()
    
    replied_df = df[df['status'].isin(['replied', 'closed_handoff'])]
    
    if replied_df.empty:
        st.info("No replies received yet.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            pos = len(replied_df[replied_df['reply_sentiment'] == 'positive'])
            st.metric("🟢 Positive", pos)
        with col2:
            neu = len(replied_df[replied_df['reply_sentiment'] == 'neutral'])
            st.metric("🟡 Neutral", neu)
        with col3:
            neg = len(replied_df[replied_df['reply_sentiment'] == 'negative'])
            st.metric("🔴 Negative", neg)
        
        st.divider()
        st.subheader("Replied Leads")
        
        for _, lead in replied_df.iterrows():
            sentiment = lead['reply_sentiment'] or 'unknown'
            badge_class = f"status-{sentiment}" if sentiment in ['positive', 'neutral', 'negative'] else "status-new"
            
            with st.expander(f"Lead #{lead['id']} - {lead['website']} - {sentiment.upper()}"):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.write(f"**Email:** {lead['contact_email']}")
                    st.write(f"**Status:** {lead['status']}")
                    st.write(f"**Sentiment:** <span class='status-badge {badge_class}'>{sentiment}</span>", unsafe_allow_html=True)
                    st.write(f"**Last Contact:** {lead['last_contacted_date']}")
                with col2:
                    st.write("**Reply Notes:**")
                    st.text(lead['notes'] or "No notes")
                    if lead['last_email_subject']:
                        st.write("**Original Subject:**")
                        st.code(lead['last_email_subject'])
        
        st.divider()
        st.subheader("Manual Actions")
        if st.button("📬 Check for Replies Now", type="secondary"):
            with st.spinner("Checking IMAP for replies..."):
                store = get_store()
                result = run_reply_phase(store)
                st.success(f"Reply check complete: {result} replies processed")
                st.cache_data.clear()
                st.rerun()
elif page == "📈 Reports":
    st.header("📈 Reports & Analytics")
    
    tab1, tab2, tab3 = st.tabs(["📊 Weekly Report", "📈 Trends", "📥 Export Data"])
    
    with tab1:
        st.subheader("Weekly Outreach Report")
        
        if st.button("📋 Generate Weekly Report", type="primary"):
            with st.spinner("Generating report..."):
                store = get_store()
                result = run_report_phase(store)
                st.success("Report generated!")
                
                try:
                    report_df = pd.read_csv("weekly_report.csv")
                    st.dataframe(report_df, use_container_width=True, hide_index=True)
                    
                    import os
                    if os.path.exists("weekly_report.html"):
                        with open("weekly_report.html", "r") as f:
                            html_content = f.read()
                        st.components.v1.html(html_content, height=600, scrolling=True)
                except Exception as e:
                    st.error(f"Error loading report: {e}")
        
        st.divider()
        
        try:
            report_df = pd.read_csv("weekly_report.csv")
            st.caption("Latest Generated Report")
            st.dataframe(report_df, use_container_width=True, hide_index=True)
        except:
            st.caption("No report generated yet. Click 'Generate Weekly Report' above.")
    
    with tab2:
        st.subheader("Pipeline Trends")
        
        conn = get_connection()
        
        daily_activity = pd.read_sql_query("""
            SELECT date(created_at) as date, COUNT(*) as new_leads
            FROM leads
            WHERE created_at >= date('now', '-30 days')
            GROUP BY date(created_at)
            ORDER BY date
        """, conn)
        
        if not daily_activity.empty:
            st.line_chart(daily_activity.set_index('date'))
        else:
            st.info("Not enough data for trends yet.")
        
        st.subheader("Status Distribution")
        status_dist = pd.read_sql_query("""
            SELECT status, COUNT(*) as count
            FROM leads
            GROUP BY status
        """, conn)
        if not status_dist.empty:
            st.bar_chart(status_dist.set_index('status'))
        
        conn.close()
    with tab3:
        st.subheader("Export Data")
        
        df = load_leads_df()
        
        col1, col2 = st.columns(2)
        with col1:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download All Leads (CSV)",
                data=csv,
                file_name=f"leads_export_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col2:
            statuses = st.multiselect("Filter by status", df['status'].unique().tolist())
            if statuses:
                filtered = df[df['status'].isin(statuses)]
                csv = filtered.to_csv(index=False).encode('utf-8')
                st.download_button(
                    f"📥 Download Filtered ({len(filtered)} leads)",
                    data=csv,
                    file_name=f"leads_filtered_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

elif page == "⚙️ Actions":
    st.header("⚙️ Manual Actions & System Controls")
    
    st.warning("⚠️ These actions run the actual outreach pipeline phases. Use with real credentials.")
    
    store = get_store()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Individual Phases")
        
        if st.button("✍️ Draft Emails", use_container_width=True):
            with st.spinner("Drafting emails with LLM..."):
                result = run_draft_phase(store)
                st.success(f"Drafted {result} emails")
                st.cache_data.clear()
                st.rerun()
        
        if st.button("📤 Send Emails", use_container_width=True):
            with st.spinner("Sending emails via SMTP..."):
                result = run_send_phase(store)
                st.success(f"Sent {result} emails")
                st.cache_data.clear()
                st.rerun()
        
        if st.button("📬 Check Replies", use_container_width=True):
            with st.spinner("Checking IMAP for replies..."):
                result = run_reply_phase(store)
                st.success(f"Processed {result} replies")
                st.cache_data.clear()
                st.rerun()
        
        if st.button("🔄 Send Follow-ups", use_container_width=True):
            with st.spinner("Sending follow-ups..."):
                result = run_followup_phase(store)
                st.success(f"Sent {result} follow-ups")
                st.cache_data.clear()
                st.rerun()
        
        if st.button("📊 Generate Report", use_container_width=True):
            with st.spinner("Generating weekly report..."):
                result = run_report_phase(store)
                st.success("Report generated!")
                st.cache_data.clear()
                st.rerun()
    
    with col2:
        st.subheader("Full Daily Cycle")
        
        if st.button("🚀 RUN FULL DAILY CYCLE", type="primary", use_container_width=True):
            with st.spinner("Running full daily outreach cycle..."):
                progress = st.progress(0)
                status = st.empty()
                
                phases = [
                    ("Drafting emails...", run_draft_phase),
                    ("Sending emails...", run_send_phase),
                    ("Checking replies...", run_reply_phase),
                    ("Sending follow-ups...", run_followup_phase),
                ]
                
                results = {}
                for i, (msg, func) in enumerate(phases):
                    status.text(msg)
                    try:
                        results[msg] = func(store)
                    except Exception as e:
                        results[msg] = f"Error: {e}"
                    progress.progress((i + 1) / len(phases))
                
                status.text("✅ Daily cycle complete!")
                
                st.json(results)
                st.cache_data.clear()
                st.rerun()
        
        st.divider()
        
        st.subheader("System Info")
        
        conn = get_connection()
        db_size = Path(DB_PATH).stat().st_size / 1024
        st.write(f"**Database:** {DB_PATH} ({db_size:.1f} KB)")
        
        table_counts = {}
        for table in ['leads', 'scrape_log']:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                table_counts[table] = count
            except:
                table_counts[table] = 0
        
        st.write(f"**Leads table:** {table_counts.get('leads', 0)} rows")
        st.write(f"**Scrape log:** {table_counts.get('scrape_log', 0)} rows")
        
        conn.close()
        
        st.subheader("Environment Check")
        import os
        env_vars = [
            'GROQ_API_KEY', 'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER',
            'IMAP_HOST', 'IMAP_PORT', 'IMAP_USER', 'SENDER_EMAIL', 'WHATSAPP_LINK'
        ]
        
        for var in env_vars:
            value = os.getenv(var)
            status = "✅ Set" if value else "❌ Missing"
            if value and var.endswith(('_KEY', '_PASSWORD', '_PASS')):
                display = value[:4] + "****" + value[-4:] if len(value) > 8 else "****"
            else:
                display = value or ""
            st.write(f"**{var}:** {status} {display}")

# Footer
st.divider()
st.caption(f"SE Global Outreach Dashboard • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • DB: {DB_PATH}")