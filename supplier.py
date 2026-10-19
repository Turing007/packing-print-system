# -*- coding: utf-8 -*-
"""供应商映射与备货清单

- 客户产品（装箱时选用的产品）→ 一个或多个供应商产品（含用量）
- 按订单/装箱项汇总出备货清单：供应商 + 供应商产品 + 数量
- 纯数据与渲染逻辑，不依赖 Tkinter，便于单元测试
"""
import csv
import json
import os
import sys
import tempfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import escape

DATA_FILE = "supplier_bom.json"
MAX_USAGE_DECIMALS = Decimal("0.001")


def _default_data_dir() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "data")


def product_key(name: str = "", sku: str = "", spec: str = "") -> str:
    """客户产品唯一键：有 SKU 用 SKU，无 SKU 用「品名+规格」。

    与装箱页的重复判定保持一致：SKU 两边都为空时才按品名+规格判断。
    """
    sku = str(sku or "").strip()
    if sku:
        return "sku:" + sku.upper()
    return "ns:" + str(name or "").strip() + "|" + str(spec or "").strip()


def parse_usage(value) -> Decimal:
    """解析用量：必须大于 0，最多 3 位小数。"""
    try:
        usage = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError, ValueError):
        raise ValueError("用量必须是数字，例如：1 或 1.5")
    if not usage.is_finite() or usage <= 0:
        raise ValueError("用量必须大于 0")
    return usage.quantize(MAX_USAGE_DECIMALS)


def format_quantity(value) -> str:
    """数量展示：整数不带小数点，小数最多 3 位且去掉末尾 0。"""
    if isinstance(value, Decimal):
        quantity = value
    else:
        try:
            quantity = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return "0"
    quantity = quantity.quantize(MAX_USAGE_DECIMALS)
    if quantity == quantity.to_integral_value():
        return str(int(quantity))
    return format(quantity, "f").rstrip("0").rstrip(".")


def _normalize_component(component: dict) -> dict:
    supplier_name = str(component.get("supplier", "") or "").strip()
    product_name = str(component.get("supplier_product", "") or "").strip()
    if not supplier_name:
        raise ValueError("请填写供应商名称")
    if not product_name:
        raise ValueError("请填写供应商产品名称")
    usage = parse_usage(component.get("usage_qty", 1))
    return {
        "supplier": supplier_name,
        "supplier_product": product_name,
        "supplier_sku": str(component.get("supplier_sku", "") or "").strip(),
        "usage_qty": float(usage),
        "remark": str(component.get("remark", "") or "").strip(),
    }


class SupplierBomStore:
    """data/supplier_bom.json 读写。"""

    def __init__(self, data_dir: str = None):
        self.data_dir = os.path.abspath(data_dir or _default_data_dir())
        self.file = os.path.join(self.data_dir, DATA_FILE)
        self.mappings = []  # [{"key","customer":{...},"components":[...],"updated_at"}]
        self._load()

    # ===== 读写 =====
    def _load(self):
        self.mappings = []
        if not os.path.exists(self.file):
            return
        try:
            with open(self.file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            items = raw.get("mappings", []) if isinstance(raw, dict) else raw
            for item in items or []:
                mapping = self._normalize_mapping(item)
                if mapping:
                    self.mappings.append(mapping)
        except Exception:
            # 数据损坏时回退为空，不能影响主程序启动
            self.mappings = []

    @staticmethod
    def _normalize_mapping(item: dict):
        if not isinstance(item, dict):
            return None
        customer = item.get("customer") or {}
        name = str(customer.get("name", "") or "").strip()
        sku = str(customer.get("sku", "") or "").strip()
        spec = str(customer.get("spec", "") or "").strip()
        key = str(customer.get("key", "") or "").strip() or product_key(name, sku, spec)
        components = []
        for component in item.get("components", []) or []:
            try:
                components.append(_normalize_component(component))
            except ValueError:
                continue
        return {
            "key": key,
            "customer": {"key": key, "name": name, "sku": sku, "spec": spec},
            "components": components,
            "updated_at": str(item.get("updated_at", "") or ""),
        }

    def _save(self):
        os.makedirs(self.data_dir, exist_ok=True)
        payload = {"version": 1, "mappings": self.mappings}
        # 原子写，避免中途崩溃写坏映射数据
        fd, tmp_path = tempfile.mkstemp(dir=self.data_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.file)
            import storage
            storage.backup_file(DATA_FILE)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    # ===== 查询 =====
    def get_mapping(self, key: str):
        for mapping in self.mappings:
            if mapping["key"] == key:
                return mapping
        return None

    def get_components(self, key: str) -> list:
        mapping = self.get_mapping(key)
        return list(mapping["components"]) if mapping else []

    def has_mapping(self, key: str) -> bool:
        mapping = self.get_mapping(key)
        return bool(mapping and mapping["components"])

    def list_mappings(self) -> list:
        return list(self.mappings)

    def suppliers(self) -> list:
        names = {c["supplier"] for m in self.mappings for c in m["components"] if c["supplier"]}
        return sorted(names)

    def mapped_count(self) -> int:
        return sum(1 for m in self.mappings if m["components"])

    # ===== 修改 =====
    def _ensure_mapping(self, key: str, customer: dict):
        mapping = self.get_mapping(key)
        if mapping is None:
            mapping = {
                "key": key,
                "customer": {
                    "key": key,
                    "name": str(customer.get("name", "") or "").strip(),
                    "sku": str(customer.get("sku", "") or "").strip(),
                    "spec": str(customer.get("spec", "") or "").strip(),
                },
                "components": [],
                "updated_at": "",
            }
            self.mappings.append(mapping)
        else:
            mapping["customer"]["name"] = str(customer.get("name", mapping["customer"]["name"]) or "").strip()
            mapping["customer"]["sku"] = str(customer.get("sku", mapping["customer"]["sku"]) or "").strip()
            mapping["customer"]["spec"] = str(customer.get("spec", mapping["customer"]["spec"]) or "").strip()
        return mapping

    def add_component(self, key: str, customer: dict, component: dict):
        normalized = _normalize_component(component)
        mapping = self._ensure_mapping(key, customer)
        mapping["components"].append(normalized)
        mapping["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save()

    def update_component(self, key: str, index: int, customer: dict, component: dict):
        mapping = self.get_mapping(key)
        if mapping is None or not (0 <= index < len(mapping["components"])):
            raise ValueError("要修改的供应商明细不存在")
        normalized = _normalize_component(component)
        mapping["components"][index] = normalized
        mapping["customer"].update({
            "name": str(customer.get("name", "") or "").strip(),
            "sku": str(customer.get("sku", "") or "").strip(),
            "spec": str(customer.get("spec", "") or "").strip(),
        })
        mapping["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save()

    def remove_component(self, key: str, index: int):
        mapping = self.get_mapping(key)
        if mapping is None or not (0 <= index < len(mapping["components"])):
            raise ValueError("要删除的供应商明细不存在")
        mapping["components"].pop(index)
        mapping["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save()

    def remove_mapping(self, key: str):
        before = len(self.mappings)
        self.mappings = [m for m in self.mappings if m["key"] != key]
        if len(self.mappings) != before:
            self._save()

    def move_mapping(self, old_key: str, new_key: str, customer: dict) -> bool:
        """产品身份变化（如改 SKU）时迁移映射，避免映射丢失。

        目标键已有映射时合并：重复（供应商+产品+货号）保留目标侧，其余追加。
        返回是否找到并迁移了旧映射。
        """
        old = self.get_mapping(old_key)
        if old is None or old_key == new_key:
            return False
        target = self.get_mapping(new_key)
        if target is None:
            old["key"] = new_key
            old["customer"] = {
                "key": new_key,
                "name": str(customer.get("name", "") or "").strip(),
                "sku": str(customer.get("sku", "") or "").strip(),
                "spec": str(customer.get("spec", "") or "").strip(),
            }
            old["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            existing = {
                (c["supplier"], c["supplier_product"], c["supplier_sku"])
                for c in target["components"]
            }
            for component in old["components"]:
                signature = (component["supplier"], component["supplier_product"], component["supplier_sku"])
                if signature not in existing:
                    target["components"].append(component)
                    existing.add(signature)
            target["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.mappings = [m for m in self.mappings if m["key"] != old_key]
        self._save()
        return True


def _to_int_quantity(value) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def build_requirement(items: list, store: SupplierBomStore) -> dict:
    """按装箱项/订单明细汇总备货清单。

    items 结构需包含 name/sku/spec/qty，可选 order/recipient。
    返回值：
    - rows: 按供应商+供应商产品汇总的行（含来源明细）
    - unmapped: 未配置映射（或映射为空）的客户产品，绝不静默丢弃
    """
    customers = {}
    for item in items:
        name = str(item.get("name", "") or "").strip()
        sku = str(item.get("sku", "") or "").strip()
        spec = str(item.get("spec", "") or "").strip()
        quantity = _to_int_quantity(item.get("qty"))
        if quantity <= 0:
            continue
        key = product_key(name, sku, spec)
        entry = customers.setdefault(key, {
            "key": key, "name": name, "sku": sku, "spec": spec,
            "quantity": 0, "sources": {},
        })
        entry["quantity"] += quantity
        source_key = (str(item.get("order", "") or "").strip(), str(item.get("recipient", "") or "").strip())
        entry["sources"][source_key] = entry["sources"].get(source_key, 0) + quantity

    grouped = {}
    unmapped = []
    mapped_customers = 0
    for key, entry in customers.items():
        components = [
            c for c in store.get_components(key)
            if c.get("supplier") and c.get("supplier_product")
        ]
        if not components:
            unmapped.append(entry)
            continue
        mapped_customers += 1
        for component in components:
            usage = Decimal(str(component.get("usage_qty", 1)))
            row_key = (
                component["supplier"].strip(),
                component["supplier_product"].strip(),
                str(component.get("supplier_sku", "") or "").strip(),
            )
            row = grouped.get(row_key)
            if row is None:
                row = {
                    "supplier": row_key[0],
                    "supplier_product": row_key[1],
                    "supplier_sku": row_key[2],
                    "quantity": Decimal("0"),
                    "sources": [],
                }
                grouped[row_key] = row
            for (order_no, recipient), source_qty in sorted(entry["sources"].items()):
                row_quantity = (Decimal(source_qty) * usage).quantize(MAX_USAGE_DECIMALS)
                row["quantity"] += row_quantity
                row["sources"].append({
                    "order_no": order_no,
                    "recipient": recipient,
                    "customer_name": entry["name"],
                    "customer_sku": entry["sku"],
                    "customer_spec": entry["spec"],
                    "customer_qty": source_qty,
                    "usage": usage,
                    "quantity": row_quantity,
                })

    rows = sorted(grouped.values(), key=lambda r: (r["supplier"], r["supplier_product"], r["supplier_sku"]))
    unmapped.sort(key=lambda e: (e["name"], e["sku"], e["spec"]))
    return {
        "rows": rows,
        "unmapped": unmapped,
        "supplier_count": len({r["supplier"] for r in rows}),
        "product_count": len(rows),
        "order_count": len({(s["order_no"], s["recipient"]) for r in rows for s in r["sources"]}),
        "customer_count": mapped_customers,
        "total_quantity": sum((r["quantity"] for r in rows), Decimal("0")),
        "unmapped_quantity": sum(e["quantity"] for e in unmapped),
    }


def _supplier_groups(rows: list):
    groups = {}
    for row in rows:
        groups.setdefault(row["supplier"], []).append(row)
    return groups


def generate_requirement_html(result: dict) -> str:
    """打印版备货清单：按供应商分页，不含客户与订单信息。"""
    rows = result.get("rows", [])
    if not rows:
        return "<p>暂无备货数据</p>"
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pages = []
    for supplier, supplier_rows in _supplier_groups(rows).items():
        subtotal = sum((row["quantity"] for row in supplier_rows), Decimal("0"))
        body = []
        for index, row in enumerate(supplier_rows, 1):
            body.append(
                "<tr>"
                f"<td>{index}</td>"
                f"<td class=\"name\">{escape(row['supplier_product'])}</td>"
                f"<td>{escape(row['supplier_sku']) or '-'}</td>"
                f"<td class=\"qty\">{format_quantity(row['quantity'])}</td>"
                "</tr>"
            )
        pages.append(
            '<div class="supplier-page">'
            '<h2>备货清单</h2>'
            f'<div class="meta"><span>供应商：<b>{escape(supplier)}</b></span>'
            f'<span>生成时间：{generated}</span></div>'
            '<table><thead><tr><th style="width:12%">序号</th>'
            '<th>供应商产品名称</th><th style="width:22%">货号</th>'
            '<th style="width:16%">数量</th></tr></thead><tbody>'
            + "".join(body)
            + '</tbody><tfoot><tr><td colspan="3" class="total-label">合计</td>'
            f'<td class="qty total">{format_quantity(subtotal)}</td></tr></tfoot></table>'
            '</div>'
        )
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><title>备货清单</title><style>'
        + _REQUIREMENT_CSS
        + '</style></head><body>'
        + "".join(pages)
        + '</body></html>'
    )


_REQUIREMENT_CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: 'Microsoft YaHei','SimHei',Arial,sans-serif; color:#000; margin:0; }
.supplier-page { page-break-after: always; }
.supplier-page:last-child { page-break-after: auto; }
h2 { text-align:center; font-size:18pt; margin:0 0 8mm 0; letter-spacing:2px; }
.meta { display:flex; justify-content:space-between; font-size:11pt; margin-bottom:4mm; }
table { width:100%; border-collapse:collapse; }
th { background:#eee; font-size:10.5pt; padding:2mm; border:1px solid #333; }
td { font-size:11pt; padding:2mm; border:1px solid #333; text-align:center; }
td.name { text-align:left; }
td.qty { font-weight:bold; }
tfoot td { font-weight:bold; background:#f7f7f7; }
tfoot .total-label { text-align:right; }
@media print { body { margin:0; } }
"""


def _order_detail_text(row: dict) -> str:
    """订单明细摘要（内部导出用，打印版不输出）：订单号/收件人(数量)。"""
    parts = []
    for source in row["sources"]:
        label = source["order_no"] or "-"
        if source.get("recipient"):
            label += "/" + source["recipient"]
        parts.append(f"{label}({format_quantity(source['quantity'])})")
    return "；".join(parts)


def _customer_detail_text(row: dict) -> str:
    totals = {}
    for source in row["sources"]:
        key = (source["customer_name"], source["customer_sku"], source["customer_spec"])
        totals[key] = totals.get(key, 0) + source["customer_qty"]
    parts = []
    for (name, sku, spec), quantity in totals.items():
        label = f"{name}({spec})" if spec else name
        if sku:
            label += f"[{sku}]"
        parts.append(f"{label}×{quantity}")
    return "；".join(parts)


def requirement_csv_text(result: dict) -> str:
    """CSV 文本（含表头，不含 BOM）。"""
    import io
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(["供应商", "供应商产品名称", "供应商货号", "备货数量", "订单明细", "客户产品明细", "备注"])
    for row in result.get("rows", []):
        writer.writerow([
            row["supplier"], row["supplier_product"], row["supplier_sku"],
            format_quantity(row["quantity"]),
            _order_detail_text(row), _customer_detail_text(row), "",
        ])
    return output.getvalue()


def write_requirement_csv(result: dict, path: str):
    """写 CSV：utf-8-sig，Excel 直接打开中文不乱码。"""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(requirement_csv_text(result))


def requirement_tsv_text(result: dict) -> str:
    """制表符分隔文本，方便直接粘贴到 Excel。"""
    lines = ["供应商\t供应商产品名称\t供应商货号\t备货数量"]
    for row in result.get("rows", []):
        lines.append("\t".join([
            row["supplier"], row["supplier_product"], row["supplier_sku"],
            format_quantity(row["quantity"]),
        ]))
    return "\n".join(lines)


def unmapped_summary(result: dict, limit: int = 30) -> str:
    """未映射客户产品提示文本（供弹窗确认）。"""
    unmapped = result.get("unmapped", [])
    lines = [
        f"{entry['name']}"
        + (f"（{entry['spec']}）" if entry["spec"] else "")
        + (f" SKU:{entry['sku']}" if entry["sku"] else "")
        + f" × {entry['quantity']}"
        for entry in unmapped[:limit]
    ]
    text = "\n".join(lines)
    if len(unmapped) > limit:
        text += f"\n……另有 {len(unmapped) - limit} 个未显示"
    return text
