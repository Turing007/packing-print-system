# -*- coding: utf-8 -*-
import socket
import threading
import time
import unittest
from unittest import mock

import single_instance


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class ActivateExistingInstanceTest(unittest.TestCase):
    def setUp(self):
        # 一律改用临时空闲端口，避免影响本机正在运行的正式实例
        patcher = mock.patch.object(single_instance, "_PORT", _free_port())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_instance_running(self):
        self.assertFalse(single_instance.activate_existing_instance())

    def test_existing_instance_replies_ok(self):
        received = []
        ready = threading.Event()

        def _server():
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.bind(("127.0.0.1", single_instance._PORT))
            srv.listen(1)
            ready.set()
            conn, _ = srv.accept()
            with conn:
                conn.settimeout(2.0)
                received.append(conn.recv(16))
                conn.sendall(single_instance._ACK)
                try:
                    conn.recv(16)  # 等客户端先关闭，避免 TIME_WAIT
                except OSError:
                    pass
            srv.close()

        t = threading.Thread(target=_server, daemon=True)
        t.start()
        self.assertTrue(ready.wait(2.0))
        self.assertTrue(single_instance.activate_existing_instance())
        t.join(2.0)
        self.assertEqual(received[0].strip().upper(), b"SHOW")

    def test_foreign_service_no_ack(self):
        """端口被无关程序占用（连接成功但不回复 OK）→ 视为没有已有实例。"""
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.bind(("127.0.0.1", single_instance._PORT))
        blocker.listen(1)
        try:
            self.assertFalse(single_instance.activate_existing_instance())
        finally:
            blocker.close()


class StartListenerTest(unittest.TestCase):
    def test_second_launch_activates_first(self):
        import tkinter as tk

        patcher = mock.patch.object(single_instance, "_PORT", _free_port())
        patcher.start()
        self.addCleanup(patcher.stop)

        root = tk.Tk()
        root.withdraw()
        activated = []

        single_instance.start_listener(root, lambda: activated.append(True))
        try:
            # 模拟第二个实例：返回 True 表示"已有实例在运行"
            self.assertTrue(single_instance.activate_existing_instance())
            deadline = time.time() + 3.0
            while not activated and time.time() < deadline:
                root.update()
                time.sleep(0.02)
            self.assertTrue(activated)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
