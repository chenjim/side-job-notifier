# scrapers/browser_headers.py
# 统一的真实 Chrome 请求头，降低站点风控把抓取判为机器人的概率。
# 各抓取器统一从这里取头，避免每个文件各写一份过期 UA。
#
# 维护：Chrome 版本号需随稳定版更新。
# 2026-10 桌面稳定版为 154（155 预计 2026-10-06 发布）。

import random
from typing import Dict, Optional

# 近几个桌面稳定版：真实用户不会都在最新版，每次随机取一个更自然，
# 也避免所有请求顶着同一个版本号。取最近约 2 个月内发布过的稳定版。
CHROME_VERSIONS = ("152", "153", "154")
# 最新稳定版（默认/参考用）
CHROME_VERSION = CHROME_VERSIONS[-1]

# AppleWebKit 与 Safari 的版本号是 Chromium 长期冻结值，真实桌面 Chrome 恒为
# 537.36，并没有多个「合理」变体；不同值只会来自 Edge/Opera/Safari 等别的浏览器，
# 套在 Chrome 上反而露馅，故固定不动。
APPLE_WEBKIT_VERSION = "537.36"
SAFARI_VERSION = "537.36"

# sec-ch-ua 首段是 Chrome 每次请求随机生成的 GREASE 品牌，随机化更贴近真实。
_GREASE_BRANDS = ("Not_A Brand", "Not(A:Brand", "Not?A_Brand")
_GREASE_VERSIONS = ("8", "24", "99")

# UA 精简（UA Reduction）后，桌面 Chrome 只上报主版本号，故形如 154.0.0.0
_PLATFORM_UA = {
    "windows": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/{wk} "
        "(KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/{safari}"
    ),
    "macos": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/{wk} "
        "(KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/{safari}"
    ),
}

_PLATFORM_LABEL = {
    "windows": '"Windows"',
    "macos": '"macOS"',
}

PLATFORMS = tuple(_PLATFORM_UA.keys())


def pick_chrome_version() -> str:
    """从近几个稳定版里随机取一个 Chrome 主版本号。"""
    return random.choice(CHROME_VERSIONS)


def chrome_user_agent(platform: str = "windows",
                      version: Optional[str] = None) -> str:
    """返回指定平台的真实 Chrome UA；version 缺省时随机取一个稳定版。"""
    if platform not in _PLATFORM_UA:
        raise ValueError(f"不支持的平台: {platform}")
    version = version or pick_chrome_version()
    return _PLATFORM_UA[platform].format(
        v=version, wk=APPLE_WEBKIT_VERSION, safari=SAFARI_VERSION
    )


def _build_sec_ch_ua(version: str) -> str:
    """按给定主版本生成 sec-ch-ua，GREASE 品牌每次随机。"""
    grease = f'"{random.choice(_GREASE_BRANDS)}";v="{random.choice(_GREASE_VERSIONS)}"'
    return f'{grease}, "Chromium";v="{version}", "Google Chrome";v="{version}"'


def chrome_headers(platform: str = "windows",
                   referer: Optional[str] = None,
                   fetch_site: str = "none",
                   version: Optional[str] = None) -> Dict[str, str]:
    """返回一组贴近真实 Chrome 的请求头。

    - platform：windows / macos，UA 与 sec-ch-ua-platform 保持一致。
    - version：指定 Chrome 主版本；缺省时随机取一个稳定版。
    - referer：部分站点需要来源页，缺省不带。
    - fetch_site：Sec-Fetch-Site，默认 none（地址栏直接访问）。

    注意：这里故意不设 Accept-Encoding。本环境未安装 brotli，谎称支持 br
    会导致响应无法解码，交给 requests 自动协商（gzip, deflate）即可。
    """
    if platform not in _PLATFORM_UA:
        raise ValueError(f"不支持的平台: {platform}")

    version = version or pick_chrome_version()

    headers = {
        "User-Agent": chrome_user_agent(platform, version),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8,"
            "application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "sec-ch-ua": _build_sec_ch_ua(version),
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": _PLATFORM_LABEL[platform],
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": fetch_site,
        "Sec-Fetch-User": "?1",
    }
    if referer:
        headers["Referer"] = referer
    return headers
