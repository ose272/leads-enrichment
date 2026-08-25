"""
Streamlit Cloud-Compatible Lead Enrichment Dashboard
====================================================
Upload CSV of leads (with website column) → enrich with emails → download results.

Constraints for Streamlit Cloud:
- No persistent SQLite (uses in-memory pandas DataFrames)
- No background jobs / APScheduler
- No local Ollama (uses cloud LLM API via st.secrets)
- No SMTP/IMAP (email compose preview only, no sending)
- Ephemeral filesystem (downloads via st.download_button)

Run locally: streamlit run streamlit_app.py
Deploy: Push to GitHub → connect at share.streamlit.io
"""

import io
import csv
import re
import time
from typing import Optional

import pandas as pd
import streamlit as st

# Optional: cloud LLM (OpenAI, Anthropic, Groq) - configured via st.secrets
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# =============================================================================
# CONFIGURATION & SECRETS
# =============================================================================

st.set_page_config(
    page_title="SE Global Lead Enrichment",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="collapsed",  # Collapsed on mobile for more screen space
    menu_items={
        "Get Help": "https://github.com/YOUR_USERNAME/YOUR_REPO/issues",
        "Report a bug": "https://github.com/YOUR_USERNAME/YOUR_REPO/issues",
        "About": "SE Global Lead Enrichment — CSV upload, email enrichment, download results",
    },
)

# Mobile-friendly CSS injection
st.markdown("""
<style>
/* Larger touch targets for mobile */
button[kind="primary"] { min-height: 48px; font-size: 16px; }
button[kind="secondary"] { min-height: 44px; font-size: 16px; }
.stDownloadButton > button { min-height: 48px; font-size: 16px; }
.stFileUploader { min-height: 120px; }

/* Better table scrolling on mobile */
[data-testid="stDataFrame"] { overflow-x: auto; }

/* Reduce padding on mobile */
@media (max-width: 640px) {
    .main .block-container { padding: 1rem 0.5rem; }
    .stSidebar { min-width: 100% !important; }
    h1 { font-size: 1.5rem !important; }
    h2 { font-size: 1.25rem !important; }
    h3 { font-size: 1.1rem !important; }
    .stMetric { font-size: 0.9rem; }
}

/* Prevent horizontal scroll on mobile */
.main { overflow-x: hidden; }
</style>
""", unsafe_allow_html=True)

# PWA manifest for "Add to Home Screen" (served as static file from repo root)
st.markdown("""
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#ff4b4b">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Lead Enrich">
<link rel="apple-touch-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📧</text></svg>">
""", unsafe_allow_html=True)

# Load secrets (works both locally with .streamlit/secrets.toml and on Streamlit Cloud)
def get_secret(key: str, default: str = "") -> str:
    """Get secret from st.secrets or environment variable."""
    try:
        return st.secrets.get(key, default)
    except Exception:
        import os
        return os.getenv(key, default)
# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def validate_csv(df: pd.DataFrame) -> tuple[bool, str]:
    """Validate uploaded CSV has required columns."""
    required_cols = {"website"}
    cols_lower = {c.lower().strip() for c in df.columns}
    missing = required_cols - cols_lower
    if missing:
        return False, f"Missing required columns: {missing}. Need at least 'website'."
    if df.empty:
        return False, "CSV is empty."
    return True, "OK"


def clean_website(url: str) -> str:
    """Normalize website URL."""
    if not isinstance(url, str):
        return ""
    url = url.strip()
    if not url:
        return ""
    # Add scheme if missing
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    # Remove trailing slash
    url = url.rstrip("/")
    return url


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return ""
    # Remove scheme
    domain = re.sub(r"^https?://", "", url, flags=re.I)
    # Remove path/query
    domain = domain.split("/")[0].split("?")[0].split("#")[0]
    # Remove www prefix
    domain = re.sub(r"^www\.", "", domain, flags=re.I)
    return domain.lower()


def dedupe_by_domain(df: pd.DataFrame, website_col: str = "website") -> pd.DataFrame:
    """Keep first row per unique domain."""
    df = df.copy()
    df["_domain"] = df[website_col].apply(extract_domain)
    df = df.drop_duplicates(subset=["_domain"], keep="first")
    df = df.drop(columns=["_domain"])
    return df.reset_index(drop=True)


# Simple email regex for validation
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
# =============================================================================
# LLM-BASED EMAIL EXTRACTION (Cloud API)
# =============================================================================

def extract_emails_with_llm(website: str, company_name: str = "") -> list[str]:
    """
    Use cloud LLM to guess likely email patterns for a domain.
    Returns list of guessed emails (not verified).
    """
    provider = get_secret("LLM_PROVIDER", "groq").lower()
    api_key = get_secret(f"{provider.upper()}_API_KEY", "")
    
    if not api_key:
        return []
    
    domain = extract_domain(website)
    if not domain:
        return []
    
    prompt = f'''Given the company domain "{domain}"{" and name " + company_name if company_name else ""}, 
    list the most likely 3-5 business email addresses (e.g., info@, hello@, contact@, sales@, support@).
    Return ONLY a JSON array of email strings. No explanation.'''
    
    try:
        if provider == "openai" and HAS_OPENAI:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=get_secret("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            )
            content = response.choices[0].message.content
            
        elif provider == "groq" and HAS_GROQ:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=get_secret("GROQ_MODEL", "llama-3.1-8b-instant"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            )
            content = response.choices[0].message.content
            
        elif provider == "anthropic" and HAS_ANTHROPIC:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=get_secret("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
                max_tokens=200,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
            
        else:
            return []
        
        # Parse JSON array from response
        import json
        emails = json.loads(content.strip())
        if isinstance(emails, list):
            return [e for e in emails if is_valid_email(e)]
        return []
        
    except Exception as e:
        st.warning(f"LLM extraction failed for {domain}: {e}")
        return []


def is_valid_email(email: str) -> bool:
    """Basic email validation."""
    if not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


# =============================================================================
# EMAIL PATTERN GENERATION (Fallback - no API needed)
# =============================================================================

COMMON_PREFIXES = [
    "info", "hello", "contact", "sales", "support", "team", "hr", "careers",
    "press", "media", "partnerships", "business", "inquiries", "admin",
    "office", "mail", "enquiries", "general", "help", "service"
]

def generate_email_patterns(domain: str, first_name: str = "", last_name: str = "") -> list[str]:
    """Generate common email patterns for a domain."""
    emails = []
    domain = domain.lower()
    
    # Generic role-based
    for prefix in COMMON_PREFIXES:
        emails.append(f"{prefix}@{domain}")
    
    # Name-based patterns if names provided
    if first_name and last_name:
        fn = first_name.lower().strip()
        ln = last_name.lower().strip()
        patterns = [
            f"{fn}.{ln}@{domain}",
            f"{fn}{ln}@{domain}",
            f"{fn[0]}{ln}@{domain}",
            f"{fn}.{ln[0]}@{domain}",
            f"{fn}_{ln}@{domain}",
            f"{ln}.{fn}@{domain}",
            f"{ln}{fn}@{domain}",
        ]
        emails = patterns + emails
    
    return emails