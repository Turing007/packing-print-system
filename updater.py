# -*- coding: utf-8 -*-
"""
自动更新模块 - 通过 GitHub Releases 检查/下载/安装新版本。

设计要点：
1. 真实版本号硬编码于 __CURRENT_VERSION__，spec / 安装器 / 运行时均读这里；
   判断"当前是什么版本"只认程序自身，不读安装器写入的 version.json（仅诊断用）。
2. 启动后由 main.py 在后台线程调用 check_update_async()，有更新时只在顶栏按钮显示红点，不打扰用户。
3. 用户点击主界面「检查更新」按钮 → 同步检查 → 弹窗展示结果 → 一键跳到下载页或在本地下载安装器并启动。
4. 下载完成后 main.py 主动退出程序释放 exe 文件锁，安装器（内含占用检测与重试提示）才能可靠替换主程序。
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass, asdict
from typing import Callable, Optional

# ========== 配置 ==========
__CURRENT_VERSION__ = "1.0.3"
GITHUB_OWNER = "Turing007"
GITHUB_REPO = "packing-print-system"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_PAGE = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

# 安装器资产名约定（ASCII 命名，避免 NSIS ANSI 路径问题）
SETUP_ASSET_NAME = "PackingPrintSystem_v{version}_setup.exe"
PORTABLE_ASSET_NAME = "PackingPrint_v{version}_portable.exe"

# 用户超时（秒），更新检查不应阻塞主界面太久
HTTP_TIMEOUT = 8

APP_NAME = "装箱打印系统"


# ========== 数据结构 ==========
@dataclass
class UpdateInfo:
    has_update: bool
    current_version: str
    latest_version: str
    release_notes: str
    download_url: str
    asset_name: str
    asset_size: int
    is_prerelease: bool
    error: str = ""

    def to_dict(self):
        return asdict(self)


# ========== 工具函数 ==========
def get_current_version() -> str:
    """当前版本以程序自身内置的 __CURRENT_VERSION__ 为准。

    不再读取安装器写入的 version.json：曾出现过安装器升级失败但
    version.json 已写成新版号，导致旧程序误以为自己已是新版。
    version.json 仅保留作诊断用途。
    """
    return __CURRENT_VERSION__


def _parse_version(version: str):
    """'v1.2.3' / '1.2.3' / '1.2' / '1' 都解析成 (1, 2, 3)，缺位补 0。"""
    v = version.strip().lstrip("vV")
    parts = []
    for seg in v.split("."):
        seg = seg.strip()
        if not seg:
            parts.append(0)
            continue
        try:
            parts.append(int(seg))
        except ValueError:
            # 处理 1.2.3-beta1 这类
            num = ""
            for ch in seg:
                if ch.isdigit():
                    num += ch
                else:
                    break
            parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


# ========== 网络请求 ==========
# 允许请求/下载的主机白名单：release 元数据万一被篡改时，也不允许把请求指到别处
_ALLOWED_GITHUB_HOSTS = {"api.github.com", "github.com", "objects.githubusercontent.com"}
# 下载只允许落在系统临时目录内（模块级常量，作为路径校验的信任根）
_DOWNLOAD_DIR = os.path.abspath(tempfile.gettempdir())


def _ensure_github_url(url: str) -> str:
    """校验 URL 必须是 https 且主机在 GitHub 白名单内，否则拒绝请求。"""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_GITHUB_HOSTS:
        raise ValueError(f"拒绝请求非 GitHub 白名单地址: {url!r}")
    return url


def _assert_public_host(url: str) -> None:
    """解析域名并阻断私网/环回/链路本地/保留地址，防 SSRF 与 DNS rebinding。"""
    host = urllib.parse.urlparse(url).hostname
    if not host:
        raise ValueError(f"URL 缺少主机名: {url!r}")
    for info in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP):
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise ValueError(f"主机解析到非公网地址，已阻止: {host} -> {ip}")


class _GitHubSafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """重定向目标逐跳过白名单与公网 IP 校验。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _ensure_github_url(newurl)
        _assert_public_host(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_GitHubSafeRedirectHandler())


def _safe_urlopen(url: str, timeout: float, headers: Optional[dict] = None):
    """带协议/主机白名单、IP 边界校验与受限重定向的受控请求。"""
    url = _ensure_github_url(url)
    _assert_public_host(url)
    req = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": "PackingPrintSystem-Updater"},
    )
    return _OPENER.open(req, timeout=timeout)


def _http_get_json(url: str):
    with _safe_urlopen(url, HTTP_TIMEOUT, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "PackingPrintSystem-Updater",
    }) as resp:
        raw = resp.read()
    # GitHub release notes 经常含中文 / emoji，resp.read() 在某些平台返回 latin-1 编码过的 bytes
    # 这里强制按 utf-8 解码，失败回退 latin-1（永远不会真正失败，因为 latin-1 严格兼容 ASCII）
    try:
        return json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return json.loads(raw.decode("latin-1"))


def _http_download(url: str, dest_path: str, progress_cb: Optional[Callable[[int, int], None]] = None):
    """带进度回调的文件下载。

    先写入临时目录内系统分配的安全临时文件，下载完成后再在同一
    目录内原子替换为目标文件名，避免路径拼接写坏其他文件。
    """
    safe_name = os.path.basename(dest_path) or "download.bin"
    with _safe_urlopen(url, 60) as resp:
        fd, tmp_path = tempfile.mkstemp(dir=_DOWNLOAD_DIR, prefix="packingprint_", suffix=".part")
        try:
            total = int(resp.headers.get("Content-Length") or 0)
            downloaded = 0
            with os.fdopen(fd, "wb") as f:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        try:
                            progress_cb(downloaded, total)
                        except Exception:
                            pass
            target = os.path.join(_DOWNLOAD_DIR, safe_name)
            os.replace(tmp_path, target)
            return target
        except Exception:
            # 下载/写盘失败：清理临时文件
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise


# ========== 核心：检查更新 ==========
def check_update() -> UpdateInfo:
    """
    同步检查 GitHub Releases，返回 UpdateInfo。
    任何网络错误都会被捕获并以 has_update=False + error 信息返回。
    """
    current = get_current_version()
    try:
        data = _http_get_json(GITHUB_API_LATEST)
        latest_tag = data.get("tag_name") or data.get("name") or ""
        latest_version = latest_tag.lstrip("vV").strip()
        is_prerelease = bool(data.get("prerelease", False))
        body = data.get("body") or ""

        # 选择资产：优先 setup 安装器，否则 portable
        assets = data.get("assets") or []
        download_url = ""
        asset_name = ""
        asset_size = 0
        preferred_setup = SETUP_ASSET_NAME.format(version=latest_version)
        preferred_portable = PORTABLE_ASSET_NAME.format(version=latest_version)
        for asset in assets:
            name = asset.get("name", "")
            if name == preferred_setup or name == preferred_portable:
                download_url = asset.get("browser_download_url", "")
                asset_name = name
                asset_size = int(asset.get("size") or 0)
                break
        # 兜底：取第一个 .exe 资产
        if not download_url:
            for asset in assets:
                if asset.get("name", "").lower().endswith(".exe"):
                    download_url = asset.get("browser_download_url", "")
                    asset_name = asset.get("name", "")
                    asset_size = int(asset.get("size") or 0)
                    break

        return UpdateInfo(
            has_update=is_newer(latest_version, current),
            current_version=current,
            latest_version=latest_version,
            release_notes=body,
            download_url=download_url,
            asset_name=asset_name,
            asset_size=asset_size,
            is_prerelease=is_prerelease,
            error="",
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return UpdateInfo(False, current, current, "", "", "", 0, False, "尚未发布任何版本")
        return UpdateInfo(False, current, current, "", "", "", 0, False, f"GitHub 返回 HTTP {e.code}")
    except urllib.error.URLError as e:
        return UpdateInfo(False, current, current, "", "", "", 0, False, f"网络错误：{e.reason}")
    except Exception as e:
        return UpdateInfo(False, current, current, "", "", "", 0, False, f"检查失败：{type(e).__name__}: {e}")


# ========== 异步检查（不阻塞 UI） ==========
def check_update_async(callback: Callable[[UpdateInfo], None]):
    """
    在后台线程异步检查更新，完成后通过 callback 回调（运行在后台线程中）。
    调用方需要在主线程中通过 after() 切回 UI 线程。
    """
    def _worker():
        info = check_update()
        try:
            callback(info)
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True, name="updater-check")
    t.start()
    return t


# ========== 下载与安装 ==========
def download_and_launch_installer(info: UpdateInfo,
                                   progress_cb: Optional[Callable[[int, int], None]] = None,
                                   finished_cb: Optional[Callable[[bool, str], None]] = None):
    """
    下载安装器到临时目录并启动。安装器启动后立即返回（不阻塞 UI）。
    finished_cb 参数：(success: bool, message: str)
    """
    if not info.download_url:
        if finished_cb:
            finished_cb(False, "未找到可下载的安装包，请前往 GitHub Releases 页面手动下载。")
        return

    def _worker():
        try:
            tmp_dir = tempfile.gettempdir()
            # asset_name 来自 API 响应，只取基本文件名，防止拼出目录逃逸路径
            safe_name = os.path.basename(info.asset_name or "setup.exe") or "setup.exe"
            target = os.path.join(tmp_dir, safe_name)
            _http_download(info.download_url, target, progress_cb=progress_cb)

            # 启动安装器
            try:
                if sys.platform == "win32":
                    # Windows：用 os.startfile 异步启动并立即返回
                    os.startfile(target)  # type: ignore[attr-defined]
                else:
                    subprocess.Popen(["xdg-open", target])
            except Exception as e:
                if finished_cb:
                    finished_cb(False, f"下载完成，但启动安装器失败：{e}\n文件已保存到：{target}")
                return

            if finished_cb:
                finished_cb(True, f"安装器已启动，请按向导完成升级。\n下载位置：{target}")
        except Exception as e:
            if finished_cb:
                finished_cb(False, f"下载失败：{type(e).__name__}: {e}")

    t = threading.Thread(target=_worker, daemon=True, name="updater-download")
    t.start()
    return t


def open_releases_page():
    """直接打开 GitHub Releases 页面（兜底方案）。"""
    try:
        webbrowser.open(GITHUB_RELEASES_PAGE)
    except Exception:
        pass


# ========== 简单自测 ==========
if __name__ == "__main__":
    # 仅供开发时手动测试：python updater.py
    print(f"当前版本：{get_current_version()}")
    print("正在检查更新…")
    info = check_update()
    print(json.dumps(info.to_dict(), ensure_ascii=False, indent=2))