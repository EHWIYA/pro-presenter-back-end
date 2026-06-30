"""NAS → 현장 ProPresenter Agent (build / trigger) 프록시."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import Settings
from app.venues import Venue


class WorshipError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.hint = hint


def text_to_reference(text: str) -> str:
    """PWA `text` → 에이전트 `reference` (첫 비어 있지 않은 줄)."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    stripped = text.strip()
    if not stripped:
        raise WorshipError("text가 비어 있습니다.", status_code=400)
    return stripped


def agent_port_for(venue: Venue, settings: Settings) -> int:
    if venue.agent_port is not None:
        return venue.agent_port
    return settings.agent_port


def agent_base_url(venue: Venue, settings: Settings) -> str:
    if venue.agent_base_url:
        return venue.agent_base_url.rstrip("/")
    port = agent_port_for(venue, settings)
    return f"http://{venue.tailscale_ip}:{port}"


def build_song_agent_body(
    *,
    song_title: str,
    build_mode: str,
    sections: list[dict[str, Any]],
    source_song_id: str | None = None,
) -> dict[str, Any]:
    """PWA camelCase → 에이전트 snake_case."""
    body: dict[str, Any] = {
        "song_title": song_title,
        "build_mode": build_mode,
        "sections": [
            {
                "type": section["type"],
                "label": section["label"],
                "lines": section["lines"],
            }
            for section in sections
        ],
    }
    if source_song_id:
        body["source_song_id"] = source_song_id
    return body


def build_agent_body(
    reference: str,
    settings: Settings,
    *,
    auto_trigger: bool | None = None,
    build_mode: str | None = None,
    group_theme_key: str | None = None,
) -> dict[str, Any]:
    return {
        "reference": reference,
        "group_theme_key": group_theme_key or settings.agent_group_theme_key,
        "build_mode": build_mode or settings.agent_build_mode,
        "auto_trigger": settings.agent_auto_trigger if auto_trigger is None else auto_trigger,
        "library_category": settings.agent_library_category,
    }


def resolve_build_reference(*, reference: str | None, text: str | None) -> str:
    """PWA `reference` 또는 레거시 `text` → 에이전트 reference."""
    if reference and reference.strip():
        return reference.strip()
    if text is not None:
        return text_to_reference(text)
    raise WorshipError("reference 또는 text가 필요합니다.", status_code=400)


async def _agent_post(
    venue: Venue,
    settings: Settings,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = agent_base_url(venue, settings).rstrip("/")
    url = f"{base}{path}"
    timeout = settings.agent_http_timeout_sec
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=json_body)
    except httpx.ConnectError as exc:
        raise WorshipError(
            "현장 에이전트에 연결할 수 없습니다.",
            hint=(
                "Tailscale offline, 에이전트 미기동, 또는 방화벽이 "
                f"포트 {agent_port_for(venue, settings)} 을 막고 있을 수 있습니다."
            ),
        ) from exc
    except httpx.TimeoutException as exc:
        raise WorshipError(
            "에이전트 응답 시간이 초과되었습니다.",
            hint=f"agent_port={agent_port_for(venue, settings)} 및 현장 PC 상태를 확인하세요.",
        ) from exc
    except httpx.HTTPError as exc:
        raise WorshipError(f"에이전트 HTTP 통신 오류: {exc}") from exc

    if response.status_code >= 400:
        detail = _response_detail(response)
        raise WorshipError(
            detail,
            status_code=response.status_code,
            hint=f"agent URL: {url}",
        )

    if not response.content:
        return {"ok": True}
    try:
        data = response.json()
    except json.JSONDecodeError:
        return {"ok": True, "raw": response.text}
    if isinstance(data, dict):
        return data
    return {"ok": True, "data": data}


def _response_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except json.JSONDecodeError:
        return response.text or f"HTTP {response.status_code}"
    if isinstance(body, dict):
        if isinstance(body.get("detail"), str):
            return body["detail"]
        if isinstance(body.get("message"), str):
            return body["message"]
        return json.dumps(body, ensure_ascii=False)
    return str(body)


async def worship_build(
    venue: Venue,
    settings: Settings,
    *,
    reference: str | None = None,
    text: str | None = None,
    auto_trigger: bool | None = None,
    build_mode: str | None = None,
    group_theme_key: str | None = None,
) -> dict[str, Any]:
    resolved = resolve_build_reference(reference=reference, text=text)
    body = build_agent_body(
        resolved,
        settings,
        auto_trigger=auto_trigger,
        build_mode=build_mode,
        group_theme_key=group_theme_key,
    )
    result = await _agent_post(venue, settings, "/build", json_body=body)
    if "reference" not in result:
        result = {**result, "reference": resolved}
    return result


async def worship_trigger(
    venue: Venue,
    settings: Settings,
    index: int,
) -> dict[str, Any]:
    return await _agent_post(venue, settings, f"/trigger?index={index}")


async def worship_build_song(
    venue: Venue,
    settings: Settings,
    *,
    song_title: str,
    build_mode: str,
    sections: list[dict[str, Any]],
    source_song_id: str | None = None,
) -> dict[str, Any]:
    if not sections:
        raise WorshipError("sections가 비어 있습니다.", status_code=400)
    body = build_song_agent_body(
        song_title=song_title,
        build_mode=build_mode,
        sections=sections,
        source_song_id=source_song_id,
    )
    result = await _agent_post(venue, settings, "/build-song", json_body=body)
    if "song_title" not in result:
        result = {**result, "song_title": song_title}
    return result
