# 서버팀 회신 메일 (복사용)

## PWA 미니제어 API 계약 재확인 회신 (발송용)

**제목:** Re: [재확인] Pro Presenter 모바일 PWA API 반영/배포 기준 SHA 공유

---

안녕하세요,

재확인 요청 주신 항목 기준으로 백엔드 `main` 브랜치 최신 반영분을 공유드립니다.

### 1) 배포 기준 브랜치 / 커밋 SHA

- 브랜치: `main`
- 기준 SHA: `7d8b52e` (`feat : PWA 미니제어 API 계약 확정`)

### 2) 반영 API 계약 문서 / PR

- 계약 반영 커밋: `7d8b52e`
- 관련 문서: `README.md` API 표, `docs/api-presentations.md`

### 3) 운영 기준 확인 가능 엔드포인트 (최종 스펙)

- `GET /health`
- `GET /api/v1/books`
- `GET /venues`
- `GET /venues/{venue_id}/probe`
- `GET /venues/status`
- `GET /venues/{venue_id}/presentations`
- `GET /venues/{venue_id}/presentation/current`
- `POST /venues/{venue_id}/worship/build`
- `POST /venues/{venue_id}/worship/trigger`
- `POST /api/v1/verse/parse` (레거시)
- `POST /api/v1/verse/send` (레거시)

요청 주신 `GET /venues/status`, `GET /venues/{venue_id}/presentation/current` 두 경로는 위 기준 SHA에 포함되어 있습니다.

감사합니다.

---

## PWA 홈 presentations API 회신 (발송용)

**제목:** Re: [프론트→백엔드] PWA 홈·프레젠테이션 목록 API 공조 요청

---

안녕하세요,

요청하신 **`GET /venues/{venue_id}/presentations`** 를 `main`에 반영했습니다. 배포 후 아래로 확인 가능합니다.

```bash
curl -s https://pro-api.iwhya.kr/venues/test/presentations
```

### 협의 답변

| 항목 | 내용 |
|------|------|
| 경로 | `GET /venues/{venue_id}/presentations` |
| 인증 | worship·probe와 동일 (`X-API-Key` 없음) |
| `presentations[].id` | PP 라이브러리 항목 **UUID** (기존 `PP_PRESENTATION_ID` / trigger와 동일) |
| 그룹 매핑 | PP REST `groups[].name` → `label`, `slides` 길이 → `slide_count` (구 API `groupName`/`groupSlides` 폴백) |
| 빈 목록 | **200** + `presentations: []` |
| 소스 범위 | `venues.json`에 `pp_library_id` 있으면 해당 라이브러리만, 없으면 `/v1/libraries` 전체 |
| 스펙 | [`docs/api-presentations.md`](api-presentations.md) |

### 배포

`main` push → CI 성공 후 Deploy NAS → PWA 재빌드 없이 홈 연동 가능합니다.

404·필드 불일치 시 `venue_id`와 응답 JSON 샘플 알려주시면 맞추겠습니다.

감사합니다.

---

## PWA worship 프록시 회신 (발송용)

**제목:** Re: [공조] Pro Presenter — PWA worship 프록시·API Key

---

안녕하세요,

P0 요청 반영해 `main` push 예정입니다. 배포 run URL은 push 후 공유드리겠습니다.

### 체크리스트

| 항목 | 상태 |
|------|------|
| `POST /venues/{id}/worship/build` · `.../trigger` | **구현 완료** (배포 대기) |
| text vs reference | **pro-api에서 변환** — PWA는 `text`만 전송, NAS→에이전트는 첫 비어 있지 않은 줄을 `reference`로 `POST /build` body에 매핑 |
| 에이전트 포트 | 기본 **8787** (`AGENT_PORT` / `venues.json` `agent_port`). PP API는 기존 `pp_port`·probe와 동일 |
| API_KEY / `X-API-Key` | **미적용** (P1). worship·probe·venues는 키 없이 동작, 레거시 `verse/*`만 `API_KEY` 설정 시 요구 |

### NAS 재확인 (Deploy NAS 성공 후)

```bash
curl -s http://127.0.0.1:8003/health
curl -s -X POST http://127.0.0.1:8003/venues/test/worship/build \
  -H 'Content-Type: application/json' -d '{"text":"마 3:1"}'
curl -s -X POST http://127.0.0.1:8003/venues/test/worship/trigger \
  -H 'Content-Type: application/json' -d '{"index":1}'
```

(현장 에이전트·PP가 켜져 있어야 build/trigger가 200입니다.)

감사합니다.

---

## GHA Deploy NAS 성공 회신 (발송용)

**제목:** Re: [서버/NAS] pro-presenter — GHA CI·Deploy NAS 자동 배포 성공

---

안녕하세요,

회신 주신 Auth key(`TS_AUTH_KEY`)·NAS SSH Secrets 반영 후 `main` push 기준 **GitHub Actions 전 구간 성공** 확인했습니다. 공유 감사합니다.

### GHA 결과 (`a20b136`)

| 워크플로 | 결과 | 링크 |
|----------|------|------|
| **CI** (test + GHCR publish) | success | https://github.com/EHWIYA/pro-presenter-back-end/actions/runs/26201824724 |
| **Deploy NAS** (Tailscale → SSH → `deploy.sh`) | success | https://github.com/EHWIYA/pro-presenter-back-end/actions/runs/26201851416 |

- 이미지: `ghcr.io/ehwiya/pro-presenter-back-end:main`
- Deploy: `live/bin/deploy.sh` (B-2 Auth key + 기존 SSH)
- 레포: `deploy-nas.yml` Auth key 방식 반영 완료 (`docs/GHA-DEPLOY-B2.md`)

### NAS 측 확인 요청 (선택)

자동 배포 직후 아래 한 번만 확인해 주시면 이후 개발팀 E2E(`verse/parse`, `verse/send`) 진행하겠습니다.

```bash
curl -s http://127.0.0.1:8003/health
curl -s http://127.0.0.1:8003/venues
```

### 이후 협의 (기존 미완료)

- `live/.env` PP_THEME_ID·PP_* UUID — 송출 테스트 시 값 공유
- 현장 `venues.json` / ProPresenter probe

추가 이슈 있으면 Deploy NAS run URL·NAS 로그 알려 주세요.

감사합니다.

---

## 최신 회신 (A 완료 + B-2 Tailscale)

**제목:** Re: NAS 배포 확인 — 포트 정리·bible-krv·GHA Tailscale Secrets

---

안녕하세요,

수동 배포·`8003→8000` compose·`/venues` 확인 감사합니다.

### 포트 (8000 vs 8003) — 불일치 아님

| | 포트 |
|--|------|
| GHCR 이미지·컨테이너 **내부** | **8000** |
| NAS 호스트에서 curl / health | **8003** (`127.0.0.1:8003:8000` 매핑) |

레포 `live/docker-compose.yml`·`deploy.sh` health check는 **8003** 기준이 맞습니다.

### `/health` — bible-krv.json

`/venues` OK, `/health`는 **`live/data/bible-krv.json` 전체 66권** 필요합니다.

```bash
cd /home/iwh/pro-presenter/live
./bin/fetch-bible-krv.sh
./bin/deploy.sh ghcr.io/ehwiya/pro-presenter-back-end:main
curl -s http://127.0.0.1:8003/health
```

### GHA 자동 배포 — B-2 Tailscale (Secrets는 서버/Tailscale 측)

Hosted runner가 `100.x`에 SSH 불가하여, Deploy 워크플로에 **Tailscale ephemeral** 단계를 넣었습니다.  
NAS에는 runner 없이 기존 `deploy.sh`만 유지합니다.

**GitHub repo Secrets** (상세: `docs/GHA-DEPLOY-B2.md`, 로컬: `.env.gha`):

| Secret |
|--------|
| `TS_AUTH_KEY` |

Tailscale: reusable auth key (`tskey-auth-...`). ACL에서 CI → NAS(:22).

등록 후 Actions **Deploy NAS** → Run workflow 로 1회 검증 부탁드립니다.

감사합니다.

---

## 이전 초안 (참고)

**제목:** Re: [공조] ProPresenter 백엔드 — 레포 push·GHCR·NAS 반영 요청

---

안녕하세요,

NAS 1회 구성·Secrets·probe 검증 확인했습니다. 백엔드 MVP를 `main`에 올릴 예정이며, 아래를 반영·협조 부탁드립니다.

## 1. GHCR 이미지 (push 후 사용)

```
ghcr.io/ehwiya/pro-presenter-back-end:main
```

- GitHub: https://github.com/EHWIYA/pro-presenter-back-end  
- `main` push 시 GHA가 이미지 push → **Deploy NAS** 워크플로가  
  `/home/iwh/pro-presenter/live/bin/deploy.sh ghcr.io/ehwiya/pro-presenter-back-end:main` 실행합니다.
- 현재 로컬 alias 기동 중이시면, **첫 GHA Deploy 성공 후** 위 이미지로 전환해 주세요.

## 2. 성경 `data/bible-krv.json`

플레이스홀더 대신 **전체 66권** 반영 방법 (택1):

**A) NAS에서 생성 (권장)**

```bash
cd /home/iwh/pro-presenter/live
# bin 최신화 후 (개발팀 install-live-remote.sh 전송)
./bin/fetch-bible-krv.sh
docker compose restart   # 또는 deploy.sh 재실행
```

**B) 개발 PC에서 scp**

```bash
scp api/data/bible-krv.json iwh@100.88.40.125:/home/iwh/pro-presenter/live/data/
```

## 3. `live/.env` PP 설정 (변수명 매핑)

서버 메일의 UUID 명칭과 백엔드 키 매핑입니다. **값은 PP Swagger에서 Black Box 테마 ID 포함 확인 부탁드립니다.**

| 서버/메일 | NAS `.env` 키 | 비고 |
|-----------|---------------|------|
| `PP_THEME_ID` | `PP_THEME_ID` | 테마(부모) UUID — **필수, 현장 확인** |
| `PP_ACTION_UUID` | `PP_THEME_SLIDE_ID` | Two Lines 슬라이드 `0cdbd9c6-…` |
| `PP_DOCUMENT_UUID` | `PP_LIBRARY_ID` | Default Library `66949390-…` |
| `PP_PRESENTATION_UUID` | `PP_PRESENTATION_ID` | test 프레젠테이션 `69796aa8-…` |

`PP_SEND_METHOD=theme` 유지.

## 4. GHCR private 여부

- 저장소/패키지가 **public**이면 NAS `GHCR_TOKEN` 없이 pull 가능한 경우가 많습니다.
- **private**이면 PAT(`read:packages`)를 `live/.env`에 `GHCR_USER` / `GHCR_TOKEN` 으로 넣어 주세요. 발급 경로 필요 시 공유하겠습니다.

## 5. GHA 배포 1회

`main` push 후 Actions **Deploy NAS** 성공 여부를 알려 주시면, 개발팀에서 `verse/parse`·`verse/send` 연동 테스트를 이어가겠습니다.  
실패 시 Actions 로그(SSH·`deploy.sh`) 공유 부탁드립니다.

감사합니다.

---
