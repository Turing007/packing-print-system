import unittest

from packing import calculate_boxes, merge_selected_boxes
from product import Product, format_box_sizes, parse_box_sizes


class MultiBoxSizeCalculationTest(unittest.TestCase):
    def test_multiple_box_sizes_use_the_fewest_boxes_with_tail_last(self):
        boxes = calculate_boxes([
            Product(name="棘轮扳手", sku="RATCHET", quantity=53, qty_per_box="10,15,20", recipient="R", order_no="O")
        ], merge_tail=False)

        self.assertEqual(len(boxes), 3)
        self.assertEqual([box.quantity_in_box for box in boxes], [20, 20, 13])
        self.assertEqual([box.qty_per_box for box in boxes], [20, 20, 20])
        self.assertEqual([box.is_tail for box in boxes], [False, False, True])
        self.assertEqual([box.box_count for box in boxes], [2, 2, 1])
        self.assertTrue(all(box.total_quantity == 53 for box in boxes))

    def test_multiple_box_sizes_can_make_exact_fewest_box_plan(self):
        boxes = calculate_boxes([
            Product(name="棘轮扳手", sku="RATCHET", quantity=45, qty_per_box="10,15,20", recipient="R", order_no="O")
        ], merge_tail=False)

        self.assertEqual(len(boxes), 3)
        self.assertEqual([box.quantity_in_box for box in boxes], [15, 15, 15])
        self.assertTrue(all(not box.is_tail for box in boxes))

    def test_exact_plans_prefer_even_distribution(self):
        # 同箱数下选各箱装量最均衡的组合：30 → 15+15（而不是 20+10），50 → 20+15+15（而不是 20+20+10）
        boxes = calculate_boxes([
            Product(name="棘轮扳手", sku="RATCHET", quantity=30, qty_per_box="10,15,20", recipient="R", order_no="O")
        ], merge_tail=False)
        self.assertEqual([box.quantity_in_box for box in boxes], [15, 15])
        self.assertTrue(all(not box.is_tail for box in boxes))

        boxes = calculate_boxes([
            Product(name="棘轮扳手", sku="RATCHET", quantity=50, qty_per_box="10,15,20", recipient="R", order_no="O")
        ], merge_tail=False)
        self.assertEqual([box.quantity_in_box for box in boxes], [20, 15, 15])
        self.assertTrue(all(not box.is_tail for box in boxes))

    def test_box_size_parser_accepts_legacy_and_chinese_separators(self):
        self.assertEqual(parse_box_sizes(10), [10])
        self.assertEqual(parse_box_sizes("10，15、20"), [20, 15, 10])
        self.assertEqual(format_box_sizes("20,10,20"), "20,10")


class TailMergeCalculationTest(unittest.TestCase):
    def test_merged_tails_are_split_by_box_capacity(self):
        products = [
            Product(name="新款振动器", sku="JIB0325-DW", quantity=20, qty_per_box=3, spec="DE", recipient="郑金玲", order_no="501", remark="DW备注"),
            Product(name="新款振动器", sku="JIB0325-MT", quantity=20, qty_per_box=3, spec="MT", recipient="郑金玲", order_no="501", remark="MT备注"),
            Product(name="新款振动器", sku="JIB0325-MWK", quantity=20, qty_per_box=3, spec="MI", recipient="郑金玲", order_no="501", remark="MWK备注"),
        ]

        boxes = calculate_boxes(products, merge_tail=True)
        tail_boxes = [box for box in boxes if box.is_tail]

        self.assertEqual(len(tail_boxes), 2)
        self.assertEqual([box.quantity_in_box for box in tail_boxes], [3, 3])
        self.assertEqual(tail_boxes[0].product_sku, "JIB0325-DW(2)+JIB0325-MT(1)")
        self.assertEqual(tail_boxes[1].product_sku, "JIB0325-MT(1)+JIB0325-MWK(2)")
        self.assertEqual(
            tail_boxes[0].tail_items,
            [
                {"sku": "JIB0325-DW", "name": "新款振动器", "spec": "DE", "quantity_in_box": 2, "box_count": 1, "total_quantity": 20, "remark": "DW备注"},
                {"sku": "JIB0325-MT", "name": "新款振动器", "spec": "MT", "quantity_in_box": 1, "box_count": 1, "total_quantity": 20, "remark": "MT备注"},
            ],
        )
        self.assertTrue(all(box.qty_per_box == 3 for box in tail_boxes))
        self.assertTrue(all(box.quantity_in_box <= box.qty_per_box for box in tail_boxes))
        self.assertEqual(len(boxes), 20)

        full_box = next(box for box in boxes if not box.is_tail and box.product_sku == "JIB0325-DW")
        self.assertEqual(full_box.box_count, 6)
        self.assertEqual(full_box.total_quantity, 20)
        self.assertEqual(full_box.product_remark, "DW备注")
        self.assertEqual(full_box.order_remark, "")

    def test_product_remarks_are_preserved_for_tail_items(self):
        boxes = calculate_boxes([
            Product(name="A", sku="A", quantity=5, qty_per_box=3, spec="S", recipient="R", order_no="O", remark="A备注"),
            Product(name="B", sku="B", quantity=5, qty_per_box=3, spec="S", recipient="R", order_no="O", remark="B备注"),
        ], merge_tail=True)

        tail = next(box for box in boxes if box.is_tail)
        self.assertEqual(
            [(item["sku"], item["remark"]) for item in tail.tail_items],
            [("A", "A备注"), ("B", "B备注")],
        )

    def test_merged_tails_mix_different_box_capacities(self):
        products = [
            Product(name="A", sku="A", quantity=5, qty_per_box=3, recipient="R", order_no="O"),
            Product(name="B", sku="B", quantity=6, qty_per_box=4, recipient="R", order_no="O"),
        ]

        boxes = calculate_boxes(products, merge_tail=True)
        tail_boxes = [box for box in boxes if box.is_tail]

        self.assertEqual([(box.qty_per_box, box.quantity_in_box) for box in tail_boxes], [(4, 4)])
        self.assertEqual(
            [(item["sku"], item["quantity_in_box"]) for item in tail_boxes[0].tail_items],
            [("A", 2), ("B", 2)],
        )

    def test_box_numbers_are_calculated_per_order(self):
        boxes = calculate_boxes([
            Product(name="A", sku="A", quantity=5, qty_per_box=3, recipient="R", order_no="O1"),
            Product(name="B", sku="B", quantity=6, qty_per_box=3, recipient="R", order_no="O2"),
        ], merge_tail=False)

        by_order = {}
        for box in boxes:
            by_order.setdefault(box.order_no, []).append(box)

        self.assertEqual([box.box_number for box in by_order["O1"]], [1, 2])
        self.assertEqual([box.total_boxes for box in by_order["O1"]], [2, 2])
        self.assertEqual([box.box_number for box in by_order["O2"]], [1, 2])
        self.assertEqual([box.total_boxes for box in by_order["O2"]], [2, 2])

    def test_selected_tail_boxes_can_be_merged_manually(self):
        products = [
            Product(name="代送变器", sku="A", quantity=55, qty_per_box=50, spec="MT", recipient="陶晴", order_no="501", remark="A备注"),
            Product(name="热熔胶枪", sku="B", quantity=35, qty_per_box=20, spec="MT", recipient="陶晴", order_no="501", remark="B备注"),
        ]
        boxes = calculate_boxes(products, merge_tail=False)
        selected = [i for i, box in enumerate(boxes) if box.is_tail]

        merged = merge_selected_boxes(boxes, selected)
        tail_boxes = [box for box in merged if box.is_tail]
        manual_box = next(box for box in tail_boxes if box.remark == "手动合箱")

        self.assertEqual(len(merged), len(boxes) - 1)
        self.assertEqual(manual_box.recipient, "陶晴")
        self.assertEqual(manual_box.order_no, "501")
        self.assertEqual(manual_box.product_sku, "A(5)+B(15)")
        self.assertEqual(manual_box.quantity_in_box, 20)
        self.assertEqual(manual_box.tail_items, [
            {"sku": "A", "name": "代送变器", "spec": "MT", "quantity_in_box": 5, "box_count": 1, "total_quantity": 55, "remark": "A备注"},
            {"sku": "B", "name": "热熔胶枪", "spec": "MT", "quantity_in_box": 15, "box_count": 1, "total_quantity": 35, "remark": "B备注"},
        ])
        self.assertEqual([box.box_number for box in merged], list(range(1, len(merged) + 1)))

    def test_full_and_tail_boxes_can_be_merged(self):
        """整箱也能和尾数箱一起合箱：内容合并为一个箱子，装箱数=实际件数。"""
        boxes = calculate_boxes([
            Product(name="代送变器", sku="A", quantity=55, qty_per_box=50, spec="MT", recipient="陶晴", order_no="501", remark="A备注"),
            Product(name="热熔胶枪", sku="B", quantity=35, qty_per_box=20, spec="MT", recipient="陶晴", order_no="501", remark="B备注"),
        ], merge_tail=False)
        # A: 50整 + 5尾，B: 20整 + 15尾 → 共 4 箱
        self.assertEqual(len(boxes), 4)

        selected = [i for i, box in enumerate(boxes) if box.is_tail]
        selected.append(next(i for i, box in enumerate(boxes) if box.product_sku == "B" and not box.is_tail))
        self.assertEqual(len(selected), 3)

        merged = merge_selected_boxes(boxes, selected)
        # 3 箱合成 1 箱：只剩 A 的整箱 + 合并箱
        self.assertEqual(len(merged), 2)
        manual_box = next(box for box in merged if box.remark == "手动合箱")
        self.assertEqual(manual_box.quantity_in_box, 40)
        self.assertEqual(manual_box.product_name, "代送变器(5)+热熔胶枪(35)")
        items = {item["sku"]: item["quantity_in_box"] for item in manual_box.tail_items}
        self.assertEqual(items, {"A": 5, "B": 35})
        # 未选中的 A 整箱保持不变
        full_a = next(box for box in merged if box.product_sku == "A" and not box.is_tail)
        self.assertEqual((full_a.quantity_in_box, full_a.qty_per_box), (50, 50))
        self.assertEqual([box.box_number for box in merged], [1, 2])

    def test_manual_merge_rejects_different_orders(self):
        boxes = calculate_boxes([
            Product(name="A", sku="A", quantity=55, qty_per_box=50, recipient="R", order_no="O1"),
            Product(name="B", sku="B", quantity=25, qty_per_box=20, recipient="R", order_no="O2"),
        ], merge_tail=False)
        tail_a = next(i for i, box in enumerate(boxes) if box.is_tail and box.order_no == "O1")
        tail_b = next(i for i, box in enumerate(boxes) if box.is_tail and box.order_no == "O2")

        with self.assertRaisesRegex(ValueError, "同一个收件人和订单号"):
            merge_selected_boxes(boxes, [tail_a, tail_b])

    def test_manual_tail_merge_recalculates_totals_per_order(self):
        boxes = calculate_boxes([
            Product(name="A", sku="A", quantity=5, qty_per_box=3, recipient="R", order_no="O1"),
            Product(name="B", sku="B", quantity=5, qty_per_box=3, recipient="R", order_no="O1"),
            Product(name="C", sku="C", quantity=4, qty_per_box=3, recipient="R", order_no="O2"),
        ], merge_tail=False)
        selected = [
            i for i, box in enumerate(boxes)
            if box.is_tail and box.order_no == "O1"
        ]

        merged = merge_selected_boxes(boxes, selected)
        by_order = {}
        for box in merged:
            by_order.setdefault(box.order_no, []).append(box)

        self.assertEqual([box.box_number for box in by_order["O1"]], [1, 2, 3])
        self.assertEqual([box.total_boxes for box in by_order["O1"]], [3, 3, 3])
        self.assertEqual([box.box_number for box in by_order["O2"]], [1, 2])
        self.assertEqual([box.total_boxes for box in by_order["O2"]], [2, 2])


if __name__ == "__main__":
    unittest.main()
