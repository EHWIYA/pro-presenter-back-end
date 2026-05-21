# 서버팀 회신 메일 (복사용)

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
