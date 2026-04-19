import httpx
import logging
import time
import random
import re
from datetime import datetime, timezone
from models.job import Job
from sources.base import BaseSource
from utils.cache import load, save

logger = logging.getLogger(__name__)

API_URL = "https://www.naukri.com/jobapi/v3/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json",
    "Accept-Language": "en-US,en;q=0.6",
    "Content-Type":    "application/json",
    "Appid":           "109",
    "Clientid":        "d3skt0p",
    "Gid":             "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
    "Systemid":        "Naukri",
    "Nkparam":         "t9nG2QTXNYZiYbVkl0+UHSA70A2MhkYBZ4vIw6TeBcP9ktQdfu2cqCsbhurCKV7rvpD64K/Ygpr24t2HtMeRfg==",
}


def _ms_to_datetime(ms: int) -> datetime | None:
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


def _format_salary(detail: dict) -> str:
    if not detail or detail.get("hideSalary"):
        return ""
    mn = detail.get("minimumSalary", 0)
    mx = detail.get("maximumSalary", 0)
    cur = detail.get("currency", "INR")
    if mn and mx:
        return f"₹{mn/100000:.0f}L - ₹{mx/100000:.0f}L PA"
    if mn:
        return f"From ₹{mn/100000:.0f}L PA"
    if mx:
        return f"Up to ₹{mx/100000:.0f}L PA"
    return ""


def _parse_placeholders(placeholders: list) -> dict:
    """Extract experience, salary, location from placeholders list."""
    result = {"experience": "", "salary": "", "location": ""}
    for p in placeholders:
        t = p.get("type", "")
        label = p.get("label", "")
        if t == "experience":
            result["experience"] = label
        elif t == "salary":
            result["salary"] = label
        elif t == "location":
            result["location"] = label
    return result


def _strip_html(text: str) -> str:
    clean = re.sub(r'<[^>]+>', ' ', text or "")
    return re.sub(r'\s+', ' ', clean).strip()


def _normalize_exp(min_exp: str) -> int:
    try:
        return int(min_exp)
    except Exception:
        return 0


class NaukriSource(BaseSource):
    name = "naukri"

    def search(self, query: dict) -> list[Job]:
        cached = load(self.name, query)
        if cached:
            logger.info("[naukri] Cache hit")
            return [Job(**j) for j in cached]

        role     = query.get("role", "full stack developer")
        limit    = query.get("limit", 20)

        # Build seo key from role
        seo_key = role.strip().lower().replace(" ", "-") + "-jobs"

        all_results = []
        page = 1
        per_page = 20

        while len(all_results) < limit:
            params = {
                "noOfResults": per_page,
                "urlType":     "search_by_keyword",
                "searchType":  "adv",
                "keyword":     role,
                "pageNo":      page,
                "k":           role,
                "seoKey":      seo_key,
                "src":         "jobsearchDesk",
                "latLong":     "",
            }

            headers = {
                **HEADERS,
                "Referer": f"https://www.naukri.com/{seo_key}",
            }

            time.sleep(1 + random.uniform(0, 0.5))

            try:
                resp = httpx.get(API_URL, params=params, headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"[naukri] API request failed (page {page}): {e}")
                break

            batch = data.get("jobDetails", [])
            if not batch:
                logger.info(f"[naukri] Page {page}: empty, stopping")
                break

            logger.info(f"[naukri] Page {page}: {len(batch)} jobs")
            all_results.extend(batch)
            page += 1

        logger.info(f"[naukri] Total raw jobs: {len(all_results)}")
        jobs: list[Job] = []

        for r in all_results[:limit]:
            try:
                title   = r.get("title", "N/A")
                company = r.get("companyName", "N/A")

                # Skills from tagsAndSkills
                tags_raw = r.get("tagsAndSkills", "")
                skills   = [s.strip() for s in tags_raw.split(",") if s.strip()]

                # Placeholders → experience, salary, location
                ph        = _parse_placeholders(r.get("placeholders", []))
                location_text = ph["location"] or "N/A"
                salary_label  = ph["salary"] or ""

                # Structured salary (more precise)
                salary_detail = r.get("salaryDetail") or {}
                salary = _format_salary(salary_detail) or salary_label

                # Experience
                min_exp_str = r.get("minimumExperience", "0")
                max_exp_str = r.get("maximumExperience", "")
                exp_text    = r.get("experienceText", "")
                experience  = _normalize_exp(min_exp_str)

                # Remote flag
                is_remote = "remote" in location_text.lower() or "work from home" in location_text.lower()

                # Posted date
                created_ms = r.get("createdDate")
                posted_at  = _ms_to_datetime(created_ms) if created_ms else None

                # Apply URL
                jd_url    = r.get("jdURL", "")
                apply_url = f"https://www.naukri.com{jd_url}" if jd_url else "https://www.naukri.com"

                # Description snippet
                raw_desc = r.get("jobDescription", "")
                snippet  = _strip_html(raw_desc)[:200] + "…" if raw_desc else ""

                # Snippet enrichment
                snippet_parts = []
                if exp_text:
                    snippet_parts.append(f"Exp: {exp_text}")
                vacancy = r.get("vacancy", 0)
                if vacancy:
                    snippet_parts.append(f"{vacancy} vacancies")
                if r.get("ambitionBoxData", {}).get("AggregateRating"):
                    rating = r["ambitionBoxData"]["AggregateRating"]
                    snippet_parts.append(f"⭐ {rating} AmbitionBox")
                meta = " | ".join(snippet_parts)

                # Benefits — job type hints
                benefits = []
                if r.get("walkinJob"):
                    benefits.append("Walk-in")
                if r.get("companyApplyJob"):
                    benefits.append("Direct Apply")

                jobs.append(Job(
                    title=title,
                    company=company,
                    location=location_text,
                    source=self.name,
                    apply_url=apply_url,
                    experience=experience,
                    skills=skills,
                    posted_at=posted_at,
                    salary=salary,
                    snippet=f"{snippet} {meta}".strip(),
                    job_type="Full-time",
                    is_remote=is_remote,
                    benefits=benefits,
                ))

            except Exception as e:
                logger.debug(f"[naukri] Parse error: {e}")
                continue

        logger.info(f"[naukri] Returning {len(jobs)} jobs")

        save(self.name, query, [
            {**j.__dict__, "posted_at": j.posted_at.isoformat() if j.posted_at else None}
            for j in jobs
        ])
        return jobs