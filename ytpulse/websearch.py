"""Free web context for the report: recent news and encyclopedia background.

- Google News RSS: no key, recent headlines (used by default)
- Wikipedia API: no key, background summary of the topic (used by default)
- Naver Search API: free with a key (25,000 calls/day), used when NAVER_CLIENT_ID /
  NAVER_CLIENT_SECRET are configured

Every function returns empty results on any network or parsing error, so the
report still renders when a source is unreachable.
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

USER_AGENT = "ytpulse/1.0 (YouTube opinion report; https://github.com/footartie/you1234)"
TIMEOUT = 10


@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    published_at: str  # YYYY-MM-DD
    snippet: str = ""


@dataclass
class Background:
    title: str
    extract: str
    url: str


def _strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _date(rfc822: str) -> str:
    try:
        return parsedate_to_datetime(rfc822).date().isoformat()
    except (TypeError, ValueError):
        return ""


def google_news(topic: str, days: int = 7, language: str = "ko", region: str = "KR", limit: int = 10) -> list[NewsItem]:
    try:
        resp = requests.get(
            "https://news.google.com/rss/search",
            params={"q": f"{topic} when:{days}d", "hl": language, "gl": region, "ceid": f"{region}:{language}"},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return parse_google_news_rss(resp.text, limit)
    except (requests.RequestException, ET.ParseError):
        return []


def parse_google_news_rss(xml_text: str, limit: int = 10) -> list[NewsItem]:
    items = []
    for item in ET.fromstring(xml_text).iter("item"):
        source = item.findtext("source") or ""
        title = item.findtext("title") or ""
        # Google appends " - Source" to every headline.
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        items.append(
            NewsItem(
                title=_strip_tags(title),
                source=source,
                url=item.findtext("link") or "",
                published_at=_date(item.findtext("pubDate") or ""),
            )
        )
        if len(items) >= limit:
            break
    return items


def naver_news(topic: str, client_id: str, client_secret: str, days: int = 7, limit: int = 10) -> list[NewsItem]:
    if not (client_id and client_secret):
        return []
    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            params={"query": topic, "display": 50, "sort": "sim"},
            headers={"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return parse_naver_news(resp.json(), days, limit)
    except (requests.RequestException, ValueError):
        return []


def parse_naver_news(data: dict, days: int = 7, limit: int = 10) -> list[NewsItem]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    items = []
    for it in data.get("items", []):
        published = _date(it.get("pubDate", ""))
        if published and published < cutoff:
            continue
        url = it.get("originallink") or it.get("link", "")
        items.append(
            NewsItem(
                title=_strip_tags(it.get("title", "")),
                source=re.sub(r"^https?://(www\.)?", "", url).split("/")[0],
                url=url,
                published_at=published,
                snippet=_strip_tags(it.get("description", "")),
            )
        )
        if len(items) >= limit:
            break
    return items


def wikipedia_background(topic: str, language: str = "ko") -> Background | None:
    base = f"https://{language}.wikipedia.org"
    headers = {"User-Agent": USER_AGENT}
    try:
        search = requests.get(
            f"{base}/w/api.php",
            params={"action": "query", "list": "search", "srsearch": topic, "srlimit": 1, "format": "json"},
            headers=headers,
            timeout=TIMEOUT,
        )
        search.raise_for_status()
        hits = search.json().get("query", {}).get("search", [])
        if not hits:
            return None
        summary = requests.get(
            f"{base}/api/rest_v1/page/summary/{requests.utils.quote(hits[0]['title'])}",
            headers=headers,
            timeout=TIMEOUT,
        )
        summary.raise_for_status()
        return parse_wikipedia_summary(summary.json())
    except (requests.RequestException, ValueError, KeyError):
        return None


def parse_wikipedia_summary(data: dict) -> Background | None:
    extract = (data.get("extract") or "").strip()
    if not extract:
        return None
    url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
    return Background(title=data.get("title", ""), extract=extract, url=url)


def fetch_context(
    topic: str, days: int = 7, language: str = "ko", region: str = "KR",
    naver_client_id: str = "", naver_client_secret: str = "",
) -> tuple[list[NewsItem], str, Background | None]:
    """(news, news source label, background). Naver is used when keys are set and
    returns results; otherwise Google News RSS."""
    news = naver_news(topic, naver_client_id, naver_client_secret, days)
    source = "네이버 뉴스"
    if not news:
        news, source = google_news(topic, days, language, region), "Google 뉴스"
    return news, source, wikipedia_background(topic, language)
