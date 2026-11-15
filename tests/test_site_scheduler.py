# tests/test_site_scheduler.py
# 站点抓取节奏判定：独立间隔、区间随机、失败快速重试。

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.site_scheduler import is_due, resolve_interval  # noqa: E402
from core.time_parser import TS_FMT  # noqa: E402

NOW = datetime(2026, 10, 27, 12, 0, 0)


def ts(minutes_ago: int) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).strftime(TS_FMT)


def test_first_run_is_always_due():
    assert is_due(None, 1440, now=NOW)
    assert is_due("", (60, 120), now=NOW)


def test_fixed_interval():
    assert not is_due(ts(1439), 1440, now=NOW)   # 差 1 分钟
    assert is_due(ts(1440), 1440, now=NOW)


def test_range_interval_uses_bounds():
    # 区间内随机，但边界必须成立：不足下限一定不到期，超过上限一定到期
    assert not is_due(ts(59), (60, 120), now=NOW)
    assert is_due(ts(121), (60, 120), now=NOW)


def test_error_status_retries_early():
    # 上次失败：即使间隔是 24 小时，也按 RETRY_MINUTES(30) 快速重试
    assert not is_due(ts(29), 1440, last_status='error', now=NOW)
    assert is_due(ts(31), 1440, last_status='error', now=NOW)


def test_bad_timestamp_treated_as_due():
    assert is_due("not-a-time", 1440, now=NOW)


def test_resolve_interval_formats():
    assert resolve_interval(1440) == 1440
    assert resolve_interval((60, 120)) in range(60, 121)
    assert resolve_interval((120, 60)) in range(60, 121)   # 顺序写反也能兜住
