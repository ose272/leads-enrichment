import sqlite3
conn = sqlite3.connect('c:/Users/HP/Desktop/AUTOMATION 1/leads.db')
cursor = conn.cursor()
cursor.execute('SELECT id, raw_data FROM leads WHERE id >= 396 LIMIT 5')
for row in cursor.fetchall():
    print(f'ID {row[0]}: {row[1][:200]}')
conn.close()