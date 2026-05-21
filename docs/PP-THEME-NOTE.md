# PP 테마 API (현장 PC 확인, 2026-05)

- **Two Lines** 슬라이드 UUID: `0cdbd9c6-7ffd-45dc-8bef-fce91f8d9202` (Black Box / Lyric Styles)
- PP 21 REST API는 **Lyric Styles 그룹 안의 Black Box 테마**를 `/v1/theme/...` 로 **직접 수정할 수 없음** (전역 인덱스와 불일치)
- 백엔드 동작:
  1. 테마 경로 자동 탐색 시도
  2. 실패 시 **test 프레젠테이션 library trigger** 만 수행 (`pp_dynamic_text: false`, `pp_warning` 포함)

동적 2줄 송출을 위해 (택1):

1. PP에서 Black Box 레이아웃을 **API 노출되는 루트 테마**로 복제
2. **Message** 레이어 사용 (`PP_SEND_METHOD=message`, message 생성 후 ID 설정)
3. **test** 프레젠테이션 슬라이드 본문을 API 가능한 방식으로 연동 (추후)

`PP_THEME_ID` 는 비워 두고 `PP_THEME_SLIDE_ID=0cdbd9c6-...` 만으로도 탐색을 시도합니다.
