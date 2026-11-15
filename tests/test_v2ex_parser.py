# tests/test_v2ex_parser.py
# V2EX 列表页被 Cloudflare 拦截（403）后改抓 Atom 订阅源，锁定解析口径与 UTC 时间换算。

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.v2ex_scraper import V2exScraper  # noqa: E402
import scrapers.v2ex_scraper as v2ex_scraper  # noqa: E402
from core.time_parser import is_recent, parse_published_at  # noqa: E402

FEED_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
  <title>医学六轴网站制作</title>
  <link rel="alternate" type="text/html" href="https://www.v2ex.com/t/1254836#reply2" />
  <published>2026-11-05T15:12:27Z</published>
  <author><name>zmlvipvip</name></author>
  <content type="html"><![CDATA[<p>需要数字交互 3D 显示，报酬优</p>]]></content>
</entry>
<entry>
  <title>网站制作</title>
  <link rel="alternate" type="text/html" href="https://www.v2ex.com/t/1254804#reply4" />
  <published>2026-11-05T12:08:11Z</published>
  <author><name>zmlvipvip</name></author>
  <content type="html"><![CDATA[

  ]]></content>
</entry>
<link rel="self" type="application/atom+xml" href="https://www.v2ex.com/feed/outsourcing.xml" />
</feed>
"""


def _scraper():
    return V2exScraper("https://www.v2ex.com/feed/outsourcing.xml", [""])


def test_parse_feed_entries():
    posts = _scraper()._parse_feed(FEED_XML)
    assert len(posts) == 2

    first = posts[0]
    # 链接去掉 #reply2 锚点，保证与库内历史记录的链接一致
    assert first["link"] == "https://www.v2ex.com/t/1254836"
    assert first["title"] == "医学六轴网站制作"
    assert first["published_at"] == "2026-11-05T15:12:27Z"
    assert "作者: zmlvipvip" in first["summary"]
    assert "需要数字交互 3D 显示，报酬优" in first["summary"]

    second = posts[1]
    assert second["link"] == "https://www.v2ex.com/t/1254804"
    assert second["summary"].strip() == "作者: zmlvipvip"


def test_utc_published_at_converted_to_local():
    # Python 3.10 的 fromisoformat 不认结尾 Z，需按 UTC 正常换算成本地时间
    parsed = parse_published_at("2026-11-05T15:12:27Z")
    expected = datetime(2026, 11, 5, 15, 12, 27, tzinfo=timezone.utc).astimezone()
    assert parsed == expected.replace(tzinfo=None)


def test_recent_utc_time_is_within_window():
    assert is_recent(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 1)


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        pass


def _patch(monkeypatch, tmp_path, fake_get):
    monkeypatch.setattr(v2ex_scraper.requests, 'get', fake_get)
    monkeypatch.setattr(v2ex_scraper.time, 'sleep', lambda seconds: None)
    scraper = _scraper()
    scraper.url_data_dir = str(tmp_path)
    return scraper


def test_request_feed_retries_proxy_then_succeeds(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs.get('proxies'))
        if len(calls) < 2:
            raise v2ex_scraper.requests.RequestsError("SSL_ERROR_SYSCALL")
        return _FakeResponse(FEED_XML)

    posts = _patch(monkeypatch, tmp_path, fake_get).fetch_posts()
    assert len(posts) == 2
    assert calls == [None, None]


def test_request_feed_falls_back_to_direct(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs.get('proxies'))
        if kwargs.get('proxies') is None:
            raise v2ex_scraper.requests.RequestsError("SSL_ERROR_SYSCALL")
        return _FakeResponse(FEED_XML)

    posts = _patch(monkeypatch, tmp_path, fake_get).fetch_posts()
    assert len(posts) == 2
    assert calls == [None, None, {'http': None, 'https': None}]


def test_request_feed_all_routes_fail_sends_alert(monkeypatch, tmp_path):
    alerts = []

    def fake_get(url, **kwargs):
        raise v2ex_scraper.requests.RequestsError("SSL_ERROR_SYSCALL")

    scraper = _patch(monkeypatch, tmp_path, fake_get)
    monkeypatch.setattr(scraper, '_send_error_notification',
                        lambda error_type, message, path='': alerts.append(error_type))
    assert scraper.fetch_posts() == []
    assert alerts == ["access_error"]
