content = open('c:/Users/HP/Desktop/AUTOMATION 1/src/main.py', 'rb').read()

# Exact bytes from the file (1 newline between return sent and def)
old = b'return sent\n\ndef run_followup_phase(store: LeadStore) -> int:\n    """Send follow-ups to leads that haven\\'t replied.\n    \n    Returns:\n        Number of follow-ups sent\n    """\n    # Get leads in \\'sent\\' or \\'follow_up_1\\' status older than 2 days with no reply\n    leads = store.get_leads_for_followup(days=2)'

new = b'return sent\n\ndef run_reply_phase(store: LeadStore) -> int:\n    """Check for replies and update lead statuses.\n    \n    Returns:\n        Number of replies processed\n    """\n    return check_replies(store)\n\ndef run_followup_phase(store: LeadStore) -> int:\n    """Send follow-ups to leads that haven\\'t replied.\n    \n    Returns:\n        Number of follow-ups sent\n    """\n    # Get leads in \\'sent\\' or \\'follow_up_1\\' status older than 2 days with no reply\n    leads = store.get_leads_for_followup(days=2)'

if old in content:
    content = content.replace(old, new)
    open('c:/Users/HP/Desktop/AUTOMATION 1/src/main.py', 'wb').write(content)
    print('Fixed!')
else:
    print('Pattern not found')
    idx = content.find(b'def run_followup_phase')
    if idx >= 0:
        print('Context:', repr(content[idx-100:idx+300]))