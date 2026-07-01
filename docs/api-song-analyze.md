# POST /api/v1/song/analyze

찬양 악보·가사 구간 분석(BFF → `cursor-llm-gateway`). 응답은 **202** + `jobId`이며, 결과는 `GET /api/v1/song/jobs/{jobId}`로 폴링합니다.

## 요청 본문 (camelCase)

| 필드 | 필수 | 설명 |
|------|------|------|
| `songTitle` | 아니오 | catalog 선매칭·게이트웨이 힌트 |
| `venueId` | 아니오 | 선매칭 library hit 시 `.pro` sections 조회용 |
| `imageBase64` + `imageMimeType` | 조건부 | 악보 이미지. `lyricsText`와 **둘 중 하나만** |
| `lyricsText` | 조건부 | 가사 텍스트 |
| `forceReanalyze` | 아니오 | `true`면 catalog 선매칭 스킵 |
| `librarySongId` | 아니오 | 경로형 `songId` (예: `찬양/제목`) |
| `clientRef` | 아니오 | 클라이언트 추적용 |

`saveToLibrary` 필드는 **무시**됩니다 (data-repo 정본, job 완료 시 DB 저장 없음).

### 입력 규칙

- **정확히 하나**: `imageBase64`+`imageMimeType` **또는** `lyricsText`
- **422**: 제목만 / 이미지+가사 동시 / 이미지 쌍 불완전

## 응답 분기

| 상황 | HTTP | 본문 |
|------|------|------|
| 게이트웨이 job 생성 | 202 | `jobId`, `status`, `pollUrl` |
| catalog 1건 일치 | 200 | `source: library`, `songId` (`찬양/제목`), `category`, `sections` (`venueId` 시) |
| catalog 다건 | 200 | `source: library_candidates`, `candidates` |

선매칭: data repo `Libraries/*.pro` 파일명(제목) 정규화 비교 (`title_normalize.py`).

## job 폴링

`GET /api/v1/song/jobs/{jobId}` — 게이트웨이 프록시.

완료 시 항상 `libraryAction: skipped`, `libraryReason: data-repo`. 검수·반영은 analyze 결과로 `build-song`(sections) 후 현장 `.pro` → data repo commit.

## 환경

`docs/ENV.md` — `LLM_GATEWAY_URL`, `LLM_GATEWAY_API_KEY`, `DATA_REPO_PATH`.
