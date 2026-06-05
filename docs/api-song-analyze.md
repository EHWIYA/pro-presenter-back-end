# POST /api/v1/song/analyze

찬양 악보·가사 구간 분석(BFF → `cursor-llm-gateway`). 응답은 **202** + `jobId`이며, 결과는 `GET /api/v1/song/jobs/{jobId}`로 폴링합니다.

## 요청 본문 (camelCase)

| 필드 | 필수 | 설명 |
|------|------|------|
| `songTitle` | 아니오 | 선매칭·게이트웨이 힌트. **신규 악보(이미지만)** 는 생략. 재분석·가사 경로에서는 전달 권장 |
| `imageBase64` + `imageMimeType` | 조건부 | 악보 이미지. `lyricsText`와 **둘 중 하나만** |
| `lyricsText` | 조건부 | 가사 텍스트. 이미지와 **둘 중 하나만** |
| `forceReanalyze` | 아니오 | `true`면 라이브러리 선매칭 스킵 (기본 `false`) |
| `saveToLibrary` | 아니오 | job 완료 시 DB upsert (기본 `true`) |
| `librarySongId` | 아니오 | 재분석·기존 곡 갱신 시 UUID |
| `clientRef` | 아니오 | 클라이언트 추적용 |

### 입력 규칙

- **정확히 하나**: `imageBase64`+`imageMimeType` **또는** `lyricsText`
- **422**: 제목만 / 이미지+가사 동시 / 이미지 쌍 불완전

### 신규 악보 (이미지만, 제목 없음)

```json
{
  "imageBase64": "<base64>",
  "imageMimeType": "image/jpeg",
  "saveToLibrary": true
}
```

- BFF: `songTitle` 없으면 **DB 제목 선매칭 스킵** → 게이트웨이 AI analyze (202)
- upstream: `songTitle` 필드 **생략** (빈 문자열 전달 안 함)
- job `finished` → `parsed.song_title` (또는 `songTitle`)로 프론트 검수·저장

### AI 재분석 (`forceReanalyze: true`)

```json
{
  "songTitle": "확정·편집 중 제목",
  "imageBase64": "...",
  "imageMimeType": "image/jpeg",
  "forceReanalyze": true,
  "saveToLibrary": false,
  "librarySongId": "<uuid>"
}
```

- 선매칭 스킵, `songTitle`은 upstream에 포함 (프론트 전송 유지)
- job 완료 시 **자동 DB 저장 안 함** (`saveToLibrary: false` 계약 유지)

### 가사만 analyze

```json
{
  "songTitle": "미등록곡",
  "lyricsText": "1절 가사\n2줄"
}
```

- `songTitle`이 있고 `forceReanalyze`가 아니면 DB **선매칭** (library hit / candidates) 가능

## 응답 분기

| 상황 | HTTP | 본문 |
|------|------|------|
| 게이트웨이 job 생성 | 202 | `jobId`, `status`, `pollUrl` (`/api/v1/song/jobs/{jobId}`) |
| 라이브러리 1건 일치 | 200 | `source: library`, `songId`, `category`, `sections` 등 |
| 라이브러리 다건 | 200 | `source: library_candidates`, `candidates` (각 `category` 포함) |

## 라이브러리 선매칭 (현재 BFF)

| 조건 | 동작 |
|------|------|
| `songTitle` 정규화 제목이 DB에 **1건** | `source: library` (AI 생략) |
| **2건 이상** | `source: library_candidates` |
| `songTitle` **없음** (이미지만) | 선매칭 **안 함** → 항상 job (202) |
| `forceReanalyze: true` | 선매칭 **안 함** → 항상 job |

- 매칭 키: `title_normalized` (공백·괄호·절 표기 등 정규화, `app/title_normalize.py`)
- **미구현**: OCR 제목·`hymnNumber`·이미지 해시·유사도 임계값 기반 이미지 선매칭
- library 히트 후 재분석: **`forceReanalyze: true`** (+ `librarySongId` 권장). 히트 응답만으로 job을 동시에 주는 옵션은 없음.

## job 폴링 · 라이브러리 저장

`GET /api/v1/song/jobs/{jobId}` — 게이트웨이 프록시. `status`가 `finished`/`completed`이고 `saveToLibrary`이면 `parsed`의 제목·sections로 DB upsert (`songId`, `libraryAction` 부가).

- 제목은 **analyze 요청이 아니라** `parsed.song_title` 기준 (검수 후 PUT sections·확정 제목은 별도 API)
- `librarySongId`가 있으면 해당 곡 **갱신**; 없으면 제목 1건 일치 시 갱신, 아니면 **신규 생성**
- `saveToLibrary: false` (재분석) → DB 저장 없음

## job `parsed` — 찬송가 메타 (게이트웨이·BFF 프록시)

프론트 타입 미연동 시 **필드 없으면 무시**. snake / camel 별칭 동일.

| 필드 | 설명 |
|------|------|
| `is_hymn` / `isHymn` | 찬송가 여부 |
| `hymn_book` / `hymnBook` | 예: 새찬송가 |
| `hymn_number` / `hymnNumber` | 1~645, 없으면 null |
| `hymn_confidence` / `hymnConfidence` | `high` / `medium` / `low` |
| `song_title` / `songTitle` | 곡명(N장) 형식 (서버 정규화) |

- **DB 영속화 계획 없음** — 검수 UI·수동 `category: hymn` 저장용. `suggested_category` 등 자동 장르 추론 필드는 미정.
- analyze library 응답·job 완료 시 **저장된 `category`는 DB 값** (`api-song-library.md`).

## 환경

`docs/ENV.md` — `LLM_GATEWAY_URL`, `LLM_GATEWAY_API_KEY`, `SONG_LIBRARY_AUTO_SAVE`, `DATABASE_URL`.
