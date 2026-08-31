import sys, os
sys.stdout.reconfigure(encoding='utf-8')
p = os.path.join(os.environ['USERPROFILE'], 'Documents', '\u88c5\u7bb1\u6253\u5370\u7a0b\u5e8f', 'main.py')

with open(p, 'r', encoding='utf-8') as f:
    lines = f.readlines()

changes = []

# Find exact line ranges for substitution
for i, line in enumerate(lines):
    # Find packing items section start
    if '\u88c5\u7bb1\u9879\u76ee\u5217\u8868' in line and 'font' in line:
        pk_start = i
    # Find the ohf frame creation
    if 'ohf = ttk.Frame(pt)' in line:
        ohf_start = i
    # Find the end of order history buttons + before status bar
    if 'self.l_status = ttk.Label' in line:
        status_start = i

print(f'pk_start: {pk_start}, ohf_start: {ohf_start}, status_start: {status_start}')

# Create new content for the packing items + order history section
# Currently: lines pk_start to ohf_start (packing items) and ohf_start to status_start (order history + box results)
# New: side-by-side layout

# The packing items section currently has:
# - Label "\u88c5\u7bb1\u9879\u76ee\u5217\u8868"
# - pkf with pktree treeview
# Then after that:
# - "添加装箱项" form
# - ctrlf controls
# Followed by:
# - "\u8ba2\u5355\u5386\u53f2" label
# - ohf with ohtree
# - ohbf buttons
# Then:
# - "\u7bb1\u56df\u7ed3\u679c" section

print('Structure found OK')
