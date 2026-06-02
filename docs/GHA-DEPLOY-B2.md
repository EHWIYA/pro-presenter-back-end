# GHA Deploy NAS — B-2 Tailscale (서버·Tailscale 담당)

## 배경

GitHub **hosted runner**는 공인 인터넷에서만 동작합니다. `NAS_HOST`가 Tailscale `100.x` 이면 SSH가 `dial tcp … i/o timeout` 으로 실패합니다.

**해결:** Deploy job에서 **ephemeral Tailscale** 로 tailnet에 잠깐 합류한 뒤, 기존처럼 SSH → `ops/bin/deploy.sh` 한 줄만 실행합니다. NAS에는 runner를 두지 않습니다.

## 포트 (불일치 아님)

| 구분 | 포트 | 설명 |
|------|------|------|
| 컨테이너 / CI 이미지 | **8000** | `api/Dockerfile` `uvicorn --port 8000`, `EXPOSE 8000` |
| NAS·로컬 호스트 | **8003** | `ops/docker-compose.yml` `127.0.0.1:8003:8000` |

NAS에서 `curl http://127.0.0.1:8003/health` 가 맞습니다. 이미지 내부만 8000입니다.

## Tailscale Admin (1회)

1. **태그** `tag:ci` — GHA ephemeral 노드용  
2. **태그** `tag:nas` (권장) — NAS 기기에 부여  
3. **ACL** 예시 (SSH만):

```json
"grants": [
  {
    "src": ["tag:ci"],
    "dst": ["tag:nas"],
    "ip": ["22"]
  }
]
```

4. **Reusable auth key** (OAuth clients 없을 때)  
   - Tailscale Admin → Keys → Generate auth key  
   - Reusable, `tag:ci` (또는 ACL에 맞는 태그)  
   - 로컬 보관: repo 루트 `.env.gha` (`TS_AUTH_KEY=tskey-auth-...`) — git 제외

## GitHub Secrets (repo → Settings → Secrets)

로컬 보관: repo 루트 **`.env.gha`** (git 제외). 아래 이름과 동일하게 GitHub에 등록.

| Secret | 담당 | 설명 |
|--------|------|------|
| `TS_AUTH_KEY` | 서버/Tailscale | Reusable auth key (`tskey-auth-...`) |
| `NAS_HOST` | 기존 | Tailscale IP (예: `100.88.40.125`) |
| `NAS_USER` | 기존 | SSH 사용자 |
| `NAS_SSH_KEY` | 기존 | deploy용 private key |
| `NAS_DEPLOY_PATH` | 기존 | `/home/iwh/pro-presenter/api` |
| `NAS_SSH_PORT` | 선택 | 기본 22 |

Secrets 등록 후 **Actions → Deploy NAS → Run workflow** 로 검증.

## NAS (가벼운 역할 유지)

- GHA runner **설치하지 않음**
- `ops/bin/deploy.sh` + `docker compose` 만 유지
- `/health` 정상: `ops/data/bible-krv.json` 실데이터 필요

```bash
cd /home/iwh/pro-presenter/api/ops
./bin/fetch-bible-krv.sh
./bin/deploy.sh ghcr.io/ehwiya/pro-presenter-back-end:main
curl -s http://127.0.0.1:8003/health | jq .
```

## 흐름

```
CI success → Deploy NAS job
  → tailscale/github-action (tag:ci, ping NAS_HOST)
  → ssh deploy.sh ghcr.io/ehwiya/pro-presenter-back-end:main
```
