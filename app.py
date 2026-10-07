"""Streamlit UI: streamlit run app.py"""
from __future__ import annotations

import hmac
import os

import streamlit as st
from dotenv import load_dotenv

from ytpulse import Video, YouTubeClient, build_report, make_analyzer

load_dotenv()


def secret(name: str) -> str:
    """Read a key from Streamlit secrets (deployment) or the environment / .env (local).
    Keys stay on the server and are never sent to the visitor's browser."""
    try:
        value = st.secrets.get(name)
    except Exception:  # no secrets.toml configured
        value = None
    return str(value or os.environ.get(name, ""))


YOUTUBE_API_KEY = secret("YOUTUBE_API_KEY")
ANTHROPIC_API_KEY = secret("ANTHROPIC_API_KEY")
APP_PASSWORD = secret("APP_PASSWORD")

st.set_page_config(page_title="YouTube 반응 요약", page_icon="📺", layout="wide")
st.title("📺 유튜브 주제 반응 한눈에 보기")
st.caption("주제만 입력하면 최근 일주일 동안 조회수 높은 순으로 긍정/부정 영상, 영상 속 주요 발언, 인기 댓글을 보여줍니다.")

if not YOUTUBE_API_KEY:
    st.error(
        "서버에 YouTube API 키가 설정되지 않았습니다. 관리자는 YOUTUBE_API_KEY를 "
        "Streamlit secrets(또는 .env)에 등록하세요."
    )
    st.stop()

# Optional shared password so only people you send it to can spend your API quota.
if APP_PASSWORD and not st.session_state.get("authed"):
    with st.form("login"):
        pw = st.text_input("접속 비밀번호", type="password")
        if st.form_submit_button("입장"):
            if hmac.compare_digest(pw, APP_PASSWORD):
                st.session_state["authed"] = True
                st.rerun()
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

with st.form("search"):
    topic = st.text_input("주제", placeholder="예: 갤럭시 S26, 금리 인하, 신작 드라마 …")
    with st.expander("상세 설정"):
        c1, c2 = st.columns(2)
        days = c1.slider("기간(일)", 1, 30, 7)
        per_side = c2.slider("긍정/부정 각 영상 수", 1, 10, 5)
        n_comments = c1.slider("영상별 댓글 수", 1, 10, 5)
        candidates = c2.slider("분석 후보 영상 최대 수", 10, 100, 50, step=10)
        region = c1.text_input("지역 코드", "KR")
        lang = c2.text_input("언어 코드", "ko")
    submitted = st.form_submit_button("분석하기", type="primary")
st.caption(
    "분석 방식: Claude AI" if ANTHROPIC_API_KEY
    else "분석 방식: 무료 키워드 분석 (긍정/부정 단어 빈도로 판단, 비용 없음)"
)


@st.cache_data(ttl=3600, show_spinner=False)
def run(topic, days, per_side, n_comments, candidates, region, lang):
    status = st.status("분석 중...", expanded=True)
    report = build_report(
        topic,
        YouTubeClient(YOUTUBE_API_KEY, region=region, language=lang),
        make_analyzer(ANTHROPIC_API_KEY),
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
    try:
        report = run(topic.strip(), days, per_side, n_comments, candidates, region.strip(), lang.strip())
    except Exception as e:
        st.error(f"분석 중 오류가 발생했습니다: {e}  \n(YouTube API 하루 할당량 초과일 수 있습니다. 내일 다시 시도해 보세요.)")
        st.stop()
    left, right = st.columns(2)
    for col, label, videos in ((left, "👍 긍정 반응", report.positive), (right, "👎 부정 반응", report.negative)):
        with col:
            st.subheader(f"{label} ({len(videos)})")
            if not videos:
                st.info("해당하는 영상을 찾지 못했습니다.")
            for i, v in enumerate(videos, 1):
                render(v, i)
