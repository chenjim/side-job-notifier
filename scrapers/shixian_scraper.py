# scrapers/shixian_scraper.py

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
from .base_scraper import BaseScraper
from logger import log_info, log_error, log_warning

class ShixianScraper(BaseScraper):
    """实现网抓取器"""
    
    def fetch_posts(self) -> List[Dict[str, str]]:
        """获取并解析实现网的项目列表，筛选出包含关键词的新项目。"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            error_msg = f"请求网页失败: {e}"
            log_error(error_msg)
            # 发送访问异常邮件通知
            self._send_error_notification("access_error", error_msg)
            return []
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 将完整的HTML内容保存到 urlData 目录
        self._save_html_debug(response.text, "debug")
        
        # 查找项目列表容器
        job_list_container = soup.find('div', class_='job-list')
        if not job_list_container:
            error_msg = "错误：找不到项目容器 div.job"
            log_error(error_msg)
            # 保存解析错误的 HTML 并发送通知
            html_filepath = self._save_html_debug(response.text, "parse_error")
            self._send_error_notification("parse_error", error_msg, html_filepath)
            return []
            
        # 查找所有项目
        project_containers = job_list_container.find_all('div', class_='job')
        
        if not project_containers:
            log_warning("未找到项目容器 div.job")
            return []
        
        posts = []
            
        for container in project_containers:
            try:
                # 查找项目信息容器
                info_div = container.find('div', class_='info')
                if not info_div:
                    continue
                
                # 提取项目标题和链接
                title_link = info_div.find('a')
                if not title_link:
                    continue
                
                # 获取链接
                link = title_link.get('href')
                if link and not link.startswith('http'):
                    if link.startswith('/'):
                        link = f"https://shixian.com{link}"
                    else:
                        link = f"https://shixian.com/{link}"
                
                # 获取标题
                title_elem = title_link.find('h5', class_='title')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                
                # 移除类型标签（如"远程兼职"）
                type_span = title_elem.find('span', class_='type')
                if type_span:
                    title = title.replace(type_span.get_text(strip=True), '').strip()
                
                # 检查标题是否包含关键词（如果有关键词配置）
                if self.keywords and self.keywords != [''] and not self._contains_keywords(title):
                    continue
                
                # 提取项目描述
                desc_elem = title_link.find('p', class_='describe')
                description = ''
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                
                # 提取发布者信息和发布时间
                user_div = container.find('div', class_='user')
                published_at = ''
                publisher = ''
                
                if user_div:
                    # 提取发布者名称
                    name_elem = user_div.find('a', class_='name')
                    if name_elem:
                        publisher = name_elem.get_text(strip=True)
                    
                    # 提取发布时间
                    time_elem = user_div.find('span', class_='publish-at')
                    if time_elem:
                        published_at = time_elem.get_text(strip=True)
                
                # 构建摘要信息
                summary_parts = []
                if description:
                    # 限制描述长度
                    desc_preview = description[:150] + '...' if len(description) > 150 else description
                    summary_parts.append(desc_preview)
                
                if publisher and publisher != '昵称登录后显示':
                    summary_parts.append(f"发布者: {publisher}")
                
                final_summary = ' | '.join(summary_parts) if summary_parts else ''
                
                post = {
                    'title': title,
                    'link': link,
                    'summary': final_summary,
                    'published_at': published_at
                }
                
                posts.append(post)
                
            except Exception as e:
                log_error(f"解析项目时出错: {e}")
                continue
        
        log_info(f"实现网: 找到 {len(posts)} 个匹配的项目")
        return posts