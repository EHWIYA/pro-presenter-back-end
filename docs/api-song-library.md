# 곡 라이브러리 API — pro-presenter-data catalog

PWA 찬양 탭(`/worship/song`) 연동. **정본**: `pro-presenter-data` → `Libraries/*.pro` (Postgres 곡 DB 없음).

상세 계약: [`handoff/song-catalog.md`](handoff/song-catalog.md)

## songId

`{libraryCategory}/{제목}` — `.pro` 확장자 제외.

예: `찬양/주님의 마음`, `찬송가/413.내 평생`

URL에는 percent-encoding 사용.

## category (API 필터)

| 값 | `Libraries/` 폴더 |
|----|-------------------|
| `praise` | 찬양 |
| `special` | 찬양 (동일 폴더) |
| `hymnal` | 찬송가 |
| `hymn` | 성가곡 |

`libraryCategory=찬양` 쿼리로 폴더 직접 필터 가능.

## GET `/api/v1/songs`

| 쿼리 | 설명 |
|------|------|
| `q` | 제목 검색 |
| `category` | `praise` \| `hymn` \| `hymnal` \| `special` |
| `libraryCategory` | `찬양` \| `찬송가` \| `성가곡` |
| `limit` / `offset` | 페이지네이션 |

응답 `items[]`: `songId`, `title`, `category`, `libraryCategory`, `presentationFilename`, `sectionCount`(null), `updatedAt`

## GET `/api/v1/songs/{songId}`

카탈로그 메타. `?venueId=` 제공 시 에이전트가 `.pro`에서 `sections` 조회 시도.

## 제거됨 (410 Gone)

`POST/PATCH/DELETE /songs`, `PUT .../sections`, `/song-categories`, `/admin/songs/import`  
→ 편집은 data repo Git.

## analyze · build-song

- `POST /api/v1/song/analyze` — 제목 선매칭은 catalog; job 완료 시 **DB 저장 없음** (`libraryAction: skipped`)
- `POST /api/v1/worship/build-song` — `songId` 또는 `sections` (XOR)
- `GET /api/v1/venues/{venueId}/library/songs/{songId}/sections` — 에이전트 `.pro` 프록시

## NAS 환경

`DATA_REPO_PATH=/app/data/pro-presenter-data` — `ops/data/README.md`
