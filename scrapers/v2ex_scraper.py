# scrapers/v2ex_scraper.py
# V2EX 外包节点抓取器。
# 2026-11 起列表页 https://www.v2ex.com/go/outsourcing 被 Cloudflare 人机验证拦截（HTTP 403，
# 响应为 "Just a moment..." 挑战页），curl_cffi 无法通过；改抓官方 Atom 订阅源
# https://www.v2ex.com/feed/outsourcing.xml —— 同样是节点最新主题，且附带正文摘要。

import re
import time
import xml.etree.ElementTree as ET
from curl_cffi import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from .base_scraper import BaseScraper
from .browser_headers import chrome_headers
from core.logger import log_info, log_error, log_warning

_ATOM = '{http://www.w3.org/2005/Atom}'
_SUMMARY_LIMIT = 500  # 订阅源正文转纯文本后的摘要长度上限

# 请求线路（proxies, 线路名, 本次尝试前等待秒数）：
# 代理偶发 TLS 断连（SSL_ERROR_SYSCALL），间隔重试一次后仍失败则绕过代理直连兜底
_ROUTES = (
    (None, "代理", 0),
    (None, "代理", 2),
    ({'http': None, 'https': None}, "直连", 5),
)


class V2exScraper(BaseScraper):
    """V2EX 外包节点抓取器（走 Atom 订阅源）。"""

    def fetch_posts(self) -> List[Dict[str, str]]:
        """获取并解析 V2EX /feed/outsourcing.xml 的最新主题。

        返回字段：
            - title: 帖子标题
            - link: 帖子链接 (https://www.v2ex.com/t/{id})
            - summary: 作者 + 正文摘要
            - published_at: ISO8601 发布时间（UTC，如 2026-11-05T15:12:27Z）
        """
        response, error = self._request_feed()
        if response is None:
            error_msg = f"请求网页失败（代理重试与直连均失败）: {error}"
            log_error(error_msg)
            # 发送访问异常邮件通知
            self._send_error_notification("access_error", error_msg)
            return []

        debug_path = self._save_html_debug(response.text, "debug", ext="xml")

        try:
            posts = self._parse_feed(response.text)
        except ET.ParseError as e:
            error_msg = f"解析订阅源失败: {e}"
            log_error(error_msg)
            # 带上调试文件路径，告警邮件里能直接定位原始订阅源内容
            self._send_error_notification("parse_error", error_msg, debug_path)
            return []

        log_info(f"  V2EX 外包节点解析到 {len(posts)} 条帖子")
        return posts

    def _request_feed(self):
        """按 _ROUTES 依次尝试请求订阅源，返回 (response, 最后一次异常)。"""
        last_error = None
        for proxies, route, delay in _ROUTES:
            if delay:
                time.sleep(delay)
            try:
                response = requests.get(self.url, headers=chrome_headers(),
                                        impersonate="chrome", timeout=15,
                                        proxies=proxies)
                response.raise_for_status()
                return response, None
            except requests.RequestsError as e:
                last_error = e
                log_warning(f"  V2EX 订阅源{route}请求失败: {e}")
        return None, last_error

    def _parse_feed(self, xml_text: str) -> List[Dict[str, str]]:
        """解析 Atom 订阅源，返回标准帖子字段列表。"""
        root = ET.fromstring(xml_text)
        posts = []
        for entry in root.findall(f'{_ATOM}entry'):
            title = (entry.findtext(f'{_ATOM}title') or '').strip()
            href = entry.find(f'{_ATOM}link')
            href = href.get('href', '') if href is not None else ''
            m = re.search(r'/t/(\d+)', href)
            if not title or not m:
                continue
            link = f"https://www.v2ex.com/t/{m.group(1)}"

            author = (entry.findtext(f'{_ATOM}author/{_ATOM}name') or '').strip()
            body = entry.findtext(f'{_ATOM}content') or ''
            text = BeautifulSoup(body, 'html.parser').get_text(' ', strip=True)
            if len(text) > _SUMMARY_LIMIT:
                text = text[:_SUMMARY_LIMIT] + '...'
            summary = f"作者: {author}" + (f"\n{text}" if text else '')

            posts.append({
                "title": title,
                "link": link,
                "summary": summary,
                "published_at": (entry.findtext(f'{_ATOM}published') or '').strip(),
            })
        return posts
