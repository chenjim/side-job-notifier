# scrapers/base_scraper.py

import os
import smtplib
from datetime import datetime
from abc import ABC, abstractmethod
from typing import List, Dict
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from logger import log_info, log_error, log_warning

class BaseScraper(ABC):
    """抓取器基类，定义所有抓取器的通用接口。"""
    
    def __init__(self, url: str, keywords: List[str]):
        self.url = url
        self.keywords = keywords
        # 从类名推导网站名称（如 EleduckScraper -> eleduck）
        self.site_name = self.__class__.__name__.replace('Scraper', '').lower()
        # 使用 urlData 目录，不创建子目录
        self.url_data_dir = 'urlData'
        os.makedirs(self.url_data_dir, exist_ok=True)
    
    @abstractmethod
    def fetch_posts(self) -> List[Dict[str, str]]:
        """获取并解析帖子列表，筛选出包含关键词的新帖子。
        
        Returns:
            List[Dict[str, str]]: 包含帖子信息的字典列表，每个字典包含:
                - title: 帖子标题
                - link: 帖子链接
                - summary: 帖子摘要
                - published_at: 发布时间
        """
        pass
    
    def _contains_keywords(self, text: str) -> bool:
        """检查文本是否包含关键词。
        
        Args:
            text: 要检查的文本
            
        Returns:
            bool: 如果包含任一关键词则返回True
        """
        return any(keyword.lower() in text.lower() for keyword in self.keywords)
    
    def _save_html_debug(self, html_content: str, error_type: str = "debug") -> str:
        """保存 HTML 调试文件到 urlData 目录。
        
        Args:
            html_content: HTML 内容
            error_type: 错误类型（debug, access_error, parse_error）
            
        Returns:
            str: 保存的文件路径
        """
        filename = f"{self.site_name}_{error_type}.html"
        filepath = os.path.join(self.url_data_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            log_info(f"HTML 调试文件已保存: {filepath}")
            return filepath
        except Exception as e:
            log_error(f"保存 HTML 调试文件失败: {e}")
            return ""
    
    def _send_error_notification(self, error_type: str, error_message: str, html_filepath: str = ""):
        """发送错误通知邮件。
        
        Args:
            error_type: 错误类型（access_error, parse_error）
            error_message: 错误信息
            html_filepath: HTML 调试文件路径
        """
        try:
            # 导入配置信息
            from config import SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL, SMTP_SERVER, SMTP_PORT
            
            subject = f"[JobNotifier] {self.site_name.upper()} 抓取错误: {error_type}"
            
            body_parts = [
                f"<h4>网站抓取错误通知</h4>",
                f"<p><b>网站:</b> {self.site_name.upper()}</p>",
                f"<p><b>URL:</b> {self.url}</p>",
                f"<p><b>错误类型:</b> {error_type}</p>",
                f"<p><b>错误信息:</b> {error_message}</p>",
                f"<p><b>发生时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"  # 使用本地时区
            ]
            
            if html_filepath:
                body_parts.append(f"<p><b>调试文件:</b> {html_filepath}</p>")
            
            body = "\n".join(body_parts)
            
            message = MIMEText(body, 'html', 'utf-8')
            message['From'] = formataddr(("JobNotifier", SENDER_EMAIL))
            message['To'] = formataddr(("h89_cn", RECIPIENT_EMAIL))
            message['Subject'] = Header(subject, 'utf-8')
            
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, [RECIPIENT_EMAIL], message.as_string())
            
            log_info(f"错误通知邮件发送成功: {error_type}")
            
        except Exception as e:
            log_error(f"发送错误通知邮件失败: {e}")