import asyncio
import random
import logging
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

logger = logging.getLogger(__name__)

VIEWPORT = {"width": 1366, "height": 768}

LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
]


async def _fetch_html(url: str, params: dict = None, delay: float = 1.5) -> str:
    if params:
        from urllib.parse import urlencode
        url = f"{url}?{urlencode(params)}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=LAUNCH_ARGS,
        )
        context = await browser.new_context(
            viewport=VIEWPORT,
            locale="en-US",
            timezone_id="Asia/Kolkata",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await stealth_async(page)

        logger.info(f"[browser] GET {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        await asyncio.sleep(delay + random.uniform(0.3, 1.0))

        # Wait for job cards OR the embedded JSON blob — whichever comes first
        try:
            await page.wait_for_selector("div.job_seen_beacon", timeout=8_000)
        except Exception:
            try:
                await page.wait_for_function(
                    "() => document.documentElement.innerHTML"
                    ".includes('mosaic-provider-jobcards')",
                    timeout=8_000,
                )
            except Exception:
                logger.warning("[browser] Timed out waiting for job cards — parsing whatever loaded")

        html = await page.content()
        await browser.close()
        return html


def get_html(url: str, params: dict = None, delay: float = 1.5) -> str:
    return asyncio.run(_fetch_html(url, params=params, delay=delay))