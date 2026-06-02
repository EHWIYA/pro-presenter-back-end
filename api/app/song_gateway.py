"""NAS BFF → cursor-llm-gateway (찬양 악보 구간 분석)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import Settings


class SongGatewayError(Exception):
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


def _gateway_base(settings: Settings) -> str:
    raw = (settings.llm_gateway_url or "").strip()
    if not raw:
        raise SongGatewayError(
            "LLM 게이트웨이가 설정되지 않았습니다.",
            status_code=503,
            hint="LLM_GATEWAY_URL 환경 변수를 설정하세요.",
        )
    return raw.rstrip("/")


def _gateway_headers(settings: Settings) -> dict[str, str]:
    key = (settings.llm_gateway_api_key or "").strip()
    if not key:
        raise SongGatewayError(
            "LLM 게이트웨이 API 키가 설정되지 않았습니다.",
            status_code=503,
            hint="LLM_GATEWAY_API_KEY 환경 변수를 설정하세요.",
        )
    return {"x-api-key": key}


def _response_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except json.JSONDecodeError:
        return response.text or f"HTTP {response.status_code}"
    if isinstance(body, dict):
        for key in ("detail", "message", "error"):
            val = body.get(key)
            if isinstance(val, str):
                return val
        return json.dumps(body, ensure_ascii=False)
    return str(body)


def _normalize_analyze_response(data: dict[str, Any], *, job_id: str) -> dict[str, Any]:
    """게이트웨이 응답을 PWA 계약(camelCase pollUrl)으로 정규화."""
    out: dict[str, Any] = {
        "jobId": data.get("jobId") or data.get("job_id") or job_id,
        "status": data.get("status", "pending"),
        "pollUrl": f"/api/v1/song/jobs/{job_id}",
    }
    for key, value in data.items():
        if key not in out and key not in ("job_id", "poll_url", "pollUrl"):
            out[key] = value
    return out


async def song_analyze(settings: Settings, body: dict[str, Any]) -> dict[str, Any]:
    base = _gateway_base(settings)
    url = f"{base}/v1/song/analyze"
    headers = _gateway_headers(settings)
    timeout = settings.llm_gateway_timeout_sec
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=body, headers=headers)
    except httpx.ConnectError as exc:
        raise SongGatewayError(
            "LLM 게이트웨이에 연결할 수 없습니다.",
            hint=f"LLM_GATEWAY_URL={base} 및 게이트웨이 기동 여부를 확인하세요.",
        ) from exc
    except httpx.TimeoutException as exc:
        raise SongGatewayError(
            "LLM 게이트웨이 응답 시간이 초과되었습니다.",
            hint=f"timeout={timeout}s",
        ) from exc
    except httpx.HTTPError as exc:
        raise SongGatewayError(f"LLM 게이트웨이 HTTP 통신 오류: {exc}") from exc

    if response.status_code >= 400:
        raise SongGatewayError(
            _response_detail(response),
            status_code=response.status_code,
            hint=f"upstream: POST {url}",
        )

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise SongGatewayError(
            "LLM 게이트웨이 응답이 JSON이 아닙니다.",
            hint=response.text[:200] if response.text else None,
        ) from exc

    if not isinstance(data, dict):
        raise SongGatewayError("LLM 게이트웨이 응답 형식이 올바르지 않습니다.")

    job_id = str(data.get("jobId") or data.get("job_id") or "")
    if not job_id:
        raise SongGatewayError(
            "LLM 게이트웨이 응답에 jobId가 없습니다.",
            hint=json.dumps(data, ensure_ascii=False)[:300],
        )
    return _normalize_analyze_response(data, job_id=job_id)


async def song_get_job(settings: Settings, job_id: str) -> dict[str, Any]:
    base = _gateway_base(settings)
    url = f"{base}/v1/jobs/{job_id}"
    headers = _gateway_headers(settings)
    timeout = settings.llm_gateway_timeout_sec
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
    except httpx.ConnectError as exc:
        raise SongGatewayError(
            "LLM 게이트웨이에 연결할 수 없습니다.",
            hint=f"LLM_GATEWAY_URL={base}",
        ) from exc
    except httpx.TimeoutException as exc:
        raise SongGatewayError(
            "LLM 게이트웨이 응답 시간이 초과되었습니다.",
        ) from exc
    except httpx.HTTPError as exc:
        raise SongGatewayError(f"LLM 게이트웨이 HTTP 통신 오류: {exc}") from exc

    if response.status_code == 404:
        raise SongGatewayError("작업을 찾을 수 없습니다.", status_code=404)
    if response.status_code >= 400:
        raise SongGatewayError(
            _response_detail(response),
            status_code=response.status_code,
            hint=f"upstream: GET {url}",
        )

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise SongGatewayError("LLM 게이트웨이 응답이 JSON이 아닙니다.") from exc

    if not isinstance(data, dict):
        raise SongGatewayError("LLM 게이트웨이 응답 형식이 올바르지 않습니다.")
    return data
