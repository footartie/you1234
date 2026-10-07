# you1234 · 유튜브 주제 반응 요약 (ytpulse)

주제를 입력하면 **최근 7일** 동안 올라온 유튜브 영상을 **조회수 순**으로 훑어서

- 📄 **여론 분석 리포트** (요약 + 6개 섹션, Markdown 다운로드)
- 👍 **긍정 반응 영상 5개** / 👎 **부정 반응 영상 5개**
- 각 영상 속 **인물의 주요 발언** (자막 기반, 타임스탬프 포함)
- 각 영상의 **주요 댓글 5개** (좋아요 순)

을 빠르게 보여주는 프로그램입니다. 웹 화면(Streamlit)과 터미널(CLI) 둘 다 지원합니다.

## 📄 여론 분석 리포트

조회수 상위 **N개 영상(기본 10개, 0~50 선택, 0이면 리포트 생략)** 을 모두 분석해 아래 순서로 정리합니다. 긍정/부정이 일찍 채워져도 N개는 끝까지 분석해서 비중 통계가 한쪽으로 쏠리지 않게 합니다.

| 섹션 | 내용 | 만드는 방법 (전부 무료) |
|---|---|---|
| **요약** (맨 위) | 한 줄 결론 + 핵심 포인트 | 아래 섹션의 숫자·키워드로 문장 구성 |
| 1) 주제 개요 · 정량 분석 | 위키백과 개요, 입장별 영상 수·비중·총 조회수·조회수 비중·총 댓글 수·평균 좋아요 + 막대그래프 | 코드로 직접 계산 |
| 2) 긍정·찬성 여론 및 논거 | 긍정 측이 반복 언급한 내용 + 공감 많은 실제 댓글/발언 | 댓글·발언마다 긍정/부정 판단 → 각 측에서 자주 나온 단어와 대표 문장 추출 |
| 3) 부정·반대 여론 및 논거 | 〃 | 〃 |
| 4) 중립·회의적 반응 | "글쎄", "지켜봐야" 같은 관망·혼합 의견, 중립 영상 | 회의 표현 사전 |
| 5) 핵심 쟁점 | 양측이 모두 거론한 단어별 긍정 vs 부정 대표 의견 비교표 | 양측 공통 키워드 |
| 6) 배경 맥락 · 관련 지식 | 최근 뉴스 헤드라인, 위키백과 배경, 뉴스 빈출 단어 | **무료 웹 검색** (아래) |

모든 논거·의견에는 근거가 된 **실제 댓글/발언과 영상 링크**가 붙습니다. AI가 쓴 글이 아니라 실제 데이터에서 뽑아낸 것이라 지어낸 내용은 없지만, 문장으로 매끄럽게 풀어 쓴 해설은 아닙니다.

### 무료 웹 검색 (6번 섹션)

| 출처 | 키 | 비용 | 용도 |
|---|---|---|---|
| Google 뉴스 RSS | 필요 없음 | 무료 | 최근 N일 뉴스 헤드라인 (기본) |
| 위키백과 API | 필요 없음 | 무료 | 주제 배경 지식 |
| 네이버 검색 API (선택) | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 무료, 하루 25,000회 | 한국 뉴스 품질 향상 (설정 시 Google 뉴스 대신 사용) |

네이버 키 발급: https://developers.naver.com → **Application → 애플리케이션 등록** → 사용 API에 **검색** 선택 → 환경은 **WEB 설정**(URL은 배포 주소) → 발급된 Client ID / Client Secret을 secrets에 추가.

어느 출처든 접속에 실패하면 그 부분만 비워두고 리포트는 정상적으로 만들어집니다.

## 💸 완전 무료로 쓰기

**필요한 건 무료 YouTube API 키 하나뿐입니다.** Anthropic 키가 없으면 자동으로 **무료 키워드 분석 모드**로 동작합니다.

| 구성 요소 | 비용 |
|---|---|
| YouTube Data API v3 | 무료 (하루 10,000 단위 ≈ 검색 60회 이상) |
| Streamlit Community Cloud 호스팅 | 무료 |
| 무료 키워드 분석 (기본) | 무료 – 외부 서비스 호출 없음 |
| Claude AI 분석 (선택) | 유료 – `ANTHROPIC_API_KEY`를 넣었을 때만 사용 |

**무료 키워드 분석은 이렇게 동작합니다.**
- 제목(가중치 3)·설명·자막·댓글(좋아요 많을수록 가중)에서 긍정어(최고, 추천, 감동…)와 부정어(최악, 논란, 실망…)를 세어 입장을 정합니다. "안 좋아요"처럼 부정된 긍정어는 부정으로 셉니다.
- 판단 근거에 실제로 잡힌 단어와 횟수를 보여줍니다.
- 주요 발언은 자막에서 주제어와 감정 단어가 가장 많이 나온 구간을 타임스탬프와 함께 뽑습니다. 화자 이름은 알 수 없어 "영상 속 화자"로 표시합니다.
- 반어법·비꼼은 구분하지 못하므로 Claude 모드보다 정확도가 낮습니다. 단어 목록은 `ytpulse/free_analyzer.py`의 `POSITIVE` / `NEGATIVE`에서 바로 고칠 수 있습니다.

### YouTube API 키 무료 발급

1. https://console.cloud.google.com 접속 → 새 프로젝트 만들기 (결제 정보 등록 불필요)
2. **API 및 서비스 → 라이브러리**에서 *YouTube Data API v3* 검색 → **사용**
3. **사용자 인증 정보 → 사용자 인증 정보 만들기 → API 키** → 생성된 키 복사
4. 키 설정에서 **API 제한사항**을 *YouTube Data API v3*로 제한 (권장)

## 동작 방식

1. **YouTube Data API v3**로 `publishedAfter = 지금-7일`, `order=viewCount` 검색 → 실제 조회수로 재정렬
2. 조회수 높은 영상부터 8개씩 병렬로
   - 인기 댓글 수집 (`commentThreads`, 좋아요 순 상위 5개)
   - 자막 수집 (`youtube-transcript-api`, 한국어 → 영어 순)
   - 입장(긍정/부정/중립)·요약·판단 근거·주요 발언 분석: 기본은 **무료 키워드 분석**, `ANTHROPIC_API_KEY`가 있으면 **Claude**가 제목·설명·자막·댓글을 읽고 판단
3. 긍정 5개·부정 5개가 다 채워지면 **즉시 중단** → 불필요한 API 호출 최소화

## 설치

```bash
pip install -r requirements.txt
cp .env.example .env   # 키 입력
```

| 환경변수 | 설명 |
|---|---|
| `YOUTUBE_API_KEY` | Google Cloud Console에서 *YouTube Data API v3* 사용 설정 후 발급한 API 키 |
| `ANTHROPIC_API_KEY` (선택, 유료) | 넣으면 Claude AI 분석 사용. 비워두면 무료 키워드 분석 |
| `CLAUDE_MODEL` (선택) | 기본값 `claude-opus-5-5` |
| `MAX_TRANSCRIPT_CHARS` (선택) | 영상당 Claude에 보내는 자막 최대 글자 수 (기본 40000, `0`이면 제한 없음) |

## 사용법

### 웹 화면

```bash
streamlit run app.py
```

주제를 입력하고 **리포트 분석 영상 수**(기본 10)를 고른 뒤 분석하면 **📄 분석 리포트** 탭과 **🎬 긍정/부정 영상** 탭이 나옵니다. **상세 설정**에서 기간·영상 수·댓글 수·지역/언어를 바꿀 수 있습니다. 긍정/부정이 좌우 두 칸으로 나뉘어 표시됩니다. 같은 검색은 1시간 동안 캐시됩니다.

### 터미널

```bash
python -m ytpulse "갤럭시 S26"
python -m ytpulse "금리 인하" --days 3 --per-side 3
python -m ytpulse "AI 규제" --region US --lang en --json > result.json
python -m ytpulse "갤럭시 S26" --free   # Anthropic 키가 있어도 무료 모드 강제
python -m ytpulse "갤럭시 S26" --report 30 > report.md   # 상위 30개로 리포트 (0이면 리포트 생략)
```

## 웹에 배포해서 공유하기 (주제만 입력하면 되는 버전)

API 키는 **서버 비밀값(secrets)** 으로만 저장되고 방문자 화면에는 절대 노출되지 않습니다. 방문자는 주제 입력란만 보게 됩니다.

### Streamlit Community Cloud (무료, 추천)

1. https://share.streamlit.io 에 GitHub 계정으로 로그인
2. **Create app** → 저장소 `footartie/you1234`, 브랜치 선택, Main file `app.py`
3. **Advanced settings → Secrets** 에 아래 내용 붙여넣기 (`.streamlit/secrets.toml.example` 참고)
   ```toml
   YOUTUBE_API_KEY = "AIza..."
   APP_PASSWORD = "원하는-비밀번호"   # 비워두면 누구나 사용 가능
   # ANTHROPIC_API_KEY = "sk-ant-..."  # 선택(유료). 없으면 무료 키워드 분석
   # NAVER_CLIENT_ID = "..."            # 선택(무료). 리포트 뉴스를 네이버에서 가져옴
   # NAVER_CLIENT_SECRET = "..."
   ```
4. **Deploy** → `https://<앱이름>.streamlit.app` 주소를 공유

키를 바꾸려면 앱 메뉴 **Settings → Secrets** 에서 수정하면 바로 반영됩니다.

### 보안 권장 사항

- 링크를 아는 사람은 누구나 내 YouTube 할당량(무료 모드여도 하루 한도가 있음)과, Claude 모드라면 Anthropic 요금을 쓸 수 있으므로 **`APP_PASSWORD` 설정을 권장**합니다.
- Google Cloud Console에서 YouTube API 키의 **API 제한**을 *YouTube Data API v3* 하나로 걸어두세요.
- Claude 모드를 쓴다면 Anthropic Console에서 월 사용 한도(spend limit)를 설정해 두면 안전합니다.
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
