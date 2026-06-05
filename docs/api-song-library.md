# 곡 라이브러리 API — category · sections

PWA 찬양 탭(`/worship/song`) 연동. DB: `DATABASE_URL` (PostgreSQL), 마이그레이션 `002_song_category`.

## category 값

| 값 | UI 라벨 |
|----|---------|
| `praise` | 찬양 (기본값) |
| `hymn` | 성가곡 |
| `special` | 특송 |
| `custom:<slug>` | 사용자 추가 (예: `custom:주일-1부`) |

- 생략 시 **`praise`**
- `custom:<slug>`: slug는 한글·영숫자·`_`·`-` (1자 이상)
- **422**: 위 형식 외 값

구 값(`chantsong`/`gospel`/`worship` → `special`, `contemporary`/`other` → `praise`)은 **프론트에서 정규화** 후 전송.

## GET `/api/v1/songs`

| 쿼리 | 설명 |
|------|------|
| `q` | 제목 검색 |
| `category` | 정확 일치 필터 (`praise`, `hymn`, `special`, `custom:...`) |
| `limit` / `offset` | 페이지네이션 |

응답 `items[]`: `songId`, `title`, `artist`, `tags`, **`category`**, `sectionCount`, `updatedAt`

```bash
curl -s "https://pro-api.iwhya.kr/api/v1/songs?category=hymn&limit=20"
```

## GET `/api/v1/songs/{songId}`

상세에 `category`, `sections`, `sectionCount` 포함.

## POST `/api/v1/songs`

```json
{
  "title": "주님의 마음",
  "category": "praise",
  "sections": [{ "type": "verse", "label": "1절", "lines": ["가사1", "가사2"] }]
}
```

## PATCH `/api/v1/songs/{songId}`

`title`, `artist`, `tags`, `category` 부분 갱신.

## PUT `/api/v1/songs/{songId}/sections`

검수 후 저장. **부분 갱신** 지원.

```json
{
  "sections": [{ "type": "verse", "label": "1절", "lines": ["a", "b"] }],
  "title": "수정 제목",
  "category": "hymn"
}
```

### sections 정책 (BFF 확정)

| body `sections` | 동작 |
|-----------------|------|
| **필드 생략** (`null`/미포함) | 기존 DB 구간 **유지** |
| **빈 배열** `[]` | 기존 DB 구간 **유지** (실수로 전체 삭제 방지) |
| **1개 이상** | 해당 배열로 **전체 교체** |

- 구간을 비우는 API는 제공하지 않음 (의도적 삭제는 곡 soft-delete 사용).
- `title`·`category`만내면 메타만 갱신, 구간 유지.

### 성공 응답 (200)

갱신된 곡 스냅샷 반환:

```json
{
  "ok": true,
  "songId": "...",
  "title": "...",
  "category": "hymn",
  "sections": [...],
  "sectionCount": 3,
  "createdAt": "...",
  "updatedAt": "..."
}
```

## analyze 응답의 category

- `source: library` (200): 저장된 곡의 `category` 포함.
- `source: library_candidates`: 후보 `items[]`에 `category` 포함.
- job 완료·게이트웨이 `parsed`: 찬송가 메타는 [`api-song-analyze.md`](api-song-analyze.md) 참고. **DB 영속화는 검수 후 PUT/PATCH `category`로 저장** (자동 추론→저장 계획 없음).

## P3 (미구현) song-categories 마스터

팀 공통 `custom:*` 분류가 필요할 때 `GET/POST/DELETE /api/v1/song-categories` 협의. P0 없이도 PWA는 localStorage로 동작.
