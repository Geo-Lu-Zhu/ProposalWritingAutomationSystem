"""In-memory background job registry.

A prototype-scale substitute for a real task queue: jobs run as asyncio
background tasks within the same process, progress is kept in memory, and
the frontend polls GET /jobs/{id}. Fine for a single-user app; state is
lost on server restart (nothing durable is written to job state itself,
only to the JSON files/artifacts a job produces).
"""
import asyncio
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional


@dataclass
class Job:
    id: str
    status: str = "queued"  # queued | running | done | error
    progress: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


_jobs: dict[str, Job] = {}


def get_job(job_id: str) -> Optional[Job]:
    return _jobs.get(job_id)


def _touch(job: Job) -> None:
    job.updated_at = datetime.now(timezone.utc).isoformat()


def set_progress(job_id: str, **progress: Any) -> None:
    job = _jobs.get(job_id)
    if not job:
        return
    job.progress.update(progress)
    _touch(job)


def start_job(fn: Callable[[str], Any]) -> str:
    """Register a job and run `fn(job_id)` in the background.

    `fn` should be an async callable. It reports progress via
    `set_progress(job_id, ...)` as it goes, and its return value becomes
    the job's `result` on success.
    """
    job_id = uuid.uuid4().hex[:12]
    job = Job(id=job_id)
    _jobs[job_id] = job

    async def runner():
        job.status = "running"
        _touch(job)
        try:
            result = await fn(job_id)
            job.result = result
            job.status = "done"
        except Exception as exc:  # noqa: BLE001
            job.status = "error"
            job.error = f"{exc}\n{traceback.format_exc()}"
        finally:
            _touch(job)

    asyncio.create_task(runner())
    return job_id
