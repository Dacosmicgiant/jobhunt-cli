from datetime import datetime
from rapidfuzz import fuzz
from jobhunt.models.job import Job


def _skill_match(job_skills: list[str], query_skills: list[str]) -> float:
    """
    Fraction of query skills found in job skills (fuzzy match).
    Returns 0.5 if no query skills specified (neutral).
    """
    if not query_skills:
        return 0.5

    if not job_skills:
        return 0.1

    matched = 0
    job_skills_lower = [s.lower() for s in job_skills]

    for qs in query_skills:
        qs_lower = qs.lower().strip()
        if qs_lower in job_skills_lower:
            matched += 1
            continue
        for js in job_skills_lower:
            if fuzz.partial_ratio(qs_lower, js) >= 80:
                matched += 1
                break

    return matched / len(query_skills)


def _recency_score(posted_at: datetime | str | None) -> float:
    """
    Score based on how recently job was posted.
    Today = 1.0, 7 days = 0.7, 30 days = 0.3, unknown = 0.4
    """
    if posted_at is None:
        return 0.4

    # Defensive: deserialize if somehow still a string
    if isinstance(posted_at, str):
        try:
            posted_at = datetime.fromisoformat(posted_at)
        except Exception:
            return 0.4

    now = datetime.now()
    age = (now - posted_at).days

    if age <= 1:
        return 1.0
    if age <= 3:
        return 0.9
    if age <= 7:
        return 0.7
    if age <= 14:
        return 0.5
    if age <= 30:
        return 0.3
    return 0.1


def _role_match(title: str, role_query: str) -> float:
    """
    How closely the job title matches the searched role.
    """
    title_lower = title.lower()
    role_lower  = role_query.lower()

    if role_lower in title_lower:
        return 1.0

    role_words  = set(role_lower.split())
    title_words = set(title_lower.split())
    overlap = len(role_words & title_words)
    if overlap:
        return min(1.0, overlap / len(role_words))

    return fuzz.partial_ratio(role_lower, title_lower) / 100.0


def _experience_score(experience: int) -> float:
    """
    Fresher-first scoring. 0 yrs = 1.0, penalize higher exp.
    """
    if experience == 0:
        return 1.0
    if experience <= 1:
        return 0.85
    if experience <= 2:
        return 0.65
    if experience <= 3:
        return 0.4
    return max(0.1, 1.0 - (experience * 0.1))


def score_job(job: Job, query: dict) -> float:
    """
    Compute a 0-1 score for a job given the search query.

    Weights:
        0.35 * skill_match
        0.25 * recency
        0.20 * role_match
        0.20 * experience_fit
    """
    query_skills = [s.lower().strip() for s in query.get("skills", []) if s.strip()]
    role_query   = query.get("role", "full stack developer")

    skill   = _skill_match(job.skills, query_skills)
    recency = _recency_score(job.posted_at)
    role    = _role_match(job.title, role_query)
    exp     = _experience_score(job.experience)

    score = (
        0.35 * skill   +
        0.25 * recency +
        0.20 * role    +
        0.20 * exp
    )

    return round(score, 3)


def score_jobs(jobs: list[Job], query: dict) -> list[Job]:
    """Score and sort all jobs. Mutates job.score in place."""
    for job in jobs:
        job.score = score_job(job, query)
    return sorted(jobs, key=lambda j: j.score or 0, reverse=True)