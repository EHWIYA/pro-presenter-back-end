# GET `/venues/{venue_id}/presentations`

PWA 홈 화면용 — 현장 ProPresenter 라이브러리의 프레젠테이션·그룹·슬라이드 **수치만** 반환합니다.

## 인증

`probe` · `worship`과 동일. `X-API-Key` 없음 (레거시 `verse/*`만 `API_KEY` 설정 시 필요).

## 데이터 소스

NAS → `venues.json`의 `tailscale_ip` + `pp_port` → ProPresenter REST API (probe와 동일 경로).

| PP API | 용도 |
|--------|------|
| `GET /v1/libraries` | 이름→UUID 해석 (짧은 타임아웃, 기본 5s) |
| `GET /v1/library/{library_id}` | 프레젠테이션 항목 (`uuid`, `name`) |
| `GET /v1/presentation/{uuid}` | 그룹·슬라이드 수 (`groups[].name`, `slides` 길이) |

라이브러리 UUID는 **`pp_library_name`(기본 `worship-2`)** 으로 `/v1/libraries`에서 찾습니다.  
`pp_library_id`가 있으면 짧은 probe(기본 3s)로 먼저 시도하고, hang·404·타임아웃 시 이름으로 fallback 합니다 (stale UUID 30s 502 방지).

## 응답 (200)

```json
{
  "venue_id": "test",
  "presentations": [
    {
      "id": "69796aa8-6b79-4688-b266-467e79bb3bde",
      "label": "주일 1부",
      "group_count": 3,
      "slide_count": 42,
      "groups": [
        { "label": "찬양", "slide_count": 8 },
        { "label": "말씀", "slide_count": 24 },
        { "label": "봉헌", "slide_count": 10 }
      ]
    }
  ]
}
```

### 필드

| 필드 | 설명 |
|------|------|
| `presentations[].id` | PP 프레젠테이션 UUID (`library` trigger 경로와 동일) |
| `presentations[].label` | PP `name` (라이브러리 항목 `name` 폴백) |
| `groups[].label` | PP slide group `name` (구버전 `groupName` 호환) |
| `groups[].slide_count` | 해당 그룹 `slides` 배열 길이 |
| `slide_count` | 모든 그룹 슬라이드 수 합 |
| `group_count` | `groups` 길이 |

슬라이드 본문·이미지·미리보기는 포함하지 않습니다.

## 오류

| HTTP | 조건 |
|------|------|
| 404 | `venue_id` 미등록·비활성 |
| 502 | PP 연결 실패·API 오류 (`detail.message`, `detail.hint`) |

## 빈 목록

라이브러리에 항목이 없거나 PP가 빈 배열을 주면 **`200` + `presentations: []`** (4xx 아님).

## 확인

```bash
curl -s https://pro-api.iwhya.kr/venues/main/presentations
curl -s http://127.0.0.1:8003/venues/main/presentations
```

(현장 PP API가 켜져 있어야 200·목록이 채워집니다.)

## PP 매핑 (협의 답)

| 질문 | 답 |
|------|-----|
| 경로 | **`GET /venues/{venue_id}/presentations`** 확정 |
| `id` 형식 | 라이브러리 항목 **`uuid`** (trigger의 `presentation_id`와 동일) |
| group 매핑 | PP REST `groups[].name` + `slides` 길이. 구 REST/WS는 `presentationSlideGroups` / `groupName` / `groupSlides` 폴백 |
| 빈 목록 | `200`, `presentations: []` |
| CORS | `CORS_ORIGINS`에 `https://pro-app.iwhya.kr` 포함 (NAS `ops/.env`) |
