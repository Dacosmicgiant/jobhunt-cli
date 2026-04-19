from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Job:
    title: str
    company: str
    location: str
    source: str
    apply_url: str
    experience: int = 0
    skills: list[str] = field(default_factory=list)
    posted_at: datetime | None = None
    score: float | None = None
    salary: str = ""
    snippet: str = ""
    job_type: str = ""       # Full-time, Part-time, Contract, Internship
    is_remote: bool = False
    benefits: list[str] = field(default_factory=list)