from src.tracker import LeadStore
import sqlite3

store = LeadStore('outreach.db')
conn = sqlite3.connect('outreach.db')
conn.row_factory = sqlite3.Row
stats = {}
stats['total'] = conn.execute('SELECT COUNT(*) FROM leads').fetchone()[0]
status_counts = conn.execute('SELECT status, COUNT(*) as count FROM leads GROUP BY status').fetchall()
stats['by_status'] = {row['status']: row['count'] for row in status_counts}
print('Stats:', stats)
conn.close()
store.close()