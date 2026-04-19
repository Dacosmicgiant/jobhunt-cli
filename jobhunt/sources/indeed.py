import re
import json
import logging
from datetime import datetime, timedelta
from jobhunt.models.job import Job
from jobhunt.sources.base import BaseSource
from jobhunt.utils.http import get_html
from jobhunt.utils.cache import load, save
from jobhunt.utils.skill_extractor import extract_skills

logger = logging.getLogger(__name__)

BASE_URL = "https://in.indeed.com/jobs"

_EXP_NOISE = re.compile(
    r'\b(\d+\+?\s*(year|yr|years|yrs))|'
    r'(senior|lead|principal|staff|manager|architect)\b',
    re.IGNORECASE
)


def _is_experienced_role(title: str) -> bool:
    return bool(_EXP_NOISE.search(title))


def _strip_html(html_text: str) -> str:
    clean = re.sub(r'<[^>]+>', ' ', html_text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def _parse_taxonomy(taxonomy: list[dict]) -> dict:
    result = {
        "job_type":  "",
        "is_remote": False,
        "benefits":  [],
        "shifts":    [],
    }
    for group in taxonomy:
        label = group.get("label", "")
        attrs = [a.get("label", "") for a in group.get("attributes", []) if a.get("label")]
        if label == "job-types" and attrs:
            result["job_type"] = attrs[0]
        elif label == "remote" and attrs:
            result["is_remote"] = True
        elif label == "benefits":
            result["benefits"] = attrs
        elif label == "shifts":
            result["shifts"] = attrs
    return result


def _parse_relative_date(text: str) -> datetime | None:
    if not text:
        return None
    text = text.lower().strip()
    now = datetime.now()
    try:
        if "just now" in text or "today" in text:
            return now
        if "hour" in text:
            n = int(''.join(filter(str.isdigit, text)) or 1)
            return now - timedelta(hours=n)
        if "day" in text:
            n = int(''.join(filter(str.isdigit, text)) or 1)
            return now - timedelta(days=n)
        if "month" in text:
            n = int(''.join(filter(str.isdigit, text)) or 1)
            return now - timedelta(days=30 * n)
    except Exception:
        pass
    return None


def _extract_job_data(html: str) -> list[dict]:
    pattern = r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\});'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        logger.warning("[indeed] Could not find embedded job data blob in HTML")
        return []
    try:
        data = json.loads(match.group(1))
        results = (
            data.get("metaData", {})
                .get("mosaicProviderJobCardsModel", {})
                .get("results", [])
        )
        if not results:
            results = data.get("results", [])
        logger.info(f"[indeed] Extracted {len(results)} jobs from embedded JSON")
        return results
    except json.JSONDecodeError as e:
        logger.error(f"[indeed] JSON parse error: {e}")
        return []


class IndeedSource(BaseSource):
    name = "indeed"

    def search(self, query: dict) -> list[Job]:
        cached = load(self.name, query)
        if cached:
            logger.info("[indeed] Cache hit")
            return [Job(**j) for j in cached]

        role       = query.get("role", "full stack developer")
        location   = query.get("location", "india")
        experience = query.get("experience", 0)
        limit      = query.get("limit", 60)

        params_base = {
            "q":    f"{role} fresher" if experience == 0 else role,
            "l":    location,
            "sort": "date",
        }

        all_results = []
        per_page     = 10
        pages_needed = max(1, (limit // per_page) + 1)

        for page_num in range(pages_needed):
            if len(all_results) >= limit:
                break

            params = {**params_base, "start": page_num * per_page}

            try:
                html = get_html(BASE_URL, params=params)
            except Exception as e:
                logger.error(f"[indeed] Browser fetch failed (page {page_num}): {e}")
                break

            raw_results = _extract_job_data(html)
            if not raw_results:
                logger.warning(f"[indeed] Page {page_num}: no data, stopping")
                break

            logger.info(f"[indeed] Page {page_num} (start={page_num * per_page}): {len(raw_results)} jobs")
            all_results.extend(raw_results)

            if len(raw_results) < per_page:
                break

        logger.info(f"[indeed] Total raw results: {len(all_results)}")
        jobs: list[Job] = []

        for r in all_results:
            try:
                title         = r.get("title") or r.get("displayTitle", "N/A")
                company       = r.get("company") or r.get("truncatedCompany", "N/A")
                location_text = r.get("formattedLocation", "N/A")
                date_text     = r.get("formattedRelativeTime", "")
                posted_at     = _parse_relative_date(date_text)
                jobkey        = r.get("jobkey", "")
                apply_url     = (
                    f"https://in.indeed.com/viewjob?jk={jobkey}"
                    if jobkey else "https://in.indeed.com"
                )

                salary_snippet = r.get("salarySnippet") or {}
                salary         = salary_snippet.get("text", "")

                raw_snippet = r.get("snippet", "")
                snippet     = _strip_html(raw_snippet)
                skills      = extract_skills(snippet)

                taxonomy  = r.get("taxonomyAttributes") or []
                tax       = _parse_taxonomy(taxonomy)
                is_remote = tax["is_remote"] or r.get("remoteLocation", False)

                if is_remote and "remote" not in location_text.lower():
                    location_text = f"Remote ({location_text})" if location_text != "N/A" else "Remote"

                if _is_experienced_role(title):
                    logger.debug(f"[indeed] Filtered: {title}")
                    continue

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
                    snippet=snippet,
                    job_type=tax["job_type"],
                    is_remote=is_remote,
                    benefits=tax["benefits"],
                ))

            except Exception as e:
                logger.debug(f"[indeed] Result parse error: {e}")
                continue

        save(self.name, query, [
            {**j.__dict__, "posted_at": j.posted_at.isoformat() if j.posted_at else None}
            for j in jobs
        ])
        return jobs