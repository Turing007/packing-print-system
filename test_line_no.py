import json
import tempfile
import unittest

from packing import (
    BoxLabel,
    calculate_boxes,
    format_recipient,
    generate_individual_box_labels_html,
    merge_selected_boxes,
)
from product import Product
from storage import load_order_history, save_order_to_history


class FormatRecipientTest(unittest.TestCase):
    def test_line_no_is_appended_in_parentheses(self):
        self.assertEqual(format_recipient("郑金玲", "501"), "郑金玲（501）")
        self.assertEqual(format_recipient("郑金玲", ""), "郑金玲")
        self.assertEqual(format_recipient("郑金玲", "  "), "郑金玲")
        self.assertEqual(format_recipient("", "5"), "（5）")
        self.assertEqual(format_recipient("", ""), "")


class PackingLineNoTest(unittest.TestCase):
    def test_line_no_follows_order_to_every_box(self):
        boxes = calculate_boxes([
            Product(name="棘轮扳手", sku="A", quantity=30, qty_per_box=10,
                    recipient="张三", order_no="PO1", line_no="7"),
            Product(name="热熔胶枪", sku="B", quantity=25, qty_per_box=10,
                    recipient="张三", order_no="PO1", line_no="7"),
        ], merge_tail=False)

        self.assertTrue(boxes)
        self.assertTrue(all(box.line_no == "7" for box in boxes))
        self.assertTrue(all(box.display_recipient == "张三（7）" for box in boxes))

    def test_merged_tail_boxes_keep_order_line_no(self):
        boxes = calculate_boxes([
            Product(name="A", sku="A", quantity=5, qty_per_box=3,
                    recipient="张三", order_no="PO1", line_no="7"),
            Product(name="B", sku="B", quantity=5, qty_per_box=3,
                    recipient="张三", order_no="PO1", line_no="7"),
        ], merge_tail=True)

        tail_boxes = [box for box in boxes if box.is_tail]
        self.assertTrue(tail_boxes)
        self.assertTrue(all(box.line_no == "7" for box in tail_boxes))

    def test_orders_without_line_no_render_plain_recipient(self):
        boxes = calculate_boxes([
            Product(name="A", sku="A", quantity=10, qty_per_box=10,
                    recipient="张三", order_no="PO1"),
        ], merge_tail=False)

        self.assertEqual(boxes[0].line_no, "")
        self.assertEqual(boxes[0].display_recipient, "张三")

    def test_manual_merge_keeps_line_no(self):
        boxes = calculate_boxes([
            Product(name="A", sku="A", quantity=15, qty_per_box=10,
                    recipient="张三", order_no="PO1", line_no="9"),
        ], merge_tail=False)
        self.assertEqual(len(boxes), 2)

        merged = merge_selected_boxes(boxes, [0, 1])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].line_no, "9")
        self.assertEqual(merged[0].display_recipient, "张三（9）")

    def test_box_label_from_legacy_dict_defaults_line_no(self):
        label = BoxLabel.from_dict({"recipient": "张三", "order_no": "PO1"})
        self.assertEqual(label.line_no, "")
        self.assertEqual(label.display_recipient, "张三")


class LabelHtmlTest(unittest.TestCase):
    def test_printed_label_shows_recipient_with_line_no(self):
        html = generate_individual_box_labels_html([
            BoxLabel(box_number=1, total_boxes=1, product_name="A", product_sku="A",
                    qty_per_box=10, quantity_in_box=10, recipient="张三",
                    order_no="PO1", line_no="7"),
        ])

        self.assertIn("张三（7）", html)


class OrderHistoryLineNoTest(unittest.TestCase):
    def test_line_no_is_saved_and_loaded(self):
        import storage

        original = storage.DATA_DIR
        with tempfile.TemporaryDirectory() as data_dir:
            storage.DATA_DIR = data_dir
            try:
                save_order_to_history("张三", "PO1", [{"name": "A", "sku": "A", "qty": 10, "per": 10}],
                                      "", "7")
                history = load_order_history()
                self.assertEqual(history[0]["line_no"], "7")
            finally:
                storage.DATA_DIR = original

    def test_order_without_line_no_defaults_to_empty(self):
        import storage

        original = storage.DATA_DIR
        with tempfile.TemporaryDirectory() as data_dir:
            storage.DATA_DIR = data_dir
            try:
                save_order_to_history("张三", "PO1", [{"name": "A", "sku": "A", "qty": 10, "per": 10}])
                history = load_order_history()
                self.assertEqual(history[0]["line_no"], "")
            finally:
                storage.DATA_DIR = original


if __name__ == "__main__":
    unittest.main()
