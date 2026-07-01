# pro-presenter-data (NAS 마운트)

BFF 곡 카탈로그 정본. `Libraries/{찬양,찬송가,성가곡}/*.pro` 를 스캔합니다.

**운영 데이터는 반드시 GitHub `EHWIYA/pro-presenter-data` 클론이어야 합니다.**  
`api/data/fixtures/pro-presenter-data`(pytest용 5곡)를 이 경로에 복사하면 안 됩니다.

## 동기화 (권장)

```bash
cd /home/iwh/pro-presenter/live
./bin/sync-data-repo.sh
```

`deploy.sh`·`setup-nas.sh`도 배포 시 위 스크립트를 호출합니다.

## 수동 준비

```bash
cd /home/iwh/pro-presenter/live/data
git clone --depth 1 https://github.com/EHWIYA/pro-presenter-data.git pro-presenter-data
```

갱신:

```bash
cd pro-presenter-data && git pull --ff-only
```

compose: `./data/pro-presenter-data` → 컨테이너 `/app/data/pro-presenter-data`

## 현장 PC와의 관계

| 위치 | 용도 |
|------|------|
| NAS `data/pro-presenter-data` | BFF `GET /api/v1/songs` 카탈로그 |
| PC `%USERPROFILE%\Documents\pro-presenter` | 에이전트 런타임 `.pro` (동일 repo, `git pull`로 맞춤) |

계약: `docs/handoff/song-catalog.md`
