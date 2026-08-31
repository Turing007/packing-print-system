import sys, os
sys.stdout.reconfigure(encoding="utf-8")
p = os.path.join(os.environ["USERPROFILE"], "Documents", "\u88c5\u7bb1\u6253\u5370\u7a0b\u5e8f", "main.py")

with open(p, "r", encoding="utf-8") as f:
    content = f.read()

# Fix all known broken patterns from the v4 generator
import re

# Fix messagebox.showinfo(""...
content = content.replace('showinfo(""\u63d0\u793a"",""', 'showinfo("\u63d0\u793a","')
content = content.replace('showinfo(""\u6210\u529f"", f""', 'showinfo("\u6210\u529f", f"')
content = content.replace('showinfo(""\u63d0\u793a"",""\u6ca1\u6709\u53ef\u52a0\u8f7d\u7684\u8ba2\u5355\u6570\u636e"")', 'showinfo("\u63d0\u793a","\u6ca1\u6709\u53ef\u52a0\u8f7d\u7684\u8ba2\u5355\u6570\u636e")')
content = content.replace('showinfo(""\u63d0\u793a"",""\u8bf7\u5728\u8ba2\u5355\u5386\u53f2\u4e2d\u9009\u62e9\u4e00\u4e2a\u8ba2\u5355"")', 'showinfo("\u63d0\u793a","\u8bf7\u5728\u8ba2\u5355\u5386\u53f2\u4e2d\u9009\u62e9\u4e00\u4e2a\u8ba2\u5355")')

# Fix h.get(""...
content = content.replace('h.get(""items", [])', 'h.get("items", [])')
content = content.replace('h.get(""sku","")', 'h.get("sku","")')

# Fix h[""...]
content = content.replace('h[""order_no""]', 'h["order_no"]')

# Fix .replace("oh_", """)
content = content.replace('replace("oh_", """)', 'replace("oh_", "")')

# Fix duplicate "" around identifiers in dict
content = content.replace('"name": item["name"], "sku": item.get(', '"name": item["name"], "sku": item.get(')
content = content.replace('"per": item["per"], "recipient": h["recipient"]', '"per": item["per"], "recipient": h["recipient"]')

with open(p, "w", encoding="utf-8") as f:
    f.write(content)

try:
    compile(content, "main.py", "exec")
    print("Syntax: OK!")
except SyntaxError as e:
    print(f"Error line {e.lineno}: {e.msg}")
    lines = content.split("\n")
    for k in range(max(0,e.lineno-2), min(len(lines), e.lineno+3)):
        m = ">>>" if k+1 == e.lineno else "   "
        print(f"{m} {k+1}: {lines[k][:150]}")
