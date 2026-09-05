content = open('c:/Users/HP/Desktop/AUTOMATION 1/src/main.py', encoding='utf-8').read()

# Use the exact text from the file (with escaped single quotes)
old = """return sent


def run_followup_phase(store: LeadStore) -> int:
    \"\"\"Send follow-ups to leads that haven\\'t replied.

    Returns:
        Number of follow-ups sent
    \"\"\"
    # Get leads in \\'sent\\' or \\'follow_up_1\\' status older than 2 days with no reply
    leads = store.get_leads_for_followup(days=2)"""

new = """return sent


def run_reply_phase(store: LeadStore) -> int:
    \"\"\"Check for replies and update lead statuses.

    Returns:
        Number of replies processed
    \"\"\"
    return check_replies(store)


def run_followup_phase(store: LeadStore) -> int:
    \"\"\"Send follow-ups to leads that haven\\'t replied.

    Returns:
        Number of follow-ups sent
    \"\"\"
    # Get leads in \\'sent\\' or \\'follow_up_1\\' status older than 2 days with no reply
    leads = store.get_leads_for_followup(days=2)"""

if old in content:
    content = content.replace(old, new)
    open('c:/Users/HP/Desktop/AUTOMATION 1/src/main.py', 'w', encoding='utf-8').write(content)
    print('Fixed!')
else:
    print('Pattern not found')
    idx = content.find('def run_followup_phase')
    if idx >= 0:
        print('Context:', repr(content[idx-100:idx+300]))