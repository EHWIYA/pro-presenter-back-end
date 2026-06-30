# 백엔드 담당 — Pro Presenter BFF

NAS `pro-api.iwhya.kr` FastAPI BFF. **`.pro` 생성·PP 슬라이드 추가는 하지 않음** — Windows 현장 에이전트(`:8787`)로 프록시만 수행.

전체 시스템 정본: **pro-presenter-data** 레포 `docs/system/` (`overview.md`, `flows.md`, `repos.md`)

## 미션

| 담당 | 미담당 |
|------|--------|
| 성경 JSON 파싱·2줄 분할 (`bible.py`, `split.py`) | Protobuf `.pro` 조립 |
| Postgres 곡 DB CRUD | PP REST로 슬라이드 생성 |
| venue → 에이전트 프록시 (`worship.py`) | 에이전트 NAS 배포 |
| 악보 analyze → cursor-llm-gateway 프록시 | PWA UI |
| OpenAPI·DTO 변환 (PWA camelCase ↔ 에이전트 snake_case) | PP Show Directory Git 관리 |

## 핵심 API (PWA 주 경로)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/venues/{id}/build` | `reference` → 에이전트 `POST /build` |
| POST | `/api/v1/venues/{id}/trigger?index=N` | 에이전트 `POST /trigger?index=N` |
| POST | `/api/v1/worship/build-song` | 찬양 sections/songId → 에이전트 `build-song` |
| POST | `/api/v1/song/analyze` | LLM 게이트웨이 프록시 + 곡 DB 선매칭 |
| GET/POST/PATCH | `/api/v1/songs` | 곡 라이브러리 CRUD |

**호환 경로** (기존 PWA·운영 curl): `/venues/{id}/worship/build`, `/venues/{id}/worship/trigger` — 동일 핸들러.

### build 요청

```json
{
  "reference": "마 3:1-10",
  "auto_trigger": false
}
```

레거시: `text` 필드(첫 줄 → `reference`). `reference`가 있으면 우선.

### 에이전트로 전달되는 body

```json
{
  "reference": "마 3:1-10",
  "group_theme_key": "reader-context",
  "build_mode": "append",
  "auto_trigger": false,
  "library_category": "말씀"
}
```

성경(sermon) 테마 프로필 ↔ `group_theme_key: reader-context` (data repo `theme-profiles.md` 참고).  
찬양(song_lyric)은 에이전트 `build-song` 경로 — BFF는 sections만 전달.

환경 변수: `AGENT_GROUP_THEME_KEY`, `AGENT_BUILD_MODE`, `AGENT_AUTO_TRIGGER`, `AGENT_LIBRARY_CATEGORY`, `AGENT_PORT`.

**index 계약:** `slide_map[].index` = `trigger?index=` = 에이전트 `POST /trigger?index=`.

## data repo·PP 자산과의 경계

- **에이전트**가 `Documents/pro-presenter/Libraries/` 아래 `.pro` N장 생성·갱신.
- **재생목록(Playlists)** 모델이 정본 — 레거시 `worship-2.pro` 단일 파일은 사용 안 함.
- BFF의 `pp_library_name` / `presentations` API는 PP REST **라이브러리 목록 조회**용(홈 UI). 에이전트 빌드 대상 `.pro`와는 별개 설정일 수 있음 → 현장 `venues.json`·data repo·에이전트 설정 일치 확인 필요.

## 구현 상태 (2026-06)

| 영역 | 상태 |
|------|------|
| `/api/v1/venues/{id}/build` · `trigger` | ✅ |
| worship 호환 경로 | ✅ |
| worship build-song + 곡 DB | ✅ |
| song analyze → gateway | ✅ |
| presentations / probe / status | ✅ |
| pytest 계약 테스트 | ✅ |
| worship·songs `X-API-Key` | ⏳ P1 |
| analyze job 컨텍스트 | ⚠️ 인메모리 |

## 협업 주의

1. **DTO** — 에이전트 `docs/agent/api.md` 정본. BFF 변경 시 `worship.py` + pytest.
2. **다교회** — NAS 1대, venue별 Tailscale → 교회 PC 에이전트 `:8787`.
3. **배포** — `main` push → CI → GHCR → Deploy NAS.

## 하지 않을 것

- `.pro` 직접 생성
- PP REST로 슬라이드 추가
- 에이전트 Docker화·NAS 배포
