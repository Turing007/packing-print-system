"""
装箱计算引擎
"""
from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import os
from html import escape
from datetime import datetime
from math import gcd
from product import Product, parse_box_sizes


@dataclass
class BoxLabel:
    """箱唛数据"""
    box_number: int = 0
    total_boxes: int = 0
    product_name: str = ""
    product_sku: str = ""
    qty_per_box: int = 0
    quantity_in_box: int = 0
    is_tail: bool = False
    recipient: str = ""
    order_no: str = ""
    spec: str = ""
    remark: str = ""
    created_at: str = ""
    box_count: int = 0
    total_quantity: int = 0
    tail_items: list = field(default_factory=list)
    product_remark: str = ""
    order_remark: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "BoxLabel":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PackingRecord:
    """装箱记录（暂存/历史）"""
    id: str = ""
    created_at: str = ""
    products: list = field(default_factory=list)
    boxes: list = field(default_factory=list)
    merge_tail: bool = False
    remark: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["boxes"] = [b.to_dict() for b in self.boxes]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "PackingRecord":
        boxes_data = data.get("boxes", [])
        record = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__ and k != "boxes"})
        record.boxes = [BoxLabel.from_dict(b) for b in boxes_data]
        return record

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "PackingRecord":
        return cls.from_dict(json.loads(json_str))

_MAX_BALANCED_DFS_NODES = 300000


def _balanced_fill_plan(quantity: int, sizes, box_count: int):
    """在"恰好 box_count 个标准箱装满 quantity"的所有组合中，返回各箱装量最均衡
    （极差最小）的一种，箱装量按从大到小排列；找不到或搜索过于复杂时返回 None。

    例：sizes=10/15/20 时 30 → [15, 15]（而不是 20+10），50 → [20, 15, 15]（而不是 20+20+10）。
    """
    if box_count <= 0:
        return None
    sizes_desc = sorted(set(sizes), reverse=True)
    min_size, max_size = sizes_desc[-1], sizes_desc[0]
    common = 0
    for size in sizes_desc:
        common = gcd(common, size)
    if common == 0 or quantity % common:
        return None
    if not (min_size * box_count <= quantity <= max_size * box_count):
        return None

    best_spread = None
    best_plan = None
    chosen = []   # 保持非升序：chosen[0] 为当前最大，chosen[-1] 为当前最小
    nodes = 0

    def dfs(remaining, boxes_left, start_idx):
        nonlocal best_spread, best_plan, nodes
        nodes += 1
        if nodes > _MAX_BALANCED_DFS_NODES:
            return
        if boxes_left == 0:
            if remaining == 0:
                spread = chosen[0] - chosen[-1]
                if best_spread is None or spread < best_spread:
                    best_spread, best_plan = spread, list(chosen)
            return
        if remaining < min_size * boxes_left or remaining > max_size * boxes_left:
            return
        if remaining % common:
            return
        if chosen and best_spread is not None and chosen[0] - chosen[-1] >= best_spread:
            return  # 前缀极差已不优于当前最优（极差只会随装箱变大），剪枝

        for idx in range(start_idx, len(sizes_desc)):
            size = sizes_desc[idx]
            if size > remaining - min_size * (boxes_left - 1):
                continue  # 选它会让剩余件数装不下；更小的箱还有机会
            if size * boxes_left < remaining:
                break     # 当前及更小的箱都凑不满剩余件数
            chosen.append(size)
            dfs(remaining - size, boxes_left - 1, idx)
            chosen.pop()

    dfs(quantity, box_count, 0)
    return best_plan


def _packing_plan(quantity: int, box_sizes) -> list[tuple[int, int, bool]]:
    """Find the fewest boxes, preferring the fullest standard-box plan."""
    if quantity <= 0:
        return []

    sizes = parse_box_sizes(box_sizes)
    max_size = sizes[0]
    reachable = [{0: []}]
    min_size = sizes[-1]
    for box_count in range(1, quantity // min_size + 1):
        previous = reachable[-1]
        current = {}
        for total, chosen in previous.items():
            for size in sizes:
                new_total = total + size
                if new_total <= quantity and new_total not in current:
                    current[new_total] = chosen + [size]
        reachable.append(current)

    max_boxes = quantity // max_size + 1
    for total_boxes in range(1, max_boxes + 1):
        candidates = []
        if total_boxes < len(reachable) and quantity in reachable[total_boxes]:
            candidates.append((quantity, reachable[total_boxes][quantity], 0))

        standard_count = total_boxes - 1
        if standard_count == 0:
            if quantity <= max_size:
                candidates.append((0, [], quantity))
        elif standard_count < len(reachable):
            partials = [
                (total, chosen)
                for total, chosen in reachable[standard_count].items()
                if quantity - max_size <= total < quantity
            ]
            if partials:
                full_total, chosen = max(partials, key=lambda item: item[0])
                candidates.append((full_total, chosen, quantity - full_total))

        if candidates:
            full_total, chosen, tail_quantity = max(candidates, key=lambda item: item[0])
            # 箱数最少的前提下，同箱数选各箱装量最均衡的组合（30 → 15+15，50 → 20+15+15）
            balanced = _balanced_fill_plan(full_total, sizes, len(chosen))
            if balanced:
                chosen = balanced
            plan = [(size, size, False) for size in chosen]
            if tail_quantity:
                plan.append((tail_quantity, max_size, True))
            return plan

    return [(quantity, max_size, True)]


def calculate_boxes(products: list[Product], merge_tail: bool, order_remark: str = "") -> list[BoxLabel]:
    boxes = []

    if merge_tail:
        rec_groups = {}
        for p in products:
            key = (p.recipient, p.order_no)
            if key not in rec_groups:
                rec_groups[key] = []
            rec_groups[key].append(p)

        for (recipient, order_no), group in rec_groups.items():
            order_totals = {}
            full_box_counts = {}
            for product in group:
                key = (product.sku, product.name, product.spec)
                order_totals[key] = order_totals.get(key, 0) + product.quantity
                for quantity_in_box, qty_per_box, is_tail in _packing_plan(product.quantity, product.qty_per_box):
                    if not is_tail:
                        count_key = key + (qty_per_box,)
                        full_box_counts[count_key] = full_box_counts.get(count_key, 0) + 1

            tail_products = []
            tail_capacity = 0
            for product in group:
                for quantity_in_box, qty_per_box, is_tail in _packing_plan(product.quantity, product.qty_per_box):
                    if is_tail:
                        tail_products.append((product, quantity_in_box))
                        tail_capacity = max(tail_capacity, qty_per_box)

            if tail_products:
                current_parts = []
                current_qty = 0

                def append_tail_box():
                    tail_name = "+".join(f"{product.name}({qty})" for product, qty in current_parts)
                    tail_sku = _format_tail_parts(current_parts, "sku")
                    tail_items = _build_tail_items(current_parts, order_totals)
                    boxes.append(BoxLabel(
                        box_number=0, total_boxes=0,
                        product_name=tail_name,
                        product_sku=tail_sku,
                        qty_per_box=tail_capacity,
                        quantity_in_box=current_qty,
                        box_count=1,
                        total_quantity=current_qty,
                        is_tail=True,
                        recipient=recipient, order_no=order_no,
                        remark="尾数合并",
                        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        tail_items=tail_items,
                        order_remark=order_remark,
                    ))

                for product, remaining in tail_products:
                    while remaining > 0:
                        take = min(remaining, tail_capacity - current_qty)
                        current_parts.append((product, take))
                        current_qty += take
                        remaining -= take
                        if current_qty == tail_capacity:
                            append_tail_box()
                            current_parts = []
                            current_qty = 0

                if current_qty > 0:
                    append_tail_box()
            for product in group:
                product_key = (product.sku, product.name, product.spec)
                for quantity_in_box, qty_per_box, is_tail in _packing_plan(product.quantity, product.qty_per_box):
                    if is_tail:
                        continue
                    boxes.append(BoxLabel(
                        box_number=0, total_boxes=0,
                        product_name=product.name,
                        product_sku=product.sku,
                        qty_per_box=qty_per_box,
                        quantity_in_box=quantity_in_box,
                        box_count=full_box_counts.get(product_key + (qty_per_box,), 1),
                        total_quantity=order_totals.get(product_key, product.quantity),
                        is_tail=False,
                        recipient=recipient, order_no=order_no,
                        spec=product.spec,
                        product_remark=product.remark,
                        order_remark=order_remark,
                        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))
    else:
        order_totals = {}
        full_box_counts = {}
        for product in products:
            key = (product.recipient, product.order_no, product.sku, product.name, product.spec)
            order_totals[key] = order_totals.get(key, 0) + product.quantity
            for quantity_in_box, qty_per_box, is_tail in _packing_plan(product.quantity, product.qty_per_box):
                if not is_tail:
                    count_key = key + (qty_per_box,)
                    full_box_counts[count_key] = full_box_counts.get(count_key, 0) + 1

        for product in products:
            product_key = (product.recipient, product.order_no, product.sku, product.name, product.spec)
            for quantity_in_box, qty_per_box, is_tail in _packing_plan(product.quantity, product.qty_per_box):
                if is_tail:
                    boxes.append(BoxLabel(
                        box_number=0, total_boxes=0,
                        product_name=product.name,
                        product_sku=product.sku,
                        qty_per_box=qty_per_box,
                        quantity_in_box=quantity_in_box,
                        box_count=1,
                        total_quantity=order_totals.get(product_key, product.quantity),
                        is_tail=True,
                        recipient=product.recipient,
                        order_no=product.order_no,
                        spec=product.spec,
                        remark="尾数",
                        product_remark=product.remark,
                        order_remark=order_remark,
                        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))
                    continue
                boxes.append(BoxLabel(
                    box_number=0, total_boxes=0,
                    product_name=product.name,
                    product_sku=product.sku,
                    qty_per_box=qty_per_box,
                    quantity_in_box=quantity_in_box,
                    box_count=full_box_counts.get(product_key + (qty_per_box,), 1),
                    total_quantity=order_totals.get(product_key, product.quantity),
                    is_tail=False,
                    recipient=product.recipient,
                    order_no=product.order_no,
                    spec=product.spec,
                    product_remark=product.remark,
                    order_remark=order_remark,
                    created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))

    _renumber_boxes_by_order(boxes)
    return boxes


def _renumber_boxes_by_order(boxes: list[BoxLabel]) -> None:
    """按收件人和订单号分别设置箱号及订单总箱数。"""
    order_counts = {}
    for box in boxes:
        key = (box.recipient, box.order_no)
        order_counts[key] = order_counts.get(key, 0) + 1

    order_numbers = {}
    for box in boxes:
        key = (box.recipient, box.order_no)
        order_numbers[key] = order_numbers.get(key, 0) + 1
        box.box_number = order_numbers[key]
        box.total_boxes = order_counts[key]


def _format_tail_parts(parts, attr: str) -> str:
    totals = []
    indexes = {}
    for product, qty in parts:
        value = getattr(product, attr) or "-"
        if value not in indexes:
            indexes[value] = len(totals)
            totals.append([value, 0])
        totals[indexes[value]][1] += qty
    return "+".join(f"{value}({qty})" for value, qty in totals)


def _build_tail_items(parts, order_totals: dict) -> list:
    items = []
    indexes = {}
    for product, qty in parts:
        key = (product.sku, product.name, product.spec)
        if key not in indexes:
            indexes[key] = len(items)
            items.append({
                "sku": product.sku or "-",
                "name": product.name,
                "spec": product.spec,
                "quantity_in_box": 0,
                "box_count": 1,
                "total_quantity": order_totals.get(key, product.quantity),
                "remark": product.remark,
            })
        items[indexes[key]]["quantity_in_box"] += qty
    return items


def merge_selected_boxes(boxes: list[BoxLabel], selected_indexes: list[int]) -> list[BoxLabel]:
    """手动合箱：把选中的箱子（整箱、尾数箱均可）内容合并成一个箱子。

    - 只能合并同一个收件人和订单号的箱子，且至少选择两个；
    - 合并后的箱子装箱数=实际件数（可能超过标准装箱数），
      类型为尾数箱、备注"手动合箱"。
    """
    indexes = sorted(set(int(i) for i in selected_indexes))
    if len(indexes) < 2:
        raise ValueError("请选择至少两个箱子进行合箱")
    if any(i < 0 or i >= len(boxes) for i in indexes):
        raise ValueError("选择的箱子不存在")

    selected_boxes = [boxes[i] for i in indexes]
    first = selected_boxes[0]
    if any((box.recipient, box.order_no) != (first.recipient, first.order_no) for box in selected_boxes):
        raise ValueError("只能合并同一个收件人和订单号的箱子")

    tail_items = []
    item_indexes = {}
    for box in selected_boxes:
        source_items = box.tail_items or [
            {
                "sku": box.product_sku or "-",
                "name": box.product_name,
                "spec": box.spec,
                "quantity_in_box": box.quantity_in_box,
                "box_count": 1,
                "total_quantity": box.total_quantity or box.quantity_in_box,
                "remark": box.product_remark,
            }
        ]
        for item in source_items:
            key = (item.get("sku", "-"), item.get("name", ""), item.get("spec", ""))
            if key not in item_indexes:
                item_indexes[key] = len(tail_items)
                tail_items.append({
                    "sku": key[0] or "-",
                    "name": key[1],
                    "spec": key[2],
                "quantity_in_box": 0,
                "box_count": 1,
                "total_quantity": item.get("total_quantity", 0),
                "remark": item.get("remark", ""),
                })
            tail_items[item_indexes[key]]["quantity_in_box"] += int(item.get("quantity_in_box", 0) or 0)

    product_name = "+".join(f"{item['name']}({item['quantity_in_box']})" for item in tail_items)
    product_sku = "+".join(f"{item['sku']}({item['quantity_in_box']})" for item in tail_items)
    quantity_in_box = sum(item["quantity_in_box"] for item in tail_items)
    insert_at = indexes[0]
    merged_box = BoxLabel(
        box_number=0,
        total_boxes=0,
        product_name=product_name,
        product_sku=product_sku,
        qty_per_box=quantity_in_box,
        quantity_in_box=quantity_in_box,
        box_count=1,
        total_quantity=quantity_in_box,
        is_tail=True,
        recipient=first.recipient,
        order_no=first.order_no,
        remark="手动合箱",
        order_remark=first.order_remark,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        tail_items=tail_items,
    )

    selected_index_set = set(indexes)
    merged_boxes = []
    inserted = False
    for i, box in enumerate(boxes):
        if i == insert_at:
            merged_boxes.append(merged_box)
            inserted = True
        if i not in selected_index_set:
            merged_boxes.append(box)
    if not inserted:
        merged_boxes.append(merged_box)

    _renumber_boxes_by_order(merged_boxes)
    return merged_boxes

def generate_box_label_html(boxes: list[BoxLabel], customer_name: str = "") -> str:
    """生成装箱明细表，按收件人分组"""
    if not boxes:
        return "<p>暂无装箱数据</p>"
    from datetime import datetime
    
    recipients = {}
    for box in boxes:
        r = box.recipient or "未指定"
        if r not in recipients:
            recipients[r] = []
        recipients[r].append(box)
    
    rec_counts = {}
    for box in boxes:
        r = box.recipient or "未指定"
        rec_counts[r] = rec_counts.get(r, 0) + 1
    
    html = '<!DOCTYPE html><html><head><meta charset="utf-8"><style>' + _get_packing_list_css() + '</style></head><body><div class="packing-list">'
    html += '<h2>装箱明细表</h2>'
    html += '<p style="text-align:center;font-size:12px;color:#666;margin-bottom:15px;">生成时间: ' + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + '</p>'
    
    for r in sorted(recipients.keys()):
        box_group = recipients[r]
        item_groups = {}
        for box in box_group:
            key = (box.product_name, box.product_sku, box.spec, box.qty_per_box, box.is_tail)
            if key not in item_groups:
                item_groups[key] = {"name":box.product_name, "sku":box.product_sku, "spec":box.spec or "", "per":box.qty_per_box, "is_tail":box.is_tail, "remark":box.remark, "count":0, "qty":0}
            item_groups[key]["count"] += 1
            item_groups[key]["qty"] += box.quantity_in_box
        
        html += '<div class="recipient-group"><h3>收件人: ' + r + ' (共 ' + str(len(box_group)) + ' 箱)</h3>'
        html += '<table><thead><tr><th>品名</th><th>SKU</th><th>规格</th><th>装箱数</th><th>箱数</th><th>总数量</th><th>类型</th><th>备注</th></tr></thead><tbody>'
        for g in item_groups.values():
            bt = "尾数箱" if g["is_tail"] else "整箱"
            html += '<tr><td>' + g["name"] + '</td><td>' + g["sku"] + '</td><td>' + g["spec"] + '</td><td>' + str(g["per"]) + '</td><td>' + str(g["count"]) + '</td><td>' + str(g["qty"]) + '</td><td>' + bt + '</td><td>' + g["remark"] + '</td></tr>'
        html += '</tbody></table></div>'
    
    count_parts = [f"{r}:{c}箱" for r, c in rec_counts.items()]
    count_str = "共 " + str(len(boxes)) + " 箱 (" + ", ".join(count_parts) + ")" if count_parts else "共 " + str(len(boxes)) + " 箱"
    html += '<p class="summary">' + count_str + '</p></div></body></html>'
    return html


def generate_individual_box_labels_html(boxes: list[BoxLabel]) -> str:
    """Generate 10x10cm labels with SKU and order remarks."""
    if not boxes:
        return "<p>暂无装箱数据</p>"

    def text(value, fallback="-"):
        value = "" if value is None else str(value)
        return escape(value or fallback)

    pages = []
    total_by_product = {}
    for box in boxes:
        key = (box.order_no, box.product_name, box.product_sku, box.spec, box.qty_per_box)
        total_by_product[key] = total_by_product.get(key, 0) + box.quantity_in_box

    for box in boxes:
        tail_badge = '<span class="l-tail-badge">尾数箱</span>' if box.is_tail else ''
        label_class = ' tail' if box.is_tail else ''
        parts = [
            '<div class="page"><div class="label' + label_class + '">',
            '<div class="l-header"><div class="l-title">箱 唛 / BOX LABEL</div>' + tail_badge + '</div>',
            '<div class="l-row"><span class="l-label">收件人: </span><span class="l-recipient">' + text(box.recipient) + '</span></div>',
            '<div class="l-row"><span class="l-label">订单号: </span><span class="l-value">' + text(box.order_no) + '</span></div>',
            '<div class="l-box-no">' + text(box.box_number) + ' / ' + text(box.total_boxes) + '</div>',
        ]

        parts.append('<div class="l-sku-group"><table class="l-table"><thead><tr><th>SKU</th><th>品名</th><th>规格</th><th>装箱数</th><th>箱数</th><th>总数量</th></tr></thead><tbody>')
        if box.is_tail and box.tail_items:
            for item in box.tail_items:
                parts.append('<tr>')
                parts.append('<td>' + text(item.get("sku")) + '</td>')
                parts.append('<td>' + text(item.get("name"), "") + '</td>')
                parts.append('<td>' + text(item.get("spec")) + '</td>')
                parts.append('<td class="qty">' + text(item.get("quantity_in_box"), "0") + '</td>')
                parts.append('<td class="qty">' + text(item.get("box_count"), "1") + '</td>')
                parts.append('<td class="qty">' + text(item.get("total_quantity"), "0") + '</td></tr>')
                if item.get("remark", ""):
                    parts.append('<tr class="l-product-remark-row"><td colspan="6">SKU备注: ' + text(item.get("remark"), "") + '</td></tr>')
        else:
            parts.append('<tr>')
            parts.append('<td style="font-family:Consolas,monospace">' + text(box.product_sku) + '</td>')
            parts.append('<td>' + text(box.product_name, "") + '</td><td>' + text(box.spec) + '</td>')
            product_key = (box.order_no, box.product_name, box.product_sku, box.spec, box.qty_per_box)
            box_count = box.box_count if box.box_count else 1
            total_quantity = box.total_quantity if box.total_quantity else total_by_product.get(product_key, 0)
            parts.append('<td class="qty">' + text(box.quantity_in_box, "0") + '</td><td class="qty">' + text(box_count) + '</td><td class="qty">' + text(total_quantity, "0") + '</td>')
            parts.append('</tr>')
            if box.product_remark:
                parts.append('<tr class="l-product-remark-row"><td colspan="6">SKU备注: ' + text(box.product_remark, "") + '</td></tr>')
        parts.append('</tbody></table></div>')

        if box.order_remark:
            parts.append('<div class="l-order-remark">订单备注: ' + text(box.order_remark, "") + '</div>')
        parts.append('<div class="l-footer">日期: ' + datetime.now().strftime('%Y-%m-%d') + '</div></div></div>')
        pages.append(''.join(parts))

    return '<!DOCTYPE html><html><head><meta charset="utf-8"><title>箱唛打印 - 10x10cm</title><style>' + _BOX_LABEL_CSS + '</style></head><body>' + ''.join(pages) + '</body></html>'
def _get_packing_list_css() -> str:
    return """body {{font-family:'Microsoft YaHei','SimHei',Arial,sans-serif;padding:20px;}}
h2 {{text-align:center;margin-bottom:15px;}}
.recipient-group {{margin-bottom:20px;border:1px solid #ccc;padding:10px;border-radius:4px;}}
.recipient-group h3 {{margin:0 0 8px 0;color:#1a5276;font-size:14px;}}
table {{width:100%;border-collapse:collapse;}}
th {{background:#f0f0f0;font-size:11px;padding:5px 8px;border:1px solid #999;text-align:center;}}
td {{font-size:11px;padding:4px 8px;border:1px solid #999;text-align:center;}}
.summary {{text-align:center;margin-top:10px;color:#666;font-size:11px;}}
.packing-list {{max-width:210mm;margin:0 auto;background:#fff;padding:10px;}}"
"""# CSS for box labels (embedded for exe compatibility) - 10x10cm

import json, os

DEFAULT_LABEL_CONFIG = {
  "elements": {
    "title": {
      "label": "标题(箱响)",
      "visible": True,
      "font_size": 10,
      "bold": True
    },
    "recipient": {
      "label": "收件人",
      "visible": True,
      "font_size": 18,
      "bold": True
    },
    "order_no": {
      "label": "订单号",
      "visible": True,
      "font_size": 13.5,
      "bold": True
    },
    "box_number": {
      "label": "箱号/总箱数",
      "visible": True,
      "font_size": 22,
      "bold": True
    },
    "table_sku": {
      "label": "SKU",
      "visible": True,
      "font_size": 10,
      "bold": True
    },
    "table_name": {
      "label": "品名",
      "visible": True,
      "font_size": 10,
      "bold": True
    },
    "table_spec": {
      "label": "规格",
      "visible": True,
      "font_size": 10,
      "bold": True
    },
    "table_qty": {
      "label": "装箱数",
      "visible": True,
      "font_size": 10,
      "bold": True
    },
    "table_total": {
      "label": "总数量",
      "visible": True,
      "font_size": 10,
      "bold": True
    },
    "footer": {
      "label": "页脚(日期)",
      "visible": True,
      "font_size": 6.5,
      "bold": False
    }
  },
  "layout_order": [
    "title",
    "recipient",
    "order_no",
    "box_number",
    "table",
    "footer"
  ]
}

def load_label_config(data_dir='data'):
    cfg_path = os.path.join(data_dir, 'label_config.json')
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_LABEL_CONFIG

_BOX_LABEL_CSS = r"""@page { size: 100mm 100mm; margin: 0; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Microsoft YaHei', 'SimHei', Arial, sans-serif;
    background: #fff;
    padding: 0px;
    margin: 0;
}
.page {
    width: 100mm;
    height: 100mm;
    margin: 0;
    padding: 0;
    background: #fff;
    overflow: hidden;
}
.label {
    width: 100mm;
    height: 100mm;
    border: 1.5px solid #222;
    padding: 5mm 6mm;
    display: flex;
    flex-direction: column;
    background: #fff;
}
.label.tail { border-color: #e67e22; border-style: dashed; }
.l-header {
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 1.5px solid #222; padding-bottom: 1.5mm; margin-bottom: 2mm;
}
.l-title { font-size: 10pt; font-weight: bold; letter-spacing: 2px; }
.l-tail-badge { font-size: 7pt; background: #e67e22; color: #000; padding: 1px 4px; border-radius: 2px; }
.l-row { display: flex; margin-bottom: 1.5px; font-size: 8pt; }
.l-label { color: #000; width: 20mm; flex-shrink: 0; font-size: 11pt; }
.l-value { font-weight: bold; font-size: 13.5pt; color: #000; }
.l-recipient { font-weight: bold; font-size: 18pt; color: #000; }
.l-box-no { font-size: 22pt; font-weight: bold; color: #000; text-align: center; margin: 2mm 0; }
.l-table { width: 100%; border-collapse: collapse; margin-top: 1.5mm; }
.l-table th { background: #eee; font-size: 7.5pt; padding: 0.8mm 1.5mm; border: 1px solid #999; text-align: center; }
.l-table td { font-size: 10pt; font-weight: bold; padding: 0.8mm 1.5mm; border: 1px solid #999; text-align: center; }
.l-table .qty { color: #000; font-weight: bold; font-size: 10pt; }
.l-sku-group { margin-top: 1.5mm; }
.l-sku-group + .l-sku-group { margin-top: 3mm; }
.l-product-remark-row td { font-size: 7.5pt; font-weight: normal; text-align: left; padding: 0.8mm 1.5mm; }
.l-product-remark { font-size: 7.5pt; font-weight: normal; text-align: left; padding: 0.8mm 1.5mm; }
.l-order-remark { border-top: 1px solid #999; padding-top: 1mm; margin-top: auto; font-size: 7pt; text-align: left; overflow-wrap: anywhere; }
.l-footer { border-top: 1px solid #ddd; padding-top: 1mm; margin-top: 1mm; font-size: 6.5pt; color: #000; text-align: right; }
@media print {
    body { background: #fff; padding: 0; margin: 0; }
    .page { padding: 0; }
    .label { border: 1px solid #000; page-break-after: always; }
    .label:last-child { page-break-after: avoid; }
}"""

def _legacy_generate_individual_box_labels_html(boxes: list[BoxLabel]) -> str:
    """生成单个箱唛标签HTML，每张10x10cm，一张一页"""
    if not boxes:
        return "<p>暂无装箱数据</p>"
    from datetime import datetime
    
    pages = []
    total_by_product = {}
    for b in boxes:
        key = (b.order_no, b.product_name, b.product_sku, b.spec, b.qty_per_box)
        total_by_product[key] = total_by_product.get(key, 0) + b.quantity_in_box
    for box in boxes:
        tail_badge = '<span class="l-tail-badge">尾数箱</span>' if box.is_tail else ''
        tc = ' tail' if box.is_tail else ''
        
        parts = []
        parts.append('<div class="page">')
        parts.append('<div class="label' + tc + '">')
        parts.append('<div class="l-header"><div class="l-title">箱 唛 / BOX LABEL</div>' + tail_badge + '</div>')
        parts.append('<div class="l-row"><span class="l-label">收件人: </span><span class="l-recipient">' + (box.recipient or '-') + '</span></div>')
        parts.append('<div class="l-row"><span class="l-label">订单号: </span><span class="l-value">' + (box.order_no or '-') + '</span></div>')
        parts.append('<div class="l-box-no">' + str(box.box_number) + ' / ' + str(box.total_boxes) + '</div>')
        parts.append('<table class="l-table"><thead><tr><th>SKU</th><th>品名</th><th>规格</th><th>装箱数</th><th>箱数</th><th>总数量</th></tr></thead><tbody>')
        if box.is_tail and box.tail_items:
            for item in box.tail_items:
                parts.append('<tr>')
                parts.append('<td>' + str(item.get("sku", "-")) + '</td>')
                parts.append('<td>' + str(item.get("name", "")) + '</td>')
                parts.append('<td>' + (str(item.get("spec", "")) or '-') + '</td>')
                parts.append('<td class="qty">' + str(item.get("quantity_in_box", 0)) + '</td>')
                parts.append('<td class="qty">' + str(item.get("box_count", 1)) + '</td>')
                parts.append('<td class="qty">' + str(item.get("total_quantity", 0)) + '</td>')
                parts.append('</tr>')
        else:
            parts.append('<tr>')
            parts.append('<td style="font-family:Consolas,monospace">' + box.product_sku + '</td>')
            parts.append('<td>' + box.product_name + '</td><td>' + (box.spec or '-') + '</td>')
            product_key = (box.order_no, box.product_name, box.product_sku, box.spec, box.qty_per_box)
            box_count = box.box_count if box.box_count else 1
            total_quantity = box.total_quantity if box.total_quantity else total_by_product.get(product_key, 0)
            parts.append('<td class="qty">' + str(box.quantity_in_box) + '</td><td class="qty">' + str(box_count) + '</td><td class="qty">' + str(total_quantity) + '</td>')
            parts.append('</tr>')
        parts.append('</tbody></table>')
        parts.append('<div class="l-footer">日期: ' + datetime.now().strftime('%Y-%m-%d') + '</div>')
        parts.append('</div>')
        parts.append('</div>')
        pages.append(''.join(parts))
    
    total_labels = len(boxes)
    html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>箱唛打印 - 10x10cm</title><style>' + _BOX_LABEL_CSS + '</style></head><body>' + ''.join(pages) + '</body></html>'
    return html
