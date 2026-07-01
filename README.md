# ProPresenter 원격 방송 — 백엔드 (NAS BFF)

NAS에서 Tailscale로 현장 PC의 **ProPresenter Agent**(`:8787`) 및 **PP API**(`:12135`)에 접속합니다. 성경·찬양 데이터를 파싱·저장하고, 슬라이드 **빌드·송출은 에이전트에 프록시**합니다 (BFF는 `.pro`를 만들지 않음).

담당자 전달: [`docs/BACKEND-HANDOFF.md`](docs/BACKEND-HANDOFF.md)

## 디렉터리 구조

```
pro-presenter-back-end/
├── api/                 # FastAPI 앱 (Docker)
│   ├── app/
│   │   ├── main.py
│   │   ├── bible.py
│   │   ├── split.py
│   │   ├── venues.py
│   │   ├── worship.py          # 에이전트 build/trigger 프록시
│   │   ├── presentations.py
│   │   ├── library_resolve.py
│   │   ├── songs_api.py          # 곡 catalog·analyze·build-song
│   │   ├── song_catalog.py
│   │   ├── data_repo.py
│   │   ├── song_gateway.py
│   │   ├── propresenter.py
│   │   └── verse_service.py    # 레거시 PP 직접 송출
│   ├── data/
│   │   ├── bible-krv.sample.json   # 샘플 (repo)
│   │   ├── fixtures/pro-presenter-data/  # 곡 catalog 샘플 (CI)
│   │   └── bible-krv.json          # 전체 성경 (git 제외, NAS·로컬)
│   ├── scripts/build_bible_json.py
│   └── docker-compose.yml
└── ops/
    ├── docker-compose.yml
    ├── venues.json
    └── bin/
        ├── deploy.sh          # 배포 (GHA·수동)
        ├── setup-nas.sh       # NAS 1회 준비
        └── install-live-remote.sh
```

## 빠른 시작 (NAS / Linux)

호스트 **8003** = 컨테이너 **8000** (`ops/docker-compose.yml` 매핑). 상세: `docs/ENV.md`

```bash
cd /home/iwh/pro-presenter/api/ops   # NAS
# ops/.env · data/bible-krv.json — docs/ENV.md

./bin/deploy.sh ghcr.io/ehwiya/pro-presenter-back-end:main

curl -s http://127.0.0.1:8003/health
curl -s http://127.0.0.1:8003/venues
curl -s http://127.0.0.1:8003/venues/main/probe
```

## API

### 현장·성경 (PWA 주 경로)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 서버 상태·성경·곡 catalog (`song_catalog`) |
| GET | `/api/v1/books` | 지원 성경 66권 목록 |
| GET | `/venues` | 현장 목록 |
| GET | `/venues/{id}/probe` | NAS → PP·에이전트 연결 테스트 |
| GET | `/venues/status` | 활성 현장 일괄 probe (PWA 미니제어 상태판) |
| GET | `/venues/{id}/presentations` | PWA 홈 — PP 라이브러리 프레젠테이션·그룹·슬라이드 수 ([`docs/api-presentations.md`](docs/api-presentations.md)) |
| GET | `/venues/{id}/presentation/current` | PWA 미니제어 — 현재 프레젠테이션/슬라이드 미리보기 |
| POST | `/api/v1/venues/{id}/build` | PWA `reference` → 에이전트 빌드 (`auto_trigger` 기본 false) |
| POST | `/api/v1/venues/{id}/trigger?index=N` | 에이전트 슬라이드 송출 |
| POST | `/venues/{id}/worship/build` | 위와 동일 (호환 — `text` 필드 지원) |
| POST | `/venues/{id}/worship/trigger` | 위와 동일 (호환 — body `index`) |

### 찬양·곡 라이브러리

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/song/analyze` | 악보·가사 → LLM 게이트웨이 프록시 ([`docs/api-song-analyze.md`](docs/api-song-analyze.md)) |
| GET | `/api/v1/song/jobs/{jobId}` | analyze job 폴링 |
| GET | `/api/v1/songs` | 곡 catalog ([`docs/api-song-library.md`](docs/api-song-library.md)) |
| GET | `/api/v1/venues/{id}/library/songs/{songId}/sections` | 에이전트 `.pro` 구간 프록시 |
| POST | `/api/v1/worship/build-song` | 찬양 sections/songId → 에이전트 `build-song` |

### 레거시 (PP 직접 송출)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/verse/parse` | 참조 파싱 + 2줄 분할 |
| POST | `/api/v1/verse/send` | 파싱 후 PP 송출 (`venue_id` 필수) |

### Probe/Status 응답 계약

`/venues/{id}/probe`, `/venues/status`는 연결 판단 필드를 아래처럼 반환합니다.

- `connected`: ProPresenter API 연결 상태
- `agent_reachable`: 에이전트(기본 8787) `/health` 연결 상태
- `status_code`, `message`: ProPresenter 점검 결과
- `agent_status_code`, `agent_message`: 에이전트 점검 결과
- `checked_at` (공통), `elapsed_ms` (`/venues/status` 항목별)

FastAPI `response_model`로 OpenAPI(Swagger) 스키마도 동일 계약으로 노출됩니다.

### 요청 예시

```bash
curl -s -X POST http://127.0.0.1:8003/api/v1/verse/parse \
  -H "Content-Type: application/json" \
  -d '{"reference":"요 3:16"}'

curl -s -X POST http://127.0.0.1:8003/api/v1/verse/send \
  -H "Content-Type: application/json" \
  -d '{"reference":"요 3:16","venue_id":"main"}'
```

### 성공 응답 형태

```json
{
  "reference": "요한복음 3:16",
  "title": "요한복음 3:16",
  "lines": ["하나님이 세상을 이처럼 사랑하사", "독생자를 주셨으니 ..."],
  "raw_text": "...",
  "venue_id": "main",
  "pp_triggered": true
}
```

## 환경 변수

`api/.env`(로컬), `ops/.env`(NAS) — 전체 표는 [`docs/ENV.md`](docs/ENV.md)

| 변수 | 설명 |
|------|------|
| `VENUES_JSON_PATH` | `ops/venues.json` 경로 |
| `BIBLE_JSON_PATH` | 개역개정 JSON |
| `PP_SEND_METHOD` | `theme` (기본) 또는 `message` |
| `PP_THEME_ID` / `PP_THEME_SLIDE_ID` | 테마 슬라이드 PUT |
| `PP_LIBRARY_ID` / `PP_PRESENTATION_ID` | 송출 후 library trigger |
| `PP_LIBRARY_NAME_DEFAULT` | 라이브러리 이름 fallback (기본 `worship-2`) |
| `AGENT_PORT` / `AGENT_*` | 에이전트 프록시 (`build_mode`, `auto_trigger`, `library_category` 등) |
| `DATABASE_URL` | Postgres 곡 라이브러리 (NAS compose `:5434`) |
| `LLM_GATEWAY_URL` / `LLM_GATEWAY_API_KEY` | 찬양 악보 analyze |
| `API_KEY` | 설정 시 `X-API-Key` — 현재 **레거시 `verse/*`·admin import**만 적용 (worship·songs는 P1) |
| `CORS_ORIGINS` | PWA 도메인 (콤마 구분) |

현장별 UUID는 `ops/venues.json` 각 venue 객체에 넣을 수 있습니다 (`.env`보다 우선).

## 성경 JSON

`api/data/bible-krv.json` 형식:

```json
{
  "books": {
    "john": {
      "chapters": {
        "3": { "16": "본문..." }
      }
    }
  }
}
```

책 키는 영문 canonical(`john`, `genesis`) 또는 별칭으로 인덱싱됩니다.

전체 성경: `api/scripts/build_bible_json.py` 로 변환 → `data/bible-krv.json` (상세 [`api/data/README.md`](api/data/README.md))

## 참조 문자열 (1단계)

- `요 3:16`, `요한복음 3:16`
- `창 1:1`, `창세기 1:1`
- 절 범위: `롬 8:28-30` (연속 절 본문 합침)
- 66권 약어·정식명

## 송출 방식

1. **`theme` (권장)**  
   - `GET` 슬라이드 → 텍스트 필드 교체 → `PUT`  
   - `test` 프레젠테이션 `library trigger`로 화면에 띄움  
2. **`message`**  
   - `PUT /v1/message/{id}` + `POST .../trigger`  
   - 하단 메시지 UI 스타일

`PP_THEME_ID`는 ProPresenter에서 Black Box 테마 UUID를 Swagger 또는 UI에서 확인해 넣어야 합니다.

## 로컬 개발 (Windows)

**한글 깨짐:** PC 전역 `%USERPROFILE%\.cursor\ensure-utf8.ps1` + Cursor 터미널 프로필 `PowerShell (UTF-8)` 권장. 이 repo는 `.cursor/scripts/`, `.cursor/rules/windows-shell-utf8.mdc` 포함.

```powershell
# 테스트 (UTF-8 래퍼 — && 대신 이 스크립트 사용)
.\.cursor\scripts\dev-test.ps1

cd api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
. ..\.cursor\scripts\ensure-utf8.ps1
pip install -r requirements-dev.txt

$env:VENUES_JSON_PATH = "..\ops\venues.json"
$env:BIBLE_JSON_PATH = "data\bible-krv.sample.json"
uvicorn app.main:app --reload --port 8003
```

검증: `.\.cursor\scripts\verify-utf8.ps1` (또는 `chcp` → 65001 · `python -c "print('한글 테스트')"`)

**GHA (push 후):** `.\.cursor\scripts\gha_watch.ps1` — CI/Deploy NAS 성공·실패·backend/server 분류 (`.cursor/rules/gha-post-push-watch.mdc`)

**GHA Secrets (로컬):** 루트 `.env.gha` (git 제외) — 값 입력 후 GitHub Actions Secrets에 **동일 이름**으로 등록

## NAS 배치 (이미지 pull — git clone 불필요)

GHA가 **GHCR**에 이미지를 올리면, NAS는 `ops/` 설정만 두고 pull 합니다.

```
/home/iwh/pro-presenter/api/ops/
├── docker-compose.yml
├── .env              ← NAS 전용 (git 제외, docs/ENV.md)
├── venues.json
└── data/bible-krv.json
```

로컬 개발·빌드는 `api/docker-compose.yml` (`build: .`) 을 사용합니다.

## GitHub Actions (CI/CD)

| 워크플로 | 역할 |
|----------|------|
| [`ci.yml`](.github/workflows/ci.yml) | PR: pytest / main: pytest + GHCR push |
| [`deploy-nas.yml`](.github/workflows/deploy-nas.yml) | SSH → NAS [`ops/bin/deploy.sh`](ops/bin/deploy.sh) (pull·재시작은 NAS) |

NAS 최초: [`ops/bin/install-live-remote.sh`](ops/bin/install-live-remote.sh) · 상세 [`docs/github-actions.md`](docs/github-actions.md)

**서버 회신 후:** [`docs/PUSH-AND-HANDOFF.md`](docs/PUSH-AND-HANDOFF.md) · 서버 회신 메일 [`docs/REPLY-TO-SERVER.md`](docs/REPLY-TO-SERVER.md)

## 배포 전 체크 (운영 — 코드 밖)

- [ ] `ops/data/bible-krv.json` (전체 성경)
- [ ] `ops/.env` · `PP_THEME_ID` · GHCR `PP_API_IMAGE`
- [ ] GitHub Secrets → NAS SSH, (private) `GHCR_PULL_TOKEN`
- [ ] `venues/main/probe` OK 후 `verse/send` 화면 확인

## 팀 확인 사항 (결정 기록)

| 항목 | 결정 |
|------|------|
| 송출 (레거시) | 기본 `theme`, `message` 선택 가능 |
| 곡 DB | Postgres + Alembic (`DATABASE_URL`) |
| 빌드·송출 | worship → 에이전트 프록시, `auto_trigger` 기본 false |
| 인증 | `API_KEY` 비우면 공개; worship/songs 키 적용은 P1 |
| 송출 이력 | `SEND_LOG_PATH` JSONL (선택) |
