"""Streamlit UI: streamlit run app.py"""
from __future__ import annotations

import hmac
import os

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ytpulse import OpinionReport, Video, YouTubeClient, build_full_report, build_report, make_analyzer
from ytpulse.report import sections, to_markdown

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
# Optional, free (25,000 calls/day): better Korean news for report section 6.
NAVER_CLIENT_ID = secret("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = secret("NAVER_CLIENT_SECRET")

st.set_page_config(page_title="YouTube 반응 요약", page_icon="📺", layout="wide")
st.title("📺 유튜브 주제 반응 한눈에 보기")
st.caption("주제만 입력하면 최근 일주일 유튜브 여론을 분석 리포트로 정리하고, 조회수 높은 긍정/부정 영상·주요 발언·인기 댓글을 보여줍니다.")

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
    report_size = st.slider(
        "리포트 분석 영상 수 (조회수 상위)", 0, 50, 10,
        help="많을수록 여론 비중이 정확해지지만 시간이 더 걸립니다. 0이면 리포트 없이 영상 목록만 보여줍니다.",
    )
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
def run(topic, days, per_side, n_comments, candidates, region, lang, report_size):
    status = st.status("분석 중...", expanded=True)
    report = build_report(
        topic,
        YouTubeClient(YOUTUBE_API_KEY, region=region, language=lang),
        make_analyzer(ANTHROPIC_API_KEY),
        days=days,
        per_side=per_side,
        comments_per_video=n_comments,
        max_candidates=candidates,
        report_size=report_size,
        progress=status.write,
    )
    opinion = None
    if report_size:
        status.write("뉴스·배경 정보 검색 및 리포트 작성 중...")
        opinion = build_full_report(report, report_size, lang, region, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET)
    status.update(label=f"완료 - {report.scanned}개 영상 분석", state="complete", expanded=False)
    return report, opinion


# Polarity encoding: blue = positive, red = negative, gray = neutral midpoint.
STANCE_COLORS = {"긍정": "#2a78d6", "부정": "#e34948", "중립": "#8f8d88"}


def share_chart(op: OpinionReport):
    total_comments = sum(s.comments for s in op.stats) or 1
    rows = []
    for s in op.stats:
        rows += [
            {"지표": "영상 수", "입장": s.label, "비중": s.share, "값": f"{s.count}개"},
            {"지표": "조회수", "입장": s.label, "비중": s.view_share, "값": f"{s.views:,}회"},
            {"지표": "댓글 수", "입장": s.label, "비중": s.comments / total_comments, "값": f"{s.comments:,}개"},
        ]
    order = list(STANCE_COLORS)
    df = pd.DataFrame(rows)
    df["sort"] = df["입장"].map(order.index)  # stack 긍정 | 부정 | 중립 left to right
    base = alt.Chart(df).encode(
        y=alt.Y("지표:N", sort=["영상 수", "조회수", "댓글 수"], title=None),
        x=alt.X("비중:Q", stack="normalize", axis=alt.Axis(format="%", grid=False, tickCount=5), title=None),
        order=alt.Order("sort:Q"),
    )
    bars = base.mark_bar(size=28, cornerRadius=4).encode(
        color=alt.Color("입장:N", scale=alt.Scale(domain=order, range=list(STANCE_COLORS.values())),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=["지표", "입장", alt.Tooltip("비중:Q", format=".0%"), "값"],
    )
    labels = base.mark_text(color="white", fontWeight="bold").encode(
        x=alt.X("비중:Q", stack="normalize", bandPosition=0.5),
        text=alt.Text("비중:Q", format=".0%"),
    ).transform_filter(alt.datum["비중"] >= 0.08)
    return (bars + labels).properties(height=alt.Step(44))


def render_opinion(op: OpinionReport) -> None:
    parts = sections(op)
    st.subheader(f"📄 「{op.topic}」 유튜브 여론 분석 리포트")
    st.caption(f"최근 {op.days}일 · 조회수 상위 {op.n_videos}개 영상 · 무료 키워드 분석 (AI 요약 아님)")
    (h, body), rest = parts[0], parts[1:]
    with st.container(border=True):
        st.markdown(f"#### {h}\n{body}")
    h, body = rest[0]
    st.markdown(f"### {h}")
    if op.n_videos:
        st.altair_chart(share_chart(op), use_container_width=True)
    st.markdown(body)
    for h, body in rest[1:]:
        st.markdown(f"### {h}")
        st.markdown(body)
    st.download_button("📥 리포트 다운로드 (.md)", to_markdown(op), file_name=f"{op.topic}_여론리포트.md",
                       mime="text/markdown")


def render(v: Video, rank: int, n_comments: int) -> None:
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
        comments = v.comments[:n_comments]
        with st.expander(f"💬 주요 댓글 {len(comments)}개"):
            if not comments:
                st.caption("댓글이 없거나 비활성화되어 있습니다.")
            for c in comments:
                st.markdown(f"👍 {c.like_count:,} · **{c.author}**  \n{c.text}")


if submitted and topic.strip():
    try:
        report, opinion = run(topic.strip(), days, per_side, n_comments, candidates, region.strip(),
                              lang.strip(), report_size)
    except Exception as e:
        st.error(f"분석 중 오류가 발생했습니다: {e}  \n(YouTube API 하루 할당량 초과일 수 있습니다. 내일 다시 시도해 보세요.)")
        st.stop()
    tab_names = (["📄 분석 리포트"] if opinion else []) + ["🎬 긍정/부정 영상"]
    tabs = st.tabs(tab_names)
    if opinion:
        with tabs[0]:
            render_opinion(opinion)
    with tabs[-1]:
        left, right = st.columns(2)
        for col, label, videos in ((left, "👍 긍정 반응", report.positive), (right, "👎 부정 반응", report.negative)):
            with col:
                st.subheader(f"{label} ({len(videos)})")
                if not videos:
                    st.info("해당하는 영상을 찾지 못했습니다.")
                for i, v in enumerate(videos, 1):
                    render(v, i, n_comments)
