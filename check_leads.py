import sqlite3

conn = sqlite3.connect('leads.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Total count
c.execute('SELECT COUNT(*) FROM leads')
total = c.fetchone()[0]
print(f'Total leads: {total}')

# Status breakdown
print('\nSTATUS BREAKDOWN:')
c.execute('SELECT status, COUNT(*) as cnt FROM leads GROUP BY status')
for r in c.fetchall():
    print(f'  {r[0]}: {r[1]}')

# Detailed leads
print('\nLEADS (most recent first):')
c.execute('''SELECT id, company, website, email, scraped_summary, status, 
                  followup_count, last_contacted_at, created_at 
           FROM leads ORDER BY created_at DESC''')
rows = c.fetchall()
for r in rows:
    summary = r['scraped_summary'][:80] if r['scraped_summary'] else 'NONE'
    print(f'  ID:{r["id"]} | {r["company"] or "N/A"} | website:{r["website"] or "NONE"} | email:{r["email"] or "NONE"} | status:{r["status"]} | followup:{r["followup_count"]} | summary:{summary}')

# Check for leads with websites but no email
print('\n--- Leads with website but NO email ---')
c.execute('''SELECT id, company, website, status FROM leads 
           WHERE website IS NOT NULL AND website != '' 
           AND (email IS NULL OR email = '')''')
rows = c.fetchall()
if rows:
    for r in rows:
        print(f'  ID:{r["id"]} | {r["company"]} | website:{r["website"]} | status:{r["status"]}')
else:
    print('  None')

# Check for leads with scraped_summary but no email
print('\n--- Leads with scraped_summary but NO email ---')
c.execute('''SELECT id, company, website, email, status FROM leads 
           WHERE scraped_summary IS NOT NULL AND scraped_summary != '' 
           AND (email IS NULL OR email = '')''')
rows = c.fetchall()
if rows:
    for r in rows:
        print(f'  ID:{r["id"]} | {r["company"]} | website:{r["website"]} | email:{r["email"]} | status:{r["status"]}')
else:
    print('  None')

conn.close()