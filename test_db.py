from src.tracker import LeadStore

store = LeadStore('outreach.db')
leads = store.get_leads_by_status('new')
print('New leads:', len(leads))
for l in leads:
    print(f'  {l.id}: {l.contact_email} - {l.store_name} (seed: {l.paraphrase_seed})')
store.close()