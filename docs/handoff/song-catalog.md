# 곡 카탈로그 — pro-presenter-data 정본 (Option A)

작성: 2026-07-01 · BFF `pro-presenter-back-end`

## 정본

| 항목 | 정본 |
|------|------|
| 곡 슬라이드 실체 | `pro-presenter-data` → `Libraries/<카테고리>/*.pro` |
| 곡 목록·검색 | NAS BFF가 마운트된 data repo `Libraries/` 스캔 |
| 가사 sections (런타임) | 현장 에이전트가 `.pro` 파싱 (`GET /library/songs/.../sections`) |
| 편집·검수 | data repo Git commit (BFF CRUD 없음) |

Postgres `songs` 테이블은 **사용하지 않음**. `worship_sessions`·`venue_runtime`만 DB 유지.

## songId

형식: `{library_category}/{제목}` (확장자 `.pro` 제외)

예: `찬양/주님의 마음`, `찬송가/413.내 평생`

URL 경로에는 percent-encoding (`찬양` → `%EC%B0%AC%EC%96%91`).

## library_category ↔ API category

| `Libraries/` 폴더 | API `category` | 비고 |
|-------------------|----------------|------|
| `찬양` | `praise` | CCM·찬양·특송(`special` 필터도 동일 폴더) |
| `찬송가` | `hymnal` | 번호 곡 (`413.` 패턴) |
| `성가곡` | `hymn` | 성가 |

쿼리 `libraryCategory=찬양` 으로 폴더 직접 필터 가능.

## BFF API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/songs` | data repo 인덱스 |
| GET | `/api/v1/songs/{songId}` | 메타; `?venueId=` 시 sections 에이전트 조회 |
| POST | `/api/v1/song/analyze` | LLM 프록시; 제목 선매칭은 catalog |
| GET | `/api/v1/song/jobs/{jobId}` | analyze 폴링 (DB 저장 없음) |
| POST | `/api/v1/worship/build-song` | `songId` 또는 `sections` |
| GET | `/api/v1/venues/{id}/library/songs/{songId}/sections` | 에이전트 `.pro` 구간 프록시 |

**제거됨 (410):** `POST/PATCH/DELETE /songs`, `PUT .../sections`, `/song-categories`, `/admin/songs/import`

## 에이전트 계약 (신규)

```
GET /library/songs/{library_category}/{stem}/sections
→ { "sections": [ { "type", "label", "lines" }, ... ] }
```

`stem` = `.pro` 파일명에서 확장자 제외 (곡 제목).

## NAS 배포

`DATA_REPO_PATH` = `/app/data/pro-presenter-data` (compose volume)  
`ops/data/pro-presenter-data/` 에 shallow clone 또는 rsync.
