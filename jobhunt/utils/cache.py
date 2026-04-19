import json
import hashlib
import time
from datetime import datetime
from pathlib import Path

CACHE_DIR = Path.home() / ".jobhunt" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _key(source: str, query: dict) -> str:
    raw = json.dumps({"source": source, "query": query}, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def load(source: str, query: dict, ttl: int = 1800) -> list | None:
    path = CACHE_DIR / f"{_key(source, query)}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if time.time() - data["ts"] > ttl:
        return None

    jobs = data["jobs"]

    # Deserialize posted_at from ISO string back to datetime
    for j in jobs:
        if j.get("posted_at") and isinstance(j["posted_at"], str):
            try:
                j["posted_at"] = datetime.fromisoformat(j["posted_at"])
            except Exception:
                j["posted_at"] = None

    return jobs


def save(source: str, query: dict, jobs: list[dict]) -> None:
    path = CACHE_DIR / f"{_key(source, query)}.json"
    path.write_text(json.dumps({"ts": time.time(), "jobs": jobs}))


def cache_status(source: str, query: dict, ttl: int = 1800) -> dict:
    """Return cache status for a source+query combo."""
    path = CACHE_DIR / f"{_key(source, query)}.json"
    if not path.exists():
        return {"status": "missing", "age_seconds": None, "expires_in": None}
    data = json.loads(path.read_text())
    age  = time.time() - data["ts"]
    return {
        "status":      "fresh" if age < ttl else "expired",
        "age_seconds": int(age),
        "expires_in":  max(0, int(ttl - age)),
    }


def invalidate(source: str, query: dict) -> None:
    """Delete cache entry for a specific source+query."""
    path = CACHE_DIR / f"{_key(source, query)}.json"
    if path.exists():
        path.unlink()