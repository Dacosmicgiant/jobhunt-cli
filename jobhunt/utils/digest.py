import json
import hashlib
from pathlib import Path
from jobhunt.models.job import Job
DIGEST_PATH = Path.home() / ".jobhunt" / "seen_jobs.json"
DIGEST_PATH.parent.mkdir(parents=True, exist_ok=True)


def _job_hash(job: Job) -> str:
    """Stable hash for a job — based on apply_url, falling back to title+company."""
    key = job.apply_url if job.apply_url else f"{job.title}|{job.company}"
    return hashlib.md5(key.encode()).hexdigest()


def load_seen() -> set[str]:
    if not DIGEST_PATH.exists():
        return set()
    try:
        return set(json.loads(DIGEST_PATH.read_text()))
    except Exception:
        return set()


def save_seen(hashes: set[str]) -> None:
    DIGEST_PATH.write_text(json.dumps(list(hashes)))


def filter_new(jobs: list[Job]) -> tuple[list[Job], int]:
    """
    Return only jobs not seen before.
    Also returns total seen count for display.
    """
    seen = load_seen()
    new_jobs = [j for j in jobs if _job_hash(j) not in seen]
    return new_jobs, len(seen)


def mark_seen(jobs: list[Job]) -> None:
    """Add all current jobs to the seen set."""
    seen = load_seen()
    for job in jobs:
        seen.add(_job_hash(job))
    save_seen(seen)


def reset_seen() -> None:
    if DIGEST_PATH.exists():
        DIGEST_PATH.unlink()