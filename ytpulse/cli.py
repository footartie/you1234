"""Command-line entry point: python -m ytpulse "주제" """
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict

from dotenv import load_dotenv

from .free_analyzer import make_analyzer
from .models import TopicReport, Video
from .pipeline import build_report
from .youtube import YouTubeClient


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="최근 N일 유튜브 긍정/부정 반응 영상 요약")
    p.add_argument("topic", help="검색할 주제 (예: '아이폰 18')")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--per-side", type=int, default=5, help="긍정/부정 각각 표시할 영상 수")
    p.add_argument("--comments", type=int, default=5, help="영상별 주요 댓글 수")
    p.add_argument("--candidates", type=int, default=50, help="분석 후보 영상 최대 수")
    p.add_argument("--region", default="KR")
    p.add_argument("--lang", default="ko")
    p.add_argument("--json", action="store_true", help="JSON으로 출력")
    p.add_argument("--free", action="store_true", help="Anthropic 키가 있어도 무료 키워드 분석 사용")
    args = p.parse_args(argv)

    yt_key = os.environ.get("YOUTUBE_API_KEY")
    if not yt_key:
        print("YOUTUBE_API_KEY 환경변수(.env)가 필요합니다.", file=sys.stderr)
        return 2

    log = (lambda m: print(m, file=sys.stderr)) if not args.json else (lambda m: None)
    report = build_report(
        args.topic,
        YouTubeClient(yt_key, region=args.region, language=args.lang),
        make_analyzer(os.environ.get("ANTHROPIC_API_KEY", ""), free=args.free),
        days=args.days,
        per_side=args.per_side,
        comments_per_video=args.comments,
        max_candidates=args.candidates,
        progress=log,
    )

    if args.json:
        json.dump(_report_dict(report), sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print_report(report)
    return 0


def _report_dict(report: TopicReport) -> dict:
    def video(v: Video) -> dict:
        d = asdict(v)
        d.pop("transcript")
        d["url"] = v.url
        return d

    return {
        "topic": report.topic,
        "days": report.days,
        "scanned": report.scanned,
        "positive": [video(v) for v in report.positive],
        "negative": [video(v) for v in report.negative],
    }


def print_report(report: TopicReport) -> None:
    line = "=" * 72
    print(f"\n{line}\n'{report.topic}' - 최근 {report.days}일 유튜브 반응 ({report.scanned}개 영상 분석)\n{line}")
    for label, videos in (("👍 긍정 반응", report.positive), ("👎 부정 반응", report.negative)):
        print(f"\n## {label} (조회수 순, {len(videos)}개)\n")
        if not videos:
            print("  해당하는 영상을 찾지 못했습니다.\n")
        for i, v in enumerate(videos, 1):
            print(f"{i}. {v.title}")
            print(f"   {v.channel} | 조회수 {v.view_count:,} | 좋아요 {v.like_count:,} | {v.published_at[:10]}")
            print(f"   {v.url}")
            print(f"   요약: {v.summary}")
            print(f"   판단 근거: {v.reason}")
            if v.quotes:
                print("   🎙 주요 발언:")
                for q in v.quotes:
                    ts = f"[{q.timestamp}] " if q.timestamp else ""
                    print(f"     - {ts}{q.speaker}: \"{q.text}\"")
            else:
                print("   🎙 주요 발언: (자막 없음)")
            if v.comments:
                print("   💬 주요 댓글:")
                for c in v.comments:
                    text = c.text.replace("\n", " ")
                    if len(text) > 150:
                        text = text[:150] + "…"
                    print(f"     - (👍{c.like_count:,}) {text}")
            else:
                print("   💬 주요 댓글: (댓글 없음/비활성화)")
            print()


if __name__ == "__main__":
    sys.exit(main())
