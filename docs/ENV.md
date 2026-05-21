# 환경 변수

`.env` 는 git에 포함되지 않습니다. 새 환경은 아래 표를 보고 `api/.env`, `live/.env` 를 직접 만듭니다.

## api/.env (로컬 개발)

| 변수 | 예시 |
|------|------|
| `VENUES_JSON_PATH` | `../live/venues.json` |
| `BIBLE_JSON_PATH` | `data/bible-krv.sample.json` |
| `PP_SEND_METHOD` | `theme` \| `message` |
| `PP_THEME_ID` | Black Box 테마 UUID |
| `PP_THEME_SLIDE_ID` | Two Lines 슬라이드 UUID |
| `PP_LIBRARY_ID` | Default Library UUID |
| `PP_PRESENTATION_ID` | test 프레젠테이션 UUID |

## live/.env (NAS)

| 변수 | 예시 |
|------|------|
| `PP_API_IMAGE` | `ghcr.io/ehwiya/pro-presenter-back-end:main` |
| `GHCR_USER` / `GHCR_TOKEN` | private GHCR 시 |
| `VENUES_JSON_PATH` | `/live/venues.json` |
| `BIBLE_JSON_PATH` | `/app/data/bible-krv.json` |

## NAS 포트

- 컨테이너 API: **8000** (이미지 기본)
- 호스트 접속: **8003** (`live/docker-compose.yml` → `127.0.0.1:8003:8000`)
- `/health`·`/venues`: `http://127.0.0.1:8003/...`
- `/health` 정상: `live/data/bible-krv.json` 실데이터 (`./bin/fetch-bible-krv.sh`)

서버 메일 별칭: `PP_PRESENTATION_UUID` → `PP_PRESENTATION_ID`, `PP_DOCUMENT_UUID` → `PP_LIBRARY_ID`, `PP_ACTION_UUID` → `PP_THEME_SLIDE_ID`
