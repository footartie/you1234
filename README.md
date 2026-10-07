# you1234 · 유튜브 주제 반응 요약 (ytpulse)

주제를 입력하면 **최근 7일** 동안 올라온 유튜브 영상을 **조회수 순**으로 훑어서

- 👍 **긍정 반응 영상 5개** / 👎 **부정 반응 영상 5개**
- 각 영상 속 **인물의 주요 발언** (자막 기반, 타임스탬프 포함)
- 각 영상의 **주요 댓글 5개** (좋아요 순)

을 빠르게 보여주는 프로그램입니다. 웹 화면(Streamlit)과 터미널(CLI) 둘 다 지원합니다.

## 동작 방식

1. **YouTube Data API v3**로 `publishedAfter = 지금-7일`, `order=viewCount` 검색 → 실제 조회수로 재정렬
2. 조회수 높은 영상부터 8개씩 병렬로
   - 인기 댓글 수집 (`commentThreads`, 좋아요 순 상위 5개)
   - 자막 수집 (`youtube-transcript-api`, 한국어 → 영어 순)
   - **Claude**가 제목·설명·자막·댓글을 보고 주제에 대한 입장(긍정/부정/중립), 요약, 판단 근거, 주요 발언(최대 3개)을 JSON으로 반환
3. 긍정 5개·부정 5개가 다 채워지면 **즉시 중단** → 불필요한 API 호출 최소화

## 설치

```bash
pip install -r requirements.txt
cp .env.example .env   # 키 입력
```

| 환경변수 | 설명 |
|---|---|
| `YOUTUBE_API_KEY` | Google Cloud Console에서 *YouTube Data API v3* 사용 설정 후 발급한 API 키 |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com 에서 발급 |
| `CLAUDE_MODEL` (선택) | 기본값 `claude-opus-5-5` |
| `MAX_TRANSCRIPT_CHARS` (선택) | 영상당 Claude에 보내는 자막 최대 글자 수 (기본 40000, `0`이면 제한 없음) |

## 사용법

### 웹 화면

```bash
streamlit run app.py
```

사이드바에서 기간, 영상 수, 댓글 수, 지역/언어를 조정할 수 있고, 긍정/부정이 좌우 두 칸으로 나뉘어 표시됩니다. 같은 검색은 1시간 동안 캐시됩니다.

### 터미널

```bash
python -m ytpulse "갤럭시 S26"
python -m ytpulse "금리 인하" --days 3 --per-side 3
python -m ytpulse "AI 규제" --region US --lang en --json > result.json
```

## 참고 / 제약

- **YouTube API 할당량**: 기본 하루 10,000 단위. 검색 1페이지(50개)=100단위, 영상/댓글 조회=1단위씩이라 검색 1회에 약 110~160단위를 씁니다.
- **자막이 없는 영상**은 발언 추출을 하지 않고(지어내지 않음) 제목·설명·댓글로만 입장을 판단합니다. 클라우드 서버 IP에서는 유튜브가 자막 요청을 막는 경우가 있어, 로컬 PC에서 실행하는 것이 가장 안정적입니다.
- 긍정/부정 영상이 후보(기본 50개) 안에서 5개가 안 나오면 찾은 만큼만 보여줍니다. `--candidates`(최대 100 권장)로 늘릴 수 있습니다.
- 안전 분류기가 분석을 거절하면 서버 측 fallback(`fallbacks: "default"`)으로 다른 모델이 재시도합니다.

## 테스트

```bash
python -m pytest -q
```
