import sys, os
sys.stdout.reconfigure(encoding='utf-8')
p = os.path.join(os.environ['USERPROFILE'], 'Documents', '\u88c5\u7bb1\u6253\u5370\u7a0b\u5e8f', 'main.py')
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()

# === CHANGE 1: Side-by-side layout ===
# Replace the packing items section + order history section with combined horizontal layout

# Find the section from '\u88c5\u7bb1\u9879\u76ee\u5217\u8868' label to after ohbf buttons
start_marker = 'ttk.Label(pt, text=\"\u88c5\u7bb1\u9879\u76ee\u5217\u8868\"'
end_marker = 'ttk.Button(ohbf,text=\"\u5220\u9664\u9009\u4e2d\"'
s1 = c.find(start_marker)
s2 = c.find(end_marker)
# Find the end of that line + a few more
e = c.find('\n', s2) + 1
# Find the next blank line or real content
e2 = c.find('\n\n', e) + 2

old_block = c[s1:e+1]
print('OLD BLOCK to replace:')
print(old_block[:200])
print('...')
print(old_block[-200:])
