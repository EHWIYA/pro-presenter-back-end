# API v2 데이터 모델 (프론트 handoff)

작성 기준: 2026-06-20 · API `1.2.0`

프론트는 **NAS BFF만** 호출합니다. 아래 DTO가 유일한 계약입니다.

## Venue

`GET /venues` — 공개 목록 (snake_case)

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | venue 식별자 |
| `name` | string | 표시 이름 |
| `tailscale_ip` | string | |
| `pp_port` | int | |
| `enabled` | bool | |

설정 정본: NAS `live/venues.json` (레포 `ops/venues.json` 은 샘플)

## VenueRuntime

`GET /api/v1/venues/{venueId}/runtime` — 캐시 조회 (camelCase)

| 필드 | 타입 | 설명 |
|------|------|------|
| `venueId` | string | |
| `updatedAt` | ISO8601 \| null | 마지막 갱신 |
| `stale` | bool | heartbeat·캐시 age 초과 시 true |
| `pp.reachable` | bool | |
| `pp.currentPresentationId` | string \| null | |
| `pp.currentSlideIndex` | int \| null | |
| `pp.previewText` | string | |
| `agent.reachable` | bool | |
| `agent.version` | string \| null | |
| `agent.lastHeartbeatAt` | ISO8601 \| null | |
| `data.gitRevision` | string \| null | pro-presenter-data git |
| `data.reportedAt` | ISO8601 \| null | |
| `lastBuild` | object \| null | 아래 WorshipSession 요약 |

`GET /api/v1/venues/{venueId}/runtime/probe` — live pull (느려도 됨). probe 후 DB 갱신.

## WorshipSession

`POST /api/v1/venues/{venueId}/worship/sessions`

Request (하나 이상):

```json
{ "text": "마 3:1-10\n마 3:2" }
```

또는

```json
{ "reference": "마 3:1-10" }
```

Response (agent BuildResponse + sessionId):

```json
{
  "sessionId": "uuid",
  "reference": "마 3:1-10",
  "slide_map": [{ "index": 33, "label": "마 3:1" }],
  "slide_count": 1,
  "total_slide_count": 10,
  "ok": true
}
```

`slide_map[].index` = `POST .../trigger` 의 `index` = agent `trigger?index=`

`POST /api/v1/venues/{venueId}/worship/sessions/{sessionId}/trigger`

```json
{ "index": 33 }
```

## SongLibrary

`GET/POST/PATCH/DELETE /api/v1/songs…` — camelCase (`songId`, `buildMode` 등). 기존 문서 `docs/api-song-library.md` 참고.

## Bible

`GET /api/v1/books` — 성경 책 목록  
`POST /api/v1/verse/parse` — API_KEY 필요

## 인증

| 구분 | 경로 | 인증 |
|------|------|------|
| 공개 read | `/venues`, `/api/v1/venues/{id}/runtime` | 없음 |
| write | build, trigger, songs write | `X-API-Key` (설정 시) |
| internal | `POST /internal/agent/{id}/heartbeat` | `X-Agent-Key` |

## 레거시 (사용 금지)

| 경로 | 대체 |
|------|------|
| `POST /api/v1/verse/send` | worship sessions + trigger |
| `POST /venues/{id}/worship/build` | `POST /api/v1/venues/{id}/worship/sessions` |

## E2E 흐름 (말씀)

```
PWA → POST /api/v1/venues/{id}/worship/sessions  (build)
    → slide_map 버튼 UI
    → POST /api/v1/venues/{id}/worship/sessions/{sid}/trigger?index=N
    → PP 화면 송출
```

상태판: `GET /api/v1/venues/{id}/runtime` (주기적). 연결 테스트: `.../runtime/probe`.
