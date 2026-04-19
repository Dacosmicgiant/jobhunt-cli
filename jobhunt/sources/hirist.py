import httpx
import logging
import time
import random
from datetime import datetime, timezone
from jobhunt.models.job import Job
from jobhunt.sources.base import BaseSource
from jobhunt.utils.cache import load, save

logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "full stack":           16,
    "full stack developer": 16,
    "backend":              3,
    "backend developer":    3,
    "frontend":             2,
    "frontend developer":   2,
    "mobile":               14,
}
DEFAULT_CATEGORY = 16

API_BASE = "https://gladiator.hirist.tech/job/category/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin":          "https://www.hirist.tech",
    "Referer":         "https://www.hirist.tech/",
}


def _ms_to_datetime(ms: int) -> datetime | None:
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


def _format_salary(r: dict) -> str:
    if r.get("hideSal", 1):
        return ""
    min_sal = r.get("minSal", 0)
    max_sal = r.get("maxSal", 0)
    if min_sal and max_sal:
        return f"₹{min_sal}L - ₹{max_sal}L PA"
    if min_sal:
        return f"From ₹{min_sal}L PA"
    if max_sal:
        return f"Up to ₹{max_sal}L PA"
    return ""


def _build_snippet(r: dict) -> str:
    parts = []
    tags = r.get("tags", [])
    mandatory = [t["name"] for t in tags if t.get("isMandatory")]
    if mandatory:
        parts.append(f"Must: {', '.join(mandatory)}")
    min_exp = r.get("min", 0)
    max_exp = r.get("max", 0)
    if min_exp or max_exp:
        parts.append(f"Exp: {min_exp}-{max_exp} yrs")
    apply_count = r.get("applyCount", -1)
    if apply_count > 0:
        parts.append(f"{apply_count} applicants")
    if r.get("premium"):
        parts.append("⭐ Premium")
    return " | ".join(parts)


class HiristSource(BaseSource):
    name = "hirist"

    def search(self, query: dict) -> list[Job]:
        cached = load(self.name, query)
        if cached:
            logger.info("[hirist] Cache hit")
            return [Job(**j) for j in cached]

        role = query.get("role", "full stack developer").lower()

        category_id = DEFAULT_CATEGORY
        for key, cid in CATEGORY_MAP.items():
            if key in role:
                category_id = cid
                break

        all_results = []

        for page in range(3):
            time.sleep(1 + random.uniform(0, 0.5))
            params = {
                "page":       page,
                "categoryId": category_id,
                "size":       50,
                "ref":        "jobsearch",
            }
            try:
                resp = httpx.get(
                    API_BASE, params=params, headers=HEADERS, timeout=15
                )
                resp.raise_for_status()
                batch = resp.json().get("data", [])
                if not batch:
                    logger.info(f"[hirist] Page {page}: empty, stopping")
                    break
                logger.info(f"[hirist] Page {page}: {len(batch)} jobs")
                all_results.extend(batch)
            except Exception as e:
                logger.error(f"[hirist] API request failed (page {page}): {e}")
                break

        logger.info(f"[hirist] Total raw jobs fetched: {len(all_results)}")
        jobs: list[Job] = []

        for r in all_results:
            if len(jobs) >= 150:  # hard cap
                break
            try:
                title   = r.get("jobdesignation") or r.get("title", "N/A")
                company = (
                    r.get("companyData", {}).get("companyName")
                    or r.get("creatorDomainName", "N/A")
                )

                locations     = r.get("locations") or r.get("location", [])
                location_text = ", ".join(l["name"] for l in locations) if locations else "N/A"
                is_remote     = bool(r.get("workFromHome"))
                if is_remote:
                    location_text = (
                        f"Remote ({location_text})"
                        if location_text != "N/A" else "Remote"
                    )

                tags   = r.get("tags", [])
                skills = [t["name"] for t in tags]

                created_ms = r.get("createdTimeMs") or r.get("createdTime")
                posted_at  = _ms_to_datetime(created_ms) if created_ms else None

                apply_url = (
                    r.get("jobDetailUrl")
                    or r.get("applyUrl")
                    or "https://www.hirist.tech"
                )

                salary  = _format_salary(r)
                snippet = _build_snippet(r)
                min_exp = r.get("min", 0)

                recruiter  = r.get("recruiter", {})
                rec_name   = recruiter.get("recruiterName", "")
                rec_desig  = recruiter.get("designation", "")
                benefits   = (
                    [f"Recruiter: {rec_name} ({rec_desig})"]
                    if rec_name else []
                )

                jobs.append(Job(
                    title=title,
                    company=company,
                    location=location_text,
                    source=self.name,
                    apply_url=apply_url,
                    experience=min_exp,
                    skills=skills,
                    posted_at=posted_at,
                    salary=salary,
                    snippet=snippet,
                    job_type="Full-time",
                    is_remote=is_remote,
                    benefits=benefits,
                ))

            except Exception as e:
                logger.debug(f"[hirist] Parse error: {e}")
                continue

        logger.info(f"[hirist] Returning {len(jobs)} jobs")

        save(self.name, query, [
            {**j.__dict__, "posted_at": j.posted_at.isoformat() if j.posted_at else None}
            for j in jobs
        ])
        return jobs