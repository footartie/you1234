"""Free, offline analyzer: keyword-based stance scoring and transcript quote picking.

No API key or paid service needed. Less nuanced than the Claude analyzer (it can't
tell sarcasm or who is speaking), but it runs anywhere at zero cost.
"""
from __future__ import annotations

import math
import re

from .models import Quote, Video

# Matched as substrings, so Korean stems catch conjugations (좋 -> 좋다, 좋아요, 좋은).
POSITIVE = [
    "좋", "최고", "추천", "대박", "감동", "성공", "혁신", "만족", "호평", "기대", "훌륭",
    "멋지", "멋있", "완벽", "강추", "꿀팁", "인정", "찬성", "지지", "응원", "환영", "개선",
    "역대급", "레전드", "사랑", "행복", "재밌", "재미있", "유익", "상승", "호재", "수혜",
    "great", "amazing", "awesome", "love", "best", "excellent", "recommend", "impressive",
]
NEGATIVE = [
    "최악", "실망", "논란", "비판", "망했", "망함", "폭망", "실패", "거짓", "사기", "불만",
    "혹평", "위험", "폭락", "반대", "규탄", "의혹", "결함", "별로", "후회", "문제점", "황당",
    "어이없", "짜증", "분노", "충격", "비추", "손해", "하락", "악재", "피해", "적자", "부작용",
    "구리", "노답", "헛소리", "쓰레기", "환불",
    "worst", "terrible", "awful", "scam", "fail", "disappoint", "hate", "bad", "broken", "problem",
]
# Negated positives that would otherwise count as positive.
NEGATED_POSITIVE = ["안 좋", "안좋", "좋지 않", "좋지않", "좋진 않", "추천 안", "추천안", "비추천", "not good", "not great"]

THRESHOLD = 0.15  # |score| below this is "neutral"


def _count(text: str, words: list[str]) -> dict[str, int]:
    text = text.lower()
    return {w: c for w in words if (c := text.count(w))}


def _polarity(text: str) -> tuple[int, int, dict[str, int], dict[str, int]]:
    pos = _count(text, POSITIVE)
    neg = _count(text, NEGATIVE)
    negated = sum(_count(text, NEGATED_POSITIVE).values())
    if negated:
        neg["부정어+긍정어"] = negated
    p = max(sum(pos.values()) - negated, 0)
    return p, sum(neg.values()), pos, neg


def _clean(text: str) -> str:
    text = re.sub(r"https?://\S+|#\S+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class FreeAnalyzer:
    """Same interface as Analyzer: analyze(topic, video) fills the video in place."""

    model = "free-keyword"

    def analyze(self, topic: str, video: Video) -> Video:
        # Title and description state the video's framing, so they weigh more than
        # the transcript; comments are a weaker signal, weighted by likes.
        pos = neg = 0.0
        pos_words: dict[str, int] = {}
        neg_words: dict[str, int] = {}
        sources = [(video.title, 3.0), (video.description[:1000], 1.0), (video.transcript, 1.0)]
        sources += [(c.text, 0.5 * (1 + math.log10(1 + c.like_count))) for c in video.comments]
        for text, weight in sources:
            p, n, pw, nw = _polarity(text)
            pos += weight * p
            neg += weight * n
            for k, v in pw.items():
                pos_words[k] = pos_words.get(k, 0) + v
            for k, v in nw.items():
                neg_words[k] = neg_words.get(k, 0) + v

        score = (pos - neg) / (pos + neg + 1)
        video.sentiment = "positive" if score > THRESHOLD else "negative" if score < -THRESHOLD else "neutral"
        video.confidence = round(min(abs(score), 1.0), 2)
        video.summary = _summary(video)
        video.reason = _reason(pos_words, neg_words)
        video.quotes = _quotes(topic, video.transcript)
        return video


def _summary(video: Video) -> str:
    desc = _clean(video.description)
    if not desc:
        return video.title
    return desc if len(desc) <= 160 else desc[:160] + "…"


def _reason(pos_words: dict[str, int], neg_words: dict[str, int]) -> str:
    def top(words: dict[str, int]) -> str:
        items = sorted(words.items(), key=lambda kv: kv[1], reverse=True)[:5]
        return ", ".join(f"{w}({c})" for w, c in items) or "없음"

    return f"[키워드 분석] 긍정: {top(pos_words)} / 부정: {top(neg_words)}"


_LINE = re.compile(r"^\[(\d+:\d{2})\] (.*)$")


def _quotes(topic: str, transcript: str, n: int = 3) -> list[Quote]:
    """Pick the transcript passages that mention the topic or carry the most opinion words."""
    lines = [m.groups() for line in transcript.splitlines() if (m := _LINE.match(line))]
    if not lines:
        return []
    topic_terms = [t.lower() for t in topic.split() if len(t) > 1]
    # Auto-captions split sentences across short snippets, so score 3-line windows.
    windows = []
    for i in range(0, len(lines), 3):
        chunk = lines[i : i + 3]
        text = _clean(" ".join(t for _, t in chunk))
        if len(text) < 15:
            continue
        p, neg, _, _ = _polarity(text)
        hits = sum(text.lower().count(t) for t in topic_terms)
        windows.append((2 * hits + p + neg, i, chunk[0][0], text))
    best = sorted(windows, key=lambda w: w[0], reverse=True)[:n]
    best = [w for w in best if w[0] > 0] or best[:1]
    return [Quote(speaker="영상 속 화자", text=t, timestamp=ts) for _, _, ts, t in sorted(best, key=lambda w: w[1])]


def make_analyzer(anthropic_api_key: str = "", free: bool = False):
    """Claude analyzer when an Anthropic key is configured, otherwise the free one."""
    if anthropic_api_key and not free:
        from .analyzer import Analyzer

        return Analyzer(api_key=anthropic_api_key)
    return FreeAnalyzer()
