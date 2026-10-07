"""Streamlit UI: streamlit run app.py"""
from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from ytpulse import Analyzer, Video, YouTubeClient, build_report

load_dotenv()
st.set_page_config(page_title="YouTube 반응 요약", page_icon="📺", layout="wide")
st.title("📺 유튜브 주제 반응 한눈에 보기")
st.caption("최근 일주일 동안 조회수 높은 순으로 긍정/부정 영상, 영상 속 주요 발언, 인기 댓글을 보여줍니다.")

with st.sidebar:
    yt_key = st.text_input("YouTube API Key", value=os.environ.get("YOUTUBE_API_KEY", ""), type="password")
    claude_key = st.text_input("Anthropic API Key", value=os.environ.get("ANTHROPIC_API_KEY", ""), type="password")
    days = st.slider("기간(일)", 1, 30, 7)
    per_side = st.slider("긍정/부정 각 영상 수", 1, 10, 5)
    n_comments = st.slider("영상별 댓글 수", 1, 10, 5)
    candidates = st.slider("분석 후보 영상 최대 수", 10, 100, 50, step=10)
    region = st.text_input("지역 코드", "KR")
    lang = st.text_input("언어 코드", "ko")

with st.form("search"):
    topic = st.text_input("주제", placeholder="예: 갤럭시 S26, 금리 인하, 신작 드라마 …")
    submitted = st.form_submit_button("분석하기", type="primary")


@st.cache_data(ttl=3600, show_spinner=False)
def run(topic, days, per_side, n_comments, candidates, region, lang, yt_key, claude_key):
    status = st.status("분석 중...", expanded=True)
    report = build_report(
        topic,
        YouTubeClient(yt_key, region=region, language=lang),
        Analyzer(api_key=claude_key or None),
        days=days,
        per_side=per_side,
        comments_per_video=n_comments,
        max_candidates=candidates,
        progress=status.write,
    )
    status.update(label=f"완료 - {report.scanned}개 영상 분석", state="complete", expanded=False)
    return report


def render(v: Video, rank: int) -> None:
    with st.container(border=True):
        cols = st.columns([1, 3])
        if v.thumbnail_url:
            cols[0].image(v.thumbnail_url)
        cols[1].markdown(f"**{rank}. [{v.title}]({v.url})**")
        cols[1].caption(
            f"{v.channel} · 조회수 {v.view_count:,} · 좋아요 {v.like_count:,} · {v.published_at[:10]}"
        )
        st.write(v.summary)
        st.caption(f"판단 근거: {v.reason}")
        with st.expander("🎙 영상 속 주요 발언", expanded=True):
            if not v.quotes:
                st.caption("자막이 없어 발언을 추출하지 못했습니다.")
            for q in v.quotes:
                ts = f"`{q.timestamp}` " if q.timestamp else ""
                st.markdown(f"{ts}**{q.speaker}**: “{q.text}”")
        with st.expander(f"💬 주요 댓글 {len(v.comments)}개"):
            if not v.comments:
                st.caption("댓글이 없거나 비활성화되어 있습니다.")
            for c in v.comments:
                st.markdown(f"👍 {c.like_count:,} · **{c.author}**  \n{c.text}")


if submitted and topic.strip():
    if not yt_key:
        st.error("YouTube API Key를 입력하세요.")
        st.stop()
    report = run(topic.strip(), days, per_side, n_comments, candidates, region, lang, yt_key, claude_key)
    left, right = st.columns(2)
    for col, label, videos in ((left, "👍 긍정 반응", report.positive), (right, "👎 부정 반응", report.negative)):
        with col:
            st.subheader(f"{label} ({len(videos)})")
            if not videos:
                st.info("해당하는 영상을 찾지 못했습니다.")
            for i, v in enumerate(videos, 1):
                render(v, i)
