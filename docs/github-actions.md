# GitHub Actions + NAS 스크립트

## 역할 분담

| 위치 | 하는 일 | 시간 |
|------|---------|------|
| **GHA** | pytest, 이미지 build·push | 수 분 (캐시) |
| **GHA Deploy** | SSH 1줄 → `deploy.sh` 호출 | **수 초** |
| **NAS** | `docker pull`, compose, health | NAS CPU·디스크 |

배포마다 compose scp·긴 inline 스크립트 **없음**.

## 흐름

```
push main → CI: test → publish (GHCR :main, :sha-xxx)
         → Deploy NAS: ssh …/bin/deploy.sh ghcr.io/owner/repo:main
```

## NAS 1회 준비

```bash
# 개발 PC에서 (live/bin·compose 전송)
NAS_SSH=iwh@100.x.x.x LIVE_PATH=/home/iwh/pro-presenter/live \
  ./live/bin/install-live-remote.sh

# NAS에서
cd /home/iwh/pro-presenter/live
./bin/setup-nas.sh
# .env, venues.json, data/bible-krv.json 편집
```

`live/bin` 수정 후에는 `install-live-remote.sh` 만 다시 실행.

## NAS 일상 명령

```bash
./bin/deploy.sh ghcr.io/OWNER/REPO:main   # 수동 배포
./bin/probe-venue.sh main
./bin/probe-all-venues.sh
```

## GitHub Secrets

| Secret | 필수 |
|--------|------|
| `NAS_HOST` | ✅ |
| `NAS_USER` | ✅ |
| `NAS_SSH_KEY` | ✅ |
| `NAS_DEPLOY_PATH` | 기본 `/home/iwh/pro-presenter/live` |
| `NAS_SSH_PORT` | 선택 |

Private GHCR: NAS `live/.env` 에 `GHCR_USER`, `GHCR_TOKEN` (GHA Secret 불필요).

## CI 파일

- `.github/workflows/ci.yml` — test + publish
- `.github/workflows/deploy-nas.yml` — SSH → `deploy.sh`
