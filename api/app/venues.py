"""ops/venues.json 로드 및 ProPresenter 연결 점검."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
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
    agent_base_url: str | None = None
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
                agent_base_url=item.get("agent_base_url"),
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
    *,
    agent_timeout: float,
    default_agent_port: int,
) -> dict[str, Any]:
    url = f"{venue.base_url}/v1/presentation/current"
    if venue.agent_base_url:
        agent_base = venue.agent_base_url.rstrip("/")
    else:
        agent_port = venue.agent_port if venue.agent_port is not None else default_agent_port
        agent_base = f"http://{venue.tailscale_ip}:{agent_port}"
    agent_health_url = f"{agent_base}/health"
    checked_at = datetime.now(UTC).isoformat()

    agent_reachable = False
    agent_status_code = "unknown"
    agent_message = "에이전트 상태를 확인하지 못했습니다."

    try:
        async with httpx.AsyncClient(timeout=agent_timeout) as client:
            agent_response = await client.get(agent_health_url)
        if agent_response.status_code == 200:
            agent_reachable = True
            agent_status_code = "ok"
            agent_message = "에이전트 연결됨"
        else:
            agent_status_code = "http_status_error"
            agent_message = f"에이전트 HTTP {agent_response.status_code}"
    except httpx.ConnectError:
        agent_status_code = "connect_error"
        agent_message = "에이전트 연결 불가"
    except httpx.TimeoutException:
        agent_status_code = "timeout"
        agent_message = "에이전트 응답 시간 초과"
    except httpx.HTTPError as exc:
        agent_status_code = "http_error"
        agent_message = f"에이전트 통신 오류: {exc}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
    except httpx.ConnectError:
        return {
            "connected": False,
            "venue_id": venue.id,
            "name": venue.name,
            "url": url,
            "status_code": "connect_error",
            "message": "Tailscale 연결 불가 또는 ProPresenter가 꺼져 있습니다.",
            "agent_reachable": agent_reachable,
            "agent_status_code": agent_status_code,
            "agent_message": agent_message,
            "agent_health_url": agent_health_url,
            "checked_at": checked_at,
        }
    except httpx.TimeoutException:
        return {
            "connected": False,
            "venue_id": venue.id,
            "name": venue.name,
            "url": url,
            "status_code": "timeout",
            "message": "요청 시간 초과 - 방화벽 또는 ProPresenter API 미응답",
            "agent_reachable": agent_reachable,
            "agent_status_code": agent_status_code,
            "agent_message": agent_message,
            "agent_health_url": agent_health_url,
            "checked_at": checked_at,
        }
    except httpx.HTTPError as exc:
        return {
            "connected": False,
            "venue_id": venue.id,
            "name": venue.name,
            "url": url,
            "status_code": "http_error",
            "message": f"HTTP 통신 오류: {exc}",
            "agent_reachable": agent_reachable,
            "agent_status_code": agent_status_code,
            "agent_message": agent_message,
            "agent_health_url": agent_health_url,
            "checked_at": checked_at,
        }

    connected = response.status_code == 200
    message = "연결됨"
    status_code = "ok"
    if not connected:
        if response.status_code in (502, 503, 504):
            status_code = "gateway_error"
            message = "ProPresenter API가 일시적으로 응답하지 않습니다."
        else:
            status_code = "http_status_error"
            message = f"HTTP {response.status_code} - 포트({venue.pp_port}) 또는 API 경로를 확인하세요."

    return {
        "connected": connected,
        "venue_id": venue.id,
        "name": venue.name,
        "url": url,
        "status_code": status_code,
        "http_status": response.status_code,
        "message": message,
        "agent_reachable": agent_reachable,
        "agent_status_code": agent_status_code,
        "agent_message": agent_message,
        "agent_health_url": agent_health_url,
        "checked_at": checked_at,
    }
