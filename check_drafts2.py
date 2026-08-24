import imaplib
import os
import email
from dotenv import load_dotenv

load_dotenv('c:/Users/HP/Desktop/AUTOMATION 1/.env')

client = imaplib.IMAP4_SSL(os.getenv('IMAP_HOST'), int(os.getenv('IMAP_PORT')))
client.login(os.getenv('IMAP_USER'), os.getenv('IMAP_PASSWORD'))

status, _ = client.select('[Gmail]/Drafts', readonly=True)
print('Select status:', status)

status, data = client.search(None, 'ALL')
print('Search status:', status)
msg_ids = data[0].split()
print(f'Total messages: {len(msg_ids)}')

for msg_id in msg_ids:
    status, msg_data = client.fetch(msg_id, '(RFC822)')
    raw = msg_data[0][1]
    msg = email.message_from_bytes(raw)
    
    subject = msg.get('Subject', '')
    print(f'\n--- Message {msg_id.decode()} ---')
    print(f'Subject: {subject}')
    print(f'From: {msg.get("From")}')
    print(f'Date: {msg.get("Date")}')
    
    # Check for attachments
    has_attachment = False
    for part in msg.walk():
        if part.get_content_disposition() == 'attachment':
            filename = part.get_filename()
            print(f'  Attachment: {filename}')
            has_attachment = True
            if filename and 'leads_' in filename.lower():
                print(f'  *** MATCHES leads_ marker! ***')
            if '[NEW LEADS]' in subject.upper():
                print(f'  *** MATCHES [NEW LEADS] subject tag! ***')
    
    if not has_attachment:
        print('  No attachments')

client.logout()