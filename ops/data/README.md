# pro-presenter-data (NAS 마운트)

BFF 곡 카탈로그 정본. `Libraries/{찬양,찬송가,성가곡}/*.pro` 를 스캔합니다.

## 최초 준비 (NAS)

```bash
cd /home/iwh/pro-presenter/live/data
git clone --depth 1 https://github.com/EHWIYA/pro-presenter-data.git pro-presenter-data
```

이후 `launch-worship` / 현장 PC와 동일 repo. 갱신:

```bash
cd pro-presenter-data && git pull --ff-only
```

compose: `./data/pro-presenter-data` → 컨테이너 `/app/data/pro-presenter-data`

## 로컬·CI

fixture: `api/data/fixtures/pro-presenter-data/` (pytest 기본)

계약: `docs/handoff/song-catalog.md`
