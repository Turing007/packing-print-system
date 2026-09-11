import unittest


class LiveBoxCountStatusTest(unittest.TestCase):
    """状态栏箱数应随装箱项实时更新，无需先点「计算装箱」。"""

    def setUp(self):
        import tkinter as tk
        from main import PackingApp

        self.root = tk.Tk()
        self.root.withdraw()
        self.app = PackingApp(self.root)

    def tearDown(self):
        self.root.destroy()

    @staticmethod
    def _item(name, sku, qty, per, recipient="R", order="O", spec="", remark=""):
        return {"name": name, "sku": sku, "per": per, "spec": spec,
                "recipient": recipient, "order": order, "qty": qty, "remark": remark}

    def _status(self):
        return self.app.l_status.cget("text")

    def _set_items(self, items):
        self.app.packing_items = items
        self.app.refresh_packing_table()

    def test_no_box_count_when_no_items(self):
        self.assertNotIn("箱数", self._status())

    def test_box_count_appears_without_calculate(self):
        self._set_items([
            self._item("棘轮扳手", "RATCHET", 53, "10,15,20"),
            self._item("棘轮扳手", "RATCHET2", 45, "10,15,20"),
        ])
        # 53 → 3箱，45 → 3箱，未点「计算装箱」也应显示
        self.assertIn("箱数: 6", self._status())

    def test_box_count_follows_tail_merge_switch(self):
        self._set_items([
            self._item("A", "A", 20, "3"),
            self._item("B", "B", 20, "3"),
            self._item("C", "C", 20, "3"),
        ])
        self.app.merge_tail.set(False)
        self.app.refresh_packing_table()
        self.assertIn("箱数: 21", self._status())
        self.assertIn("尾数合并: 否", self._status())

        self.app.merge_tail.set(True)
        self.app.refresh_packing_table()
        self.assertIn("箱数: 20", self._status())
        self.assertIn("尾数合并: 是", self._status())

    def test_computed_boxes_take_precedence_over_estimate(self):
        from packing import BoxLabel

        self._set_items([self._item("A", "A", 53, "10,15,20")])
        self.assertIn("箱数: 3", self._status())
        # 已生成箱唛后（例如手动合箱使箱数变少）以 current_boxes 为准
        self.app.current_boxes = [BoxLabel(recipient="R", order_no="O")]
        self.app.refresh_packing_table()
        self.assertIn("箱数: 1", self._status())


if __name__ == "__main__":
    unittest.main()
