# -*- coding: utf-8 -*-
"""装箱添加时的重复产品检查测试。

规则：SKU 相同（且非空）即视为同一产品；SKU 不同（或为空）时
品名+规格完全相同也视为同一产品；命中时弹窗确认是否仍要添加。
"""
import os
import tempfile
import unittest
from unittest import mock

import storage
from product import Product


def _make_app():
    import tkinter as tk
    from main import PackingApp
    root = tk.Tk()
    root.withdraw()
    app = PackingApp(root)
    return root, app


class DuplicatePackingItemTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        data_dir = os.path.join(self._tmp.name, "data")
        os.makedirs(data_dir, exist_ok=True)
        patcher = mock.patch.object(storage, "get_data_dir", return_value=data_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.root, self.app = _make_app()
        self.addCleanup(self.root.destroy)

    def _add(self, product, qty=10):
        self.app.selected_prod_for_packing = product
        self.app.e_pk_qty.delete(0, "end")
        self.app.e_pk_qty.insert(0, str(qty))
        self.app.add_packing_item()

    def test_no_duplicate_adds_without_dialog(self):
        self._add(Product(name="振动器", sku="JIB", spec="DE"))
        with mock.patch("tkinter.messagebox.askyesno") as ask:
            self._add(Product(name="包装膜", sku="FILM", spec="S"))
        ask.assert_not_called()
        self.assertEqual(len(self.app.packing_items), 2)

    def test_same_sku_is_duplicate_even_with_different_name(self):
        self._add(Product(name="振动器", sku="JIB", spec="DE"))
        with mock.patch("tkinter.messagebox.askyesno", return_value=True) as ask:
            self._add(Product(name="别的名字", sku="JIB", spec="XX"))
        ask.assert_called_once()
        self.assertIn("重复", ask.call_args[0][1])
        self.assertEqual(len(self.app.packing_items), 2)

    def test_same_name_and_spec_different_sku_is_duplicate(self):
        self._add(Product(name="振动器", sku="JIB", spec="DE"))
        with mock.patch("tkinter.messagebox.askyesno", return_value=True) as ask:
            self._add(Product(name="振动器", sku="OTHER", spec="DE"))
        ask.assert_called_once()
        self.assertEqual(len(self.app.packing_items), 2)

    def test_cancel_does_not_add(self):
        self._add(Product(name="振动器", sku="JIB", spec="DE"))
        with mock.patch("tkinter.messagebox.askyesno", return_value=False) as ask:
            self._add(Product(name="振动器", sku="JIB", spec="DE"))
        ask.assert_called_once()
        self.assertEqual(len(self.app.packing_items), 1)

    def test_same_name_different_spec_not_duplicate(self):
        self._add(Product(name="振动器", sku="JIB", spec="DE"))
        with mock.patch("tkinter.messagebox.askyesno") as ask:
            self._add(Product(name="振动器", sku="OTHER", spec="MT"))
        ask.assert_not_called()
        self.assertEqual(len(self.app.packing_items), 2)

    def test_empty_sku_falls_back_to_name_and_spec(self):
        self._add(Product(name="无码产品A", sku="", spec=""))
        with mock.patch("tkinter.messagebox.askyesno") as ask:
            # 两个都没有 SKU 且品名不同：不算重复
            self._add(Product(name="无码产品B", sku="", spec=""))
        ask.assert_not_called()
        with mock.patch("tkinter.messagebox.askyesno", return_value=True) as ask:
            # 品名+规格完全相同：算重复
            self._add(Product(name="无码产品A", sku="", spec=""))
        ask.assert_called_once()
        self.assertEqual(len(self.app.packing_items), 3)


if __name__ == "__main__":
    unittest.main()
