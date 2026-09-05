import pathlib

p = pathlib.Path('c:/Users/HP/Desktop/AUTOMATION 1/dashboard.py')
content = p.read_text(encoding='utf-8')
lines = content.split('\n')

report_start = None
for i, line in enumerate(lines):
    if 'elif page == "ðŸ“ˆ Reports":' in line:
        report_start = i
        break

pre_reports = lines[:report_start]