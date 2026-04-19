import json
import csv
from pathlib import Path
from datetime import datetime
from jobhunt.models.job import Job

def _job_to_dict(job: Job) -> dict:
    return {
        "title":      job.title,
        "company":    job.company,
        "location":   job.location,
        "salary":     job.salary,
        "job_type":   job.job_type,
        "experience": job.experience,
        "skills":     ", ".join(job.skills),
        "posted_at":  job.posted_at.strftime("%Y-%m-%d") if job.posted_at else "",
        "score":      job.score,
        "snippet":    job.snippet,
        "source":     job.source,
        "apply_url":  job.apply_url,
        "is_remote":  job.is_remote,
        "benefits":   ", ".join(job.benefits),
    }


def save_json(jobs: list[Job], path: Path) -> None:
    data = [_job_to_dict(j) for j in jobs]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def save_csv(jobs: list[Job], path: Path) -> None:
    if not jobs:
        return
    rows = [_job_to_dict(j) for j in jobs]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def auto_save(jobs: list[Job], fmt: str) -> Path:
    """Save to ~/jobhunt_exports/ with timestamped filename."""
    export_dir = Path.home() / "jobhunt_exports"
    export_dir.mkdir(exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = export_dir / f"jobs_{ts}.{fmt}"
    if fmt == "json":
        save_json(jobs, path)
    elif fmt == "csv":
        save_csv(jobs, path)
    return path