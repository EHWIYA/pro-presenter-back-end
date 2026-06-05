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

## song-categories 마스터 (전역)

`custom:*` 분류 ID·라벨을 서버에서 공유합니다. **venue 파라미터 없음** (곡 API와 동일 스코프).

DB: `song_categories` 테이블, 마이그레이션 `003_song_categories`.

### GET `/api/v1/song-categories`

```json
{
  "builtin": ["praise", "hymn", "special"],
  "custom": [
    {
      "id": "custom:주일-1부",
      "label": "주일 1부",
      "createdAt": "2026-06-05T00:00:00Z",
      "updatedAt": "2026-06-05T00:00:00Z"
    }
  ]
}
```

- `custom` 정렬: `createdAt` 오름차순 → `label` 가나다순
- 인증: songs API와 동일 (운영 `API_KEY` 설정 시 `X-API-Key`)

### POST `/api/v1/song-categories`

```json
{ "label": "주일 1부" }
```

- 서버가 `slugifyCategoryLabel`과 동일 규칙으로 `custom:<slug>` 발급
- slug 규칙: 공백→`-`, `[\w가-힣\-]+` 1자 이상 (예: `주일 1부` → `custom:주일-1부`)
- **422**: 빈 라벨, 24자 초과, 기본 3종 라벨(찬양·성가곡·특송)과 동일, slug 생성 불가
- **409**: 동일 slug ID 이미 존재

### PATCH `/api/v1/song-categories/{id}`

```json
{ "label": "주일 예배 1부" }
```

- `id`는 URL 인코딩 (`custom:%EC%A3%BC%EC%9D%BC-1%EB%B6%80`)
- ID(slug)는 불변, **라벨만** 변경
- builtin(`praise`/`hymn`/`special`) → **404**

### DELETE `/api/v1/song-categories/{id}`

- **200**: 삭제 성공 `{"deleted": true}`
- **404**: 없음 / builtin 삭제 시도
- **409**: 해당 category를 쓰는 활성 곡 1건 이상

```json
{
  "detail": "category_in_use",
  "message": "이 카테고리를 사용하는 곡이 있습니다.",
  "songCount": 3
}
```

### 곡 API 연동

- `POST`/`PATCH`/`PUT .../sections` 에 `category: custom:xxx` 전송 시 **마스터에 등록된 ID만 허용** (미등록 → **422**)
- builtin 3종은 마스터 테이블 없이 코드 상수로 처리
- 마스터 삭제 후에도 곡 DB의 `category` 문자열은 유지 → `GET /songs?category=custom:xxx` 필터는 동작, 라벨은 프론트 ID fallback

```bash
curl -s -H "X-API-Key: $KEY" "https://pro-api.iwhya.kr/api/v1/song-categories"
curl -s -X POST -H "Content-Type: application/json" -H "X-API-Key: $KEY" \
  -d '{"label":"주일 1부"}' "https://pro-api.iwhya.kr/api/v1/song-categories"
```
