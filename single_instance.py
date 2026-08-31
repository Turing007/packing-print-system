# -*- coding: utf-8 -*-
"""单实例守护：程序已在运行时，二次启动不再开新进程，而是唤起已有实例的主窗口。

机制：本机回环 TCP 端口。
- 首个实例：启动后占用 127.0.0.1:<PORT> 并在后台线程监听；
- 后续实例：连接该端口发送 SHOW，收到 OK 即认为已有实例在运行，
  立即退出（已有实例会把主窗口带到前台）。

端口被无关程序占用等异常场景自动降级：退回"允许多开"的原有行为，
不影响正常使用。仅用标准库，打包（PyInstaller onefile）无需额外处理。
"""

import socket
import sys
import threading
import time

_HOST = "127.0.0.1"
# 专属端口：位于 Windows 临时端口范围（49152+）之外，避免被系统随机分配挤占
_PORT = 45761
_CMD = b"SHOW\n"
_ACK = b"OK\n"


def activate_existing_instance() -> bool:
    """若已有实例在运行：通知其显示主窗口并返回 True（调用方应直接退出）。

    连接成功但对方未按协议回复 OK（端口被无关程序占用）时返回 False，
    调用方按"没有已有实例"继续正常启动。
    """
    try:
        with socket.create_connection((_HOST, _PORT), timeout=0.5) as s:
            s.settimeout(1.5)
            s.sendall(_CMD)
            resp = s.recv(16)
            return resp.startswith(_ACK)
    except OSError:
        return False


def start_listener(root, on_activate) -> None:
    """首个实例：后台线程监听专属端口，收到 SHOW 时调用 on_activate() 唤起主窗口。

    必须在 Tk root 创建之后调用。on_activate 由调用方保证切回 Tk 主线程
    （与 tray.py 一致，通过 root.after 调度）。监听失败只打日志，不影响主程序。
    """
    def _listener():
        srv = _bind_listener()
        if srv is None:
            print("[single-instance] 监听端口失败，二次启动将不再唤起已有窗口",
                  file=sys.stderr)
            return
        while True:
            try:
                conn, _addr = srv.accept()
            except OSError:
                return  # socket 已关闭（进程退出）
            with conn:
                try:
                    conn.settimeout(2.0)
                    data = conn.recv(64)
                except OSError:
                    continue
                if not data.strip().upper().startswith(b"SHOW"):
                    continue
                try:
                    on_activate()
                except Exception:
                    pass
                try:
                    conn.sendall(_ACK)
                    # 等客户端先关闭连接，避免本端进入 TIME_WAIT
                    # （否则短暂占用端口，影响旧实例退出后新实例立即启动）
                    conn.settimeout(2.0)
                    conn.recv(16)
                except OSError:
                    pass

    threading.Thread(target=_listener, daemon=True, name="single-instance").start()


def _bind_listener():
    """绑定监听 socket；偶发的端口残留占用做几次短重试，最终失败返回 None。"""
    for _ in range(5):
        srv = None
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.bind((_HOST, _PORT))
            srv.listen(4)
            return srv
        except OSError:
            if srv is not None:
                try:
                    srv.close()
                except Exception:
                    pass
            time.sleep(0.2)
    return None
