# ProPresenter 원격 방송 — 백엔드 (1단계 MVP)

NAS에서 Tailscale로 현장 PC의 **ProPresenter API**에 접속해, 성경 구절을 파싱·2줄로 나눈 뒤 화면에 송출하는 **FastAPI** 서버입니다.

## 디렉터리 구조

```
pro-presenter-back-end/
├── api/                 # FastAPI 앱 (Docker)
│   ├── app/
│   │   ├── main.py
│   │   ├── bible.py
│   │   ├── split.py
│   │   ├── venues.py
│   │   ├── propresenter.py
│   │   └── verse_service.py
│   ├── data/
│   │   ├── bible-krv.sample.json   # 샘플 (repo)
│   │   └── bible-krv.json          # 전체 성경 (git 제외, NAS·로컬)
│   ├── scripts/build_bible_json.py
│   └── docker-compose.yml
└── live/
    ├── docker-compose.yml
    ├── venues.json
    └── bin/
        ├── deploy.sh          # 배포 (GHA·수동)
        ├── setup-nas.sh       # NAS 1회 준비
        └── install-live-remote.sh
```

## 빠른 시작 (NAS / Linux)

호스트 **8003** = 컨테이너 **8000** (`live/docker-compose.yml` 매핑). 상세: `docs/ENV.md`

```bash
cd /home/iwh/pro-presenter/live   # NAS
# live/.env · data/bible-krv.json — docs/ENV.md

./bin/deploy.sh ghcr.io/ehwiya/pro-presenter-back-end:main

curl -s http://127.0.0.1:8003/health
curl -s http://127.0.0.1:8003/venues
curl -s http://127.0.0.1:8003/venues/main/probe
```

## API (MVP)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 서버 상태·성경 로드 절 수 |
| GET | `/api/v1/books` | 지원 성경 66권 목록 |
| GET | `/venues` | 현장 목록 |
| GET | `/venues/{id}/probe` | NAS → PP 연결 테스트 |
| POST | `/api/v1/verse/parse` | 참조 파싱 + 2줄 분할 |
| POST | `/api/v1/verse/send` | 파싱 후 PP 송출 (`venue_id` 필수) |

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

`api/.env`(로컬), `live/.env`(NAS) — 전체 표는 [`docs/ENV.md`](docs/ENV.md)

| 변수 | 설명 |
|------|------|
| `VENUES_JSON_PATH` | `live/venues.json` 경로 |
| `BIBLE_JSON_PATH` | 개역개정 JSON |
| `PP_SEND_METHOD` | `theme` (기본) 또는 `message` |
| `PP_THEME_ID` / `PP_THEME_SLIDE_ID` | 테마 슬라이드 PUT |
| `PP_LIBRARY_ID` / `PP_PRESENTATION_ID` | 송출 후 library trigger |
| `PP_MESSAGE_ID` | message 방식일 때 |
| `API_KEY` | 설정 시 `X-API-Key` 헤더 필요 |
| `CORS_ORIGINS` | PWA 도메인 (콤마 구분) |

현장별 UUID는 `live/venues.json` 각 venue 객체에 넣을 수 있습니다 (`.env`보다 우선).

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

$env:VENUES_JSON_PATH = "..\live\venues.json"
$env:BIBLE_JSON_PATH = "data\bible-krv.sample.json"
uvicorn app.main:app --reload --port 8003
```

검증: `.\.cursor\scripts\verify-utf8.ps1` (또는 `chcp` → 65001 · `python -c "print('한글 테스트')"`)

**GHA (push 후):** `.\.cursor\scripts\gha_watch.ps1` — CI/Deploy NAS 성공·실패·backend/server 분류 (`.cursor/rules/gha-post-push-watch.mdc`)

**GHA Secrets (로컬):** 루트 `.env.gha` (git 제외) — 값 입력 후 GitHub Actions Secrets에 **동일 이름**으로 등록

## NAS 배치 (이미지 pull — git clone 불필요)

GHA가 **GHCR**에 이미지를 올리면, NAS는 `live/` 설정만 두고 pull 합니다.

```
/home/iwh/pro-presenter/live/
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
| [`deploy-nas.yml`](.github/workflows/deploy-nas.yml) | SSH → NAS [`live/bin/deploy.sh`](live/bin/deploy.sh) (pull·재시작은 NAS) |

NAS 최초: [`live/bin/install-live-remote.sh`](live/bin/install-live-remote.sh) · 상세 [`docs/github-actions.md`](docs/github-actions.md)

**서버 회신 후:** [`docs/PUSH-AND-HANDOFF.md`](docs/PUSH-AND-HANDOFF.md) · 서버 회신 메일 [`docs/REPLY-TO-SERVER.md`](docs/REPLY-TO-SERVER.md)

## 배포 전 체크 (운영 — 코드 밖)

- [ ] `live/data/bible-krv.json` (전체 성경)
- [ ] `live/.env` · `PP_THEME_ID` · GHCR `PP_API_IMAGE`
- [ ] GitHub Secrets → NAS SSH, (private) `GHCR_PULL_TOKEN`
- [ ] `venues/main/probe` OK 후 `verse/send` 화면 확인

## 팀 확인 사항 (결정 기록)

| 항목 | 1단계 결정 |
|------|------------|
| 송출 | 기본 `theme`, `message` 선택 가능 |
| DB | 미사용 |
| 인증 | `API_KEY` 비우면 공개 |
| 송출 이력 | `SEND_LOG_PATH` JSONL (선택) |
