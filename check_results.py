from storage import LeadStore

store = LeadStore('leads.db')
leads = store.connection.execute("""
    SELECT id, company, website, email, status, scraped_summary 
    FROM leads 
    WHERE status != 'new'
""").fetchall()

for l in leads:
    summary = l['scraped_summary'][:50] if l['scraped_summary'] else 'N/A'
    print(f"ID: {l['id']}, Company: {l['company']}, Email: {l['email']}, Status: {l['status']}, Summary: {summary}")

# Also check counts
total = store.connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
new_count = store.connection.execute("SELECT COUNT(*) FROM leads WHERE status = 'new'").fetchone()[0]
emailed = store.connection.execute("SELECT COUNT(*) FROM leads WHERE status = 'emailed'").fetchone()[0]
no_email = store.connection.execute("SELECT COUNT(*) FROM leads WHERE status = 'no_email_found'").fetchone()[0]

print(f"\nTotal: {total}, New: {new_count}, Emailed: {emailed}, No Email: {no_email}")