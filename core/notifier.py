# notifier.py

import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from config import SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL, SMTP_SERVER, SMTP_PORT
from typing import Dict, List

def send_notification(post: Dict[str, str], site_name: str = "ELEDUCK"):
    """发送单条新帖子通知邮件。"""
    title = post.get('title', '')
    link = post.get('link', '')
    summary = post.get('summary', '')
    published_at = post.get('published_at', '')

    subject = f"[JobNotifier]{site_name}: {title}"
    body = f"""<h4>{title}</h4>
               <p><b>发布时间:</b> {published_at}</p>
               <p><b>摘要:</b> {summary}</p>
               <p><b>链接:</b> <a href=\"{link}\">{link}</a></p>"""

    _send_mail(subject, body)

def send_recommendation_batch(items: List[Dict]):
    """发送推荐汇总邮件，按评分降序排列。

    items: [{site_name, title, link, summary, score, reason}]
    """
    if not items:
        return

    rows = []
    for it in items:
        rows.append(
            f"<tr>"
            f"<td style='padding:6px'>{it['score']}</td>"
            f"<td style='padding:6px'>{it['site_name']}</td>"
            f"<td style='padding:6px'><a href=\"{it['link']}\">{it['title']}</a></td>"
            f"<td style='padding:6px'>{it['reason']}</td>"
            f"</tr>"
        )

    subject = f"[JobNotifier] 推荐 {len(items)} 个新机会"
    body = f"""<h4>以下是今天发现、值得关注的新机会（按匹配度排序）:</h4>
               <table border='1' cellspacing='0' cellpadding='4'>
               <tr><th>评分</th><th>来源</th><th>标题</th><th>推荐理由</th></tr>
               {''.join(rows)}
               </table>
               <p>来自 <b>side-job-notifier</b> 自动推荐</p>"""

    _send_mail(subject, body)

def send_alert(subject: str, body_html: str):
    """发送告警邮件（用于失败通知）。"""
    _send_mail(subject, body_html)

def _send_mail(subject: str, body_html: str):
    """发送 HTML 邮件。"""
    message = MIMEText(body_html, 'html', 'utf-8')
    message['From'] = formataddr(("JobNotifier", SENDER_EMAIL))
    message['To'] = formataddr(("JobNotifier", RECIPIENT_EMAIL))
    message['Subject'] = Header(subject, 'utf-8')

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [RECIPIENT_EMAIL], message.as_string())
        print(f"邮件发送成功: {subject}")
    except smtplib.SMTPException as e:
        print(f"邮件发送失败: {e}")
