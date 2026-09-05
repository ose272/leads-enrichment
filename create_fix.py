import pathlib

# Read fix1.py (has the pre-reports extraction logic)
fix1 = pathlib.Path('c:/Users/HP/Desktop/AUTOMATION 1/fix1.py').read_text(encoding='utf-8')

# Read rest_part1.txt
part1 = pathlib.Path('c:/Users/HP/Desktop/AUTOMATION 1/rest_part1.txt').read_text(encoding='utf-8')

# Read rest_part2.txt
part2 = pathlib.Path('c:/Users/HP/Desktop/AUTOMATION 1/rest_part2.txt').read_text(encoding='utf-8')

# Write the complete script
script = fix1 + '\n\nreports_page = """' + part1 + '\n' + part2 + '\n"""\n\n# Combine pre_reports with the new reports_page\nnew_content = \'\\n\'.join(pre_reports) + \'\\n\' + reports_page\np.write_text(new_content, encoding=\'utf-8\')\nprint(\'Fixed! Total length:\', len(new_content))'

pathlib.Path('c:/Users/HP/Desktop/AUTOMATION 1/run_fix.py').write_text(script, encoding='utf-8')
print('Script written')