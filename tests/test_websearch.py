from ytpulse import websearch
from ytpulse.websearch import parse_google_news_rss, parse_naver_news, parse_wikipedia_summary

RSS = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>x</title>
<item><title>갤럭시 S26 사전판매 신기록 - 연합뉴스</title><link>https://news.google.com/a</link>
<pubDate>Tue, 06 Oct 2026 07:00:00 GMT</pubDate><description>&lt;a&gt;x&lt;/a&gt;</description>
<source url="https://www.yna.co.kr">연합뉴스</source></item>
<item><title>S26 &amp; 가격 논란 - 한겨레</title><link>https://news.google.com/b</link>
<pubDate>Mon, 05 Oct 2026 01:00:00 GMT</pubDate><source url="https://hani.co.kr">한겨레</source></item>
</channel></rss>"""


def test_parse_google_news_rss():
    items = parse_google_news_rss(RSS)
    assert [(i.title, i.source, i.published_at) for i in items] == [
        ("갤럭시 S26 사전판매 신기록", "연합뉴스", "2026-10-06"),
        ("S26 & 가격 논란", "한겨레", "2026-10-05"),
    ]
    assert len(parse_google_news_rss(RSS, limit=1)) == 1


def test_parse_naver_news_filters_old_and_strips_tags():
    from datetime import datetime, timedelta

    recent = (datetime.now() - timedelta(days=1)).strftime("%a, %d %b %Y 10:00:00 +0900")
    data = {"items": [
        {"title": "<b>갤럭시</b> S26 &quot;흥행&quot;", "originallink": "https://www.example.com/a/1",
         "link": "https://n.news.naver.com/1", "description": "<b>요약</b>", "pubDate": recent},
        {"title": "옛날 기사", "originallink": "https://old.com/x", "pubDate": "Mon, 01 Jan 2024 10:00:00 +0900"},
    ]}
    items = parse_naver_news(data, days=7)
    assert len(items) == 1
    assert items[0].title == '갤럭시 S26 "흥행"' and items[0].source == "example.com" and items[0].snippet == "요약"


def test_parse_wikipedia_summary():
    bg = parse_wikipedia_summary({"title": "T", "extract": "설명.", "content_urls": {"desktop": {"page": "https://w/T"}}})
    assert (bg.title, bg.extract, bg.url) == ("T", "설명.", "https://w/T")
    assert parse_wikipedia_summary({"title": "T", "extract": ""}) is None


def test_network_failures_return_empty(monkeypatch):
    def boom(*a, **k):
        raise websearch.requests.ConnectionError("blocked")

    monkeypatch.setattr(websearch.requests, "get", boom)
    assert websearch.google_news("x") == []
    assert websearch.naver_news("x", "id", "secret") == []
    assert websearch.wikipedia_background("x") is None
    news, source, bg = websearch.fetch_context("x", naver_client_id="id", naver_client_secret="s")
    assert (news, source, bg) == ([], "Google 뉴스", None)


def test_naver_skipped_without_keys(monkeypatch):
    monkeypatch.setattr(websearch.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    assert websearch.naver_news("x", "", "") == []
