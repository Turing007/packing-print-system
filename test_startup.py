import unittest


class StartupSmokeTest(unittest.TestCase):
    def test_core_modules_import(self):
        import packing  # noqa: F401
        import main  # noqa: F401

    def test_app_can_be_constructed(self):
        from main import PackingApp
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        try:
            PackingApp(root)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
