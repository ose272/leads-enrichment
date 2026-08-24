from storage import LeadStore

store = LeadStore('leads.db')
leads = store.connection.execute("""
    SELECT id, company, email, status 
    FROM leads 
    WHERE id IN (1831, 1836)
""").fetchall()

for l in leads:
    print(f"ID: {l['id']}, Company: {l['company']}, Email: '{l['email']}', Status: {l['status']}")