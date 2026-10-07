import streamlit as st
from streamlit.testing.v1 import AppTest

import ytpulse
from ytpulse.models import TopicReport, Video


def _app(monkeypatch, **env):
    for k in ("YOUTUBE_API_KEY", "ANTHROPIC_API_KEY", "APP_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    st.cache_data.clear()  # results are cached per topic across tests
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return AppTest.from_file("../app.py", default_timeout=30)


def test_missing_keys_shows_admin_error(monkeypatch):
    at = _app(monkeypatch).run()
    assert "API 키가 설정되지 않았습니다" in at.error[0].value
    assert not at.text_input  # no key inputs exposed to visitors


def test_password_gate(monkeypatch):
    at = _app(monkeypatch, YOUTUBE_API_KEY="y", ANTHROPIC_API_KEY="a", APP_PASSWORD="pw").run()
    assert at.text_input[0].label == "접속 비밀번호"
    at.text_input[0].input("wrong")
    at.button[0].click().run()
    assert "비밀번호가 틀렸습니다" in at.error[0].value
    at.text_input[0].input("pw")
    at.button[0].click().run()
    assert at.text_input[0].label == "주제"


def test_topic_search_renders_report_and_videos(monkeypatch):
    from ytpulse import build_opinion_report

    v = Video("id1", "좋은 영상", "ch", "2026-10-05T00:00:00Z", "", 1234, 5, 1, sentiment="positive", summary="요약")
    calls = {}

    def fake_report(topic, yt, analyzer, **kw):
        calls["report_size"] = kw["report_size"]
        return TopicReport(topic, 7, [v], [], 3, analyzed=[v])

    def fake_full(report, size, *a):
        return build_opinion_report(report.topic, report.days, report.analyzed[:size])

    monkeypatch.setattr(ytpulse, "build_report", fake_report)
    monkeypatch.setattr(ytpulse, "build_full_report", fake_full)
    at = _app(monkeypatch, YOUTUBE_API_KEY="y", ANTHROPIC_API_KEY="a").run()
    assert [t.label for t in at.text_input][0] == "주제"
    assert all("Key" not in t.label for t in at.text_input)
    at.text_input[0].input("갤럭시")
    at.button[0].click().run()
    assert not at.exception
    assert calls["report_size"] == 10  # default
    assert [t.label for t in at.tabs] == ["📄 분석 리포트", "🎬 긍정/부정 영상"]
    md = " ".join(m.value for m in at.markdown)
    for heading in ("요약", "1) 주제 개요", "2) 긍정", "3) 부정", "4) 중립", "5) 핵심 쟁점", "6) 여론 배경"):
        assert heading in md
    assert "좋은 영상" in md
    assert "해당하는 영상을 찾지 못했습니다" in at.info[0].value


def test_report_size_zero_shows_only_videos(monkeypatch):
    def fake_report(topic, yt, analyzer, **kw):
        return TopicReport(topic, 7, [], [], 0)

    def fail(*a, **k):
        raise AssertionError("report should not be built")

    monkeypatch.setattr(ytpulse, "build_report", fake_report)
    monkeypatch.setattr(ytpulse, "build_full_report", fail)
    at = _app(monkeypatch, YOUTUBE_API_KEY="y").run()
    at.text_input[0].input("갤럭시")
    at.slider[0].set_value(0)
    at.button[0].click().run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["🎬 긍정/부정 영상"]


def test_free_mode_without_anthropic_key(monkeypatch):
    seen = {}

    def fake_report(topic, yt, analyzer, **kw):
        seen["analyzer"] = analyzer
        return TopicReport(topic, 7, [], [], 0)

    monkeypatch.setattr(ytpulse, "build_report", fake_report)
    monkeypatch.setattr(ytpulse, "build_full_report", lambda *a: None)
    at = _app(monkeypatch, YOUTUBE_API_KEY="y").run()
    assert not at.error
    assert any("무료 키워드 분석" in c.value for c in at.caption)
    at.text_input[0].input("갤럭시")
    at.button[0].click().run()
    assert isinstance(seen["analyzer"], ytpulse.FreeAnalyzer)
