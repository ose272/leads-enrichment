"""Operator dashboard for the SE Global outreach workflow."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "outreach.db"
UPLOAD_DIR = ROOT / "data" / "uploads"
LOG_DIR = ROOT / "logs"
RUN_LOG = LOG_DIR / "dashboard_run.log"

st.set_page_config(page_title="SE Global Operations", page_icon="📊", layout="wide")


def env_values() -> dict[str, str]:
    return {key: value or "" for key, value in dotenv_values(ROOT / ".env").items()}


def db_frame(query: str, params: tuple = ()) -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as connection:
        return pd.read_sql_query(query, connection, params=params)


def status_counts() -> pd.DataFrame:
    return db_frame("SELECT status, COUNT(*) AS count FROM leads GROUP BY status ORDER BY count DESC")


def latest_leads() -> pd.DataFrame:
    return db_frame(
        """SELECT id, website, contact_email, status, follow_up_count,
                  last_contacted_date
           FROM leads ORDER BY id DESC LIMIT 100"""
    )


def process_running() -> bool:
    process = st.session_state.get("run_process")
    return process is not None and process.poll() is None


def start_run(csv_path: Path, live_mode: bool) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    environment = os.environ.copy()
    environment.update(env_values())
    environment["DRY_RUN"] = "false" if live_mode else "true"
    command = [
        sys.executable,
        str(ROOT / "src" / "main.py"),
        "--mode",
        "full",
        "--csv",
        str(csv_path),
        "--db",
        str(DB_PATH),
    ]
    log_handle = open(RUN_LOG, "a", encoding="utf-8")
    log_handle.write(f"\n--- Run started {datetime.now().isoformat()} ---\n")
    log_handle.flush()
    st.session_state.run_process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    st.session_state.run_log_handle = log_handle
    st.session_state.run_started = datetime.now().isoformat(timespec="seconds")


def stage_upload(upload: object, preview: pd.DataFrame, batch_size: int) -> Path:
    """Persist the selected batch once per uploaded file."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    signature = f"{upload.name}:{upload.size}:{batch_size}"
    if st.session_state.get("upload_signature") != signature:
        saved = UPLOAD_DIR / f"leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        preview.head(int(batch_size)).to_csv(saved, index=False)
        st.session_state.upload_signature = signature
        st.session_state.selected_csv = str(saved)
    return Path(st.session_state.selected_csv)


def main() -> None:
    st.title("📊 SE Global Outreach Operations")
    st.caption("Upload leads, scrape contacts, send controlled batches, and monitor reports.")

    values = env_values()
    dry_run_configured = values.get("DRY_RUN", "true").lower() == "true"
    process_active = process_running()

    if process_active:
        st.warning(f"Automation is running (started {st.session_state.get('run_started', 'recently')}).")
    else:
        st.success("Automation is idle and ready.")

    counts = status_counts()
    count_map = dict(zip(counts.get("status", []), counts.get("count", [])))
    metrics = st.columns(5)
    for column, label, key in zip(
        metrics,
        ["Total", "New", "Scraped", "Sent", "Simulated"],
        ["total", "new", "scraped", "sent", "dry_run"],
    ):
        value = int(counts["count"].sum()) if label == "Total" and not counts.empty else count_map.get(key, 0)
        column.metric(label, value)

    st.divider()
    upload = st.file_uploader("Upload a CSV (website or email column required)", type=["csv"])
    batch_size = st.number_input("Daily batch size", min_value=1, max_value=70, value=70, step=1)
    if upload is not None:
        try:
            preview = pd.read_csv(upload)
            valid = any(column.lower().strip() in ("website", "url", "email", "contact_email") for column in preview.columns)
            if not valid:
                st.error("CSV must contain a website or email column.")
            else:
                st.write(f"{len(preview)} rows loaded; the next run will use up to {batch_size}.")
                st.dataframe(preview.head(10), use_container_width=True, hide_index=True)
                staged = stage_upload(upload, preview, int(batch_size))
                st.success(f"Staged {len(preview.head(int(batch_size)))} leads from `{staged.name}`.")
        except Exception as exc:
            st.error(f"Could not read CSV: {exc}")

    selected_csv = st.session_state.get("selected_csv")
    st.write(f"Selected file: `{selected_csv or 'none'}`")
    live_mode = st.checkbox("Enable live sending (real emails)", value=not dry_run_configured)
    if live_mode:
        st.error("Live mode sends real external emails. Verify the selected CSV before starting.")
    live_confirm = st.checkbox(
        "I confirm this batch is approved for live delivery.",
        disabled=not live_mode,
    )
    if process_active:
        st.info("A run is already active. Refresh to monitor it.")
    elif not selected_csv:
        st.info("Upload a valid CSV before starting.")
    elif live_mode and not live_confirm:
        st.info("Live mode requires delivery confirmation before starting.")
    if st.button("▶ Start automation", type="primary"):
        if process_active:
            st.error("A run is already active. Wait for it to finish before starting another.")
        elif not selected_csv:
            st.error("Upload a valid CSV first, then click Start automation again.")
        elif live_mode and not live_confirm:
            st.error("Tick the live-delivery confirmation box before starting.")
        elif not Path(selected_csv).is_file():
            st.error("The staged CSV is no longer available. Upload it again.")
        else:
            start_run(Path(selected_csv), live_mode)
            st.success("Automation started. Use Refresh to monitor progress.")
            st.rerun()

    if st.button("🔄 Refresh"):
        st.rerun()

    st.subheader("Pipeline status")
    if counts.empty:
        st.info("No leads have been loaded yet.")
    else:
        st.bar_chart(counts.set_index("status")["count"])
        st.dataframe(latest_leads(), use_container_width=True, hide_index=True)

    st.subheader("Run log")
    if RUN_LOG.exists():
        st.code(RUN_LOG.read_text(encoding="utf-8", errors="replace")[-12000:], language="text")
    else:
        st.info("No automation run log yet.")


if __name__ == "__main__":
    main()
