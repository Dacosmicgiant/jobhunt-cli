import logging
from jobhunt.models.job import Job
from jobhunt.sources.base import BaseSource
from jobhunt.utils.dedupe import fuzzy_dedupe
from jobhunt.core.scorer import score_jobs


logger = logging.getLogger(__name__)


def aggregate(sources: list[BaseSource], query: dict) -> list[Job]:
    all_jobs: list[Job] = []

    for source in sources:
        try:
            jobs = source.search(query)
            logger.info(f"[{source.name}] Returned {len(jobs)} jobs")
            all_jobs.extend(jobs)
        except Exception as e:
            logger.error(f"[{source.name}] Failed: {e}")

    logger.info(f"[aggregator] Total before dedup: {len(all_jobs)}")

    # Fuzzy dedup
    deduped = fuzzy_dedupe(all_jobs)
    logger.info(f"[aggregator] After fuzzy dedup: {len(deduped)} (removed {len(all_jobs) - len(deduped)})")

    # Score and sort
    scored = score_jobs(deduped, query)
    logger.info(f"[aggregator] Scored and sorted {len(scored)} jobs")

    return scored