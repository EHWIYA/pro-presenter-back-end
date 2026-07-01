"""analyze job 컨텍스트 (BFF 인메모리, DB 저장 없음)."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class AnalyzeJobContext:
    save_to_library: bool = True
    library_song_id: str | None = None
    client_ref: str | None = None
    input_kind: str | None = None


_store: dict[str, AnalyzeJobContext] = {}
_lock = Lock()


def set_job_context(job_id: str, ctx: AnalyzeJobContext) -> None:
    with _lock:
        _store[job_id] = ctx


def get_job_context(job_id: str) -> AnalyzeJobContext | None:
    with _lock:
        return _store.get(job_id)


def pop_job_context(job_id: str) -> AnalyzeJobContext | None:
    with _lock:
        return _store.pop(job_id, None)


def clear_job_contexts() -> None:
    """테스트용."""
    with _lock:
        _store.clear()
