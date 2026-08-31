# -*- coding: utf-8 -*-
"""
系统托盘（常驻状态栏）模块 - pystray + PIL

功能：
- 程序启动后在系统托盘常驻一个图标
- 左键单击托盘图标：显示/置顶主窗口
- 右键菜单：打开主窗口 / 检查更新 / 退出
- 点窗口 X 关闭时：默认最小化到托盘（不退出），可从托盘退出或再次打开
- 图标用 generate_icon.py 的绘制逻辑生成（不依赖磁盘文件，打包后也能用）

线程模型：
- pystray.Icon.run() 在独立 daemon 线程中跑（Windows 后端内部处理消息循环）
- 对 Tk 主窗口的一切操作都通过 root.after() 切回 Tk 主线程
"""

from __future__ import annotations

import os
import sys
import threading

from PIL import Image, ImageDraw

# 复用图标绘制（与 generate_icon.py 同一套视觉）
try:
    from generate_icon import draw_icon
except Exception:  # 打包时 generate_icon 可能不在，退化为简版图标
    draw_icon = None


def _make_icon_image() -> Image.Image:
    """生成托盘图标图像（32x32 源，PIL 会按需缩放）。"""
    if draw_icon is not None:
        try:
            return draw_icon(32)
        except Exception:
            pass
    # 兜底：纯色方块
    img = Image.new("RGBA", (32, 32), (28, 64, 110, 255))
    d = ImageDraw.Draw(img)
    d.rectangle((8, 10, 24, 26), fill=(180, 142, 92, 255))
    d.rectangle((10, 14, 22, 20), fill=(252, 252, 250, 255))
    return img


class TrayApp:
    """把 Tk 主窗口挂到系统托盘。用法：
        tray = TrayApp(root, on_show_window=None)
        tray.start()          # 启动托盘线程
        tray.stop()           # 退出前调用
    """

    def __init__(self, root, app_name: str = "装箱打印系统",
                 on_check_update=None, on_quit=None):
        self.root = root
        self.app_name = app_name
        self.on_check_update = on_check_update  # 由 main.py 注入：打开检查更新弹窗
        self.on_quit = on_quit                  # 由 main.py 注入：真正的退出逻辑

        self._icon = None
        self._started = False
        self._really_quit = False   # 标记：托盘菜单里点了"退出"

        # 点窗口 X → 最小化到托盘（拦截 WM_DELETE_WINDOW）
        root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

    # ---------- 窗口操作（必须在 Tk 主线程执行） ----------
    def _show_window_impl(self):
        try:
            self.root.deiconify()          # 从任务栏/托盘恢复
            self.root.state("zoomed" if os.name == "nt" and
                            self._was_zoomed() else "normal")
            self.root.lift()               # 置顶
            self.root.focus_force()
        except Exception:
            try:
                self.root.deiconify()
            except Exception:
                pass

    def _was_zoomed(self) -> bool:
        # 记录窗口是否曾经最大化过，恢复时保持
        try:
            return getattr(self.root, "_tray_was_zoomed", False)
        except Exception:
            return False

    def show_window(self):
        """线程安全：从托盘线程切回 Tk 主线程显示窗口。"""
        self.root.after(0, self._show_window_impl)

    def hide_to_tray(self):
        """点窗口 X：隐藏到托盘（不退出）。"""
        try:
            # 记录当前是否最大化
            self.root._tray_was_zoomed = (
                self.root.state() == "zoomed"
            )
        except Exception:
            pass
        try:
            self.root.withdraw()           # 隐藏窗口（任务栏图标也消失）
        except Exception:
            pass

    # ---------- 托盘菜单动作 ----------
    def _menu_open(self, icon, item):
        self.show_window()

    def _menu_update(self, icon, item):
        if self.on_check_update:
            # 检查更新需要在 Tk 主线程跑（会弹 messagebox）
            self.root.after(0, self.on_check_update)

    def _menu_quit(self, icon, item):
        self._really_quit = True
        # 通知 Tk 主线程真正退出
        self.root.after(0, self._do_quit)

    def _do_quit(self):
        try:
            if self.on_quit:
                self.on_quit()             # main.py 注入的退出清理
            self.stop()
        finally:
            try:
                self.root.destroy()
            except Exception:
                pass

    # ---------- 生命周期 ----------
    def start(self):
        if self._started:
            return
        try:
            from pystray import Icon, Menu, MenuItem

            menu = Menu(
                MenuItem("打开主窗口", self._menu_open, default=True),  # default=左键单击
                MenuItem("检查更新", self._menu_update),
                Menu.SEPARATOR,
                MenuItem("退出", self._menu_quit),
            )
            self._icon = Icon(self.app_name, _make_icon_image(),
                              title=f"{self.app_name}", menu=menu)
            t = threading.Thread(target=self._icon.run, daemon=True,
                                 name="tray-icon")
            t.start()
            self._started = True
        except Exception as e:
            # 托盘失败不影响主程序（例如无桌面环境的异常场景）
            print(f"[tray] 托盘初始化失败（不影响主程序）: {e}", file=sys.stderr)

    def stop(self):
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
        self._started = False
