# core/site_scheduler.py
# 站点抓取节奏判定：每个站点可以有独立的最小抓取间隔（分钟），与调度心跳解耦。
# 心跳（LOOP_TICK_MINUTES）只负责「问一句是否到期」，到期才抓，避免低频站点被反复请求。

import random
from datetime import datetime, timedelta
from typing import Optional, Tuple, Union

from core.time_parser import TS_FMT

# 抓取失败后的重试间隔上限（分钟）：别因为一次失败就按整天间隔干等
RETRY_MINUTES = 30

Interval = Union[int, Tuple[int, int]]


def resolve_interval(interval: Interval) -> int:
    """把配置的间隔归一成分钟数：(min, max) 元组表示区间内随机，int 表示固定间隔。"""
    if isinstance(interval, (tuple, list)):
        low, high = int(interval[0]), int(interval[1])
        if low > high:
            low, high = high, low
        return random.randint(low, high)
    return int(interval)


def is_due(last_fetch_at: Optional[str], interval: Interval,
           last_status: str = 'ok', now: Optional[datetime] = None) -> bool:
    """判断站点是否到了下一次抓取时间。

    Args:
        last_fetch_at: 上次抓取时间（'YYYY-MM-DD HH:MM:SS'），None 表示从没抓过
        interval: 最小抓取间隔（分钟，或 (min, max) 分钟区间）
        last_status: 上次抓取结果，'error' 时按 RETRY_MINUTES 上限快速重试
        now: 便于测试注入当前时间
    """
    if not last_fetch_at:
        return True

    now = now or datetime.now()
    try:
        last = datetime.strptime(last_fetch_at, TS_FMT)
    except (TypeError, ValueError):
        return True

    minutes = resolve_interval(interval)
    if last_status == 'error':
        minutes = min(minutes, RETRY_MINUTES)
    return now - last >= timedelta(minutes=minutes)
