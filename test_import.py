import pandas as pd
from src.tracker import LeadStore

store = LeadStore("outreach.db")
df = pd.read_csv("test_prederived.csv")
imported = 0
skipped = 0

for _, row in df.iterrows():
    website = str(row.get('website', '')).strip()
    if not website:
        continue
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    existing = store.get_lead_by_website(website)
    if existing:
        skipped += 1
        continue
    contact_email = str(row.get('contact_email', '')).strip() or None
    company_name = str(row.get('company_name', '')).strip() or None
    first_name = str(row.get('first_name', '')).strip() or None
    last_name = str(row.get('last_name', '')).strip() or None
    row_has_email = contact_email is not None
    row_has_names = any(x is not None for x in [company_name, first_name, last_name])
    row_is_pre_derived = row_has_email and row_has_names
    lead_id = store.add_lead(
        website=website,
        contact_email=contact_email or '',
        company_name=company_name or '',
        first_name=first_name or '',
        last_name=last_name or ''
    )
    if row_is_pre_derived:
        store.update_status(lead_id, 'scraped', contact_email=contact_email)
    imported += 1

print(f'Imported {imported} new leads, skipped {skipped} duplicates')

# Verify status
for _, row in df.iterrows():
    website = str(row.get('website', '')).strip()
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    lead = store.get_lead_by_website(website)
    print(f'  {website}: status={lead.status}, email={lead.contact_email}, name={lead.company_name} {lead.first_name} {lead.last_name}')