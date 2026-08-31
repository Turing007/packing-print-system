import sys, os
sys.stdout.reconfigure(encoding='utf-8')
p = os.path.join(os.environ['USERPROFILE'], 'Documents', '\u88c5\u7bb1\u6253\u5370\u7a0b\u5e8f', 'main.py')
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()
changes = 0

# === CHANGE 1: Side-by-side layout ===
old = '''ttk.Label(pt, text=\"""\u88c5\u7bb1\u9879\u76ee\u5217\u8868\""", font=(\"""\Microsoft YaHei\"",12,\""bold\""")).pack(anchor=tk.W,pady=(0,3))

        pkf = ttk.Frame(pt)
        pkf.pack(fill=tk.BOTH, expand=True)
        pkcols = (\"""recipient\"",\""order\"",\""name\"",\""sku\"",\""qty\"",\""per\""")
        self.pktree = ttk.Treeview(pkf, columns=pkcols, show=\""headings\"", height=6)
        pkhdrs = [\"""\u6536\u4ef6\u4eba\"",\""\u8ba2\u5355\u53f7\"",\""\u54c1\u540d\"",\""SKU\"",\""\u603b\u6570\"",\""\u6bcf\u7bb1\"""]
        for i,h in enumerate(pkhdrs):
            self.pktree.heading(pkcols[i], text=h)
        pkw = [80,100,120,80,60,60]
        for i,w in enumerate(pkw):
            self.pktree.column(pkcols[i], width=w, minwidth=40)
        pkvsb = ttk.Scrollbar(pkf, orient=tk.VERTICAL, command=self.pktree.yview)
        self.pktree.configure(yscrollcommand=pkvsb.set)
        self.pktree.grid(row=0,column=0,sticky=\""nsew\""")
        pkvsb.grid(row=0,column=1,sticky=\""ns\""")
        pkf.grid_rowconfigure(0,weight=1)
        pkf.grid_columnconfigure(0,weight=1)
        self.pktree.bind(\""<<TreeviewSelect>>\"", self.on_packing_select)

        # \u88c5\u7bb1\u8f93\u5165
        inf = ttk.LabelFrame(pt, text=\"""\u6dfb\u52a0\u88c5\u7bb1\u9879\"", padding=8)'''

new = '''mid_pane = ttk.PanedWindow(pt, orient=tk.HORIZONTAL)
        mid_pane.pack(fill=tk.BOTH, expand=True)

        # \u5de6\u4fa7\uff1a\u88c5\u7bb1\u9879\u76ee\u5217\u8868
        pk_frame = ttk.Frame(mid_pane)
        mid_pane.add(pk_frame, weight=1)
        ttk.Label(pk_frame, text=\"""\u88c5\u7bb1\u9879\u76ee\u5217\u8868\"", font=(\"""Microsoft YaHei\"",12,\""bold\""")).pack(anchor=tk.W)

        pkf = ttk.Frame(pk_frame)
        pkf.pack(fill=tk.BOTH, expand=True)
        pkcols = (\"""recipient\"",\""order\"",\""name\"",\""sku\"",\""qty\"",\""per\""")
        self.pktree = ttk.Treeview(pkf, columns=pkcols, show=\""headings\"", height=8)
        pkhdrs = [\"""\u6536\u4ef6\u4eba\"",\""\u8ba2\u5355\u53f7\"",\""\u54c1\u540d\"",\""SKU\"",\""\u603b\u6570\"",\""\u6bcf\u7bb1\"""]
        for i,h in enumerate(pkhdrs):
            self.pktree.heading(pkcols[i], text=h)
        pkw = [80,100,120,80,60,60]
        for i,w in enumerate(pkw):
            self.pktree.column(pkcols[i], width=w, minwidth=40)
        pkvsb = ttk.Scrollbar(pkf, orient=tk.VERTICAL, command=self.pktree.yview)
        self.pktree.configure(yscrollcommand=pkvsb.set)
        self.pktree.grid(row=0,column=0,sticky=\""nsew\""")
        pkvsb.grid(row=0,column=1,sticky=\""ns\""")
        pkf.grid_rowconfigure(0,weight=1)
        pkf.grid_columnconfigure(0,weight=1)
        self.pktree.bind(\""<<TreeviewSelect>>\"", self.on_packing_select)

        # \u53f3\u4fa7\uff1a\u8ba2\u5355\u5386\u53f2
        oh_frame = ttk.Frame(mid_pane)
        mid_pane.add(oh_frame, weight=1)
        ttk.Label(oh_frame, text=\"""\u8ba2\u5355\u5386\u53f2\"", font=(\"""Microsoft YaHei\"",12,\""bold\""")).pack(anchor=tk.W)

        ohf = ttk.Frame(oh_frame)
        ohf.pack(fill=tk.BOTH, expand=True)
        ohcols = (\"""recipient\"",\""order\"",\""count\"",\""time\""")
        self.ohtree = ttk.Treeview(ohf, columns=ohcols, show=\""tree\"", height=8, selectmode=\""extended\""")
        ohhdrs = [\"""\u6536\u4ef6\u4eba\"",\""\u8ba2\u5355\u53f7\"",\""\u4ea7\u54c1\u6570\"",\""\u65f6\u95f4\"""]
        for i,h in enumerate(ohhdrs):
            self.ohtree.heading(ohcols[i], text=h)
        ohw = [80,120,60,130]
        for i,w in enumerate(ohw):
            self.ohtree.column(ohcols[i], width=w, minwidth=40)
        ohvsb = ttk.Scrollbar(ohf, orient=tk.VERTICAL, command=self.ohtree.yview)
        self.ohtree.configure(yscrollcommand=ohvsb.set)
        self.ohtree.grid(row=0,column=0,sticky=\""nsew\""")
        ohvsb.grid(row=0,column=1,sticky=\""ns\""")
        ohf.grid_rowconfigure(0,weight=1)
        ohf.grid_columnconfigure(0,weight=1)

        # \u88c5\u7bb1\u8f93\u5165
        inf = ttk.LabelFrame(pt, text=\"""\u6dfb\u52a0\u88c5\u7bb1\u9879\"", padding=8)'''

if old in c:
    c = c.replace(old, new)
    changes += 1
    print('1. Side-by-side layout applied')
else:
    print('1. FAILED: side-by-side layout')
    # Debug
    print('Looking for:', repr(old[:100]))

# === CHANGE 2: Remove old standalone ohf section, replace with button bar with "重新装箱"
old2 = '''        # \u8ba2\u5355\u5386\u53f2
        ttk.Label(pt, text=\"""\u8ba2\u5355\u5386\u53f2\"", font=(\"""Microsoft YaHei\"",12,\""bold\""")).pack(anchor=tk.W,pady=(5,0))
        ohf = ttk.Frame(pt)
        ohf.pack(fill=tk.BOTH, expand=True)
        ohcols = (\"""recipient\"",\""order\"",\""count\"",\""time\""")
        self.ohtree = ttk.Treeview(ohf, columns=ohcols, show=\""tree\"", height=6, selectmode=\""extended\""")
        ohhdrs = [\"""\u6536\u4ef6\u4eba\"",\""\u8ba2\u5355\u53f7\"",\""\u4ea7\u54c1\u6570\"",\""\u65f6\u95f4\"""]
        for i,h in enumerate(ohhdrs):
            self.ohtree.heading(ohcols[i], text=h)
        ohw = [80,120,60,130]
        for i,w in enumerate(ohw):
            self.ohtree.column(ohcols[i], width=w, minwidth=40)
        ohvsb = ttk.Scrollbar(ohf, orient=tk.VERTICAL, command=self.ohtree.yview)
        self.ohtree.configure(yscrollcommand=ohvsb.set)
        self.ohtree.grid(row=0,column=0,sticky=\""nsew\""")
        ohvsb.grid(row=0,column=1,sticky=\""ns\""")
        ohf.grid_rowconfigure(0,weight=1)
        ohf.grid_columnconfigure(0,weight=1)

        ohbf = ttk.Frame(pt)
        ohbf.pack(fill=tk.X, pady=2)
        ttk.Button(ohbf,text=\"""\u6279\u91cf\u8ba1\u7b97\u88c5\u7bb1\"",command=self.batch_calculate_from_history,width=14).pack(side=tk.LEFT,padx=2)
        ttk.Button(ohbf,text=\"""\u5220\u9664\u9009\u4e2d\"",command=self.delete_selected_order_history,width=10).pack(side=tk.LEFT,padx=2)'''

new2 = '''        ohbf = ttk.Frame(pt)
        ohbf.pack(fill=tk.X, pady=2)
        ttk.Button(ohbf,text=\"""\u91cd\u65b0\u88c5\u7bb1\"",command=self.reload_from_order_history,width=10).pack(side=tk.LEFT,padx=2)
        ttk.Button(ohbf,text=\"""\u6279\u91cf\u8ba1\u7b97\u88c5\u7bb1\"",command=self.batch_calculate_from_history,width=14).pack(side=tk.LEFT,padx=2)
        ttk.Separator(ohbf,orient=tk.VERTICAL).pack(side=tk.LEFT,fill=tk.Y,padx=5)
        ttk.Button(ohbf,text=\"""\u5220\u9664\u9009\u4e2d\"",command=self.delete_selected_order_history,width=10).pack(side=tk.LEFT,padx=2)'''

if old2 in c:
    c = c.replace(old2, new2)
    changes += 1
    print('2. Button bar updated')
else:
    print('2. FAILED: button bar')
    # Find the ohbf creation
    idx = c.find('ohbf = ttk.Frame')
    if idx >= 0:
        print('  Found ohbf at', idx)
        print('  Context:', c[idx:idx+300])

# === CHANGE 3: Modify batch_calculate_from_history to calculate per-order ===
old3 = '''        self.packing_items = new_packing_items
        self.current_boxes = calculate_boxes(temp_products, self.merge_tail.get())
        self.refresh_packing_table()
        self.refresh_box_table()
        messagebox.showinfo(\""\u6210\u529f\"", f\""\u5df2\u52a0\u8f7d {len(temp_products)} \u4e2a\u4ea7\u54c1\uff0c\u751f\u6210 {len(self.current_boxes)} \u7bb1\"")'''

new3 = '''        # \u6309\u8ba2\u5355\u53f7\u5206\u5f00\u8ba1\u7b97\u7bb1\u6570
        all_boxes = []
        order_groups = {}
        for tp in temp_products:
            key = (tp.recipient, tp.order_no)
            if key not in order_groups: order_groups[key] = []
            order_groups[key].append(tp)
        for (rec, ord_no), prods in order_groups.items():
            order_boxes = calculate_boxes(prods, self.merge_tail.get())
            all_boxes.extend(order_boxes)
        self.packing_items = new_packing_items
        self.current_boxes = all_boxes
        self.refresh_packing_table()
        self.refresh_box_table()
        messagebox.showinfo(\""\u6210\u529f\"", f\""\u5df2\u52a0\u8f7d {len(temp_products)} \u4e2a\u4ea7\u54c1\uff0c\u751f\u6210 {len(self.current_boxes)} \u7bb1 (\u6309\u8ba2\u5355\u5206\u5f00\u8ba1\u7b97)\""")'''

if old3 in c:
    c = c.replace(old3, new3)
    changes += 1
    print('3. batch_calculate per-order')
else:
    print('3. FAILED: batch calc')
    # Find the old3 content
    if 'self.packing_items = new_packing_items' in c:
        print('  Found packing_items assignment')

# === CHANGE 4: Add reload_from_order_history method before delete_selected_order_history ===
old4 = '''    def delete_selected_order_history(self):'''

new4 = '''    def reload_from_order_history(self):
        \"\"\"\u4ece\u5386\u53f2\u8ba2\u5355\u91cd\u65b0\u88c5\u7bb1\uff1a\u5c06\u9009\u4e2d\u8ba2\u5355\u7684\u4ea7\u54c1\u52a0\u8f7d\u5230\u88c5\u7bb1\u5217\u8868\"\"\"
        sel = self.ohtree.selection()
        if not sel:
            messagebox.showinfo(\""\u63d0\u793a\"",\""\u8bf7\u5728\u8ba2\u5355\u5386\u53f2\u4e2d\u9009\u62e9\u4e00\u4e2a\u8ba2\u5355\"")
            return
        history = load_order_history()
        new_items = []
        for iid in sel:
            parent = self.ohtree.parent(iid)
            real_iid = parent if parent else iid
            idx_str = real_iid.replace(\""oh_\", \""")
            try:
                idx = int(idx_str)
            except: continue
            if idx < 0 or idx >= len(history): continue
            h = history[idx]
            for item in h.get(\""items\", []):
                new_items.append({
                    \""name\"": item[\""name\""], \""sku\"": item.get(\""sku\",\"""),
                    \""per\"": item[\""per\""], \""recipient\"": h[\""recipient\""],
                    \""order\"": h[\""order_no\""], \""qty\"": item[\""qty\""]})
        if not new_items:
            messagebox.showinfo(\""\u63d0\u793a\"",\""\u6ca1\u6709\u53ef\u52a0\u8f7d\u7684\u8ba2\u5355\u6570\u636e\"")
            return
        self.packing_items = new_items
        self.refresh_packing_table()
        messagebox.showinfo(\""\u6210\u529f\"", f\""\u5df2\u52a0\u8f7d {len(new_items)} \u4e2a\u4ea7\u54c1\u5230\u88c5\u7bb1\u5217\u8868\")

    def delete_selected_order_history(self):'''

if old4 in c:
    c = c.replace(old4, new4)
    changes += 1
    print('4. reload_from_order_history added')
else:
    print('4. FAILED: reload method')

# === CHANGE 5: Refresh order history after reload ===
# The refresh_ methods already handle this. No extra change needed.

with open(p, 'w', encoding='utf-8') as f:
    f.write(c)
try:
    compile(c, 'main.py', 'exec')
    print(f'{changes} changes applied. Syntax: OK')
except SyntaxError as e:
    print(f'Syntax error line {e.lineno}: {e.msg}')
    lines = c.split('\n')
    for j in range(max(0,e.lineno-2), min(len(lines), e.lineno+3)):
        m = '>>>' if j+1 == e.lineno else '   '
        print(f'{m} {j+1}: {lines[j][:120]}')
