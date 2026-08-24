from storage import LeadStore

store = LeadStore('leads.db')
leads = store.get_leads_for_outreach()
print(f"Leads for outreach: {len(leads)}")
for l in leads:
    print(f"  ID: {l['id']}, Email: {l['email']}, Company: {l['company']}")