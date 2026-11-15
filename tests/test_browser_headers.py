# tests/test_browser_headers.py
# 校验统一 Chrome 指纹模块：版本随机但自洽、537.36 冻结、关键头齐全。

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from scrapers.browser_headers import (  # noqa: E402
    APPLE_WEBKIT_VERSION,
    CHROME_VERSIONS,
    PLATFORMS,
    chrome_headers,
    chrome_user_agent,
)


def test_ua_version_comes_from_known_pool():
    m = re.search(r"Chrome/(\d+)\.0\.0\.0", chrome_user_agent())
    assert m, "UA 应形如 Chrome/<major>.0.0.0"
    assert m.group(1) in CHROME_VERSIONS


def test_webkit_and_safari_are_frozen():
    ua = chrome_user_agent()
    assert f"AppleWebKit/{APPLE_WEBKIT_VERSION}" in ua
    assert f"Safari/{APPLE_WEBKIT_VERSION}" in ua
    assert APPLE_WEBKIT_VERSION == "537.36"


def test_ua_and_sec_ch_ua_version_match():
    for _ in range(20):
        headers = chrome_headers()
        ua_ver = re.search(r"Chrome/(\d+)\.0\.0\.0", headers["User-Agent"]).group(1)
        assert f'"Chromium";v="{ua_ver}"' in headers["sec-ch-ua"]
        assert f'"Google Chrome";v="{ua_ver}"' in headers["sec-ch-ua"]


def test_version_is_randomized():
    seen = {re.search(r"Chrome/(\d+)\.0\.0\.0", chrome_user_agent()).group(1)
            for _ in range(200)}
    # 200 次几乎不可能只命中同一个版本；至少出现 2 种
    assert len(seen) >= 2
    assert seen <= set(CHROME_VERSIONS)


def test_explicit_version_is_respected():
    headers = chrome_headers(version="153")
    assert "Chrome/153.0.0.0" in headers["User-Agent"]
    assert '"Google Chrome";v="153"' in headers["sec-ch-ua"]


def test_platform_label_matches_ua():
    assert chrome_headers("windows")["sec-ch-ua-platform"] == '"Windows"'
    assert chrome_headers("macos")["sec-ch-ua-platform"] == '"macOS"'
    assert "Windows NT" in chrome_headers("windows")["User-Agent"]
    assert "Macintosh" in chrome_headers("macos")["User-Agent"]


def test_headers_exist_for_every_platform():
    for platform in PLATFORMS:
        # 两次调用各自随机版本，比较时固定版本号
        assert (chrome_headers(platform, version="154")["User-Agent"]
                == chrome_user_agent(platform, version="154"))


def test_browser_like_headers_present():
    headers = chrome_headers()
    for key in ("Accept", "Accept-Language", "Upgrade-Insecure-Requests",
                "sec-ch-ua", "sec-ch-ua-mobile", "Sec-Fetch-Dest",
                "Sec-Fetch-Mode", "Sec-Fetch-Site"):
        assert headers.get(key)


def test_accept_encoding_not_forced():
    # 未安装 brotli，不能谎称支持 br，交给 requests 自动协商
    assert "Accept-Encoding" not in chrome_headers()


def test_referer_optional():
    assert "Referer" not in chrome_headers()
    assert chrome_headers(referer="https://example.com/")["Referer"] == "https://example.com/"


def test_unknown_platform_rejected():
    with pytest.raises(ValueError):
        chrome_headers("linux")
    with pytest.raises(ValueError):
        chrome_user_agent("linux")
