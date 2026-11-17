"""Background job queue for long-running work (dubbing, long voice changes...).

Jobs are persisted in SQLite so their status survives restarts; a small thread pool runs them.
GPU models are not re-entrant, so the default is a single worker (KONTHO_WORKERS).
"""

from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from . import db
from .config import get_settings

log = logging.getLogger(__name__)
_executor: ThreadPoolExecutor | None = None


def executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=max(1, get_settings().workers), thread_name_prefix="kontho-job")
    return _executor


class Progress:
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id

    def __call__(self, fraction: float, message: str = "") -> None:
        db.update("jobs", self.job_id, {"progress": round(max(0.0, min(1.0, fraction)), 3),
                                        "message": message, "updated_at": db.now()})


def create(kind: str, name: str, inputs: dict[str, Any], job_id: str | None = None) -> dict[str, Any]:
    job = {"id": job_id or db.new_id(), "kind": kind, "name": name, "status": "queued", "progress": 0.0,
           "message": "Queued", "input": inputs, "result": {}, "error": None,
           "created_at": db.now(), "updated_at": db.now()}
    db.insert("jobs", job)
    return job


def run(job_id: str, fn: Callable[[dict[str, Any], Progress], dict[str, Any]]) -> None:
    """Schedule ``fn(job, progress) -> result`` for an existing job."""

    def _task() -> None:
        job = db.get("jobs", job_id)
        if not job:
            return
        db.update("jobs", job_id, {"status": "running", "message": "Starting", "updated_at": db.now()})
        try:
            result = fn(job, Progress(job_id))
            db.update("jobs", job_id, {"status": "done", "progress": 1.0, "message": "Done",
                                       "result": result or {}, "updated_at": db.now()})
        except Exception as exc:  # noqa: BLE001
            log.error("Job %s failed: %s\n%s", job_id, exc, traceback.format_exc())
            db.update("jobs", job_id, {"status": "failed", "error": str(exc), "message": "Failed",
                                       "updated_at": db.now()})

    executor().submit(_task)


def recover_interrupted() -> None:
    for job in db.query("SELECT id FROM jobs WHERE status IN ('queued', 'running')"):
        db.update("jobs", job["id"], {"status": "failed", "error": "Interrupted by a server restart",
                                      "updated_at": db.now()})
