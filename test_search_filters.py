import tempfile
import unittest

from main import (
    order_history_date_options,
    order_history_indexed_latest_first,
    order_history_matches_filters,
    sort_order_history_latest_first,
)
from product import Product, ProductStore


class ProductSearchTest(unittest.TestCase):
    def test_search_matches_product_name_or_sku(self):
        with tempfile.TemporaryDirectory() as data_dir:
            store = ProductStore(data_dir=data_dir)
            store.products = [
                Product(name="振动器", sku="JIB0325-DW"),
                Product(name="热熔胶枪", sku="GLUE-001"),
                Product(name="收纳盒", sku="BOX-888"),
            ]

            by_name = store.search_by_name_or_sku_with_index("胶")
            by_sku = store.search_by_name_or_sku_with_index("jib0325")

            self.assertEqual([(i, p.sku) for i, p in by_name], [(1, "GLUE-001")])
            self.assertEqual([(i, p.name) for i, p in by_sku], [(0, "振动器")])


class OrderHistoryFilterTest(unittest.TestCase):
    def test_history_is_sorted_with_latest_created_at_first(self):
        history = [
            {"order_no": "old", "created_at": "2026-07-17 23:59:59"},
            {"order_no": "new", "created_at": "2026-07-18 00:00:01"},
            {"order_no": "middle", "created_at": "2026-07-18 00:00:00"},
        ]

        sorted_history = sort_order_history_latest_first(history)

        self.assertEqual([item["order_no"] for item in sorted_history], ["new", "middle", "old"])

    def test_sorted_history_keeps_original_indexes_for_row_actions(self):
        history = [
            {"order_no": "old", "created_at": "2026-07-17 23:59:59"},
            {"order_no": "new", "created_at": "2026-07-18 00:00:01"},
            {"order_no": "middle", "created_at": "2026-07-18 00:00:00"},
        ]

        indexed_history = order_history_indexed_latest_first(history)

        self.assertEqual([(idx, item["order_no"]) for idx, item in indexed_history], [(1, "new"), (2, "middle"), (0, "old")])

    def test_history_keyword_matches_recipient_or_order_number(self):
        history = {
            "recipient": "张三",
            "order_no": "AMZ-20260718",
            "created_at": "2026-07-18 09:30:00",
        }

        self.assertTrue(order_history_matches_filters(history, "张", "", ""))
        self.assertTrue(order_history_matches_filters(history, "amz", "", ""))
        self.assertFalse(order_history_matches_filters(history, "李四", "", ""))

    def test_history_date_options_are_unique_and_sorted(self):
        history = [
            {"created_at": "2026-07-17 10:00:00"},
            {"created_at": "2026-07-18 10:00:00"},
            {"created_at": "2026-07-17 11:00:00"},
            {"created_at": ""},
        ]

        self.assertEqual(order_history_date_options(history), ["", "2026-07-18", "2026-07-17"])


if __name__ == "__main__":
    unittest.main()
