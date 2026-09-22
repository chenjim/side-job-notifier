# scrapers/epwk_scraper.py

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from typing import List, Dict
from .base_scraper import BaseScraper
from core.logger import log_info, log_error

class EpwkScraper(BaseScraper):
    """一品威客任务列表抓取器（列表页无发布时间，按列表位置兜底）。"""

    def fetch_posts(self) -> List[Dict[str, str]]:
        """获取并解析一品威客任务列表。"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(self.url, headers=headers, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            error_msg = f"请求网页失败: {e}"
            log_error(error_msg)
            self._send_error_notification("access_error", error_msg)
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        self._save_html_debug(response.text, "debug")

        posts = []
        try:
            # 任务卡片: li > a.clearfix > span.info_title(标题) + span.info_cash(价格)
            for a in soup.find_all('a', class_='clearfix', href=True):
                href = a['href']
                if not re.search(r'task\.epwk\.com/\d+/?$', href):
                    continue
                title_elem = a.find('span', class_='info_title')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                if not title:
                    continue

                price = ""
                cash_elem = a.find('span', class_='info_cash')
                if cash_elem:
                    price = ' '.join(cash_elem.get_text(strip=True).split())

                summary = f"价格: {price}" if price else ""
                posts.append({
                    "title": title,
                    "link": href,
                    "summary": summary,
                    "published_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 列表页无发布时间，取抓取时间
                })

            log_info(f"一品威客: 找到 {len(posts)} 个任务")
        except Exception as e:
            log_error(f"解析一品威客任务失败: {e}")
            return []

        return posts
