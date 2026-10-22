# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from decimal import Decimal

import supplier
from product import Product, ProductStore
from supplier import (
    SupplierBomStore,
    build_requirement,
    format_quantity,
    generate_requirement_html,
    parse_usage,
    product_key,
    requirement_csv_text,
    requirement_tsv_text,
    write_requirement_csv,
)


CUSTOMER_A = {"name": "无刷棘轮扳手", "sku": "SEK-001", "spec": "MT"}
CUSTOMER_B = {"name": "水磨", "sku": "", "spec": "DE"}


class SupplierKeyTest(unittest.TestCase):
    def test_sku_takes_priority_and_is_case_insensitive(self):
        self.assertEqual(product_key("名字1", "abc-1", "MT"), product_key("名字2", "ABC-1", "DE"))

    def test_empty_sku_falls_back_to_name_and_spec(self):
        self.assertEqual(product_key("水磨", "", "DE"), product_key("水磨", "", "DE"))
        self.assertNotEqual(product_key("水磨", "", "DE"), product_key("水磨", "", "MT"))

    def test_usage_validation_and_format(self):
        self.assertEqual(parse_usage("1.5"), Decimal("1.5"))
        self.assertEqual(format_quantity(Decimal("20")), "20")
        self.assertEqual(format_quantity(Decimal("20.500")), "20.5")
        for invalid in ("0", "-1", "abc", ""):
            with self.assertRaises(ValueError):
                parse_usage(invalid)


class SupplierBomStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SupplierBomStore(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_update_remove_component(self):
        key = product_key(**CUSTOMER_A)
        self.store.add_component(key, CUSTOMER_A, {
            "supplier": "A厂", "supplier_product": "主体", "usage_qty": 1,
        })
        self.store.add_component(key, CUSTOMER_A, {
            "supplier": "B厂", "supplier_product": "彩盒", "supplier_sku": "BOX-1", "usage_qty": "1.5",
        })
        self.assertTrue(self.store.has_mapping(key))
        self.assertEqual(len(self.store.get_components(key)), 2)
        self.assertEqual(self.store.suppliers(), ["A厂", "B厂"])

        self.store.update_component(key, 0, CUSTOMER_A, {"supplier": "A厂", "supplier_product": "主体", "usage_qty": 2})
        self.assertEqual(self.store.get_components(key)[0]["usage_qty"], 2)

        self.store.remove_component(key, 1)
        self.assertEqual(len(self.store.get_components(key)), 1)

        # 重启后仍在
        reloaded = SupplierBomStore(self.tmp.name)
        self.assertEqual(len(reloaded.get_components(key)), 1)

    def test_invalid_component_is_rejected_before_save(self):
        key = product_key(**CUSTOMER_A)
        with self.assertRaises(ValueError):
            self.store.add_component(key, CUSTOMER_A, {"supplier": "", "supplier_product": "主体"})
        with self.assertRaises(ValueError):
            self.store.add_component(key, CUSTOMER_A, {"supplier": "A厂", "supplier_product": ""})
        self.assertFalse(self.store.has_mapping(key))

    def test_corrupt_file_falls_back_to_empty(self):
        with open(os.path.join(self.tmp.name, supplier.DATA_FILE), "w", encoding="utf-8") as f:
            f.write("{not json")
        store = SupplierBomStore(self.tmp.name)
        self.assertEqual(store.list_mappings(), [])

    def test_move_mapping_on_identity_change(self):
        old_key = product_key("扳手", "OLD-1", "MT")
        self.store.add_component(old_key, {"name": "扳手", "sku": "OLD-1", "spec": "MT"},
                                 {"supplier": "A厂", "supplier_product": "主体"})
        new_customer = {"name": "扳手", "sku": "NEW-1", "spec": "MT"}
        new_key = product_key(**new_customer)
        self.assertTrue(self.store.move_mapping(old_key, new_key, new_customer))
        self.assertFalse(self.store.has_mapping(old_key))
        self.assertTrue(self.store.has_mapping(new_key))

    def test_move_merges_into_existing_without_duplicates(self):
        old_key = product_key("扳手", "OLD-1", "MT")
        new_customer = {"name": "扳手", "sku": "NEW-1", "spec": "MT"}
        new_key = product_key(**new_customer)
        self.store.add_component(old_key, {"name": "扳手", "sku": "OLD-1", "spec": "MT"},
                                 {"supplier": "A厂", "supplier_product": "主体", "usage_qty": 2})
        self.store.add_component(new_key, new_customer,
                                 {"supplier": "A厂", "supplier_product": "主体", "usage_qty": 1})
        self.store.move_mapping(old_key, new_key, new_customer)
        components = self.store.get_components(new_key)
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["usage_qty"], 1)


class BuildRequirementTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SupplierBomStore(self.tmp.name)
        self.key_a = product_key(**CUSTOMER_A)
        self.key_b = product_key(**CUSTOMER_B)
        # 客户产品 A：主体×1 + 彩盒×2
        self.store.add_component(self.key_a, CUSTOMER_A,
                                 {"supplier": "A厂", "supplier_product": "棘轮主体", "usage_qty": 1})
        self.store.add_component(self.key_a, CUSTOMER_A,
                                 {"supplier": "C厂", "supplier_product": "彩盒", "supplier_sku": "BOX", "usage_qty": 2})
        # 客户产品 B 也用到 A 厂主体
        self.store.add_component(self.key_b, CUSTOMER_B,
                                 {"supplier": "A厂", "supplier_product": "棘轮主体", "usage_qty": 1})

    def tearDown(self):
        self.tmp.cleanup()

    def test_quantities_usage_and_cross_customer_merge(self):
        items = [
            {"name": "无刷棘轮扳手", "sku": "SEK-001", "spec": "MT", "qty": 10, "order": "PO1", "recipient": "客户甲"},
            {"name": "水磨", "sku": "", "spec": "DE", "qty": 5, "order": "PO2", "recipient": "客户乙"},
        ]
        result = build_requirement(items, self.store)
        rows = {(r["supplier"], r["supplier_product"]): r for r in result["rows"]}
        self.assertEqual(rows[("A厂", "棘轮主体")]["quantity"], Decimal("15"))
        self.assertEqual(rows[("C厂", "彩盒")]["quantity"], Decimal("20"))
        self.assertEqual(result["supplier_count"], 2)
        self.assertEqual(result["product_count"], 2)
        self.assertEqual(result["order_count"], 2)
        self.assertEqual(result["unmapped"], [])

    def test_same_product_in_multiple_orders_aggregates_first(self):
        items = [
            {"name": "无刷棘轮扳手", "sku": "SEK-001", "spec": "MT", "qty": 10, "order": "PO1", "recipient": "客户甲"},
            {"name": "无刷棘轮扳手", "sku": "SEK-001", "spec": "MT", "qty": 5, "order": "PO2", "recipient": "客户乙"},
        ]
        result = build_requirement(items, self.store)
        rows = {(r["supplier"], r["supplier_product"]): r for r in result["rows"]}
        self.assertEqual(rows[("C厂", "彩盒")]["quantity"], Decimal("30"))
        sources = rows[("C厂", "彩盒")]["sources"]
        self.assertEqual(len(sources), 2)
        self.assertEqual(sum(s["quantity"] for s in sources), Decimal("30"))

    def test_unmapped_is_reported_not_dropped(self):
        items = [
            {"name": "无刷棘轮扳手", "sku": "SEK-001", "spec": "MT", "qty": 10, "order": "PO1"},
            {"name": "未配置产品", "sku": "NO-MAP", "spec": "", "qty": 7, "order": "PO2"},
            {"name": "零数量", "sku": "ZERO", "spec": "", "qty": 0, "order": "PO3"},
        ]
        result = build_requirement(items, self.store)
        self.assertEqual([u["name"] for u in result["unmapped"]], ["未配置产品"])
        self.assertEqual(result["unmapped_quantity"], 7)
        self.assertEqual(len(result["rows"]), 2)

    def test_fractional_usage_not_rounded(self):
        key = product_key("绳", "ROPE-1", "")
        self.store.add_component(key, {"name": "绳", "sku": "ROPE-1", "spec": ""},
                                 {"supplier": "D厂", "supplier_product": "绳子", "usage_qty": "1.5"})
        result = build_requirement(
            [{"name": "绳", "sku": "ROPE-1", "spec": "", "qty": 3}], self.store)
        row = [r for r in result["rows"] if r["supplier_product"] == "绳子"][0]
        self.assertEqual(row["quantity"], Decimal("4.5"))

    def test_empty_items_return_empty_result(self):
        result = build_requirement([], self.store)
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["unmapped"], [])


class RequirementOutputTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SupplierBomStore(self.tmp.name)
        key = product_key(**CUSTOMER_A)
        self.store.add_component(key, CUSTOMER_A,
                                 {"supplier": "A厂", "supplier_product": "棘轮主体", "plug": "牧田脚", "usage_qty": 1})
        self.store.add_component(key, CUSTOMER_A,
                                 {"supplier": "C厂", "supplier_product": "彩盒", "supplier_sku": "BOX", "usage_qty": 2})
        self.result = build_requirement(
            [{"name": "无刷棘轮扳手", "sku": "SEK-001", "spec": "MT", "qty": 10,
              "order": "PO1", "recipient": "客户甲"}],
            self.store,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_html_has_one_page_per_supplier_and_no_customer_info(self):
        html = generate_requirement_html(self.result)
        self.assertEqual(html.count('class="supplier-page"'), 2)
        self.assertIn("A厂", html)
        self.assertIn("C厂", html)
        self.assertNotIn("客户甲", html)
        self.assertNotIn("PO1", html)
        self.assertIn("20", html)

    def test_csv_is_excel_friendly_and_contains_trace(self):
        path = os.path.join(self.tmp.name, "req.csv")
        write_requirement_csv(self.result, path)
        with open(path, "rb") as f:
            raw = f.read()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        text = raw.decode("utf-8-sig")
        self.assertIn("供应商产品名称", text)
        self.assertIn("插脚", text)
        self.assertIn("牧田脚", text)
        self.assertIn("PO1", text)
        self.assertIn("客户甲", text)

    def test_tsv_has_no_order_column(self):
        text = requirement_tsv_text(self.result)
        self.assertIn("供应商\t供应商产品名称\t插脚\t供应商货号\t备货数量", text)
        self.assertNotIn("PO1", text)


class PlugTest(unittest.TestCase):
    def test_spec_maps_to_plug(self):
        self.assertEqual(supplier.plug_for_spec("MT"), "牧田脚")
        self.assertEqual(supplier.plug_for_spec("de"), "得伟脚")
        self.assertEqual(supplier.plug_for_spec("MI"), "米沃奇脚")
        self.assertEqual(supplier.plug_for_spec("XX"), "")

    def test_component_plug_is_saved_and_updated(self):
        with tempfile.TemporaryDirectory() as data_dir:
            store = SupplierBomStore(data_dir)
            key = product_key(**CUSTOMER_A)
            store.add_component(key, CUSTOMER_A, {
                "supplier": "A厂", "supplier_product": "棘轮主体", "plug": "牧田脚",
            })
            self.assertEqual(store.get_components(key)[0]["plug"], "牧田脚")

            store.update_component(key, 0, CUSTOMER_A, {
                "supplier": "A厂", "supplier_product": "棘轮主体", "plug": "得伟脚",
            })
            self.assertEqual(store.get_components(key)[0]["plug"], "得伟脚")

    def test_batch_add_derives_plug_and_skips_duplicates(self):
        with tempfile.TemporaryDirectory() as data_dir:
            store = SupplierBomStore(data_dir)
            customer_mt = {"name": "28电锤", "sku": "HAMMER-MT", "spec": "MT"}
            customer_de = {"name": "28电锤", "sku": "HAMMER-DE", "spec": "DE"}
            key_mt = product_key(**customer_mt)
            key_de = product_key(**customer_de)

            added, skipped = store.add_components([
                (key_mt, customer_mt, {"supplier": "A厂", "supplier_product": "28电锤",
                                       "plug": supplier.plug_for_spec("MT")}),
                (key_de, customer_de, {"supplier": "A厂", "supplier_product": "28电锤",
                                       "plug": supplier.plug_for_spec("DE")}),
            ])
            self.assertEqual((added, skipped), (2, 0))
            self.assertEqual(store.get_components(key_mt)[0]["plug"], "牧田脚")
            self.assertEqual(store.get_components(key_de)[0]["plug"], "得伟脚")

            added, skipped = store.add_components([
                (key_mt, customer_mt, {"supplier": "A厂", "supplier_product": "28电锤",
                                       "plug": "牧田脚"}),
            ])
            self.assertEqual((added, skipped), (0, 1))

    def test_requirement_line_format(self):
        row = {"supplier_product": "干湿吸尘器", "plug": "米沃奇脚", "quantity": Decimal("2")}
        self.assertEqual(supplier.requirement_line(row), "干湿吸尘器米沃奇脚*2")
        rows = [row, {"supplier_product": "有刷包胶小吹", "plug": "得伟脚", "quantity": Decimal("1")}]
        self.assertEqual(supplier.supplier_text(rows), "干湿吸尘器米沃奇脚*2，有刷包胶小吹得伟脚*1")

    def test_same_product_with_different_plugs_stays_separate(self):
        with tempfile.TemporaryDirectory() as data_dir:
            store = SupplierBomStore(data_dir)
            customer_mt = {"name": "28电锤", "sku": "HAMMER-MT", "spec": "MT"}
            customer_de = {"name": "28电锤", "sku": "HAMMER-DE", "spec": "DE"}
            key_mt = product_key(**customer_mt)
            key_de = product_key(**customer_de)
            store.add_component(key_mt, customer_mt, {
                "supplier": "A厂", "supplier_product": "28电锤", "plug": "牧田脚"})
            store.add_component(key_de, customer_de, {
                "supplier": "A厂", "supplier_product": "28电锤", "plug": "得伟脚"})
            result = build_requirement([
                {"name": "28电锤", "sku": "HAMMER-MT", "spec": "MT", "qty": 2},
                {"name": "28电锤", "sku": "HAMMER-DE", "spec": "DE", "qty": 3},
            ], store)
            rows = {(r["supplier_product"], r["plug"]): r for r in result["rows"]}
            self.assertEqual(rows[("28电锤", "牧田脚")]["quantity"], Decimal("2"))
            self.assertEqual(rows[("28电锤", "得伟脚")]["quantity"], Decimal("3"))
            self.assertEqual(result["product_count"], 2)

    def test_legacy_component_without_plug_stays_plain(self):
        """旧映射没有插脚时保持为空，避免给彩盒等无插脚物料误加插脚。"""
        with tempfile.TemporaryDirectory() as data_dir:
            store = SupplierBomStore(data_dir)
            key = product_key(**CUSTOMER_A)
            store.add_component(key, CUSTOMER_A, {"supplier": "A厂", "supplier_product": "棘轮主体"})
            result = build_requirement(
                [{"name": "无刷棘轮扳手", "sku": "SEK-001", "spec": "MT", "qty": 2}], store)
            self.assertEqual(result["rows"][0]["plug"], "")
            self.assertEqual(supplier.requirement_line(result["rows"][0]), "棘轮主体*2")


class ProductIdentityMigrationTest(unittest.TestCase):
    """产品改 SKU 后映射迁移（数据层规则，不依赖 GUI）。"""

    def test_sku_change_migrates_mapping(self):
        with tempfile.TemporaryDirectory() as data_dir:
            products = ProductStore(data_dir=data_dir)
            products.add(Product(name="扳手", sku="OLD", spec="MT", qty_per_box=10))
            store = SupplierBomStore(data_dir)
            store.add_component(product_key("扳手", "OLD", "MT"), {"name": "扳手", "sku": "OLD", "spec": "MT"},
                                {"supplier": "A厂", "supplier_product": "主体"})
            products.update(0, Product(name="扳手", sku="NEW", spec="MT", qty_per_box=10))
            self.assertTrue(store.move_mapping(
                product_key("扳手", "OLD", "MT"), product_key("扳手", "NEW", "MT"),
                {"name": "扳手", "sku": "NEW", "spec": "MT"}))
            self.assertTrue(store.has_mapping(product_key("扳手", "NEW", "MT")))


if __name__ == "__main__":
    unittest.main()
