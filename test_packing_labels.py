import re
import unittest

from packing import BoxLabel, generate_individual_box_labels_html


class IndividualBoxLabelTest(unittest.TestCase):
    def test_total_quantity_is_grouped_by_selected_product_spec(self):
        boxes = [
            BoxLabel(
                box_number=1,
                total_boxes=2,
                product_name="水泵",
                product_sku="",
                spec="MT",
                qty_per_box=8,
                quantity_in_box=8,
                recipient="华南",
                order_no="PO1",
            ),
            BoxLabel(
                box_number=2,
                total_boxes=2,
                product_name="水泵",
                product_sku="",
                spec="DE",
                qty_per_box=8,
                quantity_in_box=8,
                recipient="华南",
                order_no="PO1",
            ),
        ]

        html = generate_individual_box_labels_html(boxes)

        self.assertEqual(_total_quantity_for_spec(html, "MT"), "8")
        self.assertEqual(_total_quantity_for_spec(html, "DE"), "8")

    def test_merged_tail_label_renders_each_sku_on_its_own_row(self):
        boxes = [
            BoxLabel(
                box_number=2,
                total_boxes=20,
                product_name="新款振动器(1)+新款振动器(2)",
                product_sku="JIB0325-MT(1)+JIB0325-MWK(2)",
                qty_per_box=3,
                quantity_in_box=3,
                is_tail=True,
                recipient="郑金玲（501）",
                order_no="PO1749674635559078",
                remark="尾数合并",
                tail_items=[
                    {"sku": "JIB0325-MT", "name": "新款振动器", "spec": "MT", "quantity_in_box": 1, "box_count": 1, "total_quantity": 20, "remark": "MT备注"},
                    {"sku": "JIB0325-MWK", "name": "新款振动器", "spec": "MWK", "quantity_in_box": 2, "box_count": 1, "total_quantity": 20, "remark": "MWK备注"},
                ],
            )
        ]

        html = generate_individual_box_labels_html(boxes)

        self.assertIn("<th>箱数</th>", html)
        self.assertIn("<td>JIB0325-MT</td><td>新款振动器</td><td>MT</td><td class=\"qty\">1</td><td class=\"qty\">1</td><td class=\"qty\">20</td>", html)
        self.assertIn("<td>JIB0325-MWK</td><td>新款振动器</td><td>MWK</td><td class=\"qty\">2</td><td class=\"qty\">1</td><td class=\"qty\">20</td>", html)
        self.assertNotIn("JIB0325-MT(1)+JIB0325-MWK(2)</td><td>新款振动器(1)+新款振动器(2)", html)
        self.assertIn('class="l-sku-group"', html)
        self.assertIn("SKU备注: MT备注", html)
        self.assertIn("SKU备注: MWK备注", html)

    def test_merged_tail_label_uses_one_header_for_all_skus(self):
        html = generate_individual_box_labels_html([
            BoxLabel(
                box_number=1,
                total_boxes=1,
                product_name="A(1)+B(2)",
                product_sku="SKU-A(1)+SKU-B(2)",
                qty_per_box=3,
                quantity_in_box=3,
                is_tail=True,
                tail_items=[
                    {"sku": "SKU-A", "name": "A", "spec": "S1", "quantity_in_box": 1, "box_count": 1, "total_quantity": 4, "remark": "备注A"},
                    {"sku": "SKU-B", "name": "B", "spec": "S2", "quantity_in_box": 2, "box_count": 1, "total_quantity": 5, "remark": ""},
                ],
            )
        ])

        self.assertEqual(html.count("<thead>"), 1)
        self.assertEqual(html.count('class="l-product-remark-row"'), 1)
        self.assertIn('colspan="6"', html)

    def test_sku_without_remark_does_not_render_empty_remark_row(self):
        html = generate_individual_box_labels_html([
            BoxLabel(
                box_number=1,
                total_boxes=1,
                product_name="A",
                product_sku="SKU-A",
                spec="S1",
                qty_per_box=3,
                quantity_in_box=3,
            )
        ])

        self.assertNotIn('class="l-product-remark-row"', html)

    def test_label_renders_sku_remark_separately_and_order_remark_at_bottom(self):
        html = generate_individual_box_labels_html([
            BoxLabel(
                box_number=1,
                total_boxes=1,
                product_name="水泵",
                product_sku="P1",
                spec="MT",
                qty_per_box=8,
                quantity_in_box=8,
                box_count=1,
                total_quantity=8,
                product_remark="易碎",
                order_remark="请先检查外箱",
            )
        ])

        self.assertIn("SKU备注: 易碎", html)
        self.assertIn("订单备注: 请先检查外箱", html)
        self.assertLess(html.index("订单备注: 请先检查外箱"), html.index("日期:"))

    def test_full_box_label_shows_order_total_quantity_and_full_box_count(self):
        boxes = []
        for index in range(6):
            boxes.append(
                BoxLabel(
                    box_number=index + 1,
                    total_boxes=7,
                    product_name="新款振动器",
                    product_sku="JIB0325-DW",
                    spec="DE",
                    qty_per_box=3,
                    quantity_in_box=3,
                    recipient="郑金玲",
                    order_no="501",
                    box_count=6,
                    total_quantity=20,
                )
            )
        boxes.append(
            BoxLabel(
                box_number=7,
                total_boxes=7,
                product_name="新款振动器",
                product_sku="JIB0325-DW",
                spec="DE",
                qty_per_box=3,
                quantity_in_box=2,
                is_tail=True,
                recipient="郑金玲",
                order_no="501",
            )
        )

        html = generate_individual_box_labels_html(boxes)

        self.assertIn("<td style=\"font-family:Consolas,monospace\">JIB0325-DW</td><td>新款振动器</td><td>DE</td><td class=\"qty\">3</td><td class=\"qty\">6</td><td class=\"qty\">20</td>", html)
        self.assertNotIn("<td class=\"qty\">3</td><td class=\"qty\">20</td>", html)


def _total_quantity_for_spec(html: str, spec: str) -> str:
    match = re.search(
        rf"<td>{re.escape(spec)}</td><td class=\"qty\">8</td><td class=\"qty\">\d+</td><td class=\"qty\">(\d+)</td>",
        html,
    )
    if not match:
        raise AssertionError(f"Could not find label row for spec {spec!r}")
    return match.group(1)


if __name__ == "__main__":
    unittest.main()
