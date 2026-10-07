from streamlit.testing.v1 import AppTest

import ytpulse
from ytpulse.models import TopicReport, Video


def _app(monkeypatch, **env):
    for k in ("YOUTUBE_API_KEY", "ANTHROPIC_API_KEY", "APP_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
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


def test_topic_search_renders_both_sides(monkeypatch):
    def fake_report(topic, yt, analyzer, **kw):
        v = Video("id1", "좋은 영상", "ch", "2026-10-05T00:00:00Z", "", 1234, 5, 1, sentiment="positive", summary="요약")
        return TopicReport(topic, 7, [v], [], 3)

    monkeypatch.setattr(ytpulse, "build_report", fake_report)
    at = _app(monkeypatch, YOUTUBE_API_KEY="y", ANTHROPIC_API_KEY="a").run()
    assert [t.label for t in at.text_input][0] == "주제"
    assert all("Key" not in t.label for t in at.text_input)
    at.text_input[0].input("갤럭시")
    at.button[0].click().run()
    md = " ".join(m.value for m in at.markdown)
    assert "좋은 영상" in md
    assert "해당하는 영상을 찾지 못했습니다" in at.info[0].value
