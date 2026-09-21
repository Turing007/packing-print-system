import unittest


class _FakeMessagebox:
    def __init__(self, confirm=True):
        self.confirm = confirm
        self.infos = []
        self.asks = []

    def showinfo(self, title, message, **kwargs):
        self.infos.append((title, message))

    def showwarning(self, title, message, **kwargs):
        self.infos.append((title, message))

    def showerror(self, title, message, **kwargs):
        self.infos.append((title, message))

    def askyesno(self, title, message, **kwargs):
        self.asks.append((title, message))
        return self.confirm


class ManualMergeBoxesTest(unittest.TestCase):
    """手动合箱：无视装箱数限制，超出装箱数时弹窗确认后仍可合箱。"""

    def setUp(self):
        import tkinter as tk
        import main
        from main import PackingApp
        from packing import calculate_boxes
        from product import Product

        self.main = main
        self._original_messagebox = main.messagebox
        self.calculate_boxes = calculate_boxes
        self.Product = Product

        self.root = tk.Tk()
        self.root.withdraw()
        self.app = PackingApp(self.root)
        self._set_boxes([
            Product(name="代送变器", sku="A", quantity=55, qty_per_box=50, spec="MT", recipient="陶晴", order_no="501"),
            Product(name="热熔胶枪", sku="B", quantity=35, qty_per_box=20, spec="MT", recipient="陶晴", order_no="501"),
        ])

    def tearDown(self):
        self.main.messagebox = self._original_messagebox
        self.root.destroy()

    def _set_boxes(self, products):
        self.boxes = self.calculate_boxes(products, merge_tail=False)
        self.app.current_boxes = self.boxes
        self.app.refresh_box_table()

    def _row_for(self, box_index):
        for row_id, indexes in self.app.box_row_indexes.items():
            if indexes and box_index in indexes:
                return row_id
        raise AssertionError("未找到包含箱索引 %s 的行" % box_index)

    def _patch(self, confirm=True):
        fake = _FakeMessagebox(confirm=confirm)
        self.main.messagebox = fake
        return fake

    def test_full_box_row_maps_to_single_representative_box(self):
        full_row = self._row_for(0)
        indexes = self.app.box_row_indexes[full_row]
        self.assertEqual(len(indexes), 1)
        self.assertFalse(self.app.current_boxes[indexes[0]].is_tail)

    def test_merging_full_box_row_leaves_n_minus_one_full_boxes(self):
        self._set_boxes([
            self.Product(name="代送变器", sku="A", quantity=55, qty_per_box=25, recipient="陶晴", order_no="501"),
        ])
        # A: 25整 + 25整 + 5尾 → 3 箱
        self.assertEqual(len(self.boxes), 3)

        fake = self._patch(confirm=True)
        self.app.btree.selection_set([self._row_for(0), self._row_for(2)])

        self.app.merge_selected_boxes()

        self.assertEqual(len(fake.asks), 1)
        self.assertEqual(len(self.app.current_boxes), 2)
        remaining_full = [box for box in self.app.current_boxes if not box.is_tail]
        self.assertEqual(len(remaining_full), 1)
        self.assertEqual(remaining_full[0].quantity_in_box, 25)
        merged = next(box for box in self.app.current_boxes if box.remark == "手动合箱")
        self.assertEqual(merged.quantity_in_box, 30)

        full_row = next(row for row, idx in self.app.box_row_indexes.items()
                        if idx and not self.app.current_boxes[idx[0]].is_tail)
        self.assertEqual(str(self.app.btree.item(full_row, "values")[5]), "1")

    def test_merge_exceeding_capacity_asks_and_merges_on_confirm(self):
        fake = self._patch(confirm=True)
        self.app.btree.selection_set([self._row_for(0), self._row_for(1)])

        self.app.merge_selected_boxes()

        self.assertEqual(len(fake.asks), 1)
        self.assertEqual(fake.asks[0][0], "超出装箱数")
        self.assertEqual(len(self.app.current_boxes), 3)
        manual = next(box for box in self.app.current_boxes if box.remark == "手动合箱")
        self.assertEqual(manual.quantity_in_box, 55)

    def test_merge_exceeding_capacity_aborts_on_cancel(self):
        fake = self._patch(confirm=False)
        self.app.btree.selection_set([self._row_for(0), self._row_for(1)])

        self.app.merge_selected_boxes()

        self.assertEqual(len(fake.asks), 1)
        self.assertEqual(len(self.app.current_boxes), len(self.boxes))
        self.assertFalse(any(box.remark == "手动合箱" for box in self.app.current_boxes))

    def test_merge_within_capacity_has_no_prompt(self):
        fake = self._patch(confirm=True)
        self.app.btree.selection_set([self._row_for(1), self._row_for(3)])

        self.app.merge_selected_boxes()

        self.assertEqual(fake.asks, [])
        self.assertEqual(len(self.app.current_boxes), 3)
        manual = next(box for box in self.app.current_boxes if box.remark == "手动合箱")
        self.assertEqual(manual.quantity_in_box, 20)

    def test_merge_across_orders_is_rejected(self):
        self._set_boxes([
            self.Product(name="A", sku="A", quantity=5, qty_per_box=3, recipient="R", order_no="O1"),
            self.Product(name="B", sku="B", quantity=5, qty_per_box=3, recipient="R", order_no="O2"),
        ])
        fake = self._patch(confirm=True)
        self.app.btree.selection_set([self._row_for(0), self._row_for(2)])

        self.app.merge_selected_boxes()

        self.assertEqual(fake.asks, [])
        self.assertEqual(len(self.app.current_boxes), len(self.boxes))
        self.assertTrue(any("同一个收件人和订单号" in msg for _, msg in fake.infos))


if __name__ == "__main__":
    unittest.main()
