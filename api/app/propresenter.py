"""ProPresenter HTTP API 클라이언트 (NAS → 현장 PC)."""

from __future__ import annotations

import copy
import json
from typing import Any
from urllib.parse import quote

import httpx

from app.venues import Venue


class ProPresenterError(Exception):
    def __init__(self, message: str, hint: str | None = None, status_code: int | None = None) -> None:
        super().__init__(message)
        self.hint = hint
        self.status_code = status_code


class ProPresenterClient:
    def __init__(self, venue: Venue, timeout: float) -> None:
        self.venue = venue
        self.timeout = timeout
        self.base = venue.base_url.rstrip("/")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        url = f"{self.base}{path}"
        effective_timeout = self.timeout if timeout is None else timeout
        try:
            async with httpx.AsyncClient(timeout=effective_timeout) as client:
                return await client.request(method, url, json=json_body)
        except httpx.ConnectError as exc:
            raise ProPresenterError(
                "현장 ProPresenter에 연결할 수 없습니다.",
                hint="Tailscale이 offline이거나 ProPresenter/방화벽이 포트를 막고 있을 수 있습니다.",
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProPresenterError(
                "ProPresenter API 응답 시간이 초과되었습니다.",
                hint=f"포트 {self.venue.pp_port} 와 PP 네트워크 설정을 확인하세요.",
            ) from exc
        except httpx.HTTPError as exc:
            raise ProPresenterError(f"HTTP 통신 오류: {exc}") from exc

    async def get_json(self, path: str, *, timeout: float | None = None) -> Any:
        response = await self._request("GET", path, timeout=timeout)
        if response.status_code >= 400:
            raise _http_error(response, path)
        if not response.content:
            return {}
        return response.json()

    async def put_json(self, path: str, body: Any) -> Any:
        response = await self._request("PUT", path, json_body=body)
        if response.status_code >= 400:
            raise _http_error(response, path)
        if not response.content:
            return {}
        try:
            return response.json()
        except json.JSONDecodeError:
            return {}

    async def post_json(self, path: str, body: Any | None = None) -> Any:
        response = await self._request("POST", path, json_body=body)
        if response.status_code >= 400:
            raise _http_error(response, path)
        if not response.content:
            return {}
        try:
            return response.json()
        except json.JSONDecodeError:
            return {}

    async def probe(self) -> dict[str, Any]:
        response = await self._request("GET", "/v1/presentation/current")
        return {"status_code": response.status_code, "ok": response.status_code == 200}

    async def resolve_theme_route(
        self,
        theme_id: str | None,
        theme_slide_id: str,
        *,
        slide_uuid: str | None = None,
    ) -> tuple[str, str]:
        """theme/slide 경로 탐색. slide_uuid 가 있으면 GET 본문 UUID 로 검증."""
        candidates: list[tuple[str, str]] = []
        if theme_id:
            candidates.append((theme_id, theme_slide_id))
        if slide_uuid:
            candidates.extend(
                [
                    ("Black Box", slide_uuid),
                    ("Black Box", "Two Lines"),
                    ("Black Box", "0"),
                ]
            )

        catalog = await self.get_json("/v1/themes")
        for group in catalog.get("groups") or []:
            for theme in group.get("themes") or []:
                tid = theme.get("id", {})
                tname = str(tid.get("name") or "")
                tidx = str(tid.get("index", 0))
                for slide in theme.get("slides") or []:
                    sid = slide.get("id", {})
                    if slide_uuid and sid.get("uuid") != slide_uuid:
                        continue
                    sname = str(sid.get("name") or "")
                    sidx = str(sid.get("index", 0))
                    for th in (tname, tidx):
                        for sl in (str(sid.get("uuid") or ""), sname, sidx):
                            if th and sl:
                                candidates.append((th, sl))

        seen: set[tuple[str, str]] = set()
        for th, sl in candidates:
            if (th, sl) in seen:
                continue
            seen.add((th, sl))
            for path in _theme_slide_paths(th, sl):
                resp = await self._request("GET", path)
                if resp.status_code >= 400:
                    continue
                if slide_uuid:
                    body = resp.json()
                    uid = (body.get("id") or {}).get("uuid", "")
                    if uid != slide_uuid:
                        continue
                return th, sl

        raise ProPresenterError(
            "테마 슬라이드 API 경로를 찾지 못했습니다 (Lyric Styles/Black Box 등 그룹 테마는 PP API 미지원일 수 있음).",
            hint="PP에서 루트 테마로 옮기거나, test 프레젠테이션 슬라이드·message 방식을 검토하세요.",
        )

    async def send_verse_theme(
        self,
        theme_id: str | None,
        theme_slide_id: str,
        title: str,
        lines: list[str],
        *,
        library_id: str | None,
        presentation_id: str | None,
        slide_uuid: str | None = None,
    ) -> None:
        th, sl = await self.resolve_theme_route(
            theme_id, theme_slide_id, slide_uuid=slide_uuid
        )
        slide_body: Any | None = None
        last_error: ProPresenterError | None = None

        for path in _theme_slide_paths(th, sl):
            try:
                slide_body = await self.get_json(path)
                break
            except ProPresenterError as exc:
                last_error = exc
        if slide_body is None:
            raise last_error or ProPresenterError("테마 슬라이드를 읽지 못했습니다.")

        updated = patch_slide_texts(slide_body, [title, lines[0], lines[1]])
        put_ok = False
        for path in _theme_slide_paths(th, sl):
            try:
                await self.put_json(path, updated)
                put_ok = True
                break
            except ProPresenterError as exc:
                last_error = exc
        if not put_ok:
            raise last_error or ProPresenterError("테마 슬라이드 PUT에 실패했습니다.")

        if library_id and presentation_id:
            await self.trigger_library_presentation(library_id, presentation_id)

    async def trigger_library_presentation(
        self,
        library_id: str,
        presentation_id: str,
    ) -> None:
        paths = [
            f"/v1/library/{library_id}/{presentation_id}/trigger",
            f"/v1/library/{library_id}/{presentation_id}/0/trigger",
        ]
        for path in paths:
            try:
                resp = await self._request("GET", path)
                if resp.status_code < 400:
                    return
            except ProPresenterError:
                continue
        raise ProPresenterError(
            "프레젠테이션 트리거에 실패했습니다.",
            hint="PP_LIBRARY_ID, PP_PRESENTATION_ID 를 확인하세요.",
        )

    async def send_verse_message(self, message_id: str, title: str, lines: list[str]) -> None:
        path = f"/v1/message/{message_id}"
        current = await self.get_json(path)
        updated = patch_message_text(current, title, lines)
        await self.put_json(path, updated)
        await self.post_json(f"/v1/message/{message_id}/trigger", {})


def _theme_slide_paths(theme_id: str, theme_slide_id: str) -> list[str]:
    tid = quote(str(theme_id), safe="")
    tsid = quote(str(theme_slide_id), safe="")
    return [
        f"/v1/theme/{tid}/slides/{tsid}",
        f"/v1/themes/{tid}/slides/{tsid}",
    ]


def patch_slide_texts(body: Any, texts: list[str]) -> Any:
    cloned = copy.deepcopy(body)
    slots = _collect_text_slots(cloned)
    for idx, value in enumerate(texts):
        if idx >= len(slots):
            break
        parent, key = slots[idx]
        parent[key] = value
    return cloned


def patch_message_text(body: Any, title: str, lines: list[str]) -> Any:
    cloned = copy.deepcopy(body)
    combined = "\n".join([title, *lines]).strip()
    slots = _collect_text_slots(cloned)
    if slots:
        parent, key = slots[0]
        parent[key] = combined
        if len(slots) > 1:
            parent2, key2 = slots[1]
            parent2[key2] = lines[0] if lines else ""
        if len(slots) > 2:
            parent3, key3 = slots[2]
            parent3[key3] = lines[1] if len(lines) > 1 else ""
    elif isinstance(cloned, dict):
        cloned["text"] = combined
    return cloned


def _collect_text_slots(node: Any, path: str = "") -> list[tuple[Any, str]]:
    results: list[tuple[Any, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            key_lower = key.lower()
            sub_path = f"{path}.{key}" if path else key
            if isinstance(value, str) and _is_text_key(key_lower):
                results.append((node, key))
            elif isinstance(value, (dict, list)):
                results.extend(_collect_text_slots(value, sub_path))
    elif isinstance(node, list):
        for item in node:
            results.extend(_collect_text_slots(item, path))
    return results


def _is_text_key(key: str) -> bool:
    markers = ("text", "token", "content", "string", "caption", "title", "body")
    return any(m in key for m in markers)


def _http_error(response: httpx.Response, path: str) -> ProPresenterError:
    hint = None
    if response.status_code in (502, 503, 504):
        hint = "ProPresenter API 게이트웨이 오류 — PP 재시작 또는 네트워크 확인"
    elif response.status_code == 404:
        hint = f"경로를 찾을 수 없음: {path} (PP 버전/API 경로 확인)"
    detail = response.text[:300] if response.text else ""
    return ProPresenterError(
        f"ProPresenter API 오류 HTTP {response.status_code}: {detail}",
        hint=hint,
        status_code=response.status_code,
    )
