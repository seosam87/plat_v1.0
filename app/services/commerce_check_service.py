"""Commercialization analysis service — SERP-based keyword intent classification."""
from __future__ import annotations

# Commercial domain signals
COMMERCIAL_DOMAINS = {
    "ozon.ru", "wildberries.ru", "market.yandex.ru", "avito.ru",
    "aliexpress.ru", "dns-shop.ru", "mvideo.ru", "eldorado.ru",
    "citilink.ru", "lamoda.ru", "sbermegamarket.ru", "kazanexpress.ru",
}

COMMERCIAL_KEYWORDS = {
    "купить", "цена", "заказать", "стоимость", "магазин", "shop",
    "store", "price", "buy", "order", "доставка", "скидка", "акция",
    "каталог", "интернет-магазин", "оптом",
}

INFORMATIONAL_DOMAINS = {
    "wikipedia.org", "ru.wikipedia.org", "zen.yandex.ru", "dzen.ru",
    "pikabu.ru", "habr.com", "otvet.mail.ru", "forum",
}

# Thresholds
COMMERCIAL_THRESHOLD = 60   # >60% commercial results = "commercial" intent
INFORMATIONAL_THRESHOLD = 20  # <20% commercial results = "informational" intent


def analyze_commercialization(phrase: str, serp_results: list[dict]) -> dict:
    """Analyze SERP results for a phrase and return commercialization metrics.

    Args:
        phrase: keyword phrase
        serp_results: list of dicts from xmlproxy_service.search_yandex_sync
            Each dict has: url, position, domain, title, snippet

    Returns:
        dict with keys: phrase, commercialization, intent, geo_dependent, localized
    """
    if not serp_results:
        return {
            "phrase": phrase,
            "commercialization": 0,
            "intent": "informational",
            "geo_dependent": False,
            "localized": False,
        }

    total = len(serp_results)
    commercial_count = 0
    has_geo_terms = False
    has_local_domains = False

    for result in serp_results:
        domain = (result.get("domain") or "").lower()
        title = (result.get("title") or "").lower()
        url = (result.get("url") or "").lower()
        snippet = (result.get("snippet") or "").lower()

        # Commercial signal: domain is known commercial
        is_commercial = any(cd in domain for cd in COMMERCIAL_DOMAINS)

        # Commercial signal: URL or title contains commercial keywords
        if not is_commercial:
            combined = f"{title} {url} {snippet}"
            is_commercial = any(kw in combined for kw in COMMERCIAL_KEYWORDS)

        if is_commercial:
            commercial_count += 1

        # Geo-dependency signals
        geo_terms = ["город", "район", "область", "адрес", "ближайш", "рядом", "карта"]
        if any(gt in f"{title} {snippet}" for gt in geo_terms):
            has_geo_terms = True

        # Localization signal: regional subdomains
        if ".ru/" in url and any(
            region in domain
            for region in ["msk.", "spb.", "nsk.", "ekb.", "kzn."]
        ):
            has_local_domains = True

    commercialization_pct = round((commercial_count / total) * 100)

    if commercialization_pct > COMMERCIAL_THRESHOLD:
        intent = "commercial"
    elif commercialization_pct < INFORMATIONAL_THRESHOLD:
        intent = "informational"
    else:
        intent = "mixed"

    return {
        "phrase": phrase,
        "commercialization": commercialization_pct,
        "intent": intent,
        "geo_dependent": has_geo_terms,
        "localized": has_local_domains,
    }
