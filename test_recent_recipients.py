import tempfile
import unittest

import storage
from storage import (
    RECENT_RECIPIENTS_LIMIT,
    load_recent_recipients,
    remember_recipient,
)


class RecentRecipientsTest(unittest.TestCase):
    def setUp(self):
        self._old_data_dir = storage.DATA_DIR
        self._temp_dir = tempfile.TemporaryDirectory()
        storage.DATA_DIR = self._temp_dir.name

    def tearDown(self):
        storage.DATA_DIR = self._old_data_dir
        self._temp_dir.cleanup()

    def test_recent_recipients_start_empty(self):
        self.assertEqual(load_recent_recipients(), [])

    def test_latest_used_recipient_comes_first(self):
        remember_recipient("张三")
        remember_recipient("李四")

        self.assertEqual(load_recent_recipients(), ["李四", "张三"])

    def test_repeated_recipient_moves_to_front_without_duplicate(self):
        remember_recipient("张三")
        remember_recipient("李四")
        remember_recipient("张三")

        self.assertEqual(load_recent_recipients(), ["张三", "李四"])

    def test_blank_recipient_is_ignored(self):
        remember_recipient("  ")
        remember_recipient("")

        self.assertEqual(load_recent_recipients(), [])

    def test_recipient_list_is_capped(self):
        for index in range(RECENT_RECIPIENTS_LIMIT + 5):
            remember_recipient(f"客户{index}")

        recipients = load_recent_recipients()

        self.assertEqual(len(recipients), RECENT_RECIPIENTS_LIMIT)
        self.assertEqual(recipients[0], f"客户{RECENT_RECIPIENTS_LIMIT + 4}")

    def test_corrupt_config_falls_back_to_empty(self):
        import json
        import os

        with open(os.path.join(self._temp_dir.name, "ui_config.json"), "w", encoding="utf-8") as f:
            f.write("{not json")

        self.assertEqual(load_recent_recipients(), [])

    def test_saving_recipients_keeps_column_widths(self):
        storage.save_order_history_column_widths({"#0": 28, "recipient": 95})
        remember_recipient("张三")

        widths = storage.load_order_history_column_widths({"#0": 1, "recipient": 1})

        self.assertEqual(widths, {"#0": 28, "recipient": 95})
        self.assertEqual(load_recent_recipients(), ["张三"])


if __name__ == "__main__":
    unittest.main()
