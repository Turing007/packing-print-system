装箱打印系统
============

一个 Windows 桌面端的装箱打印工具。维护产品资料、录入装箱任务、按规则自动计算箱唛、生成可打印 HTML 标签。

功能特性
--------

- 产品资料管理（品名、SKU、规格、装箱数候选值）
- 装箱任务计算（自动分箱、尾数处理、尾数合并、订单维度编号）
- HTML 标签预览与浏览器内打印
- 装箱暂存、历史记录、打印日志、订单历史
- 内置自动更新（通过 GitHub Releases 检测、下载、安装新版本）

快速开始
--------

下载安装包：[Releases 页面](https://github.com/Turing007/packing-print-system/releases/latest)

安装版 `*_setup.exe` 会创建开始菜单快捷方式和桌面图标，可以从控制面板正常卸载。
便携版 `*_portable.exe` 解压即用，不写注册表，适合临时环境。

自动更新
--------

启动后软件会静默检测 GitHub 上是否有新版本。如有，主界面顶栏「检查更新」按钮会显示红点。

点击「检查更新」按钮可手动触发检查，发现新版本后会弹窗展示更新说明并提供下载链接。

从源码运行
----------

需要 Python 3.12+。

```
pip install pyinstaller
python main.py
```

开发者：打包发布
----------------

修改 `updater.py` 顶部的 `__CURRENT_VERSION__`，然后：

```
release.bat patch    # 自动 bump + 打包 + git push + gh release
```

或分步操作：

```
build.bat            # 仅打包到 release/ 目录
git push origin master
gh release create v1.2.3 release\*.exe --generate-notes
```

技术栈
------

- Python 3.12
- Tkinter / ttk
- PyInstaller
- NSIS 3.x

许可证
------

MIT，详见 LICENSE.txt