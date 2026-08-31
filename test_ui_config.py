import tempfile
import unittest

import storage
from storage import load_order_history_column_widths, save_order_history_column_widths


class OrderHistoryColumnWidthConfigTest(unittest.TestCase):
    def setUp(self):
        self._old_data_dir = storage.DATA_DIR
        self._temp_dir = tempfile.TemporaryDirectory()
        storage.DATA_DIR = self._temp_dir.name

    def tearDown(self):
        storage.DATA_DIR = self._old_data_dir
        self._temp_dir.cleanup()

    def test_default_widths_are_used_before_user_adjusts_columns(self):
        defaults = {"#0": 28, "recipient": 95, "order": 170, "count": 60, "time": 150}

        self.assertEqual(load_order_history_column_widths(defaults), defaults)

    def test_user_adjusted_widths_are_saved_and_reloaded(self):
        defaults = {"#0": 28, "recipient": 95, "order": 170, "count": 60, "time": 150}
        adjusted = {"#0": 32, "recipient": 120, "order": 220, "count": 65, "time": 165}

        save_order_history_column_widths(adjusted)

        self.assertEqual(load_order_history_column_widths(defaults), adjusted)


if __name__ == "__main__":
    unittest.main()
