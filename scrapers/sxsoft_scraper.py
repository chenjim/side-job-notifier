# scrapers/sxsoft_scraper.py

from curl_cffi import requests  # curl_cffi 复刻 Chrome TLS/HTTP2 指纹
from bs4 import BeautifulSoup
from typing import List, Dict
from .base_scraper import BaseScraper
from .browser_headers import chrome_headers
from core.logger import log_info, log_error

class SxsoftScraper(BaseScraper):
    """软件项目交易网抓取器。

    列表页结构（2026-10 版）：div.list > ul.list-unstyled > li
        div.left_2（分类 + 状态）/ div.left_8（h4 标题、预算、人气、发布日期、截止日期）/ div.left_2（收藏）
    预算、发布日期等字段是「span > 标签文本 + em > 值」形式，按标签前缀识别，
    避免站点微调顺序后整段解析失效。
    """

    # 列表项里按标签前缀取值的信息块
    FIELD_LABELS = ('预算', '人气', '发布日期', '截止日期')

    def fetch_posts(self) -> List[Dict[str, str]]:
        """获取并解析项目列表，筛选出包含关键词的新项目。"""
        try:
            response = requests.get(self.url, headers=chrome_headers(),
                                    impersonate="chrome", timeout=10)
            response.raise_for_status()
        except requests.RequestsError as e:
            error_msg = f"请求网页失败: {e}"
            log_error(error_msg)
            # 发送访问异常邮件通知
            self._send_error_notification("access_error", error_msg)
            return []

        try:
            # 将完整的HTML内容保存到 urlData 目录
            self._save_html_debug(response.text, "debug")
            posts = self._parse_posts(response.text)
            if not posts:
                error_msg = "错误：未解析到任何项目（列表为空或结构变更）"
                log_error(error_msg)
                # 保存解析错误的 HTML 并发送通知
                html_filepath = self._save_html_debug(response.text, "parse_error")
                self._send_error_notification("parse_error", error_msg, html_filepath)
                return []

            log_info(f"软件项目交易网: 找到 {len(posts)} 个匹配的项目")
            return posts
        except Exception as e:
            log_error(f"抓取软件项目交易网失败: {e}")
            return []

    def _parse_posts(self, html: str) -> List[Dict[str, str]]:
        """从列表页 HTML 解析出所有项目。"""
        soup = BeautifulSoup(html, 'html.parser')
        posts = []
        for li in soup.find_all('li'):
            post = self._parse_item(li)
            if post:
                posts.append(post)
        return posts

    def _parse_item(self, li) -> Dict[str, str]:
        """解析单个列表项；不是项目条目时返回 None。"""
        info = li.find('div', class_='left_8')
        title_link = li.select_one('h4 a')
        if not info or not title_link:
            return None

        title = title_link.get_text(strip=True)
        href = title_link.get('href', '')
        if not title or not href:
            return None
        link = f"https://www.sxsoft.com{href}" if href.startswith('/') else href

        fields = self._extract_fields(info)
        parts = []

        category, state = self._extract_meta(li)
        if category:
            parts.append(f"分类: {category}")
        if state:
            parts.append(f"状态: {state}")
        if fields.get('预算'):
            parts.append(f"预算: {fields['预算']}")
        if fields.get('截止日期'):
            parts.append(f"截止: {fields['截止日期']}")
        if fields.get('人气'):
            parts.append(f"人气: {fields['人气']}")

        tags = self._extract_tags(info)
        if tags:
            parts.append(f"技能标签: {', '.join(tags)}")

        # 老版布局兜底：描述段落
        desc_elem = li.find('p', class_='text-muted')
        if desc_elem:
            desc = desc_elem.get_text(strip=True)
            if desc:
                parts.append(f"描述: {desc}")

        return {
            'title': title,
            'link': link,
            'summary': ' | '.join(parts),
            # 页面上没有发布日期时留空，由存储层回落到首次发现时间
            'published_at': fields.get('发布日期', ''),
        }

    def _extract_fields(self, info) -> Dict[str, str]:
        """提取「预算 / 人气 / 发布日期 / 截止日期」等带标签的字段。"""
        fields: Dict[str, str] = {}
        for span in info.find_all('span', recursive=False):
            text = span.get_text(' ', strip=True)
            for label in self.FIELD_LABELS:
                if text.startswith(label):
                    value = text[len(label):].strip()
                    if value:
                        fields[label] = value
                    break
        # 老版布局兜底
        if '预算' not in fields:
            price_elem = info.find('span', class_='text-danger')
            if price_elem:
                fields['预算'] = price_elem.get_text(strip=True)
        if '发布日期' not in fields:
            time_elem = info.find('small', class_='text-muted')
            if time_elem:
                fields['发布日期'] = time_elem.get_text(strip=True)
        return fields

    def _extract_meta(self, li):
        """提取分类与竞标状态（第一个 div.left_2；第二个是收藏按钮）。"""
        meta_divs = li.find_all('div', class_='left_2')
        if not meta_divs:
            return '', ''
        meta = meta_divs[0]
        category_link = meta.find('a')
        category = category_link.get_text(strip=True) if category_link else ''
        state_span = meta.find('span')
        state = state_span.get_text(strip=True) if state_span else ''
        return category, state

    def _extract_tags(self, info) -> List[str]:
        """提取技能标签值（新布局标签后的 a / span，老布局 span.skill-tag / span.label）。"""
        tags = []
        for a in info.find_all('a'):
            if a.find_parent('h4'):  # 跳过标题链接
                continue
            text = a.get_text(strip=True)
            if text and text not in tags:
                tags.append(text)
        for selector in ('span.skill-tag', 'span.label'):
            for node in info.select(selector):
                text = node.get_text(strip=True)
                if text and text not in tags:
                    tags.append(text)
        return tags
