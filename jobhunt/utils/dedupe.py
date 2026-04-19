from rapidfuzz import fuzz
from jobhunt.models.job import Job

def fuzzy_dedupe(jobs: list[Job], threshold: int = 85) -> list[Job]:
    """
    Remove duplicate jobs using fuzzy matching on (title, company).
    Keeps the first occurrence (preserve source order / score order).
    threshold: minimum similarity score to consider a duplicate (0-100)
    """
    seen: list[tuple[str, str]] = []
    unique: list[Job] = []

    for job in jobs:
        title   = job.title.lower().strip()
        company = job.company.lower().strip()

        is_dup = False
        for seen_title, seen_company in seen:
            title_sim   = fuzz.token_sort_ratio(title, seen_title)
            company_sim = fuzz.token_sort_ratio(company, seen_company)

            # Both title AND company must be similar to count as duplicate
            if title_sim >= threshold and company_sim >= threshold:
                is_dup = True
                break

        if not is_dup:
            seen.append((title, company))
            unique.append(job)

    return unique