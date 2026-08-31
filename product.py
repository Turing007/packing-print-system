"""
产品数据模型
"""
from dataclasses import dataclass, asdict
from typing import Optional
import json
import os
import re


def parse_box_sizes(value) -> list[int]:
    """Parse one or more supported box quantities from legacy or new data."""
    if isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    elif isinstance(value, str):
        raw_values = re.split(r"[,，、;/\s]+", value.strip())
    else:
        raw_values = [value]

    sizes = []
    for raw in raw_values:
        if raw in (None, ""):
            continue
        try:
            size = int(raw)
        except (TypeError, ValueError):
            raise ValueError("装箱数必须是一个或多个正整数，例如：10,15,20")
        if size <= 0:
            raise ValueError("装箱数必须大于0")
        if size not in sizes:
            sizes.append(size)
    if not sizes:
        raise ValueError("请填写至少一个装箱数")
    return sorted(sizes, reverse=True)


def format_box_sizes(value) -> str:
    """Return the canonical display/storage form for box quantities."""
    return ",".join(str(size) for size in parse_box_sizes(value))


@dataclass
class Product:
    """单个产品"""
    name: str = ""
    sku: str = ""
    quantity: int = 0
    qty_per_box: object = 1
    spec: str = ""
    recipient: str = ""
    order_no: str = ""
    remark: str = ""

    @property
    def full_boxes(self) -> int:
        """整箱数量"""
        size = max(parse_box_sizes(self.qty_per_box))
        return self.quantity // size if size > 0 else 0

    @property
    def remainder(self) -> int:
        """尾数"""
        size = max(parse_box_sizes(self.qty_per_box))
        return self.quantity % size if size > 0 else self.quantity

    def to_dict(self) -> dict:
        """保存产品和装箱所需字段。"""
        data = asdict(self)
        data["qty_per_box"] = format_box_sizes(self.qty_per_box)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "Product":
        return cls.from_dict(json.loads(json_str))


class ProductStore:
    """产品本地存储（JSON文件）"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.file = os.path.join(data_dir, "products.json")
        self.products: list = []
        self._load()

    def _load(self):
        if os.path.exists(self.file):
            try:
                with open(self.file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.products = [Product.from_dict(p) for p in data]
            except Exception:
                self.products = []
        else:
            self.products = []

    def _save(self):
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in self.products], f, ensure_ascii=False, indent=2)

    def add(self, product: Product):
        self.products.append(product)
        self._save()

    def update(self, index: int, product: Product):
        if 0 <= index < len(self.products):
            self.products[index] = product
            self._save()

    def remove(self, index: int):
        if 0 <= index < len(self.products):
            self.products.pop(index)
            self._save()

    def get(self, index: int) -> Optional[Product]:
        if 0 <= index < len(self.products):
            return self.products[index]
        return None

    def list_all(self) -> list:
        return list(self.products)

    def count(self) -> int:
        return len(self.products)

    def search_by_name(self, keyword: str) -> list:
        """按品名搜索产品"""
        if not keyword:
            return list(self.products)
        keyword = keyword.lower()
        return [p for p in self.products if keyword in p.name.lower()]

    def search_by_name_with_index(self, keyword: str) -> list:
        """按品名搜索，返回 (index, Product) 列表"""
        if not keyword:
            return list(enumerate(self.products))
        keyword = keyword.lower()
        return [(i, p) for i, p in enumerate(self.products) if keyword in p.name.lower()]

    def search_by_name_or_sku_with_index(self, keyword: str) -> list:
        """按品名或 SKU 模糊搜索，返回 (index, Product) 列表。"""
        if not keyword:
            return list(enumerate(self.products))
        keyword = keyword.lower()
        return [
            (i, p)
            for i, p in enumerate(self.products)
            if keyword in p.name.lower() or keyword in p.sku.lower()
        ]
