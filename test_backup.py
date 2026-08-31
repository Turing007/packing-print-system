# -*- coding: utf-8 -*-
"""自动备份（set_backup_dir / backup_file / backup_all）的行为测试。"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import storage


class AutoBackupTest(unittest.TestCase):
    def setUp(self):
        # 隔离：数据目录/默认目录都指向临时目录，不碰真实数据
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = os.path.join(self._tmp.name, "app_data")
        self.backup_dir = os.path.join(self._tmp.name, "backup_disk", "backup")
        os.makedirs(self.data_dir, exist_ok=True)
        patcher = mock.patch.object(storage, "_resolve_data_dir", return_value=self.data_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher2 = mock.patch.object(storage, "DATA_DIR", self.data_dir)
        patcher2.start()
        self.addCleanup(patcher2.stop)
        patcher3 = mock.patch.object(storage, "_BACKUP_DIR", "")
        patcher3.start()
        self.addCleanup(patcher3.stop)

    def test_set_backup_dir_writes_marker(self):
        result = storage.set_backup_dir(self.backup_dir)
        self.assertEqual(result, self.backup_dir)
        self.assertEqual(storage.get_backup_dir(), self.backup_dir)
        self.assertTrue(os.path.isdir(self.backup_dir))
        marker = Path(self.data_dir, storage.BACKUP_MARKER_FILE)
        self.assertEqual(
            json.loads(marker.read_text(encoding="utf-8"))["backup_dir"], self.backup_dir)

    def test_save_auto_copies_changed_table(self):
        storage.set_backup_dir(self.backup_dir)
        storage.save_order_history_column_widths({"#0": 30})
        # 数据仍在原位置
        self.assertTrue(os.path.isfile(os.path.join(self.data_dir, "ui_config.json")))
        # 改动自动同步到了备份文件夹
        self.assertTrue(os.path.isfile(os.path.join(self.backup_dir, "ui_config.json")))

    def test_data_dir_unchanged_by_backup(self):
        before = storage.get_data_dir()
        storage.set_backup_dir(self.backup_dir)
        self.assertEqual(storage.get_data_dir(), before)

    def test_backup_all_counts_tables(self):
        storage.set_backup_dir(self.backup_dir)
        storage.save_order_history_column_widths({"#0": 30})
        count = storage.backup_all()
        self.assertGreaterEqual(count, 1)
        self.assertFalse(os.path.basename(storage.BACKUP_MARKER_FILE) in
                         os.listdir(self.backup_dir))

    def test_disable_stops_auto_backup(self):
        storage.set_backup_dir(self.backup_dir)
        storage.save_order_history_column_widths({"#0": 30})
        self.assertTrue(os.path.isfile(os.path.join(self.backup_dir, "ui_config.json")))
        storage.set_backup_dir(None)
        storage.save_order_history_column_widths({"#0": 40})
        # 停用后不再同步：备份文件夹里保留最后一次备份的旧内容
        backup_text = Path(self.backup_dir, "ui_config.json").read_text(encoding="utf-8")
        self.assertIn("30", backup_text)
        # 新的保存只发生在数据目录，不再复制到备份文件夹
        data_text = Path(self.data_dir, "ui_config.json").read_text(encoding="utf-8")
        self.assertIn("40", data_text)
        self.assertNotIn("40", backup_text)

    def test_marker_respected_on_startup(self):
        storage.set_backup_dir(self.backup_dir)
        self.assertEqual(storage._apply_backup_marker(), self.backup_dir)

    def test_same_as_data_dir_raises(self):
        with self.assertRaises(Exception):
            storage.set_backup_dir(self.data_dir)
        self.assertEqual(storage.get_backup_dir(), "")

    def test_backup_file_missing_source_ignored(self):
        storage.set_backup_dir(self.backup_dir)
        self.assertFalse(storage.backup_file("not_exists.json"))


if __name__ == "__main__":
    unittest.main()
