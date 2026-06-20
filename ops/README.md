# NAS 운영 파일 (`ops/`)

레포의 `ops/` 는 **샘플·스키마 문서** 역할입니다. NAS 운영 정본은 서버팀이 관리하는 `~/pro-presenter/live/venues.json` 입니다.

## 배포 경로

| 환경 | 경로 |
|------|------|
| NAS 운영 | `/home/iwh/pro-presenter/live` |
| GHA 기본 `NAS_DEPLOY_PATH` | `/home/iwh/pro-presenter/live` |

```bash
cd /home/iwh/pro-presenter/live
./bin/deploy.sh ghcr.io/ehwiya/pro-presenter-back-end:main
curl -s http://127.0.0.1:8003/health
```

## venues.json 스키마

| 필드 | 필수 | 설명 |
|------|------|------|
| `id` | ✅ | venue 식별자 (예: `hwiya-pc`) |
| `name` | | 표시 이름 |
| `tailscale_ip` | ✅ | Tailscale 100.x IP |
| `pp_port` | ✅ | ProPresenter REST 포트 (기본 12135) |
| `agent_port` | | 현장 에이전트 포트 (기본 8787) |
| `agent_base_url` | | IP 대신 전체 URL override |
| `agent_key` | | heartbeat `X-Agent-Key` (미설정 시 `AGENT_HEARTBEAT_KEY`) |
| `pp_library_name` | | PP `/v1/libraries` 의 **library name** (`.pro` 파일명 아님) |
| `pp_library_id` | | optional — stale UUID면 짧은 probe 후 이름 fallback |
| `pp_theme_id` / `pp_theme_slide_id` | | 레거시 theme 송출용 |
| `pp_presentation_id` | | 기본 프레젠테이션 UUID |
| `enabled` | | `false` 시 API에서 비활성 |

### pp_library_name vs 프레젠테이션 파일명

현장 PP 라이브러리명은 `예배`, `말씀`, `찬양` 등입니다. `worship-2` 는 **프레젠테이션 파일명**이지 library name 이 아닙니다.

`library_resolve.py` 동작:

1. `pp_library_id` 가 있으면 짧은 probe (3s) → reachable 이면 사용
2. 아니면 `pp_library_name` 으로 `/v1/libraries` 카탈로그 매칭
3. fallback: `PP_LIBRARY_NAME_DEFAULT` env (기본 `worship-2`)

### 예시 (hwiya-pc 실측)

```json
{
  "id": "hwiya-pc",
  "tailscale_ip": "100.99.47.84",
  "pp_port": 12135,
  "agent_port": 8787,
  "pp_library_name": "말씀",
  "enabled": true
}
```

## probe

```bash
./bin/probe-venue.sh hwiya-pc
./bin/probe-all-venues.sh
```
