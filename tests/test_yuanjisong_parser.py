# tests/test_yuanjisong_parser.py
# 猿急送 v3 布局（div.job_card）解析回归，防止站点改版后静默解析出垃圾。

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup  # noqa: E402

from scrapers.yuanjisong_scraper import YuanjisongScraper  # noqa: E402

V3_CARD_HTML = """
<div class="job_card">
  <div class="job_card_head">
    <a class="job_card_title_link" href="/job/160224">小红书跳风险解核对</a>
    <h4 class="job_card_title">小红书跳风险解核对</h4>
    <span class="job_card_postnum">2 人已投递</span>
  </div>
  <div class="job_card_tags">
    <span class="job_tag_type">项目制 全国远程</span>
    <span class="job_tag_hours">工时：5 天</span>
  </div>
  <div class="job_card_desc"><span class="job_card_desc_label">描述：</span>需要一名后端工程师，能远程。</div>
  <div class="job_card_price">¥3000 元</div>
  <a class="job_card_publisher_name" href="/employer/435585">IT轻奢</a>
</div>
"""


def _scraper():
    return YuanjisongScraper("https://www.yuanjisong.com/job/allcity/zxfb", [""])


def test_parse_v3_card_fields():
    soup = BeautifulSoup(V3_CARD_HTML, "html.parser")
    card = soup.find("div", class_="job_card")
    post = _scraper()._parse_v3_card(card)

    assert post is not None
    assert post["title"] == "小红书跳风险解核对"
    assert post["link"] == "https://www.yuanjisong.com/job/160224"
    assert "项目制 全国远程" in post["summary"]
    assert "工时：5 天" in post["summary"]
    assert "¥3000 元" in post["summary"]
    assert "IT轻奢" in post["summary"]
    assert "需要一名后端工程师" in post["summary"]
    assert "描述：" not in post["summary"]


def test_parse_v3_card_without_title_returns_none():
    soup = BeautifulSoup('<div class="job_card"><div class="job_card_head"></div></div>',
                         "html.parser")
    assert _scraper()._parse_v3_card(soup.find("div", class_="job_card")) is None


def test_is_job_list_html_recognizes_layouts():
    s = _scraper()
    assert s._is_job_list_html('<div class="job_card">职位</div>')
    assert s._is_job_list_html('<div class="yjs-job-card">职位</div>')
    assert s._is_job_list_html('<div class="yjs-job-list-page">职位</div>')
    assert not s._is_job_list_html('<html><body>403 Forbidden</body></html>')
