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

- BFF: `songTitle` 없으면 **선매칭 스킵** → 게이트웨이 AI analyze (202)
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

### 가사만 analyze

```json
{
  "songTitle": "미등록곡",
  "lyricsText": "1절 가사\n2줄"
}
```

- `songTitle`이 있고 `forceReanalyze`가 아니면 DB **선매칭** (library hit / candidates) 가능

## 응답

| 상황 | HTTP | 본문 |
|------|------|------|
| 게이트웨이 job 생성 | 202 | `jobId`, `status`, `pollUrl` (`/api/v1/song/jobs/{jobId}`) |
| 라이브러리 1건 일치 | 200 | `source: library`, sections 등 |
| 라이브러리 다건 | 200 | `source: library_candidates`, `candidates` |

## job 폴링 · 라이브러리 저장

`GET /api/v1/song/jobs/{jobId}` — 게이트웨이 프록시. `status`가 `finished`/`completed`이고 `saveToLibrary`이면 `parsed`의 제목·sections로 DB upsert (`songId`, `libraryAction` 부가).

제목은 **analyze 요청이 아니라** `parsed.song_title` 기준(검수 후 PUT sections·확정 제목은 별도 API).

## 환경

`docs/ENV.md` — `LLM_GATEWAY_URL`, `LLM_GATEWAY_API_KEY`, `SONG_LIBRARY_AUTO_SAVE`, `DATABASE_URL`.
