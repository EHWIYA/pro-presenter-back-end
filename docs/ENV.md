# 환경 변수

`.env` 는 git에 포함되지 않습니다. 새 환경은 아래 표를 보고 `api/.env`, `ops/.env` 를 직접 만듭니다.

## api/.env (로컬 개발)

| 변수 | 예시 |
|------|------|
| `VENUES_JSON_PATH` | `../ops/venues.json` |
| `BIBLE_JSON_PATH` | `data/bible-krv.sample.json` |
| `PP_SEND_METHOD` | `theme` \| `message` |
| `PP_THEME_ID` | Black Box 테마 UUID |
| `PP_THEME_SLIDE_ID` | Two Lines 슬라이드 UUID |
| `PP_LIBRARY_ID` | Default Library UUID |
| `PP_PRESENTATION_ID` | test 프레젠테이션 UUID |
| `AGENT_PORT` | 현장 에이전트 포트 (기본 **8787**, `venues.json` `agent_port`로 venue별 override) |
| `AGENT_HTTP_TIMEOUT_SEC` | build/trigger 프록시 타임아웃 (기본 30) |
| `AGENT_GROUP_THEME_KEY` | 에이전트 build `group_theme_key` (기본 `reader-context`) |
| `AGENT_BUILD_MODE` | `append` (기본) |
| `AGENT_AUTO_TRIGGER` | `false` (기본) |
| `AGENT_PROBE_TIMEOUT_SEC` | probe 시 에이전트 타임아웃 (기본 **3**) |
| `AGENT_HEARTBEAT_KEY` | `POST /internal/agent/{id}/heartbeat` 인증 (`X-Agent-Key`) |
| `VENUES_STATUS_WALL_TIMEOUT_SEC` | `/venues/status` 전체 wall timeout (기본 **15**) |
| `RUNTIME_STALE_SEC` | runtime 캐시 stale 판정 (기본 **120**) |
| `AGENT_LIBRARY_CATEGORY` | 성경 build 시 에이전트 `library_category` (기본 `말씀`) |
| `LLM_GATEWAY_URL` | `https://llm-api.livbee.co.kr` (로컬 게이트웨이: `http://127.0.0.1:18080`) |
| `LLM_GATEWAY_API_KEY` | cursor-llm-gateway `x-api-key` |
| `LLM_GATEWAY_TIMEOUT_SEC` | analyze·job 폴링 프록시 타임아웃 (기본 120) |
| `DATABASE_URL` | `postgresql+asyncpg://pp_user:...@pro-presenter-postgres:5432/pp_db` (곡 라이브러리) |
| `SONG_LIBRARY_AUTO_SAVE` | analyze job 완료 시 DB upsert (기본 `true`) |
| `SONG_LIBRARY_DEFAULT_LIMIT` | 곡 검색 기본 limit (기본 20) |

## NAS 배포 경로

운영 루트: `/home/iwh/pro-presenter/live` (GHA `NAS_DEPLOY_PATH` 기본값)

- `venues.json`: `/live/venues.json` (컨테이너 volume)
- `curl http://127.0.0.1:8003/health`

## ops/.env (NAS)

| 변수 | 예시 |
|------|------|
| `PP_API_IMAGE` | `ghcr.io/ehwiya/pro-presenter-back-end:main` |
| `GHCR_USER` / `GHCR_TOKEN` | private GHCR 시 |
| `VENUES_JSON_PATH` | `/live/venues.json` |
| `BIBLE_JSON_PATH` | `/app/data/bible-krv.json` |
| `LLM_GATEWAY_URL` | `http://172.25.0.1:18080` (Docker bridge → 호스트) |
| `LLM_GATEWAY_API_KEY` | (필수) 찬양 악보 analyze 프록시 |
| `DATABASE_URL` | compose `environment` 로 주입 (아래 Postgres 참고) |
| `SONG_LIBRARY_AUTO_SAVE` | `true` |
| `SONG_LIBRARY_DEFAULT_LIMIT` | `20` |

## ops/.env.postgres (NAS, git 제외)

| 변수 | 예시 |
|------|------|
| `PP_POSTGRES_DB` | `pp_db` |
| `PP_POSTGRES_USER` | `pp_user` |
| `PP_POSTGRES_PASSWORD` | (필수) |

## NAS 포트

- 컨테이너 API: **8000** (이미지 기본)
- 호스트 접속: **8003** (`ops/docker-compose.yml` → `127.0.0.1:8003:8000`)
- Postgres: **5434** (`127.0.0.1:5434` → `pro-presenter-postgres:5432`)
- `/health`·`/venues`: `http://127.0.0.1:8003/...`
- `/health` 정상: `ops/data/bible-krv.json` 실데이터 (`./bin/fetch-bible-krv.sh`)

서버 메일 별칭: `PP_PRESENTATION_UUID` → `PP_PRESENTATION_ID`, `PP_DOCUMENT_UUID` → `PP_LIBRARY_ID`, `PP_ACTION_UUID` → `PP_THEME_SLIDE_ID`
