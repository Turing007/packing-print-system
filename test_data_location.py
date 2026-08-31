# -*- coding: utf-8 -*-
"""数据存储位置切换（set_custom_data_dir）的行为测试。"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import storage


class DataLocationTest(unittest.TestCase):
    def setUp(self):
        # 隔离：默认数据目录与初始生效目录都指向临时目录，不碰真实数据
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.default_dir = os.path.join(self._tmp.name, "default_data")
        self.new_dir = os.path.join(self._tmp.name, "backup_disk", "data")
        os.makedirs(self.default_dir, exist_ok=True)
        patcher = mock.patch.object(storage, "_resolve_data_dir", return_value=self.default_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher2 = mock.patch.object(storage, "DATA_DIR", self.default_dir)
        patcher2.start()
        self.addCleanup(patcher2.stop)

    def test_switch_copies_tables_and_writes_marker(self):
        Path(self.default_dir, "products.json").write_text('{"a": 1}', encoding="utf-8")
        Path(self.default_dir, "order_history.json").write_text('{"b": 2}', encoding="utf-8")

        result = storage.set_custom_data_dir(self.new_dir)

        self.assertEqual(result, self.new_dir)
        self.assertEqual(storage.get_data_dir(), self.new_dir)
        # 数据表被复制到新位置
        for name in ("products.json", "order_history.json"):
            self.assertTrue(os.path.isfile(os.path.join(self.new_dir, name)))
        # 旧位置文件保留（作备份）
        self.assertTrue(os.path.isfile(os.path.join(self.default_dir, "products.json")))
        # 标记文件写在默认数据目录里
        marker = Path(self.default_dir, storage.LOCATION_MARKER_FILE)
        self.assertTrue(marker.is_file())
        self.assertEqual(json.loads(marker.read_text(encoding="utf-8"))["data_dir"], self.new_dir)

    def test_save_uses_new_location_after_switch(self):
        storage.set_custom_data_dir(self.new_dir)
        storage.save_order_history_column_widths({"#0": 30})
        self.assertTrue(os.path.isfile(os.path.join(self.new_dir, "ui_config.json")))

    def test_restore_default_clears_location(self):
        storage.set_custom_data_dir(self.new_dir)
        storage.set_custom_data_dir(None)
        self.assertEqual(storage.get_data_dir(), self.default_dir)
        marker = Path(self.default_dir, storage.LOCATION_MARKER_FILE)
        self.assertEqual(json.loads(marker.read_text(encoding="utf-8"))["data_dir"], "")

    def test_marker_respected_on_startup(self):
        # 模拟"重启后"：标记存在且目录有效 → _apply_location_marker 应返回自定义目录
        storage.set_custom_data_dir(self.new_dir)
        self.assertEqual(storage._apply_location_marker(), self.new_dir)

    def test_unwritable_location_raises_and_keeps_old(self):
        # 指向一个已存在的文件路径（不可作为目录使用）→ 报错且目录不变
        blocker = Path(self._tmp.name, "not_a_dir.txt")
        blocker.write_text("x", encoding="utf-8")
        with self.assertRaises(Exception):
            storage.set_custom_data_dir(str(blocker))
        self.assertEqual(storage.get_data_dir(), self.default_dir)


if __name__ == "__main__":
    unittest.main()
