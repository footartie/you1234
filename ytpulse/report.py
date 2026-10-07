"""Free, extractive opinion report built from analyzed videos, comments and web context.

No LLM involved: numbers are computed directly, arguments and issues are the
content words that recur on each side, each backed by the most-liked real
comment or quote that contains it.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .free_analyzer import NEGATIVE, POSITIVE, _clean, _polarity
from .models import Video
from .websearch import Background, NewsItem

STANCES = (("positive", "긍정"), ("negative", "부정"), ("neutral", "중립"))

# Phrases that signal doubt or a wait-and-see attitude rather than a side.
SKEPTICAL = [
    "글쎄", "과연", "지켜봐", "두고 봐", "두고봐", "모르겠", "아직", "애매", "반반", "의문", "글쎄요",
    "확실하지", "판단하기", "시기상조", "거품", "과대", "호들갑", "글쎄다", "그닥", "딱히",
]

_JOSA = sorted(
    ["에서는", "으로는", "에게서", "까지는", "이라는", "라는", "이라고", "라고", "에서", "으로", "에게",
     "한테", "까지", "부터", "보다", "처럼", "마다", "이나", "이랑", "은", "는", "이", "가", "을", "를",
     "의", "에", "로", "와", "과", "도", "만", "랑", "요"],
    key=len, reverse=True,
)
_STOPWORDS = set(
    "진짜 정말 너무 그냥 이거 저거 그거 이번 지금 오늘 영상 구독 댓글 사람 생각 우리 이제 근데 그리고 "
    "하는 있는 없는 합니다 했다 하고 해서 같은 같아요 뭔가 아니 이런 그런 저런 많이 다시 계속 제일 가장 "
    "완전 정도 때문 하면 해도 보고 보면 있어요 없어요 입니다 있습니다 그래서 하지만 그런데 이게 저는 제가 "
    "나는 내가 우리는 여러분 어떻게 무슨 이건 그건 거의 정말로 진심 솔직히 다들 모두 항상 아직 이미 "
    "the and for that this with are was you not but have just".split()
)


@dataclass
class StanceStats:
    stance: str
    label: str
    count: int
    share: float  # of videos
    views: int
    view_share: float
    comments: int
    avg_likes: int


@dataclass
class Evidence:
    text: str
    likes: int
    video_title: str
    video_url: str
    kind: str  # "댓글" | "발언" | "제목"


@dataclass
class Argument:
    keyword: str
    mentions: int
    evidence: Evidence


@dataclass
class Issue:
    keyword: str
    positive_mentions: int
    negative_mentions: int
    positive: Evidence
    negative: Evidence


@dataclass
class OpinionReport:
    topic: str
    days: int
    n_videos: int
    headline: str
    summary: list[str]
    overview: str
    stats: list[StanceStats]
    videos: dict[str, list[Video]]
    arguments: dict[str, list[Argument]]  # "positive" / "negative"
    voices: dict[str, list[Evidence]]  # most-liked opinions per side, incl. "skeptical"
    issues: list[Issue]
    news: list[NewsItem] = field(default_factory=list)
    news_source: str = ""
    news_keywords: list[str] = field(default_factory=list)
    background: Background | None = None


# --- text helpers -------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    tokens = []
    for raw in re.findall(r"[가-힣A-Za-z0-9]+", text.lower()):
        for josa in _JOSA:
            if raw.endswith(josa) and len(raw) - len(josa) >= 2:
                raw = raw[: -len(josa)]
                break
        if len(raw) < 2 or raw.isdigit() or raw in _STOPWORDS:
            continue
        if any(w in raw for w in POSITIVE + NEGATIVE + SKEPTICAL):
            continue  # sentiment words say how people feel, not what about
        tokens.append(raw)
    return tokens


@dataclass
class _Unit:
    """One opinion-bearing piece of text with its source."""
    evidence: Evidence
    stance: str  # positive / negative / skeptical / none
    tokens: set[str]


def _stance_of(text: str) -> str:
    p, n, _, _ = _polarity(text)
    if any(w in text for w in SKEPTICAL) or (p and n and abs(p - n) <= 1 and p + n >= 2):
        return "skeptical"
    return "positive" if p > n else "negative" if n > p else "none"


def _units(videos: list[Video], topic_terms: set[str]) -> list[_Unit]:
    units = []
    for v in videos:
        pieces = [(v.title, 0, "제목")]
        pieces += [(q.text, 0, "발언") for q in v.quotes]
        pieces += [(c.text, c.like_count, "댓글") for c in v.comments]
        for text, likes, kind in pieces:
            text = _clean(text)
            if len(text) < 5:
                continue
            ev = Evidence(text=text if len(text) <= 200 else text[:200] + "…", likes=likes,
                          video_title=v.title, video_url=v.url, kind=kind)
            stance = _stance_of(text)
            if kind == "제목" and stance == "none":
                stance = v.sentiment  # an unmarked title inherits its video's stance
            units.append(_Unit(ev, stance, set(tokenize(text)) - topic_terms))
    return units


def _best(units: list[_Unit], keyword: str) -> Evidence:
    # Prefer comments/quotes (real voices) over titles, then the most liked.
    return max((u for u in units if keyword in u.tokens),
               key=lambda u: (u.evidence.kind != "제목", u.evidence.likes)).evidence


# --- report ---------------------------------------------------------------------

def build_opinion_report(
    topic: str,
    days: int,
    videos: list[Video],
    news: list[NewsItem] | None = None,
    news_source: str = "",
    background: Background | None = None,
    n_arguments: int = 5,
    n_issues: int = 5,
) -> OpinionReport:
    news = news or []
    by_stance = {s: [v for v in videos if v.sentiment == s] for s, _ in STANCES}
    total_views = sum(v.view_count for v in videos) or 1
    stats = []
    for s, label in STANCES:
        vs = by_stance[s]
        stats.append(StanceStats(
            stance=s, label=label, count=len(vs), share=len(vs) / (len(videos) or 1),
            views=sum(v.view_count for v in vs), view_share=sum(v.view_count for v in vs) / total_views,
            comments=sum(v.comment_count for v in vs),
            avg_likes=round(sum(v.like_count for v in vs) / len(vs)) if vs else 0,
        ))

    topic_terms = set(tokenize(topic)) | {t.lower() for t in topic.split()}
    units = _units(videos, topic_terms)
    side = {s: [u for u in units if u.stance == s] for s in ("positive", "negative", "skeptical")}
    freq = {s: Counter(t for u in us for t in u.tokens) for s, us in side.items()}

    arguments = {}
    for s, other in (("positive", "negative"), ("negative", "positive")):
        # Words people on this side keep coming back to, more than the other side does.
        ranked = sorted(freq[s], key=lambda t: (freq[s][t] / (1 + freq[other][t]), freq[s][t]), reverse=True)
        arguments[s] = [Argument(t, freq[s][t], _best(side[s], t)) for t in ranked if freq[s][t] >= 2][:n_arguments]
        if not arguments[s]:  # small samples: fall back to single mentions
            arguments[s] = [Argument(t, freq[s][t], _best(side[s], t)) for t in ranked][:n_arguments]

    shared = [t for t in freq["positive"] if freq["negative"][t]]
    shared.sort(key=lambda t: (min(freq["positive"][t], freq["negative"][t]),
                               freq["positive"][t] + freq["negative"][t]), reverse=True)
    issues = [Issue(t, freq["positive"][t], freq["negative"][t],
                    _best(side["positive"], t), _best(side["negative"], t)) for t in shared[:n_issues]]

    def top_voices(us: list[_Unit], n: int = 5) -> list[Evidence]:
        real = [u.evidence for u in us if u.evidence.kind != "제목"]
        return sorted(real, key=lambda e: e.likes, reverse=True)[:n]

    voices = {s: top_voices(us) for s, us in side.items()}

    news_tokens = Counter(t for n in news for t in set(tokenize(n.title)) - topic_terms)
    news_keywords = [t for t, c in news_tokens.most_common(8) if c >= 2] or [t for t, _ in news_tokens.most_common(5)]

    stat = {s.stance: s for s in stats}
    headline = _headline(stat, len(videos))
    report = OpinionReport(
        topic=topic, days=days, n_videos=len(videos), headline=headline, summary=[], overview="",
        stats=stats, videos=by_stance, arguments=arguments, voices=voices, issues=issues,
        news=news, news_source=news_source, news_keywords=news_keywords, background=background,
    )
    report.overview = _overview(report)
    report.summary = _summary(report, stat)
    return report


def _headline(stat: dict[str, StanceStats], n: int) -> str:
    if not n:
        return "분석할 영상이 없습니다"
    if stat["neutral"].share >= 0.6:
        return "뚜렷한 찬반보다 정보 전달·관망 반응이 대부분"
    diff = stat["positive"].view_share - stat["negative"].view_share
    if diff > 0.15:
        return "긍정 여론 우세"
    if diff < -0.15:
        return "부정 여론 우세"
    return "찬반 여론이 팽팽하게 맞섬"


def _first_sentences(text: str, n: int = 2) -> str:
    parts = re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s*", text.strip())
    return " ".join(p for p in parts[:n] if p).strip()


def _overview(r: OpinionReport) -> str:
    lines = []
    if r.background:
        lines.append(f"{_first_sentences(r.background.extract)} ([위키백과: {r.background.title}]({r.background.url}))")
    top = max((v for vs in r.videos.values() for v in vs), key=lambda v: v.view_count, default=None)
    if top:
        lines.append(f"최근 {r.days}일 가장 많이 본 관련 영상은 「{top.title}」({top.channel}, 조회수 {top.view_count:,})입니다.")
    if r.news:
        lines.append(f"최근 뉴스 헤드라인: 「{r.news[0].title}」({r.news[0].source}, {r.news[0].published_at})")
    return "\n\n".join(lines) or "개요 정보를 찾지 못했습니다."


def _summary(r: OpinionReport, stat: dict[str, StanceStats]) -> list[str]:
    if not r.n_videos:
        return ["분석할 영상을 찾지 못했습니다. 기간을 늘리거나 다른 검색어를 시도해 보세요."]
    p, n, z = stat["positive"], stat["negative"], stat["neutral"]
    pts = [
        f"조회수 상위 {r.n_videos}개 영상 중 긍정 {p.count}개({p.share:.0%}), 부정 {n.count}개({n.share:.0%}), "
        f"중립 {z.count}개({z.share:.0%})",
        f"조회수 기준으로는 긍정 {p.view_share:.0%} · 부정 {n.view_share:.0%} · 중립 {z.view_share:.0%}"
        + (" (영상 수와 조회수의 우세 방향이 다름)" if (p.share - n.share) * (p.view_share - n.view_share) < 0 else ""),
    ]
    for s, label in (("positive", "긍정"), ("negative", "부정")):
        if r.arguments[s]:
            pts.append(f"{label} 측이 많이 언급한 내용: " + ", ".join(a.keyword for a in r.arguments[s][:3]))
    if r.issues:
        pts.append("양측이 함께 거론하는 핵심 쟁점: " + ", ".join(i.keyword for i in r.issues[:3]))
    if r.news:
        pts.append(f"최근 뉴스: 「{r.news[0].title}」({r.news[0].source})")
    return pts


# --- markdown ---------------------------------------------------------------------

def _ev_md(e: Evidence) -> str:
    likes = f" · 👍 {e.likes:,}" if e.likes else ""
    return f"“{e.text}” — {e.kind}, [{e.video_title}]({e.video_url}){likes}"


def _video_list_md(videos: list[Video], n: int = 5) -> str:
    if not videos:
        return "_해당 영상 없음_"
    return "\n".join(f"- [{v.title}]({v.url}) — {v.channel}, 조회수 {v.view_count:,}"
                     for v in sorted(videos, key=lambda v: v.view_count, reverse=True)[:n])


def sections(r: OpinionReport) -> list[tuple[str, str]]:
    """(heading, markdown body) for the summary and sections 1-6, in display order."""
    out = [("요약", f"**{r.headline}**\n\n" + "\n".join(f"- {p}" for p in r.summary))]

    table = ["| 입장 | 영상 수 | 비중 | 총 조회수 | 조회수 비중 | 총 댓글 수 | 평균 좋아요 |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    table += [f"| {s.label} | {s.count} | {s.share:.0%} | {s.views:,} | {s.view_share:.0%} | {s.comments:,} | {s.avg_likes:,} |"
              for s in r.stats]
    out.append(("1) 주제 개요 및 여론 정량 분석",
                f"{r.overview}\n\n**조회수 상위 {r.n_videos}개 영상 기준 정량 분석**\n\n" + "\n".join(table)))

    for s, title in (("positive", "2) 긍정·찬성 여론 및 논거"), ("negative", "3) 부정·반대 여론 및 논거")):
        body = ["**주요 논거** (이 입장에서 반복적으로 언급된 내용과 대표 의견)"]
        body += [f"- **{a.keyword}** ({a.mentions}회 언급): {_ev_md(a.evidence)}" for a in r.arguments[s]] or ["- _뚜렷한 논거를 찾지 못했습니다_"]
        body += ["", "**공감을 많이 받은 의견**"]
        body += [f"- {_ev_md(e)}" for e in r.voices[s]] or ["- _해당 의견 없음_"]
        body += ["", "**관련 영상**", _video_list_md(r.videos[s])]
        out.append((title, "\n".join(body)))

    body = ["**신중·회의적 의견** (의문, 관망, 찬반이 섞인 반응)"]
    body += [f"- {_ev_md(e)}" for e in r.voices["skeptical"]] or ["- _해당 의견 없음_"]
    body += ["", "**중립·정보 전달 영상**", _video_list_md(r.videos["neutral"])]
    out.append(("4) 중립·회의적 반응 및 기타 시각", "\n".join(body)))

    if r.issues:
        rows = ["| 쟁점 | 긍정 측 의견 | 부정 측 의견 |", "|---|---|---|"]
        for i in r.issues:
            cell = lambda e: f"{e.text} ([영상]({e.video_url}){', 👍 ' + format(e.likes, ',') if e.likes else ''})".replace("|", "/")
            rows.append(f"| **{i.keyword}** (긍정 {i.positive_mentions} · 부정 {i.negative_mentions}) | {cell(i.positive)} | {cell(i.negative)} |")
        body = "양쪽 모두가 자주 거론한 단어를 쟁점으로 보고, 각 측의 대표 의견을 나란히 놓았습니다.\n\n" + "\n".join(rows)
    else:
        body = "_긍정·부정 양측이 함께 거론한 쟁점을 찾지 못했습니다. 분석 영상 수를 늘려 보세요._"
    out.append(("5) 핵심 쟁점 및 찬반 갈등 포인트", body))

    body = []
    if r.background:
        body.append(f"**배경 지식** — [위키백과: {r.background.title}]({r.background.url})\n\n> {r.background.extract}")
    if r.news:
        body.append(f"**최근 {r.days}일 주요 뉴스** (출처: {r.news_source})")
        body.append("\n".join(f"- [{n.title}]({n.url}) — {n.source}, {n.published_at}" for n in r.news))
        if r.news_keywords:
            body.append("**뉴스에 자주 등장한 단어**: " + ", ".join(r.news_keywords))
    if not body:
        body.append("_웹에서 관련 뉴스·배경 정보를 가져오지 못했습니다._")
    out.append(("6) 여론 배경 맥락 및 관련 지식", "\n\n".join(body)))
    return out


def to_markdown(r: OpinionReport) -> str:
    head = f"# 「{r.topic}」 유튜브 여론 분석 리포트\n\n최근 {r.days}일 · 조회수 상위 {r.n_videos}개 영상 · 무료 키워드 분석\n"
    return head + "\n".join(f"\n## {h}\n\n{b}\n" for h, b in sections(r))


def build_full_report(topic_report, report_size: int, language: str = "ko", region: str = "KR",
                      naver_client_id: str = "", naver_client_secret: str = "") -> OpinionReport:
    """Report over the top `report_size` analyzed videos plus free web context."""
    from .websearch import fetch_context

    videos = [v for v in topic_report.analyzed[:report_size] if v.sentiment != "error"]
    news, source, background = fetch_context(
        topic_report.topic, topic_report.days, language, region, naver_client_id, naver_client_secret
    )
    return build_opinion_report(topic_report.topic, topic_report.days, videos, news, source, background)
