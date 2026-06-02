# 성경 데이터

| 파일 | 용도 |
|------|------|
| `bible-krv.sample.json` | repo 포함 샘플 (요 3:16, 창 1:1) — CI·로컬 기본 |
| `bible-krv.json` | 운영용 전체 개역개정 (git 제외, NAS·로컬에 배치) |

## 전체 성경 생성

1. [thiagobodruk/bible](https://github.com/thiagobodruk/bible) 등에서 `ko_ko.json` 다운로드  
2. 변환:

```bash
cd api
python scripts/build_bible_json.py -i /path/to/ko_ko.json -o data/bible-krv.json
```

NAS: `ops/data/bible-krv.json` 에 복사 후 compose 볼륨 마운트.
