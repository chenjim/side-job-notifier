# tests/test_sxsoft_parser.py
# 软件项目交易网 2026-10 版列表布局解析回归，防止站点改版后静默解析出空字段。

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.sxsoft_scraper import SxsoftScraper  # noqa: E402

LIST_HTML = """
<ul class="list-unstyled">
  <li>
    <div class="left_2"><a href="#">其它分类项目</a><span>竞标中</span></div>
    <div class="left_8">
      <h4><a href="/project/show/97714" target="_blank">具身机器人二开</a></h4>
      <span>预算<em class="green">5万~10万</em></span>
      <span>人气<em>1038</em></span>
      <span>发布日期<em>2026.10.23</em></span>
      <span>截止日期<em>2026.11.07</em></span>
      <div style="margin-top:28px"><span class="jineng-label">技能标签</span></div>
    </div>
    <div class="left_2"><a href="/user/login/project_97714">收藏</a></div>
  </li>
  <li>
    <div class="left_2"><a href="#">管理系统</a><span>竞标中</span></div>
    <div class="left_8">
      <h4><a href="/project/show/97711">电厂销售管理系统</a></h4>
      <span>预算<em>10万以上</em></span>
      <span>发布日期<em>2026.10.19</em></span>
      <span>截止日期<em>2026.11.03</em></span>
      <span class="skill-tag">Java</span>
    </div>
  </li>
</ul>
"""


def _scraper():
    return SxsoftScraper("https://www.sxsoft.com/page/project", [""])


def test_parse_list_items():
    posts = _scraper()._parse_posts(LIST_HTML)
    assert len(posts) == 2

    first = posts[0]
    assert first["title"] == "具身机器人二开"
    assert first["link"] == "https://www.sxsoft.com/project/show/97714"
    assert first["published_at"] == "2026.10.23"
    assert "预算: 5万~10万" in first["summary"]
    assert "截止: 2026.11.07" in first["summary"]
    assert "分类: 其它分类项目" in first["summary"]
    assert "状态: 竞标中" in first["summary"]
    assert "人气: 1038" in first["summary"]

    second = posts[1]
    assert second["published_at"] == "2026.10.19"
    assert "技能标签: Java" in second["summary"]


def test_published_at_is_parseable():
    from core.time_parser import parse_published_at
    posts = _scraper()._parse_posts(LIST_HTML)
    assert parse_published_at(posts[0]["published_at"]).strftime('%Y-%m-%d') == "2026-10-23"


def test_non_project_li_returns_none():
    scraper = _scraper()
    posts = scraper._parse_posts(
        '<ul class="list-unstyled"><li><h4><a href="#">大家都在看的项目TOP10</a></h4></li>`'
        '<li><div class="left_8"><h4><a href="/project/show/1">缺分类</a></h4></div></li></ul>'
    )
    assert [p["title"] for p in posts] == ["缺分类"]


def test_missing_published_at_stays_empty():
    posts = _scraper()._parse_posts(
        '<li><div class="left_8"><h4><a href="/project/show/2">无日期</a></h4></div></li>'
    )
    assert posts[0]["published_at"] == ""
