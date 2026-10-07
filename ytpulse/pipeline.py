"""Topic -> top 5 positive / top 5 negative videos from the last N days."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from .analyzer import Analyzer
from .models import TopicReport, Video
from .youtube import YouTubeClient

ProgressFn = Callable[[str], None]


def build_report(
    topic: str,
    youtube: YouTubeClient,
    analyzer: Analyzer,
    days: int = 7,
    per_side: int = 5,
    comments_per_video: int = 5,
    max_candidates: int = 50,
    batch_size: int = 8,
    progress: ProgressFn = lambda _msg: None,
) -> TopicReport:
    """Walk candidates in view-count order, analyzing in parallel batches, and stop
    as soon as both the positive and negative lists are full. This keeps API
    usage proportional to how quickly each side fills up."""
    progress(f"'{topic}' 최근 {days}일 영상 검색 중...")
    candidates = youtube.search_recent(topic, days=days, max_results=max_candidates)
    progress(f"후보 {len(candidates)}개 발견 (조회수 순)")

    positive: list[Video] = []
    negative: list[Video] = []
    scanned = 0

    def enrich_and_analyze(v: Video) -> Video:
        try:
            v.comments = youtube.top_comments(v.video_id, n=comments_per_video)
            v.transcript = youtube.transcript(v.video_id)
            return analyzer.analyze(topic, v)
        except Exception as e:  # one bad video shouldn't sink the whole report
            # Runs on a worker thread: record the error and let the main thread report
            # it, since UIs like Streamlit can only be updated from the main thread.
            v.sentiment = "error"
            v.reason = f"{type(e).__name__}: {e}"
            return v

    with ThreadPoolExecutor(max_workers=batch_size) as pool:
        for start in range(0, len(candidates), batch_size):
            if len(positive) >= per_side and len(negative) >= per_side:
                break
            batch = candidates[start : start + batch_size]
            # map() preserves input order, so view-count ranking is kept.
            for v in pool.map(enrich_and_analyze, batch):
                scanned += 1
                if v.sentiment == "error":
                    progress(f"건너뜀: {v.title} ({v.reason})")
                elif v.sentiment == "positive" and len(positive) < per_side:
                    positive.append(v)
                elif v.sentiment == "negative" and len(negative) < per_side:
                    negative.append(v)
            progress(
                f"{scanned}/{len(candidates)}개 분석 완료 - 긍정 {len(positive)}, 부정 {len(negative)}"
            )

    return TopicReport(topic=topic, days=days, positive=positive, negative=negative, scanned=scanned)
