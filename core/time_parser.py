# time_parser.py
# 统一解析各站点帖子发布时间，失败返回 None

import re
from datetime import datetime, timedelta

from core.logger import log_warning


def parse_published_at(text: str) -> datetime:
    """解析发布时间文本为本地时区的 datetime。

    支持的格式：
      - ISO8601（含时区，如 eleduck: 2025-08-11T14:14:03.701+08:00）
      - YYYY.MM.DD（如 sxsoft: 2025.08.17）
      - YYYY-MM-DD、YYYY/MM/DD
      - 今天/昨天/X分钟前/X小时前/X天前
    解析失败返回 None。
    """
    if not text:
        return None

    text = text.strip()
    now = datetime.now()

    # 相对时间：X分钟前 / X小时前 / X天前 / X周前 / X个月前（容忍"大约"前缀与"发布"后缀）
    rel = re.fullmatch(r'(?:大约)?\s*(\d+)\s*(?:个)?(分钟|小时|天|周|月)前(?:发布|更新)?', text)
    if rel:
        amount, unit = int(rel.group(1)), rel.group(2)
        delta = {
            '分钟': timedelta(minutes=amount),
            '小时': timedelta(hours=amount),
            '天': timedelta(days=amount),
            '周': timedelta(weeks=amount),
            '月': timedelta(days=30 * amount),
        }[unit]
        return now - delta
    if text in ('今天', '今日'):
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if text in ('昨天', '昨日'):
        return now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)

    # ISO8601：尝试 Python 3.11 的 fromisoformat（支持时区）
    try:
        return datetime.fromisoformat(text).astimezone().replace(tzinfo=None)
    except ValueError:
        pass

    # 纯日期：YYYY.MM.DD / YYYY-MM-DD / YYYY/MM/DD
    for fmt in ('%Y.%m.%d', '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d %H:%M', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    log_warning(f"无法解析发布时间: {text!r}")
    return None


def is_recent(published_at_text: str, days: int) -> bool:
    """判断发布时间是否在最近 days 天内。解析失败视为非最近。"""
    dt = parse_published_at(published_at_text)
    if dt is None:
        return False
    return datetime.now() - dt <= timedelta(days=days)
