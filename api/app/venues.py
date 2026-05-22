"""live/venues.json 로드 및 ProPresenter 연결 점검."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings


class VenueError(Exception):
    """현장(venue) 설정 오류."""


@dataclass(frozen=True)
class Venue:
    id: str
    name: str
    tailscale_ip: str
    pp_port: int
    enabled: bool
    tailscale_hostname: str | None = None
    agent_port: int | None = None
    pp_theme_id: str | None = None
    pp_theme_slide_id: str | None = None
    pp_library_id: str | None = None
    pp_presentation_id: str | None = None
    pp_message_id: str | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.tailscale_ip}:{self.pp_port}"


def load_venues(path: Path) -> list[Venue]:
    if not path.is_file():
        raise VenueError(f"venues 설정 파일이 없습니다: {path}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    venues_raw = data.get("venues", [])
    venues: list[Venue] = []
    for item in venues_raw:
        venues.append(
            Venue(
                id=str(item["id"]),
                name=str(item.get("name", item["id"])),
                tailscale_ip=str(item["tailscale_ip"]),
                pp_port=int(item["pp_port"]),
                enabled=bool(item.get("enabled", True)),
                tailscale_hostname=item.get("tailscale_hostname"),
                agent_port=int(item["agent_port"]) if item.get("agent_port") is not None else None,
                pp_theme_id=item.get("pp_theme_id"),
                pp_theme_slide_id=item.get("pp_theme_slide_id") or item.get("pp_action_uuid"),
                pp_library_id=item.get("pp_library_id") or item.get("pp_document_uuid"),
                pp_presentation_id=item.get("pp_presentation_id") or item.get("pp_presentation_uuid"),
                pp_message_id=item.get("pp_message_id"),
            )
        )
    return venues


class VenueRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._venues: list[Venue] | None = None

    def reload(self) -> None:
        self._venues = None

    def all(self) -> list[Venue]:
        if self._venues is None:
            self._venues = load_venues(self.path)
        return self._venues

    def get(self, venue_id: str) -> Venue:
        for venue in self.all():
            if venue.id == venue_id:
                if not venue.enabled:
                    raise VenueError(f"비활성화된 현장입니다: {venue_id}")
                return venue
        raise VenueError(f"등록되지 않은 현장입니다: {venue_id}")

    def list_public(self) -> list[dict[str, Any]]:
        return [
            {
                "id": v.id,
                "name": v.name,
                "tailscale_ip": v.tailscale_ip,
                "tailscale_hostname": v.tailscale_hostname,
                "pp_port": v.pp_port,
                "enabled": v.enabled,
            }
            for v in self.all()
        ]


def pp_ids_for_venue(venue: Venue, settings: Settings) -> dict[str, str | None]:
    return {
        "theme_id": venue.pp_theme_id or settings.pp_theme_id,
        "theme_slide_id": venue.pp_theme_slide_id or settings.pp_theme_slide_id,
        "library_id": venue.pp_library_id or settings.pp_library_id,
        "presentation_id": venue.pp_presentation_id or settings.pp_presentation_id,
        "message_id": venue.pp_message_id or settings.pp_message_id,
    }


async def probe_venue(
    venue: Venue,
    timeout: float,
) -> dict[str, Any]:
    url = f"{venue.base_url}/v1/presentation/current"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
    except httpx.ConnectError:
        return {
            "ok": False,
            "venue_id": venue.id,
            "url": url,
            "hint": "Tailscale 연결 불가 또는 ProPresenter가 꺼져 있음 (ConnectError)",
        }
    except httpx.TimeoutException:
        return {
            "ok": False,
            "venue_id": venue.id,
            "url": url,
            "hint": "요청 시간 초과 — 방화벽 또는 PP API 미응답",
        }
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "venue_id": venue.id,
            "url": url,
            "hint": f"HTTP 오류: {exc}",
        }

    ok = response.status_code == 200
    hint = None
    if not ok:
        if response.status_code in (502, 503, 504):
            hint = "ProPresenter API가 일시적으로 응답하지 않음"
        else:
            hint = f"HTTP {response.status_code} — 포트({venue.pp_port}) 또는 API 경로 확인"

    return {
        "ok": ok,
        "venue_id": venue.id,
        "url": url,
        "status_code": response.status_code,
        "hint": hint,
    }
