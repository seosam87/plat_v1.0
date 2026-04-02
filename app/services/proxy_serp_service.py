"""Proxy-enabled SERP parser: Playwright + proxy rotation + rucaptcha."""
from __future__ import annotations

from loguru import logger

from app.config import settings


def is_proxy_configured() -> bool:
    """Check if proxy and anticaptcha are configured."""
    return bool(settings.PROXY_URL)


async def parse_serp_with_proxy(
    query: str, engine: str = "yandex", region: str = ""
) -> dict:
    """Parse SERP via Playwright with proxy support.

    Falls back to standard serp_parser_service if proxy not configured.
    """
    if not is_proxy_configured():
        from app.services.serp_parser_service import parse_serp
        return await parse_serp(query, engine=engine)

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                proxy={"server": settings.PROXY_URL},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            try:
                page = await context.new_page()

                if engine == "yandex":
                    url = f"https://yandex.ru/search/?text={query}&lr={region or '213'}"
                else:
                    url = f"https://www.google.com/search?q={query}"

                await page.goto(url, wait_until="domcontentloaded", timeout=20000)

                # Check for CAPTCHA
                captcha = await page.query_selector(".captcha, #captcha, .g-recaptcha")
                if captcha and settings.ANTICAPTCHA_KEY:
                    solved = await _solve_captcha(page)
                    if not solved:
                        logger.warning("CAPTCHA not solved", query=query)
                        return {"results": [], "features": [], "engine": engine, "query": query}

                # Extract results
                results = await _extract_results(page, engine)
                features = await _detect_features(page, engine)

                return {
                    "results": results,
                    "features": features,
                    "engine": engine,
                    "query": query,
                }
            finally:
                await context.close()
                await browser.close()

    except Exception as exc:
        logger.error("Proxy SERP parse failed", query=query, error=str(exc))
        return {"results": [], "features": [], "engine": engine, "query": query}


async def _extract_results(page, engine: str) -> list[dict]:
    """Extract TOP-10 search results from SERP page."""
    results = []

    if engine == "yandex":
        items = await page.query_selector_all(".serp-item, .organic")
        for i, item in enumerate(items[:10]):
            try:
                link = await item.query_selector("a.link, a.OrganicTitle-Link")
                title_el = await item.query_selector(".OrganicTitle, .organic__title")
                url = await link.get_attribute("href") if link else ""
                title = await title_el.inner_text() if title_el else ""
                domain = url.split("/")[2] if url and "/" in url else ""
                results.append({"position": i + 1, "url": url, "domain": domain, "title": title.strip()})
            except Exception:
                continue
    else:
        items = await page.query_selector_all("#search .g, .tF2Cxc")
        for i, item in enumerate(items[:10]):
            try:
                link = await item.query_selector("a")
                url = await link.get_attribute("href") if link else ""
                title = await item.query_selector("h3")
                title_text = await title.inner_text() if title else ""
                domain = url.split("/")[2] if url and "/" in url else ""
                results.append({"position": i + 1, "url": url, "domain": domain, "title": title_text.strip()})
            except Exception:
                continue

    return results


async def _detect_features(page, engine: str) -> list[str]:
    """Detect SERP features."""
    features = []
    selectors = {
        "featured_snippet": ".featured-snippet, .kp-blk",
        "paa": ".related-question, .people-also-ask",
        "video": ".video-container, .vidItem",
        "images": ".image-viewer, .img_result",
        "local_pack": ".local-organic, .map-organic",
    }
    for name, sel in selectors.items():
        el = await page.query_selector(sel)
        if el:
            features.append(name)
    return features


async def _solve_captcha(page) -> bool:
    """Attempt to solve CAPTCHA via anticaptcha service."""
    if not settings.ANTICAPTCHA_KEY:
        return False

    try:
        import httpx

        # Get captcha image or sitekey
        captcha_img = await page.query_selector(".captcha__image img, .captcha-image img")
        if captcha_img:
            src = await captcha_img.get_attribute("src")
            # Send to anticaptcha
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.rucaptcha.com/createTask",
                    json={
                        "clientKey": settings.ANTICAPTCHA_KEY,
                        "task": {
                            "type": "ImageToTextTask",
                            "body": src,
                        },
                    },
                )
                task_data = resp.json()
                task_id = task_data.get("taskId")
                if not task_id:
                    return False

                # Poll for result
                import asyncio
                for _ in range(30):
                    await asyncio.sleep(2)
                    result = await client.post(
                        "https://api.rucaptcha.com/getTaskResult",
                        json={"clientKey": settings.ANTICAPTCHA_KEY, "taskId": task_id},
                    )
                    result_data = result.json()
                    if result_data.get("status") == "ready":
                        solution = result_data.get("solution", {}).get("text", "")
                        # Type solution into captcha input
                        captcha_input = await page.query_selector(".captcha__input input, input[name='rep']")
                        if captcha_input:
                            await captcha_input.fill(solution)
                            submit = await page.query_selector(".captcha__submit, button[type='submit']")
                            if submit:
                                await submit.click()
                                await page.wait_for_load_state("domcontentloaded")
                            return True
                        return False
        return False
    except Exception as exc:
        logger.warning("Captcha solving failed", error=str(exc))
        return False
