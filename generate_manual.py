"""Generate the operator manual PDF for the outreach dashboard."""

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "SE_Global_Outreach_Operations_Manual.pdf"


def build_manual() -> None:
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=LETTER,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )
    story = [
        Paragraph("SE Global Outreach Operations Manual", styles["Title"]),
        Paragraph("Version 1.0", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("1. Purpose", styles["Heading1"]),
        Paragraph(
            "This system manages lead upload, website and email enrichment, personalized drafting, "
            "controlled sending, and weekly performance reporting.",
            styles["BodyText"],
        ),
        Paragraph("2. Starting the dashboard", styles["Heading1"]),
        Paragraph(
            "From the project folder run: streamlit run operations_dashboard.py. "
            "Open the local URL shown by Streamlit. The dashboard uses outreach.db and writes run details to logs/dashboard_run.log.",
            styles["BodyText"],
        ),
        Paragraph("3. Preparing credentials", styles["Heading1"]),
        Paragraph(
            "Put SMTP, IMAP, Groq, and WhatsApp settings in the local .env file. "
            "Use DRY_RUN=true for testing. Set DRY_RUN=false only after reviewing a batch and confirming live delivery.",
            styles["BodyText"],
        ),
        Paragraph("4. Uploading leads", styles["Heading1"]),
        Paragraph(
            "Upload a CSV containing website or email. Optional columns include company, first_name, last_name, and phone. "
            "The dashboard limits each saved run to the selected daily batch size, up to 70 leads.",
            styles["BodyText"],
        ),
        Paragraph("5. Running automation", styles["Heading1"]),
        Paragraph(
            "Save the CSV, select dry-run or live mode, and start automation. The workflow loads leads, scrapes websites, "
            "uses supplied emails when present, drafts with Groq when available, falls back safely when unavailable, "
            "sends eligible emails, and generates report files.",
            styles["BodyText"],
        ),
        Paragraph("6. Monitoring", styles["Heading1"]),
        Paragraph(
            "The status cards show total, new, scraped, sent, and simulated sends. "
            "The pipeline chart and lead table show current database state. The run log shows scraper, Groq, SMTP, "
            "and report events. Refresh the page to update the view.",
            styles["BodyText"],
        ),
        Paragraph("7. Weekly reports", styles["Heading1"]),
        Paragraph(
            "Each full run produces weekly_report.csv and weekly_report.html with lead, scrape, draft, send, reply, "
            "follow-up, and sentiment statistics.",
            styles["BodyText"],
        ),
        Paragraph("8. Safety checklist", styles["Heading1"]),
        Paragraph(
            "Start with DRY_RUN=true. Review the selected CSV. Confirm the daily batch size. "
            "Verify the SMTP sender identity and selected recipients. Only then enable live mode.",
            styles["BodyText"],
        ),
        Paragraph("9. Useful commands", styles["Heading1"]),
        Paragraph("python src/main.py --mode full --csv path\\to\\leads.csv", styles["Code"]),
        Paragraph("streamlit run operations_dashboard.py", styles["Code"]),
    ]
    document.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    build_manual()
