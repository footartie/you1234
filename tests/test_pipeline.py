from types import SimpleNamespace

from ytpulse.analyzer import Analyzer, _build_prompt
from ytpulse.models import Comment, Video
from ytpulse.pipeline import build_report


def make_video(i, views):
    return Video(
        video_id=f"v{i}", title=f"t{i}", channel="c", published_at="2026-10-01T00:00:00Z",
        description="", view_count=views, like_count=0, comment_count=0,
    )


class FakeYouTube:
    def __init__(self, videos):
        self.videos = videos
        self.comment_calls = 0

    def search_recent(self, topic, days, max_results):
        return sorted(self.videos, key=lambda v: v.view_count, reverse=True)[:max_results]

    def top_comments(self, video_id, n):
        self.comment_calls += 1
        return [Comment("a", f"{video_id}-c{k}", 10 - k, "") for k in range(n)]

    def transcript(self, video_id):
        return "[00:01] hello"


class FakeAnalyzer:
    def __init__(self, labels):
        self.labels = labels  # video_id -> sentiment

    def analyze(self, topic, v):
        if self.labels[v.video_id] == "boom":
            raise RuntimeError("bad json")
        v.sentiment = self.labels[v.video_id]
        return v


def test_picks_top_by_views_and_stops_early():
    videos = [make_video(i, views=1000 - i) for i in range(40)]
    labels = {v.video_id: ("positive" if i % 2 else "negative") for i, v in enumerate(videos)}
    labels["v0"] = "neutral"
    labels["v1"] = "boom"
    yt = FakeYouTube(videos)

    report = build_report("x", yt, FakeAnalyzer(labels), per_side=5, batch_size=4)

    assert [v.video_id for v in report.positive] == ["v3", "v5", "v7", "v9", "v11"]
    assert [v.video_id for v in report.negative] == ["v2", "v4", "v6", "v8", "v10"]
    # Stopped after the batch that filled both sides (12 videos), not all 40.
    assert report.scanned == 12
    assert yt.comment_calls == 12
    assert len(report.positive[0].comments) == 5


def test_fewer_than_requested():
    videos = [make_video(i, 100) for i in range(3)]
    labels = {"v0": "positive", "v1": "neutral", "v2": "positive"}
    report = build_report("x", FakeYouTube(videos), FakeAnalyzer(labels))
    assert len(report.positive) == 2 and report.negative == []


def test_analyzer_parses_structured_output():
    payload = (
        '{"sentiment":"negative","confidence":0.8,"summary":"s","reason":"r",'
        '"quotes":[{"speaker":"기자","text":"q","timestamp":"01:02"}]}'
    )
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=payload)],
        )

    a = Analyzer(api_key="test")
    a._client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    v = a.analyze("topic", make_video(1, 5))

    assert v.sentiment == "negative" and v.quotes[0].timestamp == "01:02"
    assert captured["fallbacks"] == "default"
    assert captured["output_config"]["format"]["type"] == "json_schema"


def test_prompt_includes_transcript_and_comments():
    v = make_video(1, 5)
    v.transcript = "[00:05] 안녕하세요"
    v.comments = [Comment("a", "좋아요", 3, "")]
    prompt = _build_prompt("주제", v)
    assert "[00:05] 안녕하세요" in prompt and "좋아요" in prompt and "<topic>주제</topic>" in prompt


def test_errors_reported_from_main_thread_only():
    import threading

    videos = [make_video(i, 100 - i) for i in range(4)]
    labels = {"v0": "boom", "v1": "positive", "v2": "boom", "v3": "negative"}
    calls = []
    report = build_report(
        "x", FakeYouTube(videos), FakeAnalyzer(labels),
        progress=lambda m: calls.append((threading.current_thread() is threading.main_thread(), m)),
    )
    assert all(on_main for on_main, _ in calls)
    assert sum("건너뜀" in m for _, m in calls) == 2
    assert len(report.positive) == 1 and len(report.negative) == 1


def test_youtube_client_uses_one_api_client_per_thread(monkeypatch):
    import threading

    import ytpulse.youtube as yt_mod

    monkeypatch.setattr(yt_mod, "build", lambda *a, **k: object())
    client = yt_mod.YouTubeClient("key")
    seen = {}

    def grab(name):
        seen[name] = (client._yt, client._yt)

    threads = [threading.Thread(target=grab, args=(n,)) for n in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert seen["a"][0] is seen["a"][1]  # reused within a thread
    assert seen["a"][0] is not seen["b"][0]  # never shared across threads


def test_report_size_keeps_analyzing_past_early_stop():
    videos = [make_video(i, 1000 - i) for i in range(30)]
    labels = {v.video_id: ("positive" if i % 2 else "negative") for i, v in enumerate(videos)}
    yt = FakeYouTube(videos)
    report = build_report("x", yt, FakeAnalyzer(labels), per_side=2, batch_size=4, report_size=10)
    # Both sides fill after 4 videos, but the top 10 must all be analyzed for the report.
    assert report.scanned == 12
    assert [v.video_id for v in report.analyzed[:10]] == [f"v{i}" for i in range(10)]
    assert len(report.analyzed[0].comments) == 20  # report gets more comments than the cards


def test_report_size_beyond_candidates_widens_search():
    videos = [make_video(i, 100 - i) for i in range(40)]
    labels = {v.video_id: "neutral" for v in videos}
    report = build_report("x", FakeYouTube(videos), FakeAnalyzer(labels), max_candidates=10, report_size=30)
    assert report.scanned == 30  # search widened from 10 to the 30 the report needs
