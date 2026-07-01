# 프론트 — 곡 catalog 마이그레이션 (2026-07)

백엔드 배포 후 PWA 필수 변경.

## songId

- **이전**: UUID (`550e8400-...`)
- **이후**: `{libraryCategory}/{제목}` — 예: `찬양/주님의 마음`
- URL: `encodeURIComponent(songId)` (슬래시 포함)

## API 변경

| 변경 | 대응 |
|------|------|
| `POST/PATCH/DELETE /songs`, `PUT .../sections` | **410** — 편집 UI 제거 또는 “data repo 관리” 안내 |
| `/song-categories` | **제거** — `category` / `libraryCategory` 필터 사용 |
| `GET /songs` | catalog 목록 (`libraryCategory`, `presentationFilename` 추가) |
| `GET /songs/{id}?venueId=` | PC에 `.pro` 있으면 `sections` 채움; 없으면 **200** + `sectionsHint` (404 아님) |
| analyze job 완료 | `libraryAction: skipped` — DB 저장 없음 |
| `build-song` + `songId` | 경로형 id; 에이전트가 sections 반환 필요 |

## sections 미리보기

`GET /api/v1/venues/{venueId}/library/songs/{songId}/sections`  
(에이전트 `GET /library/songs/{category}/{title}/sections` 프록시)

## 신규 곡 플로우

1. analyze (202) → job 폴링 → 검수 UI  
2. `POST /worship/build-song` with `sections` + `songTitle`  
3. 예배 후 data repo `Libraries/` commit (운영 워크플로)

계약 정본: `docs/handoff/song-catalog.md`
