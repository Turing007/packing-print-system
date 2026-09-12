# -*- coding: utf-8 -*-
"""托盘恢复/窗口唤起的淡入显示测试。"""
import time
import unittest

from tray import show_window_smoothly


class ShowWindowSmoothlyTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def _pump(self, seconds=0.25):
        """驱动事件循环，让淡入的 after 回调全部跑完。"""
        end = time.time() + seconds
        while time.time() < end:
            self.root.update()
            time.sleep(0.02)

    def test_withdrawn_root_restored_with_fade(self):
        show_window_smoothly(self.root)
        self._pump()
        self.assertEqual(self.root.state(), "normal")
        self.assertAlmostEqual(float(self.root.attributes("-alpha")), 1.0, places=2)

    def test_zoomed_restore_keeps_zoomed(self):
        self.root._tray_was_zoomed = True
        self.root.withdraw()
        show_window_smoothly(self.root)
        self._pump()
        self.assertEqual(self.root.state(), "zoomed")
        self.assertAlmostEqual(float(self.root.attributes("-alpha")), 1.0, places=2)

    def test_visible_window_stays_visible_without_flash(self):
        self.root.deiconify()
        show_window_smoothly(self.root)
        self._pump(0.1)
        self.assertEqual(self.root.state(), "normal")
        self.assertAlmostEqual(float(self.root.attributes("-alpha")), 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
