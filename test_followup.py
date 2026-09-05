from src.tracker import LeadStore

store = LeadStore('outreach.db')
leads = store.get_leads_for_followup(2)
print('Follow-up eligible:', len(leads))
for l in leads:
    print(f'  {l.id}: {l.contact_email} - {l.status} (followup: {l.follow_up_count})')
store.close()