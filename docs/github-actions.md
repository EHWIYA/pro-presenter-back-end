# GitHub Actions + NAS 스크립트

## 포트 (8000 vs 8003)

| 구분 | 포트 |
|------|------|
| Docker 이미지·컨테이너 내부 | **8000** (`api/Dockerfile`) |
| NAS·로컬 호스트에서 curl | **8003** (`8003:8000` 포트 매핑) |

불일치가 아니라 **호스트:컨테이너 매핑**입니다. NAS 문서·`deploy.sh` health check는 **8003** 이 맞습니다.

## 역할 분담

| 위치 | 하는 일 | 시간 |
|------|---------|------|
| **GHA** | pytest, 이미지 build·push | 수 분 (캐시) |
| **GHA Deploy** | Tailscale join → SSH → `deploy.sh` | **수십 초** |
| **NAS** | `docker pull`, compose, health | NAS CPU·디스크 |

배포마다 compose scp·긴 inline 스크립트 **없음**.

## 흐름

```
push main → CI: test → publish (GHCR :main, :sha-xxx)
         → Deploy NAS: ssh …/bin/deploy.sh ghcr.io/owner/repo:main
```

## push 후 추적 (Cursor 에이전트)

- 규칙: `.cursor/rules/gha-post-push-watch.mdc`
- 스크립트: `.\.cursor\scripts\gha_watch.ps1` (또는 `python .cursor/scripts/gha_watch.py`)

실패 job 로그 API 다운로드(선택):

```powershell
$env:GITHUB_TOKEN = "ghp_..."   # repo Actions read 권한, 커밋 금지
.\.cursor\scripts\gha_watch.ps1
```

분류: **backend** (CI test/publish) · **server** (Deploy NAS/SSH) · **both**

## NAS 1회 준비

```bash
# 개발 PC에서 (api/bin·compose 전송)
NAS_SSH=iwh@100.x.x.x NAS_DEPLOY_PATH=/home/iwh/pro-presenter/api \
  ./ops/bin/install-live-remote.sh

# NAS에서
cd /home/iwh/pro-presenter/api
./bin/setup-nas.sh
# .env, venues.json, data/bible-krv.json 편집
```

`api/bin` 수정 후에는 `install-live-remote.sh` 만 다시 실행.

## NAS 일상 명령

```bash
./bin/deploy.sh ghcr.io/OWNER/REPO:main   # 수동 배포
./bin/probe-venue.sh main
./bin/probe-all-venues.sh
```

## GitHub Secrets

| Secret | 필수 | 담당 |
|--------|------|------|
| `TS_AUTH_KEY` | ✅ (B-2) | Tailscale reusable auth key |
| `NAS_HOST` | ✅ | 서버 |
| `NAS_USER` | ✅ | 서버 |
| `NAS_SSH_KEY` | ✅ | 서버 |
| `NAS_DEPLOY_PATH` | 기본 `/home/iwh/pro-presenter/api` | 서버 |
| `NAS_SSH_PORT` | 선택 | 서버 |

설정 절차: **`docs/GHA-DEPLOY-B2.md`**

Private GHCR: NAS `api/.env` 에 `GHCR_USER`, `GHCR_TOKEN` (GHA Secret 불필요).

## CI 파일

- `.github/workflows/ci.yml` — test + publish
- `.github/workflows/deploy-nas.yml` — SSH → `deploy.sh`
