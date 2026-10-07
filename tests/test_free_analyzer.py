from ytpulse import Analyzer, FreeAnalyzer, make_analyzer
from ytpulse.models import Comment, Video


def video(title, desc="", transcript="", comments=()):
    return Video("id", title, "ch", "2026-10-05", desc, 100, 0, 0, transcript=transcript, comments=list(comments))


def test_positive_and_negative_titles():
    a = FreeAnalyzer()
    assert a.analyze("폰", video("갤럭시 실사용 후기, 역대급 최고의 폰 강추")).sentiment == "positive"
    assert a.analyze("폰", video("갤럭시 결함 논란… 최악의 실망")).sentiment == "negative"
    assert a.analyze("폰", video("갤럭시 출시일 정리")).sentiment == "neutral"


def test_negated_positive_counts_as_negative():
    v = FreeAnalyzer().analyze("폰", video("이 폰 솔직히 안 좋아요", comments=[Comment("a", "좋지 않네요 비추", 50, "")]))
    assert v.sentiment == "negative"
    assert "부정어+긍정어" in v.reason


def test_quotes_pick_topic_passages_with_timestamps():
    transcript = "\n".join([
        "[00:01] 안녕하세요 여러분",
        "[00:03] 오늘 날씨가 맑네요",
        "[00:05] 그럼 시작해 보겠습니다",
        "[01:10] 이번 갤럭시는 카메라가",
        "[01:12] 정말 최고라고 생각합니다",
        "[01:15] 강력하게 추천드려요",
    ])
    v = FreeAnalyzer().analyze("갤럭시", video("리뷰", transcript=transcript))
    assert v.quotes[0].timestamp == "01:10"
    assert "최고" in v.quotes[0].text
    assert FreeAnalyzer().analyze("갤럭시", video("리뷰")).quotes == []


def test_make_analyzer_selects_mode():
    assert isinstance(make_analyzer(""), FreeAnalyzer)
    assert isinstance(make_analyzer("sk-ant-x", free=True), FreeAnalyzer)
    assert isinstance(make_analyzer("sk-ant-x"), Analyzer)
