# -*- coding: utf-8 -*-
"""自动装箱打印系统 - 主界面"""
import os
import sys


def _configure_tcl_tk() -> None:
    """Point Tk at the bundled Tcl/Tk trees when running from a frozen build."""

    candidates = []
    if getattr(sys, "frozen", False):
        frozen_root = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        candidates.append(os.path.join(frozen_root, "tcl"))

    base_prefix = getattr(sys, "base_prefix", sys.prefix)
    exec_prefix = getattr(sys, "exec_prefix", sys.prefix)
    candidates.append(os.path.join(base_prefix, "tcl"))
    candidates.append(os.path.join(exec_prefix, "tcl"))

    for root in candidates:
        tcl_dir = os.path.join(root, "tcl8.6")
        tk_dir = os.path.join(root, "tk8.6")
        if os.path.isdir(tcl_dir):
            os.environ["TCL_LIBRARY"] = tcl_dir
        if os.path.isdir(tk_dir):
            os.environ["TK_LIBRARY"] = tk_dir
        if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
            break


_configure_tcl_tk()

import tkinter as tk
from tkinter import ttk, messagebox
import os, tempfile, webbrowser
from datetime import datetime
from product import Product, ProductStore, format_box_sizes
from packing import calculate_boxes, generate_box_label_html, generate_individual_box_labels_html, BoxLabel, merge_selected_tail_boxes as merge_tail_boxes
from storage import save_packing, load_current_packing, clear_current_packing, get_packing_history, delete_history_record, save_print_log, get_combined_history, get_packing_history_by_id, save_order_to_history, load_order_history, delete_order_history, load_order_history_column_widths, save_order_history_column_widths
from updater import (
    check_update,
    check_update_async,
    get_current_version,
    download_and_launch_installer,
    open_releases_page,
)


ORDER_HISTORY_COLUMN_DEFAULTS = {
    "#0": 28,
    "recipient": 95,
    "order": 170,
    "count": 60,
    "time": 150,
}


def order_history_date_options(history):
    dates = sorted(
        {str(h.get("created_at", ""))[:10] for h in history if str(h.get("created_at", ""))[:10]},
        reverse=True,
    )
    return [""] + dates


def sort_order_history_latest_first(history):
    return sorted(history, key=lambda h: str(h.get("created_at", "")), reverse=True)


def order_history_indexed_latest_first(history):
    return sorted(
        enumerate(history),
        key=lambda item: str(item[1].get("created_at", "")),
        reverse=True,
    )


def order_history_matches_filters(history_item, keyword, date_from, date_to):
    keyword = (keyword or "").strip().lower()
    date_from = (date_from or "").strip()
    date_to = (date_to or "").strip()

    if keyword:
        recipient = str(history_item.get("recipient", "")).lower()
        order_no = str(history_item.get("order_no", "")).lower()
        if keyword not in recipient and keyword not in order_no:
            return False

    created = str(history_item.get("created_at", ""))[:10]
    if date_from and created < date_from:
        return False
    if date_to and created > date_to:
        return False
    return True


class PackingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("自动装箱打印系统")
        self.root.geometry("1500x900")
        self.store = ProductStore()
        self.merge_tail = tk.BooleanVar(value=False)
        self.current_boxes = []
        self.box_row_indexes = {}
        self.selected_product_index = None
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_search_change)
        self.packing_items = []  # list of dict
        self.selected_packing_index = None
        self.create_widgets()
        self.refresh_product_table()
        self.refresh_box_table()
        self.refresh_packing_table()

        self.refresh_order_history()
        # 自动更新：菜单 + 后台静默检测
        self._update_state = {"pending_info": None, "busy": False}
        self._build_update_menu()
        self._kick_off_background_update_check()
    def create_widgets(self):
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ==== 左侧：产品管理 ====
        lf = ttk.Frame(main_pane, width=380)
        main_pane.add(lf, weight=0)

        ttk.Label(lf, text="产品管理", font=("Microsoft YaHei",12,"bold")).pack(anchor=tk.W,pady=(0,3))

        # 搜索框
        sf = ttk.Frame(lf)
        sf.pack(fill=tk.X, pady=(0,3))
        self.product_search_entry = ttk.Entry(sf, textvariable=self.search_var)
        self.product_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,3))
        ttk.Button(sf, text="清除", command=self.clear_product_search, width=6).pack(side=tk.LEFT, padx=(0,3))
        ttk.Label(sf, text="品名/SKU").pack(side=tk.LEFT)

        # 产品列表
        pf = ttk.Frame(lf)
        pf.pack(fill=tk.BOTH, expand=True)
        cols = ("name","sku","spec","per_box")
        self.ptree = ttk.Treeview(pf, columns=cols, show="headings", height=8)
        self.ptree.heading("name", text="品名")
        self.ptree.heading("sku", text="SKU")
        self.ptree.heading("spec", text="规格")
        self.ptree.heading("per_box", text="装箱数")
        self.ptree.column("name", width=90, minwidth=60)
        self.ptree.column("sku", width=70, minwidth=50)
        self.ptree.column("spec", width=70, minwidth=50)
        self.ptree.column("per_box", width=60, minwidth=40)
        vsb = ttk.Scrollbar(pf, orient=tk.VERTICAL, command=self.ptree.yview)
        self.ptree.configure(yscrollcommand=vsb.set)
        self.ptree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        pf.grid_rowconfigure(0, weight=1)
        pf.grid_columnconfigure(0, weight=1)
        self.ptree.bind("<<TreeviewSelect>>", self.on_product_select)

        # 产品编辑表单
        fm = ttk.LabelFrame(lf, text="产品编辑", padding=8)
        fm.pack(fill=tk.X, pady=3)
        ttk.Label(fm, text="品名:").grid(row=0,column=0,sticky=tk.W,pady=2)
        self.e_name = ttk.Entry(fm, width=35)
        self.e_name.grid(row=0,column=1,sticky=tk.EW,pady=2,padx=(5,0))
        ttk.Label(fm, text="SKU:").grid(row=1,column=0,sticky=tk.W,pady=2)
        self.e_sku = ttk.Entry(fm, width=25)
        self.e_sku.grid(row=1,column=1,sticky=tk.EW,pady=2,padx=(5,0))
        ttk.Label(fm, text="规格:").grid(row=2,column=0,sticky=tk.W,pady=2)
        self.e_spec = ttk.Entry(fm, width=25)
        self.e_spec.grid(row=2,column=1,sticky=tk.EW,pady=2,padx=(5,0))
        ttk.Label(fm, text="装箱数(逗号分隔):").grid(row=3,column=0,sticky=tk.W,pady=2)
        self.e_per = ttk.Entry(fm, width=25)
        self.e_per.grid(row=3,column=1,sticky=tk.EW,pady=2,padx=(5,0))
        bf = ttk.Frame(fm)
        bf.grid(row=4,column=0,columnspan=2,pady=(8,0))
        ttk.Button(bf,text="添加",command=self.add_product,width=8).pack(side=tk.LEFT,padx=2)
        ttk.Button(bf,text="修改",command=self.update_product,width=8).pack(side=tk.LEFT,padx=2)
        ttk.Button(bf,text="删除",command=self.delete_product,width=8).pack(side=tk.LEFT,padx=2)
        ttk.Button(bf,text="清空",command=self.clear_form,width=8).pack(side=tk.LEFT,padx=2)
        fm.grid_columnconfigure(1, weight=1)

        # ==== 右侧 ====
        rf = ttk.Frame(main_pane)
        main_pane.add(rf, weight=1)
        nb = ttk.Notebook(rf)
        nb.pack(fill=tk.BOTH, expand=True)

        # ===== Tab 1: 装箱作业 =====
        pt = ttk.Frame(nb)
        nb.add(pt, text="装箱作业")

        # 装箱项目列表
        mid_pane = ttk.PanedWindow(pt, orient=tk.HORIZONTAL)
        mid_pane.pack(fill=tk.BOTH, expand=True)

        # 左侧：装箱项目列表
        pk_frame = ttk.Frame(mid_pane)
        mid_pane.add(pk_frame, weight=1)
        ttk.Label(pk_frame, text="装箱项目列表", font=("Microsoft YaHei",12,"bold")).pack(anchor=tk.W)

        pkf = ttk.Frame(pk_frame)
        pkf.pack(fill=tk.BOTH, expand=True)
        pkcols = ("recipient","order","name","sku","spec","qty","per")
        self.pktree = ttk.Treeview(pkf, columns=pkcols, show="headings", height=8)
        pkhdrs = ["收件人","订单号","品名","SKU","规格","总数","装箱数"]
        for i,h in enumerate(pkhdrs):
            self.pktree.heading(pkcols[i], text=h)
        pkw = [80,100,120,70,60,60,60]
        for i,w in enumerate(pkw):
            self.pktree.column(pkcols[i], width=w, minwidth=40)
        pkvsb = ttk.Scrollbar(pkf, orient=tk.VERTICAL, command=self.pktree.yview)
        self.pktree.configure(yscrollcommand=pkvsb.set)
        self.pktree.grid(row=0,column=0,sticky="nsew")
        pkvsb.grid(row=0,column=1,sticky="ns")
        pkf.grid_rowconfigure(0,weight=1)
        pkf.grid_columnconfigure(0,weight=1)
        self.pktree.bind("<<TreeviewSelect>>", self.on_packing_select)

        # 右侧：订单历史
        oh_frame = ttk.Frame(mid_pane)

        mid_pane.add(oh_frame, weight=1)

        ttk.Label(oh_frame, text="装箱历史", font=("Microsoft YaHei",12,"bold")).pack(anchor=tk.W)



        # 搜索和筛选栏

        search_frame = ttk.Frame(oh_frame)

        search_frame.pack(fill=tk.X, pady=(2,3))

        ttk.Label(search_frame, text="收件人/订单号:").pack(side=tk.LEFT)

        self.oh_search_var = tk.StringVar()

        self.oh_search_entry = ttk.Entry(search_frame, width=12, textvariable=self.oh_search_var)

        self.oh_search_entry.pack(side=tk.LEFT, padx=3)

        self.oh_search_var.trace("w", lambda *a: self.refresh_order_history())

        ttk.Label(search_frame, text="  时间:").pack(side=tk.LEFT, padx=(5,0))

        ttk.Label(search_frame, text="从").pack(side=tk.LEFT)

        self.oh_date_from_var = tk.StringVar()

        self.oh_date_from = ttk.Combobox(search_frame, width=10, textvariable=self.oh_date_from_var, state="readonly")

        self.oh_date_from.pack(side=tk.LEFT, padx=2)

        ttk.Label(search_frame, text="至").pack(side=tk.LEFT)

        self.oh_date_to_var = tk.StringVar()

        self.oh_date_to = ttk.Combobox(search_frame, width=10, textvariable=self.oh_date_to_var, state="readonly")

        self.oh_date_to.pack(side=tk.LEFT, padx=2)

        ttk.Button(search_frame, text="筛选", command=self.refresh_order_history, width=6).pack(side=tk.LEFT, padx=2)

        self.oh_date_from.bind("<<ComboboxSelected>>", lambda e: self.refresh_order_history())

        self.oh_date_to.bind("<<ComboboxSelected>>", lambda e: self.refresh_order_history())



        ohf = ttk.Frame(oh_frame)

        ohf.pack(fill=tk.BOTH, expand=True)

        ohcols = ("recipient","order","count","time")

        self.ohtree = ttk.Treeview(ohf, columns=ohcols, show="tree headings", height=8, selectmode="extended")

        self.ohtree.heading("#0", text="")

        ohhdrs = ["收件人","订单号","产品数","时间"]

        for i,h in enumerate(ohhdrs):

            self.ohtree.heading(ohcols[i], text=h)

        self.apply_order_history_column_widths()

        ohvsb = ttk.Scrollbar(ohf, orient=tk.VERTICAL, command=self.ohtree.yview)

        ohhsb = ttk.Scrollbar(ohf, orient=tk.HORIZONTAL, command=self.ohtree.xview)

        self.ohtree.configure(yscrollcommand=ohvsb.set, xscrollcommand=ohhsb.set)

        self.ohtree.grid(row=0,column=0,sticky="nsew")

        ohvsb.grid(row=0,column=1,sticky="ns")

        ohhsb.grid(row=1,column=0,sticky="ew")

        ohf.grid_rowconfigure(0,weight=1)

        ohf.grid_columnconfigure(0,weight=1)

        self.ohtree.bind("<ButtonRelease-1>", self.on_order_history_column_adjusted)



        ohbf = ttk.Frame(oh_frame)

        ohbf.pack(fill=tk.X, pady=(2,0))

        ttk.Button(ohbf,text="重新装箱",command=self.reload_from_order_history,width=10).pack(side=tk.LEFT,padx=2)

        ttk.Button(ohbf,text="批量计算装箱",command=self.batch_calculate_from_history,width=14).pack(side=tk.LEFT,padx=2)

        ttk.Separator(ohbf,orient=tk.VERTICAL).pack(side=tk.LEFT,fill=tk.Y,padx=5)

        ttk.Button(ohbf,text="删除选中",command=self.delete_selected_order_history,width=10).pack(side=tk.LEFT,padx=2)# 装箱输入
        inf = ttk.LabelFrame(pt, text="添加装箱项", padding=8)
        inf.pack(fill=tk.X, pady=3)

        # 第一行：收件人 + 订单编号
        row1 = ttk.Frame(inf)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="收件人:").pack(side=tk.LEFT)
        self.e_pk_recipient = ttk.Entry(row1, width=18)
        self.e_pk_recipient.pack(side=tk.LEFT, padx=5)
        self.e_pk_recipient.bind("<KeyRelease>", self._on_recipient_order_change)
        ttk.Label(row1, text="订单编号:").pack(side=tk.LEFT, padx=(10,0))
        self.e_pk_order = ttk.Entry(row1, width=22)
        self.e_pk_order.pack(side=tk.LEFT, padx=5)
        self.e_pk_order.bind("<KeyRelease>", self._on_recipient_order_change)
        ttk.Label(row1, text="订单备注:").pack(side=tk.LEFT, padx=(10,0))
        self.e_order_remark = ttk.Entry(row1, width=30)
        self.e_order_remark.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 第二行：选中产品 + 总数量
        row2 = ttk.Frame(inf)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="选中产品:").pack(side=tk.LEFT)
        self.l_selected_product = tk.Label(row2, text="（请在左侧产品列表中选中一个产品）", fg="#888", width=38, wraplength=280, justify=tk.LEFT)
        self.l_selected_product.pack(side=tk.LEFT, padx=5)
        self.selected_prod_for_packing = None
        ttk.Label(row2, text="总数量:").pack(side=tk.LEFT, padx=(10,0))
        self.e_pk_qty = ttk.Entry(row2, width=10)
        self.e_pk_qty.pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="SKU备注:").pack(side=tk.LEFT, padx=(10, 0))
        self.e_pk_remark = ttk.Entry(row2, width=30)
        self.e_pk_remark.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 第三行：按钮
        row3 = ttk.Frame(inf)
        row3.pack(fill=tk.X, pady=(5,0))
        ttk.Button(row3, text="添加", command=self.add_packing_item, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(row3, text="修改", command=self.modify_packing_item, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(row3, text="删除", command=self.remove_packing_item, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(row3, text="清空", command=self.clear_packing_items, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Separator(row3, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Button(row3, text="保存", command=self.next_order, width=8).pack(side=tk.LEFT, padx=2)

        # 控制栏
        ctrlf = ttk.Frame(pt)
        ctrlf.pack(fill=tk.X, pady=3)
        ttk.Checkbutton(ctrlf,text="尾数合并装箱",variable=self.merge_tail,command=self.calculate_boxes).pack(side=tk.LEFT,padx=5)
        ttk.Button(ctrlf,text="计算装箱",command=self.calculate_boxes,width=10).pack(side=tk.LEFT,padx=2)
        ttk.Button(ctrlf,text="合箱",command=self.merge_selected_tail_boxes,width=8).pack(side=tk.LEFT,padx=2)
        ttk.Button(ctrlf,text="预览箱单",command=self.preview_packing_list,width=10).pack(side=tk.LEFT,padx=2)
        ttk.Button(ctrlf,text="打印箱唛",command=self.print_box_labels,width=10).pack(side=tk.LEFT,padx=2)
        ttk.Button(ctrlf,text="打印选中",command=self.print_selected_boxes,width=10).pack(side=tk.LEFT,padx=2)
        ttk.Separator(ctrlf,orient=tk.VERTICAL).pack(side=tk.LEFT,fill=tk.Y,padx=8)
        ttk.Button(ctrlf,text="暂存当前",command=self.save_current,width=10).pack(side=tk.LEFT,padx=2)
        ttk.Button(ctrlf,text="读取暂存",command=self.load_current,width=10).pack(side=tk.LEFT,padx=2)

        # 状态bar
        self.l_status = ttk.Label(pt, text="就绪 | 产品: 0 | 装箱项: 0 | 箱数: 0")
        self.l_status.pack(fill=tk.X, pady=(2,0))

        # 箱唛结果
        ttk.Label(pt, text="箱唛结果", font=("Microsoft YaHei",12,"bold")).pack(anchor=tk.W,pady=(3,0))
        bf = ttk.Frame(pt)
        bf.pack(fill=tk.BOTH, expand=True)
        bcols = ("recipient","name","sku","spec","per_box","count","total_qty","type","remark")
        self.btree = ttk.Treeview(bf, columns=bcols, show="headings", height=8, selectmode="extended")
        bhdrs = ["收件人","品名","SKU","规格","装箱数","箱数","总数量","类型","备注"]
        for i,h in enumerate(bhdrs):
            self.btree.heading(bcols[i], text=h)
        bwids = [80,120,90,70,60,50,70,60,80]
        for i,w in enumerate(bwids):
            self.btree.column(bcols[i], width=w, minwidth=40)
        bvsb = ttk.Scrollbar(bf, orient=tk.VERTICAL, command=self.btree.yview)
        self.btree.configure(yscrollcommand=bvsb.set)
        self.btree.grid(row=0,column=0,sticky="nsew")
        bvsb.grid(row=0,column=1,sticky="ns")
        bf.grid_rowconfigure(0,weight=1)
        bf.grid_columnconfigure(0,weight=1)

        # ===== Tab 2: 打印历史 =====
        ht = ttk.Frame(nb)
        nb.add(ht, text="打印历史")
        ttk.Label(ht, text="打印历史记录", font=("Microsoft YaHei",12,"bold")).pack(anchor=tk.W,pady=(0,5))
        hf = ttk.Frame(ht)
        hf.pack(fill=tk.BOTH, expand=True)
        hcols = ("time","products","boxes","merge_tail","remark","record_id")
        self.htree = ttk.Treeview(hf, columns=hcols, show="headings", height=12)
        hhdrs = ["打印时间","产品数","箱数","尾数合并","备注","ID"]
        for i,h in enumerate(hhdrs):
            self.htree.heading(hcols[i], text=h)
        hwids = [160,60,60,70,120,0]
        for i,w in enumerate(hwids):
            self.htree.column(hcols[i], width=w, minwidth=0 if w==0 else 40)
        hvsb = ttk.Scrollbar(hf, orient=tk.VERTICAL, command=self.htree.yview)
        self.htree.configure(yscrollcommand=hvsb.set)
        self.htree.grid(row=0,column=0,sticky="nsew")
        hvsb.grid(row=0,column=1,sticky="ns")
        hf.grid_rowconfigure(0,weight=1)
        hf.grid_columnconfigure(0,weight=1)
        hbf = ttk.Frame(ht)
        hbf.pack(fill=tk.X, pady=5)
        ttk.Button(hbf,text="刷新",command=self.refresh_history_table,width=10).pack(side=tk.LEFT,padx=2)
        ttk.Button(hbf,text="查看详情",command=self.view_history_detail,width=10).pack(side=tk.LEFT,padx=2)
        ttk.Button(hbf,text="重新打印",command=self.reprint_history,width=10).pack(side=tk.LEFT,padx=2)
        ttk.Button(hbf,text="删除记录",command=self.delete_history,width=10).pack(side=tk.LEFT,padx=2)
        self.l_hstatus = ttk.Label(ht, text="共 0 条记录")
        self.l_hstatus.pack(fill=tk.X, pady=(2,0))

    # ===== 产品管理 =====

    def refresh_product_table(self):
        for i in self.ptree.get_children():
            self.ptree.delete(i)
        kw = self.search_var.get().strip()
        results = self.store.search_by_name_or_sku_with_index(kw)
        for i, p in results:
            self.ptree.insert("",tk.END,iid=str(i),values=(p.name,p.sku,p.spec,format_box_sizes(p.qty_per_box)))
        # 产品列表已更新

    def on_search_change(self, *args):
        self.refresh_product_table()

    def clear_product_search(self):
        self.search_var.set("")
        self.product_search_entry.focus_set()

    def on_product_select(self, event):
        sel = self.ptree.selection()
        if sel:
            idx = int(sel[0])
            p = self.store.get(idx)
            if p:
                self.selected_product_index = idx
                self.e_name.delete(0,tk.END); self.e_name.insert(0,p.name)
                self.e_sku.delete(0,tk.END); self.e_sku.insert(0,p.sku)
                self.e_spec.delete(0,tk.END); self.e_spec.insert(0,p.spec)
                self.e_per.delete(0,tk.END); self.e_per.insert(0,format_box_sizes(p.qty_per_box))
                # 同时设为装箱作业的当前产品
                self.selected_prod_for_packing = p
                self.l_selected_product.config(text=f"{p.name}\nSKU:{p.sku} | 规格:{p.spec} | 装箱数:{format_box_sizes(p.qty_per_box)}", foreground="#1a5276")

    def get_form_data(self):
        try:
            name = self.e_name.get().strip()
            sku = self.e_sku.get().strip()
            spec = self.e_spec.get().strip()
            per = format_box_sizes(self.e_per.get() or 1)
            if not name:
                messagebox.showwarning("提示","请输入产品名称")
                return None
            return Product(name=name,sku=sku,spec=spec,qty_per_box=per)
        except ValueError:
            messagebox.showwarning("提示","装箱数请输入一个或多个正整数，例如：10,15,20")
            return None

    def add_product(self):
        p=self.get_form_data()
        if p: self.store.add(p); self.refresh_product_table(); self.clear_form()

    def update_product(self):
        if self.selected_product_index is None:
            messagebox.showinfo("提示","请先选择产品")
            return
        p=self.get_form_data()
        if p: self.store.update(self.selected_product_index,p); self.refresh_product_table(); self.clear_form()

    def delete_product(self):
        if self.selected_product_index is None:
            messagebox.showinfo("提示","请先选择产品")
            return
        if messagebox.askyesno("确认","确定删除该产品吗？"):
            self.store.remove(self.selected_product_index); self.refresh_product_table(); self.clear_form()

    def clear_form(self):
        self.e_name.delete(0,tk.END); self.e_sku.delete(0,tk.END); self.e_spec.delete(0,tk.END); self.e_per.delete(0,tk.END)
        self.selected_product_index = None

    # ===== 装箱项目管理 =====

    def refresh_packing_table(self):
        for i in self.pktree.get_children():
            self.pktree.delete(i)
        for i, item in enumerate(self.packing_items):
            self.pktree.insert("",tk.END,iid=str(i),values=(
                item["recipient"], item["order"], item["name"],
                item["sku"], item.get("spec",""), item["qty"], format_box_sizes(item.get("per", 1))
            ))
        self.update_status()

    def on_packing_select(self, event):
        sel = self.pktree.selection()
        if sel:
            idx = int(sel[0])
            self.selected_packing_index = idx
            if 0 <= idx < len(self.packing_items):
                item = self.packing_items[idx]
                self.e_pk_recipient.delete(0,tk.END)
                self.e_pk_recipient.insert(0,item.get("recipient",""))
                self.e_pk_order.delete(0,tk.END)
                self.e_pk_order.insert(0,item.get("order",""))
                self.e_pk_qty.delete(0,tk.END)
                self.e_pk_qty.insert(0,str(item.get("qty",0)))
                self.e_pk_remark.delete(0,tk.END)
                self.e_pk_remark.insert(0,item.get("remark",""))
                # 试图匹配对应的产品
                item_name = item.get("name","")
                item_sku = item.get("sku","")
                for prod in self.store.list_all():
                    if prod.name == item_name and prod.sku == item_sku:
                        self.selected_prod_for_packing = prod
                        self.l_selected_product.config(text=f"{prod.name}\nSKU:{prod.sku} | 规格:{prod.spec} | 装箱数:{format_box_sizes(prod.qty_per_box)}", foreground="#1a5276")
                        break

    def add_packing_item(self):
        if self.selected_prod_for_packing is None:
            messagebox.showwarning("提示","请先在左侧产品列表中选择一个产品")
            return

        found = self.selected_prod_for_packing
        recipient = self.e_pk_recipient.get().strip()
        order = self.e_pk_order.get().strip()
        try:
            qty = int(self.e_pk_qty.get().strip() or 0)
        except ValueError:
            messagebox.showwarning("提示","总数量请输入有效数字")
            return

        if qty <= 0:
            messagebox.showwarning("提示","总数量必须大于0")
            return

        item = {
            "name": found.name, "sku": found.sku, "per": format_box_sizes(found.qty_per_box), "spec": found.spec,
            "recipient": recipient, "order": order, "qty": qty,
            "remark": self.e_pk_remark.get().strip()
        }
        self.packing_items.append(item)
        self.refresh_packing_table()
        # 只清空数量，收件人和订单保留
        self.e_pk_qty.delete(0,tk.END)

    def next_order(self):
        """下一个订单：将当前装箱列表保存到历史，然后清空表单和列表"""
        if not self.packing_items:
            # 没有装箱项目，只清空表单
            self.e_pk_recipient.delete(0,tk.END)
            self.e_pk_order.delete(0,tk.END)
            self.e_pk_qty.delete(0,tk.END)
            return

        # 按收件人+订单号分组保存
        groups = {}
        for item in self.packing_items:
            key = (item["recipient"], item["order"])
            if key not in groups:
                groups[key] = []
            groups[key].append(item)

        for (recipient, order), items in groups.items():
            save_order_to_history(recipient, order, items, self.e_order_remark.get().strip())

        self.packing_items = []
        self.current_boxes = []
        self.selected_packing_index = None
        self.refresh_packing_table()
        self.refresh_box_table()
        self.refresh_order_history()
        self.e_pk_recipient.delete(0,tk.END)
        self.e_pk_order.delete(0,tk.END)
        self.e_pk_qty.delete(0,tk.END)
        self.e_pk_remark.delete(0,tk.END)
        self.e_order_remark.delete(0,tk.END)
        messagebox.showinfo("成功", f"已保存 {len(groups)} 个订单到历史记录")

    def modify_packing_item(self):
        """修改选中的装箱项目：用当前表单值更新"""
        if self.selected_packing_index is None:
            messagebox.showinfo("提示","请在装箱项目列表中选择要修改的项")
            return
        if self.selected_prod_for_packing is None:
            messagebox.showwarning("提示","请先在左侧产品列表中选择一个产品")
            return
        recipient = self.e_pk_recipient.get().strip()
        order = self.e_pk_order.get().strip()
        try:
            qty = int(self.e_pk_qty.get().strip() or 0)
        except ValueError:
            messagebox.showwarning("提示","总数量请输入有效数字")
            return
        if qty <= 0:
            messagebox.showwarning("提示","总数量必须大于0")
            return
        found = self.selected_prod_for_packing
        item = {
            "name": found.name, "sku": found.sku, "per": format_box_sizes(found.qty_per_box), "spec": found.spec,
            "recipient": recipient, "order": order, "qty": qty,
            "remark": self.e_pk_remark.get().strip()
        }
        if 0 <= self.selected_packing_index < len(self.packing_items):
            self.packing_items[self.selected_packing_index] = item
            self.refresh_packing_table()
            self.e_pk_qty.delete(0,tk.END)

    def clear_packing_items(self):
        self.packing_items = []
        self.current_boxes = []
        self.selected_packing_index = None
        self.e_pk_recipient.delete(0,tk.END)
        self.e_pk_order.delete(0,tk.END)
        self.e_pk_qty.delete(0,tk.END)
        self.e_pk_remark.delete(0,tk.END)
        self.e_order_remark.delete(0,tk.END)
        self.refresh_packing_table()
        self.refresh_box_table()

    def remove_packing_item(self):
        if self.selected_packing_index is None:
            messagebox.showinfo("提示","请在装箱项目列表中选择项")
            return
        if 0 <= self.selected_packing_index < len(self.packing_items):
            self.packing_items.pop(self.selected_packing_index)
            self.selected_packing_index = None
            self.refresh_packing_table()

    # ===== 装箱计算 =====

    def calculate_boxes(self):
        if not self.packing_items:
            messagebox.showinfo("提示","请先添加装箱项目")
            return
        # 创建临时产品对象
        temp_products = []
        for item in self.packing_items:
            temp_products.append(Product(
                name=item["name"],
                sku=item["sku"],
                quantity=item["qty"],
                qty_per_box=item["per"],
                spec=item.get("spec",""),
                recipient=item["recipient"],
                order_no=item["order"],
                remark=item.get("remark", "")
            ))
        self.current_boxes = calculate_boxes(temp_products, self.merge_tail.get(), self.e_order_remark.get().strip())
        self.refresh_box_table()

    def refresh_box_table(self):
        for i in self.btree.get_children():
            self.btree.delete(i)
        self.box_row_indexes = {}
        groups = {}
        for box_index, box in enumerate(self.current_boxes):
            if box.is_tail:
                item_id = self.btree.insert("", tk.END, values=(
                    box.recipient or "-",
                    box.product_name,
                    box.product_sku,
                    box.spec or "",
                    box.qty_per_box,
                    box.box_count or 1,
                    box.quantity_in_box,
                    "尾数箱",
                    box.remark,
                ))
                self.box_row_indexes[item_id] = box_index
                continue

            key = (box.recipient, box.product_name, box.product_sku, box.spec, box.qty_per_box, box.is_tail)
            if key not in groups:
                groups[key] = {"r":box.recipient,"n":box.product_name,"s":box.product_sku,"sp":box.spec,"p":box.qty_per_box,"t":box.is_tail,"c":0,"q":0,"m":box.remark}
            groups[key]["c"] += 1
            groups[key]["q"] += box.quantity_in_box
        for g in groups.values():
            bt = "尾数箱" if g["t"] else "整箱"
            item_id = self.btree.insert("",tk.END,values=(g["r"] or "-", g["n"], g["s"], g["sp"] or "", g["p"], g["c"], g["q"], bt, g["m"]))
            self.box_row_indexes[item_id] = None
        self.update_status()

    def merge_selected_tail_boxes(self):
        if not self.current_boxes:
            messagebox.showinfo("提示", "请先点击「计算装箱」生成箱唛数据")
            return
        selected_rows = self.btree.selection()
        if len(selected_rows) < 2:
            messagebox.showinfo("提示", "请选择至少两个尾数箱进行合箱")
            return

        selected_indexes = []
        for row_id in selected_rows:
            box_index = self.box_row_indexes.get(row_id)
            if box_index is None:
                messagebox.showinfo("提示", "只能选择尾数箱进行合箱")
                return
            selected_indexes.append(box_index)

        try:
            self.current_boxes = merge_tail_boxes(self.current_boxes, selected_indexes)
        except ValueError as exc:
            messagebox.showinfo("提示", str(exc))
            return

        self.refresh_box_table()
        messagebox.showinfo("成功", "已将选中的尾数箱合并为一个箱子")

    def save_current(self):
        if not self.packing_items:
            messagebox.showinfo("提示","没有装箱数据可暂存")
            return
        # 创建临时产品对象并调用 storage
        temp_products = []
        for item in self.packing_items:
            temp_products.append(Product(
                name=item["name"], sku=item["sku"], quantity=item["qty"],
                qty_per_box=item["per"], spec=item.get("spec", ""),
                recipient=item["recipient"], order_no=item["order"],
                remark=item.get("remark", "")
            ))
        rid = save_packing(temp_products, self.current_boxes, self.merge_tail.get(), order_remark=self.e_order_remark.get().strip())
        messagebox.showinfo("成功", f"装箱数据已暂存 (ID: {rid})")
        self.refresh_history_table()

    def load_current(self):
        record = load_current_packing()
        if not record:
            messagebox.showinfo("提示","没有暂存数据")
            return
        # 加载装箱项目
        self.packing_items = []
        for pd in record.products:
            if isinstance(pd, dict):
                self.packing_items.append({
                    "name": pd.get("name",""),
                    "sku": pd.get("sku",""),
                    "per": format_box_sizes(pd.get("qty_per_box",1)),
                    "spec": pd.get("spec",""),
                    "recipient": pd.get("recipient",""),
                    "order": pd.get("order_no",""),
                    "qty": pd.get("quantity",0),
                    "remark": pd.get("remark", "")
                })
        self.merge_tail.set(record.merge_tail)
        self.e_order_remark.delete(0, tk.END)
        self.e_order_remark.insert(0, getattr(record, "order_remark", "") or getattr(record, "remark", ""))
        self.current_boxes = record.boxes
        self.refresh_packing_table()
        self.refresh_box_table()
        messagebox.showinfo("成功","已读取暂存数据")

    def _on_recipient_order_change(self, event=None):
        """收件人/订单号变化时，同步更新所有装箱项目的对应字段"""
        if not self.packing_items:
            return
        new_recipient = self.e_pk_recipient.get().strip()
        new_order = self.e_pk_order.get().strip()
        changed = False
        for item in self.packing_items:
            if item.get("recipient","") != new_recipient or item.get("order","") != new_order:
                item["recipient"] = new_recipient
                item["order"] = new_order
                changed = True
        if changed:
            self.refresh_packing_table()

    def update_status(self):
        np = self.store.count()
        ni = len(self.packing_items)
        nb = len(self.current_boxes)
        nh = len(load_order_history())
        info = f"就绪 | 产品: {np} | 装箱项: {ni}"
        if nb > 0:
            info += f" | 箱数: {nb} | 尾数合并: {'是' if self.merge_tail.get() else '否'}"
        info += f" | 历史订单: {nh}"
        self.l_status.config(text=info)

    def preview_packing_list(self):
        if not self.current_boxes:
            messagebox.showinfo("提示","请先点击「计算装箱」生成箱唛数据")
            return
        html = generate_box_label_html(self.current_boxes)
        self._open_html(html, "packing_list_preview.html")
    

    def print_box_labels(self):
        if not self.current_boxes:
            messagebox.showinfo("提示","请先点击「计算装箱」生成箱唛数据")
            return
        n = len(self.current_boxes)
        if not messagebox.askyesno("确认打印", f"本次共生成 {n} 张箱唛标签（10×10cm），确认开始打印吗？"):
            return
        html = generate_individual_box_labels_html(self.current_boxes)
        self._open_html(html, "box_labels_print.html")
        # 创建临时产品对象保存到历史
        temp_products = []
        for item in self.packing_items:
            temp_products.append(Product(
                name=item["name"], sku=item["sku"], quantity=item["qty"],
                qty_per_box=item["per"], spec=item.get("spec", ""),
                recipient=item["recipient"], order_no=item["order"],
                remark=item.get("remark", "")
            ))
        rid = save_packing(temp_products, self.current_boxes, self.merge_tail.get(), order_remark=self.e_order_remark.get().strip())
        save_print_log(rid)
        self.refresh_history_table()
        self.refresh_history_table()
    

    def print_selected_boxes(self):
        """选择指定箱号打印"""
        if not self.current_boxes:
            messagebox.showinfo("提示","请先点击「计算装箱」生成箱唛数据")
            return
        # 弹出选择窗口
        win = tk.Toplevel(self.root)
        win.title("选择箱号打印")
        win.geometry("500x400")
        win.transient(self.root)
        win.grab_set()
        
        ttk.Label(win, text="选择要打印的箱号（可多选）", font=("Microsoft YaHei",12,"bold")).pack(pady=(10,5))
        
        # 列表显示所有箱唛
        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        cols = ("sel","num","total","name","sku","qty","recipient","order","type")
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        tree.heading("sel", text="")
        tree.heading("num", text="箱号")
        tree.heading("total", text="总箱数")
        tree.heading("name", text="品名")
        tree.heading("sku", text="SKU")
        tree.heading("qty", text="数量")
        tree.heading("recipient", text="收件人")
        tree.heading("order", text="订单号")
        tree.heading("type", text="类型")
        tree.column("sel", width=0, stretch=False)
        tree.column("num", width=50, minwidth=40)
        tree.column("total", width=60, minwidth=40)
        tree.column("name", width=120, minwidth=80)
        tree.column("sku", width=80, minwidth=60)
        tree.column("qty", width=50, minwidth=40)
        tree.column("recipient", width=80, minwidth=60)
        tree.column("order", width=100, minwidth=60)
        tree.column("type", width=60, minwidth=40)
        
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        # 填充数据
        for idx, box in enumerate(self.current_boxes):
            bt = "尾数" if box.is_tail else "整箱"
            tree.insert("", tk.END, iid=str(idx), values=(
                "", box.box_number, box.total_boxes, box.product_name,
                box.product_sku, box.quantity_in_box, box.recipient or "-",
                box.order_no or "-", bt
            ))
        
        # 操作按钮
        bf = ttk.Frame(win)
        bf.pack(fill=tk.X, padx=10, pady=8)
        
        def select_all():
            for item in tree.get_children():
                tree.selection_add(item)
        
        def deselect_all():
            for item in tree.get_children():
                tree.selection_remove(item)
        
        ttk.Button(bf, text="全选", command=select_all, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="取消全选", command=deselect_all, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Separator(bf, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        
        def do_print():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("提示","请选择至少一个箱号", parent=win)
                return
            selected_boxes = [self.current_boxes[int(iid)] for iid in sel]
            html = generate_individual_box_labels_html(selected_boxes)
            self._open_html(html, "box_labels_selected.html")
            # 记录打印历史
            temp_products = []
            for item in self.packing_items:
                temp_products.append(Product(
                    name=item["name"], sku=item["sku"], quantity=item["qty"],
                    qty_per_box=item["per"], spec=item.get("spec", ""),
                    recipient=item["recipient"], order_no=item["order"],
                    remark=item.get("remark", "")
                ))
            rid = save_packing(temp_products, self.current_boxes, self.merge_tail.get(), order_remark=self.e_order_remark.get().strip())
            save_print_log(rid)
            self.refresh_history_table()
            win.destroy()
        
        ttk.Button(bf, text="打印选中箱号", command=do_print, width=12).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bf, text="取消", command=win.destroy, width=8).pack(side=tk.RIGHT, padx=2)
        
        self.selected_print_win = win

    def _open_html(self, html, filename):
        try:
            d = os.path.join(tempfile.gettempdir(), "packing_labels")
            os.makedirs(d, exist_ok=True)
            fp = os.path.join(d, filename)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(html)
            webbrowser.open("file://" + fp)
        except Exception as e:
            messagebox.showerror("错误", f"打开浏览器失败: {e}")
    
    # ===== 暂存管理 =====

    def refresh_history_table(self):
        for i in self.htree.get_children():
            self.htree.delete(i)
        history = get_combined_history()
        for h in history:
            mt = "是" if h.get("merge_tail",False) else "否"
            np = len(h.get("products",[]))
            nb = len(h.get("boxes",[]))
            rm = h.get("remark","") or ""
            self.htree.insert("",tk.END,values=(h["time"],np,nb,mt,rm,h["record_id"]))
        self.l_hstatus.config(text=f"共 {len(history)} 条记录")
    

    def view_history_detail(self):
        sel = self.htree.selection()
        if not sel:
            messagebox.showinfo("提示","请先选择一条历史记录")
            return
        vals = self.htree.item(sel[0],"values")
        if not vals: return
        record = get_packing_history_by_id(vals[5])
        if record: self.show_detail_window(record)
    

    def show_detail_window(self, record):
        win = tk.Toplevel(self.root)
        win.title("记录详情")
        win.geometry("700x500")
        win.transient(self.root)
        
        info = f"时间: {record.get('created_at','')}   "
        merge_tail = record.get('merge_tail', False)
        info += f"尾数合并: {'是' if merge_tail else '否'}   "
        boxes_data = record.get('boxes', [])
        info += f"总箱数: {len(boxes_data)}"
        # Get unique recipients
        recs = set()
        for b in boxes_data:
            if isinstance(b, dict) and b.get('recipient'):
                recs.add(b['recipient'])
        if recs:
            info += f"   收件人: {','.join(recs)}"
        ttk.Label(win,text=info,font=("Microsoft YaHei",10)).pack(anchor=tk.W,padx=10,pady=8)
        
        ttk.Label(win,text="产品清单:",font=("Microsoft YaHei",10,"bold")).pack(anchor=tk.W,padx=10)
        pt = tk.Text(win,height=5,font=("Microsoft YaHei",9))
        pt.pack(fill=tk.X,padx=10,pady=2)
        for p in record.get("products",[]):
            if isinstance(p,dict):
                pt.insert(tk.END,f"  {p.get('name','')} | SKU: {p.get('sku','')} | 收件人: {p.get('recipient','')} | 订单: {p.get('order_no','')} | 总数: {p.get('quantity',0)} | 每箱: {p.get('qty_per_box',0)}\n")
        pt.config(state=tk.DISABLED)
        
        ttk.Label(win,text="箱唛清单:",font=("Microsoft YaHei",10,"bold")).pack(anchor=tk.W,padx=10)
        bt = tk.Text(win,height=12,font=("Consolas",9))
        bt.pack(fill=tk.BOTH,expand=True,padx=10,pady=2)
        hdr = f"{'箱号':<6}{'总箱数':<8}{'品名':<18}{'SKU':<14}{'每箱':<8}{'本箱':<8}{'类型':<8}{'备注'}\n"
        bt.insert(tk.END, hdr)
        bt.insert(tk.END, "-"*80 + "\n")
        for b in record.get("boxes",[]):
            if isinstance(b,dict):
                bt2 = "尾数" if b.get("is_tail",False) else "整箱"
                line = f"{b.get('box_number',''):<6}{b.get('total_boxes',''):<8}{b.get('product_name',''):<18}{b.get('product_sku',''):<14}{b.get('qty_per_box',''):<8}{b.get('quantity_in_box',''):<8}{bt2:<8}{b.get('remark','')}\n"
                bt.insert(tk.END, line)
        bt.config(state=tk.DISABLED)
        
        bf = ttk.Frame(win); bf.pack(fill=tk.X,pady=8)
        ttk.Button(bf,text="重新打印箱唛",
                  command=lambda: self._reprint_from_record(record),width=15).pack(side=tk.LEFT,padx=10)
    

    def _reprint_from_record(self, record):
        boxes_data = record.get("boxes",[])
        boxes = [BoxLabel.from_dict(b) if isinstance(b,dict) else b for b in boxes_data]
        if boxes:
            html = generate_individual_box_labels_html(boxes)
            self._open_html(html, "box_labels_reprint.html")
            messagebox.showinfo("成功","箱唛已打开，请在浏览器中打印")
        else:
            messagebox.showwarning("提示","没有箱唛数据可打印")
    

    def reprint_history(self):
        sel = self.htree.selection()
        if not sel:
            messagebox.showinfo("提示","请先选择一条历史记录")
            return
        vals = self.htree.item(sel[0],"values")
        if not vals: return
        record = get_packing_history_by_id(vals[5])
        if record: self._reprint_from_record(record)
    

    def delete_history(self):
        sel = self.htree.selection()
        if not sel:
            messagebox.showinfo("提示","请先选择一条记录")
            return
        vals = self.htree.item(sel[0],"values")
        if not vals: return
        if messagebox.askyesno("确认","确定要删除该历史记录吗？"):
            delete_history_record(vals[5])
            self.refresh_history_table()

    def apply_order_history_column_widths(self):
        widths = load_order_history_column_widths(ORDER_HISTORY_COLUMN_DEFAULTS)
        self.ohtree.column("#0", width=widths["#0"], minwidth=24, stretch=False)
        for col in ("recipient", "order", "count", "time"):
            self.ohtree.column(col, width=widths[col], minwidth=40, stretch=False)

    def get_order_history_column_widths(self):
        return {col: int(self.ohtree.column(col, "width")) for col in ORDER_HISTORY_COLUMN_DEFAULTS}

    def on_order_history_column_adjusted(self, event=None):
        self.root.after_idle(lambda: save_order_history_column_widths(self.get_order_history_column_widths()))
    
    # ===== 订单历史管理 =====

    def refresh_order_history(self):
        for i in self.ohtree.get_children():
            self.ohtree.delete(i)

        history = load_order_history()
        date_values = order_history_date_options(history)
        self.oh_date_from.configure(values=date_values)
        self.oh_date_to.configure(values=date_values)

        keyword = self.oh_search_var.get().strip()
        date_from = self.oh_date_from_var.get().strip()
        date_to = self.oh_date_to_var.get().strip()

        for original_idx, h in order_history_indexed_latest_first(history):
            if not order_history_matches_filters(h, keyword, date_from, date_to):
                continue

            n_items = len(h.get("items", []))
            parent_id = f"oh_{original_idx}"
            self.ohtree.insert("", tk.END, iid=parent_id, values=(
                h["recipient"], h["order_no"], n_items, h["created_at"])
            )

            for item in h.get("items", []):
                self.ohtree.insert(parent_id, tk.END, values=(
                    f"  {item['name']}", item.get('sku',''), f"{item['qty']}个/箱{item['per']}", ""
                ))

    def reload_from_order_history(self):
        sel = self.ohtree.selection()
        if not sel:
            messagebox.showinfo("提示","请在订单历史中选择一个订单")
            return
        history = load_order_history()
        new_items = []
        for iid in sel:
            parent = self.ohtree.parent(iid)
            real_iid = parent if parent else iid
            idx_str = real_iid.replace("oh_","")
            try:
                idx = int(idx_str)
            except:
                continue
            if idx < 0 or idx >= len(history):
                continue
            h = history[idx]
            for item in h.get("items",[]):
                new_items.append({
                    "name":item["name"],"sku":item.get("sku",""),
                    "per":format_box_sizes(item.get("per", 1)),"spec":item.get("spec",""),
                    "recipient":h["recipient"],
                    "order":h["order_no"],"qty":item["qty"],
                    "remark":item.get("remark", ""),
                    "order_remark":h.get("order_remark", "")})
        if not new_items:
            messagebox.showinfo("提示","没有可加载的订单数据")
            return
        self.packing_items = new_items
        self.refresh_packing_table()
        if new_items:
            self.e_pk_recipient.delete(0,tk.END)
            self.e_pk_recipient.insert(0,new_items[0].get("recipient",""))
            self.e_pk_order.delete(0,tk.END)
            self.e_pk_order.insert(0,new_items[0].get("order",""))
            self.e_order_remark.delete(0, tk.END)
            self.e_order_remark.insert(0, new_items[0].get("order_remark", ""))

    def batch_calculate_from_history(self):
        sel = self.ohtree.selection()
        if not sel:
            messagebox.showinfo("提示","请在订单历史中选择要计算的订单（Ctrl+点击多选）")
            return
        history = load_order_history()
        temp_products = []
        for iid in sel:
            parent = self.ohtree.parent(iid)
            if parent:
                continue
            idx_str = iid.replace("oh_", "")
            try:
                idx = int(idx_str)
            except:
                continue
            if idx < 0 or idx >= len(history):
                continue
            h = history[idx]
            for item in h.get("items", []):
                temp_products.append(Product(
                    name=item["name"], sku=item.get("sku",""),
                    quantity=item["qty"], qty_per_box=item["per"],
                    spec=item.get("spec",""),
                    recipient=h["recipient"], order_no=h["order_no"],
                    remark=item.get("remark", "")))
        if not temp_products:
            messagebox.showinfo("提示","没有可计算的订单数据")
            return
        order_groups = {}
        for tp in temp_products:
            key = (tp.recipient, tp.order_no)
            if key not in order_groups:
                order_groups[key] = {"products": [], "order_remark": ""}
            order_groups[key]["products"].append(tp)
        for iid in sel:
            if self.ohtree.parent(iid):
                continue
            try:
                h = history[int(iid.replace("oh_", ""))]
            except Exception:
                continue
            key = (h.get("recipient", ""), h.get("order_no", ""))
            if key in order_groups:
                order_groups[key]["order_remark"] = h.get("order_remark", "")
        all_boxes = []
        for group in order_groups.values():
            order_boxes = calculate_boxes(group["products"], self.merge_tail.get(), group["order_remark"])
            all_boxes.extend(order_boxes)
        self.current_boxes = all_boxes
        self.refresh_box_table()
        messagebox.showinfo("成功", f"已生成 {len(all_boxes)} 箱(按订单分开计算)")

    def delete_selected_order_history(self):
        sel = self.ohtree.selection()
        if not sel:
            messagebox.showinfo("提示","请选择要删除的订单历史")
            return
        history = load_order_history()
        indexes_to_del = set()
        for iid in sel:
            parent = self.ohtree.parent(iid)
            real_iid = parent if parent else iid
            idx_str = real_iid.replace("oh_", "")
            try:
                indexes_to_del.add(int(idx_str))
            except:
                continue
        indexes = list(indexes_to_del)
        if messagebox.askyesno("确认", f"确定删除 {len(indexes)} 个订单历史记录吗？"):
            delete_order_history(indexes)
            self.refresh_order_history()


    # ============================================================
    # 自动更新（菜单 + 后台检测 + 弹窗）
    # ============================================================
    def _build_update_menu(self):
        """在窗口顶部建一个 tk.Menu，包含帮助 - 检查更新。"""
        menubar = tk.Menu(self.root)
        help_menu = tk.Menu(menubar, tearoff=0)
        self._help_menu = help_menu
        self._update_menu_label_text = "检查更新"
        help_menu.add_command(label=self._update_menu_label_text, command=self.on_check_update_click)
        help_menu.add_command(label="打开发布页", command=open_releases_page)
        help_menu.add_separator()
        help_menu.add_command(label=f"关于 (v{get_current_version()})", command=self.on_about_click)
        menubar.add_cascade(label="帮助(H)", menu=help_menu, underline=0)
        try:
            self.root.config(menu=menubar)
        except Exception:
            pass
        self._menubar = menubar

    def _set_update_menu_label(self, text):
        self._update_menu_label_text = text
        try:
            self._help_menu.entryconfigure(0, label=text)
        except Exception:
            pass

    def _kick_off_background_update_check(self):
        """启动后 1.5 秒，在后台静默检测有无新版本。"""
        import threading
        def _after_start():
            def _cb(info):
                try:
                    self.root.after(0, lambda: self._on_background_update_done(info))
                except Exception:
                    pass
            check_update_async(_cb)
        self.root.after(1500, _after_start)

    def _on_background_update_done(self, info):
        if info.has_update:
            self._update_state["pending_info"] = info
            self._set_update_menu_label(f"检查更新 (⚡ v{info.latest_version})")
        # 出错不通知用户，避免打扰

    def on_check_update_click(self):
        """菜单点击：同步检查 + 弹窗展示。"""
        import threading
        if self._update_state["pending_info"] is not None:
            self._show_update_dialog(self._update_state["pending_info"])
            return
        if self._update_state["busy"]:
            return
        self._update_state["busy"] = True
        self._set_update_menu_label("检查中...")
        def _worker():
            info = check_update()
            self.root.after(0, lambda: self._after_manual_check(info))
        threading.Thread(target=_worker, daemon=True).start()

    def _after_manual_check(self, info):
        self._update_state["busy"] = False
        if info.error and not info.has_update:
            messagebox.showinfo("检查更新", f"未检测到更新：{info.error}")
            self._set_update_menu_label("检查更新")
            return
        self._show_update_dialog(info)

    def _show_update_dialog(self, info):
        if info.has_update:
            body = info.release_notes.strip() or "本次发布未提供详情。"
            size_mb = (info.asset_size / (1024*1024)) if info.asset_size else 0
            asset = info.asset_name or "—"
            msg = (
                f"检测到新版本：v{info.latest_version}\n"
                f"当前版本：v{info.current_version}\n"
                f"下载文件：{asset}"
                + (f" ({size_mb:.2f} MB)" if size_mb else "")
                + f"\n\n--- 更新说明 ---\n{body[:2000]}"
            )
            if messagebox.askyesno("检查更新", msg + "\n\n是否现在下载并安装？"):
                self._set_update_menu_label("下载中...")
                def _on_done(ok, m):
                    self.root.after(0, lambda: self._on_download_finished(ok, m))
                download_and_launch_installer(info, finished_cb=_on_done)
            else:
                self._set_update_menu_label(f"检查更新 (⚡ v{info.latest_version})")
        else:
            messagebox.showinfo("检查更新", f"已为最新版本（v{info.current_version}）。")

    def _on_download_finished(self, ok, msg):
        if ok:
            self._set_update_menu_label("检查更新")
            messagebox.showinfo("下载完成", f"{msg}\n\n安装器启动后请按向导完成升级。本程序现在可以先关闭。")
        else:
            self._set_update_menu_label("检查更新 (错误)")
            messagebox.showerror("下载失败", msg)

    def on_about_click(self):
        messagebox.showinfo(
            "关于",
            f"装箱打印系统\nv{get_current_version()}\n\n设计为 Windows 桌面工具，仅用于内部使用。"
        )

def main():
    root = tk.Tk()
    root.title("自动装箱打印系统")
    try:
        root.iconbitmap(default=os.path.join(os.path.dirname(__file__),"icon.ico"))
    except: pass
    app = PackingApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
