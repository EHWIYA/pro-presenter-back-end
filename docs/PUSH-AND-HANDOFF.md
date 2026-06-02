# push 전·후 체크리스트 (서버 회신 반영)

## 레포·GHCR (push 후 확정)

| 항목 | 값 |
|------|-----|
| GitHub | `https://github.com/EHWIYA/pro-presenter-back-end` |
| GHCR 이미지 | `ghcr.io/ehwiya/pro-presenter-back-end:main` |
| SHA 태그 | `ghcr.io/ehwiya/pro-presenter-back-end:sha-<commit>` |

> GHCR 패키지명은 **소문자**입니다.

## push 직후 (개발)

1. GitHub → Actions → **CI** 성공 (pytest + GHCR push)
2. **Deploy NAS** 자동 실행 또는 수동 Run
3. 실패 시 로그 `deploy.sh` 구간을 서버팀에 전달

## push 직후 (서버팀 NAS)

```bash
# 1) ops/bin 동기화 (개발 PC, 1회 또는 bin 변경 시)
NAS_SSH=iwh@100.88.40.125 NAS_DEPLOY_PATH=/home/iwh/pro-presenter/api \
  ./ops/bin/install-live-remote.sh

# 2) 성경 전체 (NAS에서, python3+curl)
cd /home/iwh/pro-presenter/api/ops
./bin/fetch-bible-krv.sh

# 3) GHCR 배포 (GHA 성공 후 또는 수동)
./bin/deploy.sh ghcr.io/ehwiya/pro-presenter-back-end:main

# 4) 검증
curl -s http://127.0.0.1:8003/health
./bin/probe-venue.sh main
```

**또는** 개발 PC에서 성경 파일만 전송:

```bash
scp api/data/bible-krv.json iwh@100.88.40.125:/home/iwh/pro-presenter/api/ops/data/
```

(로컬에서 `api/scripts/build_bible_json.py` 로 생성 — git에는 포함하지 않음)

## ops/.env — PP 변수 (서버팀·PP 담당)

| 서버 메일 명칭 | 이 백엔드 `.env` 키 | 테스트 PC UUID (참고) |
|----------------|---------------------|------------------------|
| `PP_THEME_ID` | `PP_THEME_ID` | Black Box **테마** UUID (Swagger 확인 필요) |
| `PP_ACTION_UUID` | `PP_THEME_SLIDE_ID` | `0cdbd9c6-7ffd-45dc-8bef-fce91f8d9202` |
| `PP_DOCUMENT_UUID` | `PP_LIBRARY_ID` | `66949390-bdcd-43e0-9ed3-1d8af609f5f0` |
| `PP_PRESENTATION_UUID` | `PP_PRESENTATION_ID` | `69796aa8-6b79-4688-b266-467e79bb3bde` |

`venues.json` 에 동일 값을 넣어도 됩니다 (venue별 우선).

## GHCR private

- **Public repo + public package:** NAS `GHCR_TOKEN` 불필요
- **Private package:** NAS `ops/.env` 에 `GHCR_USER`, `GHCR_TOKEN`(read:packages)

## NAS Secrets (등록 완료 — 재확인)

| Secret | 값 |
|--------|-----|
| `NAS_HOST` | `100.88.40.125` |
| `NAS_DEPLOY_PATH` | `/home/iwh/pro-presenter/api` |
| `NAS_USER` | `iwh` |
