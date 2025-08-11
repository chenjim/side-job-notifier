# scrapers/sxsoft_scraper.py

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
from .base_scraper import BaseScraper
from logger import log_info, log_error, log_warning

class SxsoftScraper(BaseScraper):
    """软件项目交易网抓取器"""
    
    def fetch_posts(self) -> List[Dict[str, str]]:
        """获取并解析项目列表，筛选出包含关键词的新项目。"""
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            error_msg = f"请求网页失败: {e}"
            log_error(error_msg)
            # 发送访问异常邮件通知
            self._send_error_notification("access_error", error_msg)
            return []
            
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 将完整的HTML内容保存到 urlData 目录
            self._save_html_debug(response.text, "debug")
                
            # 查找项目列表容器
            project_lists = soup.find_all('ul', class_='list-unstyled')
            if not project_lists:
                error_msg = "错误：找不到项目列表容器"
                log_error(error_msg)
                # 保存解析错误的 HTML 并发送通知
                html_filepath = self._save_html_debug(response.text, "parse_error")
                self._send_error_notification("parse_error", error_msg, html_filepath)
                return []
                
            posts = []
            
            # 遍历所有项目列表容器，找到包含项目的那个
            for project_list in project_lists:
                # 遍历每个项目
                for li in project_list.find_all('li'):
                    try:
                        # 提取项目标题和链接
                        h4_elem = li.find('h4')
                        if not h4_elem:
                            continue
                            
                        a_elem = h4_elem.find('a')
                        if not a_elem:
                            continue
                            
                        title = a_elem.get_text(strip=True)
                        if not title:
                            continue
                            
                        # 检查项目类别是否为APP
                        category_div = li.find('div', class_='left_2')
                        if not category_div:
                            continue
                            
                        category_link = category_div.find('a')
                        if not category_link:
                            continue
                            
                        category_text = category_link.get_text(strip=True)
                        # 只匹配APP类别的项目
                        if category_text != 'APP':
                            continue
                            
                        # 构建完整链接
                        href = a_elem.get('href', '')
                        if href.startswith('/'):
                            link = f"https://www.sxsoft.com{href}"
                        else:
                            link = href
                            
                        # 提取项目详细信息
                        summary_parts = []
                        
                        # 提取价格信息
                        price_elem = li.find('span', class_='text-danger')
                        if price_elem:
                            price = price_elem.get_text(strip=True)
                            if price:
                                summary_parts.append(f"价格: {price}")
                        
                        # 提取项目描述
                        desc_elem = li.find('p', class_='text-muted')
                        if desc_elem:
                            desc = desc_elem.get_text(strip=True)
                            if desc:
                                summary_parts.append(f"描述: {desc}")
                        
                        # 提取发布时间
                        time_elem = li.find('small', class_='text-muted')
                        published_at = ""
                        if time_elem:
                            time_text = time_elem.get_text(strip=True)
                            if time_text:
                                published_at = time_text
                                summary_parts.append(f"发布时间: {time_text}")
                        
                        # 提取其他信息（如技能要求等）
                        info_divs = li.find_all('div', class_='row')
                        for info_div in info_divs:
                            info_text = info_div.get_text(strip=True)
                            if info_text and '技能' in info_text:
                                summary_parts.append(f"技能要求: {info_text}")
                        
                        # 提取标签信息
                        tags = li.find_all('span', class_='label')
                        if tags:
                            tag_texts = [tag.get_text(strip=True) for tag in tags if tag.get_text(strip=True)]
                            if tag_texts:
                                summary_parts.append(f"标签: {', '.join(tag_texts)}")
                        
                        # 提取技能标签
                        skills = li.find_all('span', class_='skill-tag')
                        if skills:
                            skill_texts = [skill.get_text(strip=True) for skill in skills if skill.get_text(strip=True)]
                            if skill_texts:
                                summary_parts.append(f"技能标签: {', '.join(skill_texts)}")
                        
                        summary = ' | '.join(summary_parts)
                        
                        post = {
                            'title': title,
                            'link': link,
                            'summary': summary,
                            'published_at': published_at
                        }
                        
                        posts.append(post)
                            
                    except Exception as e:
                        log_error(f"解析项目时出错: {e}")
                        continue
            
            log_info(f"软件项目交易网: 找到 {len(posts)} 个匹配的项目")
            return posts
        
        except Exception as e:
            log_error(f"抓取软件项目交易网失败: {e}")
            return []