from ytpulse import FreeAnalyzer, build_opinion_report, to_markdown
from ytpulse.models import Comment, Video
from ytpulse.report import sections, tokenize
from ytpulse.websearch import Background, NewsItem


def V(i, title, views, comments, transcript=""):
    return Video(f"id{i}", title, f"채널{i}", "2026-10-05", f"{title} 설명", views, views // 50, len(comments) * 10,
                 transcript=transcript, comments=[Comment("u", c, likes, "") for c, likes in comments])


def sample():
    vs = [
        V(1, "갤럭시 S26 카메라 역대급! 최고의 폰", 900_000,
          [("카메라 화질 진짜 최고네요 추천", 1200), ("배터리도 만족스러워요", 300)]),
        V(2, "갤럭시 S26 가격 논란… 실망입니다", 700_000,
          [("가격 실망 최악", 2000), ("발열 문제점 심각하네요 실망", 800)]),
        V(3, "갤럭시 S26 출시일 스펙 정리", 500_000, [("글쎄요 지켜봐야 알 듯", 120)]),
        V(4, "S26 발열 결함 의혹 정리", 300_000, [("발열 때문에 환불했어요 최악", 600), ("가격 대비 별로", 200)]),
        V(5, "S26 한달 사용기 강추", 200_000, [("배터리 좋고 카메라 최고", 150), ("발열은 좀 있지만 만족", 90)]),
    ]
    a = FreeAnalyzer()
    for v in vs:
        a.analyze("갤럭시 S26", v)
    return vs


def test_tokenize_strips_particles_and_sentiment_words():
    assert tokenize("카메라가 최고이고 배터리는 좋아요") == ["카메라", "배터리"]
    assert "가격" in tokenize("가격이 너무 비싸요")


def test_report_numbers_and_sections():
    news = [NewsItem("S26 가격 인상 논란", "한겨레", "https://n/2", "2026-10-05")]
    bg = Background("삼성 갤럭시 S 시리즈", "삼성전자의 플래그십 스마트폰이다. 2010년 출시.", "https://w")
    r = build_opinion_report("갤럭시 S26", 7, sample(), news, "Google 뉴스", bg)

    stats = {s.stance: s for s in r.stats}
    assert (stats["positive"].count, stats["negative"].count, stats["neutral"].count) == (2, 2, 1)
    assert stats["positive"].views == 1_100_000
    assert abs(sum(s.view_share for s in r.stats) - 1) < 1e-9
    assert stats["negative"].comments == 40

    assert [a.keyword for a in r.arguments["positive"]][:2] == ["카메라", "배터리"]
    assert {a.keyword for a in r.arguments["negative"]} >= {"가격", "발열"}
    assert r.arguments["negative"][0].evidence.likes == 2000  # most-liked real comment
    assert [i.keyword for i in r.issues] == ["발열"]
    assert any("지켜봐야" in e.text for e in r.voices["skeptical"])

    heads = [h for h, _ in sections(r)]
    assert heads[0] == "요약" and heads[1].startswith("1)") and heads[-1].startswith("6)")
    md = to_markdown(r)
    assert "S26 가격 인상 논란" in md and "위키백과" in md and "| 긍정 | 2 | 40% |" in md


def test_report_handles_no_videos_and_no_context():
    r = build_opinion_report("없는주제", 7, [])
    assert r.n_videos == 0 and "찾지 못했습니다" in r.summary[0]
    md = to_markdown(r)
    assert "가져오지 못했습니다" in md
