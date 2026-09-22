# scrapers/v2ex_scraper.py
# V2EX 外包节点抓取器（https://www.v2ex.com/go/outsourcing）

import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from .base_scraper import BaseScraper
from core.logger import log_info, log_error


class V2exScraper(BaseScraper):
    """V2EX 外包节点抓取器。"""

    def fetch_posts(self) -> List[Dict[str, str]]:
        """获取并解析 V2EX /go/outsourcing 的帖子列表。

        返回字段：
            - title: 帖子标题
            - link: 帖子链接 (https://www.v2ex.com/t/{id})
            - summary: 作者名（V2EX 列表页无正文摘要）
            - published_at: ISO8601 发布时间（取自 span[title]，转标准格式）
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
            }
            response = requests.get(self.url, headers=headers, timeout=15)
            response.raise_for_status()  # 如果请求失败则抛出异常
        except requests.RequestException as e:
            error_msg = f"请求网页失败: {e}"
            log_error(error_msg)
            # 发送访问异常邮件通知
            self._send_error_notification("access_error", error_msg)
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        self._save_html_debug(response.text, "debug")

        posts = []
        # 每个帖子条目：td 内含 span.item_title > a.topic-link（标题）和 span.topic_info > span[title]（发布时间）
        for a in soup.select('a.topic-link'):
            title = a.get_text(strip=True)
            href = a.get('href', '')
            m = re.search(r'/t/(\d+)', href)
            if not m:
                continue
            topic_id = m.group(1)
            link = f"https://www.v2ex.com/t/{topic_id}"

            # 发布时间：在同级 span.topic_info 内的 span[title] 属性
            published_at = ''
            td = a.find_parent('td')
            if td:
                tspan = td.select_one('span.topic_info span[title]')
                if tspan and tspan.get('title'):
                    raw = tspan['title'].strip()
                    # 转标准 ISO8601：'2026-09-09 15:11:33 +08:00' -> '2026-09-09T15:11:33+08:00'
                    published_at = raw.replace(' ', 'T', 1).replace(' ', '')

            # 作者名作为摘要
            author = ''
            if td:
                aspan = td.select_one('span.topic_info strong a')
                if aspan:
                    author = aspan.get_text(strip=True)

            posts.append({
                "title": title,
                "link": link,
                "summary": f"作者: {author}" if author else '',
                "published_at": published_at
            })

        log_info(f"  V2EX 外包节点解析到 {len(posts)} 条帖子")
        return posts