import httpx
import logging
import time
import random
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from jobhunt.models.job import Job
from jobhunt.sources.base import BaseSource
from jobhunt.utils.cache import load, save
from jobhunt.utils.skill_extractor import extract_skills

logger = logging.getLogger(__name__)

BASE_URL = "https://internshala.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://internshala.com",
}


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
        if "week" in text:
            n = int(''.join(filter(str.isdigit, text)) or 1)
            return now - timedelta(weeks=n)
        if "month" in text:
            n = int(''.join(filter(str.isdigit, text)) or 1)
            return now - timedelta(days=30 * n)
    except Exception:
        pass
    return None


def _parse_experience(card) -> int:
    try:
        for item in card.select("div.row-1-item"):
            if item.select_one("i.ic-16-briefcase"):
                text = item.get_text(strip=True).lower()
                nums = re.findall(r'\d+', text)
                return int(nums[0]) if nums else 0
    except Exception:
        pass
    return 0


def _parse_cards(soup: BeautifulSoup) -> list:
    all_cards = soup.select("div.individual_internship")
    return [
        c for c in all_cards
        if "jos_native_ad_text" not in c.get("class", [])
    ]


def _parse_card(card) -> dict | None:
    try:
        title_el  = card.select_one("h2.job-internship-name a")
        title     = title_el.get_text(strip=True) if title_el else "N/A"
        href      = title_el["href"] if title_el and title_el.get("href") else ""
        apply_url = f"{BASE_URL}{href}" if href.startswith("/") else href or BASE_URL

        company_el = card.select_one("p.company-name")
        company    = company_el.get_text(strip=True) if company_el else "N/A"

        loc_el        = card.select_one("p.locations span")
        location_text = loc_el.get_text(strip=True) if loc_el else "N/A"
        is_remote     = "work from home" in location_text.lower() or "remote" in location_text.lower()
        if is_remote:
            location_text = "Remote"

        salary = ""
        for item in card.select("div.row-1-item"):
            if item.select_one("i.ic-16-money"):
                span = item.select_one("span.desktop")
                if span:
                    salary = span.get_text(strip=True)
                    if salary and "/year" not in salary and "year" not in salary.lower():
                        salary = f"{salary} /year"
                break

        experience = _parse_experience(card)

        skill_els       = card.select("div.job_skill")
        explicit_skills = [s.get_text(strip=True) for s in skill_els if s.get_text(strip=True)]

        desc_el = card.select_one("div.about_job div.text")
        snippet = desc_el.get_text(strip=True)[:200] + "…" if desc_el else ""

        desc_skills = extract_skills(snippet)
        seen        = {s.lower() for s in explicit_skills}
        extra       = [s for s in desc_skills if s.lower() not in seen]
        skills      = explicit_skills + extra

        date_el   = card.select_one("div.color-labels")
        posted_at = _parse_relative_date(
            date_el.get_text(strip=True) if date_el else ""
        )

        return {
            "title":      title,
            "company":    company,
            "location":   location_text,
            "apply_url":  apply_url,
            "salary":     salary,
            "experience": experience,
            "skills":     skills,
            "snippet":    snippet,
            "posted_at":  posted_at,
            "is_remote":  is_remote,
        }

    except Exception as e:
        logger.debug(f"[internshala] Card parse error: {e}")
        return None


class InternshalaSource(BaseSource):
    name = "internshala"

    def search(self, query: dict) -> list[Job]:
        cached = load(self.name, query)
        if cached:
            logger.info("[internshala] Cache hit")
            return [Job(**j) for j in cached]

        role = query.get("role", "full stack developer")

        slug           = role.strip().lower().replace(" ", "-")
        all_cards_data = []

        for page in range(1, 4):
            url = f"{BASE_URL}/jobs/{slug}-jobs/page-{page}"
            time.sleep(1 + random.uniform(0, 0.5))

            try:
                resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
                if resp.status_code != 200:
                    logger.warning(f"[internshala] Page {page}: status {resp.status_code}")
                    break

                soup  = BeautifulSoup(resp.text, "html.parser")
                cards = _parse_cards(soup)

                if not cards:
                    logger.info(f"[internshala] Page {page}: no cards, stopping")
                    break

                logger.info(f"[internshala] Page {page}: {len(cards)} cards")
                all_cards_data.extend(cards)

            except Exception as e:
                logger.error(f"[internshala] Fetch error page {page}: {e}")
                break

        logger.info(f"[internshala] Total raw cards: {len(all_cards_data)}")
        jobs: list[Job] = []

        for card in all_cards_data:
            if len(jobs) >= 100:  # hard cap
                break
            data = _parse_card(card)
            if not data or data["title"] == "N/A":
                continue

            jobs.append(Job(
                title=data["title"],
                company=data["company"],
                location=data["location"],
                source=self.name,
                apply_url=data["apply_url"],
                experience=data["experience"],
                skills=data["skills"],
                posted_at=data["posted_at"],
                salary=data["salary"],
                snippet=data["snippet"],
                job_type="Full-time",
                is_remote=data["is_remote"],
                benefits=[],
            ))

        logger.info(f"[internshala] Returning {len(jobs)} jobs")

        save(self.name, query, [
            {**j.__dict__, "posted_at": j.posted_at.isoformat() if j.posted_at else None}
            for j in jobs
        ])
        return jobs