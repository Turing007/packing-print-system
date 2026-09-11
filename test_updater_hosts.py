import unittest

from updater import _ensure_github_url


class AllowedHostTest(unittest.TestCase):
    """下载白名单必须放行 GitHub 的资产 CDN，同时挡住其他主机。"""

    def test_accepts_api_and_web_hosts(self):
        self.assertEqual(
            _ensure_github_url("https://api.github.com/repos/a/b/releases/latest"),
            "https://api.github.com/repos/a/b/releases/latest",
        )
        self.assertEqual(
            _ensure_github_url("https://github.com/a/b/releases/download/v1/x.exe"),
            "https://github.com/a/b/releases/download/v1/x.exe",
        )

    def test_accepts_release_asset_cdn_hosts(self):
        # GitHub 现在把资产下载重定向到 release-assets.githubusercontent.com，
        # 之前写死主机名时这里会被自己的白名单拒绝，导致下载必然失败。
        for host in ("objects.githubusercontent.com",
                     "release-assets.githubusercontent.com"):
            url = f"https://{host}/github-production-release-asset/x?sig=abc"
            self.assertEqual(_ensure_github_url(url), url)

    def test_rejects_non_github_host(self):
        with self.assertRaisesRegex(ValueError, "白名单"):
            _ensure_github_url("https://evil.example.com/x.exe")

    def test_rejects_lookalike_domains(self):
        # 后缀必须带前导点，避免 evilgithubusercontent.com / 把域名塞进子域这类绕过
        for url in ("https://evilgithubusercontent.com/x.exe",
                    "https://githubusercontent.com.evil.example.com/x.exe"):
            with self.assertRaisesRegex(ValueError, "白名单"):
                _ensure_github_url(url)

    def test_rejects_non_https(self):
        with self.assertRaisesRegex(ValueError, "白名单"):
            _ensure_github_url("http://github.com/x.exe")


if __name__ == "__main__":
    unittest.main()
