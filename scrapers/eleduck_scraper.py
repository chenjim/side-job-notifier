# scrapers/eleduck_scraper.py

from curl_cffi import requests  # curl_cffi 复刻 Chrome TLS/HTTP2 指纹
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
from typing import List, Dict
from .base_scraper import BaseScraper
from .browser_headers import chrome_headers
from core.logger import log_info, log_error, log_warning

class EleduckScraper(BaseScraper):
    """电鸭社区抓取器。"""
    
    def fetch_posts(self) -> List[Dict[str, str]]:
        """获取并解析电鸭社区的帖子列表，筛选出包含关键词的新帖子。"""
        try:
            response = requests.get(self.url, headers=chrome_headers(),
                                    impersonate="chrome", timeout=10)
            response.raise_for_status()  # 如果请求失败则抛出异常
        except requests.RequestsError as e:
            error_msg = f"请求网页失败: {e}"
            log_error(error_msg)
            # 发送访问异常邮件通知
            self._send_error_notification("access_error", error_msg)
            return []

        soup = BeautifulSoup(response.text, 'html.parser')

        # 将完整的HTML内容保存到 urlData 目录
        self._save_html_debug(response.text, "debug")

        next_data_script = soup.find('script', {'id': '__NEXT_DATA__'})
        if not next_data_script:
            error_msg = "错误：找不到 __NEXT_DATA__ script 标签"
            log_error(error_msg)
            # 保存解析错误的 HTML 并发送通知
            html_filepath = self._save_html_debug(response.text, "parse_error")
            self._send_error_notification("parse_error", error_msg, html_filepath)
            return []

        try:
            data = json.loads(next_data_script.string)
            # 将解析后的JSON数据写入文件，方便调试
            json_content = json.dumps(data, ensure_ascii=False, indent=4)
            self._save_html_debug(json_content, "data")
        except json.JSONDecodeError as e:
            error_msg = f"错误: 解析 __NEXT_DATA__ 的 JSON 内容失败: {e}"
            log_error(error_msg)
            # 保存解析错误的 HTML 并发送通知
            html_filepath = self._save_html_debug(response.text, "json_parse_error")
            self._send_error_notification("parse_error", error_msg, html_filepath)
            return []

        posts = []
        try:
            post_list_data = data['props']['initialProps']['pageProps']['postList']

            if isinstance(post_list_data, dict) and 'posts' in post_list_data:
                raw_posts = post_list_data['posts']
            else:
                error_msg = "错误: `postList` 结构不符合预期。"
                log_error(error_msg)
                # 保存解析错误的 HTML 并发送通知
                html_filepath = self._save_html_debug(response.text, "structure_parse_error")
                self._send_error_notification("parse_error", error_msg, html_filepath)
                return []

            for post_data in raw_posts:
                if not isinstance(post_data, dict):
                    continue

                title = post_data.get('title', '')
                post_id = post_data.get('id')
                if post_id:
                    link = f"https://eleduck.com/posts/{post_id}"
                    summary = post_data.get('summary', '')
                    published_at = post_data.get('published_at', '')
                    posts.append({
                        "title": title,
                        "link": link,
                        "summary": summary,
                        "published_at": published_at
                    })

        except Exception as e:
            log_error(f"解析帖子时发生未知错误: {e}")
            return []

        return posts