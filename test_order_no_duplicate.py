# -*- coding: utf-8 -*-
"""订单号重复提醒测试。

规则：在订单号输入框失去焦点时，若订单历史中已存在相同订单号，
弹出提醒（保存时会覆盖旧记录）；同一订单号未再次编辑时只提醒一次。
"""
import os
import tempfile
import unittest
from unittest import mock

import storage


def _make_app():
    import tkinter as tk
    from main import PackingApp
    root = tk.Tk()
    root.withdraw()
    app = PackingApp(root)
    return root, app


class OrderNoDuplicateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        data_dir = os.path.join(self._tmp.name, "data")
        os.makedirs(data_dir, exist_ok=True)
        patcher = mock.patch.object(storage, "get_data_dir", return_value=data_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.root, self.app = _make_app()
        self.addCleanup(self.root.destroy)

        self.history = [
            {"recipient": "张三", "order_no": "A100", "items": [], "created_at": "2026-09-01 10:00:00"},
            {"recipient": "李四", "order_no": "B200", "items": [], "created_at": "2026-09-02 10:00:00"},
        ]
        self._history_patcher = mock.patch("main.load_order_history", return_value=self.history)
        self._history_patcher.start()
        self.addCleanup(self._history_patcher.stop)

    def _focus_out(self, order_no):
        self.app.e_pk_order.delete(0, "end")
        self.app.e_pk_order.insert(0, order_no)
        self.app._on_order_no_focus_out()

    def test_existing_order_no_warns(self):
        with mock.patch("tkinter.messagebox.showwarning") as warn:
            self._focus_out("A100")
        warn.assert_called_once()
        self.assertIn("A100", warn.call_args[0][1])
        self.assertIn("张三", warn.call_args[0][1])

    def test_new_order_no_no_warning(self):
        with mock.patch("tkinter.messagebox.showwarning") as warn:
            self._focus_out("C300")
        warn.assert_not_called()

    def test_empty_order_no_no_warning(self):
        with mock.patch("tkinter.messagebox.showwarning") as warn:
            self._focus_out("")
        warn.assert_not_called()

    def test_same_value_only_warns_once(self):
        with mock.patch("tkinter.messagebox.showwarning") as warn:
            self._focus_out("A100")
            self._focus_out("A100")
        warn.assert_called_once()

    def test_edit_reenables_warning(self):
        with mock.patch("tkinter.messagebox.showwarning") as warn:
            self._focus_out("A100")
            self.app.e_pk_order.delete(0, "end")
            self.app.e_pk_order.insert(0, "A100")
            self.app._on_recipient_order_change()
            self.app._on_order_no_focus_out()
        self.assertEqual(warn.call_count, 2)


if __name__ == "__main__":
    unittest.main()
