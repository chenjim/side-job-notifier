# notifier.py

import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from config import SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL, SMTP_SERVER, SMTP_PORT
from typing import Dict

def send_notification(post: Dict[str, str], site_name: str = "ELEDUCK"):
    """发送新帖子通知邮件。"""
    title = post.get('title', '')
    link = post.get('link', '')
    summary = post.get('summary', '')
    published_at = post.get('published_at', '')

    subject = f"[JobNotifier]{site_name}: {title}"
    body = f"""<h4>{title}</h4>
               <p><b>发布时间:</b> {published_at}</p>
               <p><b>摘要:</b> {summary}</p>
               <p><b>链接:</b> <a href=\"{link}\">{link}</a></p>"""
    
    message = MIMEText(body, 'html', 'utf-8')
    message['From'] = formataddr(("JobNotifier", SENDER_EMAIL))
    message['To'] = formataddr(("h89_cn", RECIPIENT_EMAIL))
    message['Subject'] = Header(subject, 'utf-8')

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECIPIENT_EMAIL], message.as_string())
        print(f"邮件发送成功: {title}")
    except smtplib.SMTPException as e:
        print(f"邮件发送失败: {e}")