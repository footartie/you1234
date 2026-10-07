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

주제만 입력하면 되고, **상세 설정**에서 기간·영상 수·댓글 수·지역/언어를 바꿀 수 있습니다. 긍정/부정이 좌우 두 칸으로 나뉘어 표시됩니다. 같은 검색은 1시간 동안 캐시됩니다.

### 터미널

```bash
python -m ytpulse "갤럭시 S26"
python -m ytpulse "금리 인하" --days 3 --per-side 3
python -m ytpulse "AI 규제" --region US --lang en --json > result.json
```

## 웹에 배포해서 공유하기 (주제만 입력하면 되는 버전)

API 키는 **서버 비밀값(secrets)** 으로만 저장되고 방문자 화면에는 절대 노출되지 않습니다. 방문자는 주제 입력란만 보게 됩니다.

### Streamlit Community Cloud (무료, 추천)

1. https://share.streamlit.io 에 GitHub 계정으로 로그인
2. **Create app** → 저장소 `footartie/you1234`, 브랜치 선택, Main file `app.py`
3. **Advanced settings → Secrets** 에 아래 내용 붙여넣기 (`.streamlit/secrets.toml.example` 참고)
   ```toml
   YOUTUBE_API_KEY = "AIza..."
   ANTHROPIC_API_KEY = "sk-ant-..."
   APP_PASSWORD = "원하는-비밀번호"   # 비워두면 누구나 사용 가능
   ```
4. **Deploy** → `https://<앱이름>.streamlit.app` 주소를 공유

키를 바꾸려면 앱 메뉴 **Settings → Secrets** 에서 수정하면 바로 반영됩니다.

### 보안 권장 사항

- 링크를 아는 사람은 누구나 내 YouTube 할당량과 Anthropic 요금을 쓸 수 있으므로 **`APP_PASSWORD` 설정을 권장**합니다.
- Google Cloud Console에서 YouTube API 키의 **API 제한**을 *YouTube Data API v3* 하나로 걸어두세요.
- Anthropic Console에서 월 사용 한도(spend limit)를 설정해 두면 안전합니다.
- 같은 주제·설정의 검색 결과는 1시간 캐시되어 반복 검색 시 API를 다시 쓰지 않습니다.

### 로컬에서 같은 방식으로 실행

`.streamlit/secrets.toml.example`을 `.streamlit/secrets.toml`로 복사해 키를 넣거나 `.env`를 쓰면 됩니다. (`secrets.toml`과 `.env`는 git에 올라가지 않습니다.)

## 참고 / 제약

- **YouTube API 할당량**: 기본 하루 10,000 단위. 검색 1페이지(50개)=100단위, 영상/댓글 조회=1단위씩이라 검색 1회에 약 110~160단위를 씁니다.
- **자막이 없는 영상**은 발언 추출을 하지 않고(지어내지 않음) 제목·설명·댓글로만 입장을 판단합니다. 클라우드 서버 IP에서는 유튜브가 자막 요청을 막는 경우가 있습니다(Streamlit Cloud 포함). 이 경우에도 입장 분류와 댓글은 정상 동작하며, 발언 추출이 꼭 필요하면 로컬 PC에서 실행하세요.
- 긍정/부정 영상이 후보(기본 50개) 안에서 5개가 안 나오면 찾은 만큼만 보여줍니다. `--candidates`(최대 100 권장)로 늘릴 수 있습니다.
- 안전 분류기가 분석을 거절하면 서버 측 fallback(`fallbacks: "default"`)으로 다른 모델이 재시도합니다.

## 테스트

```bash
python -m pytest -q
```
