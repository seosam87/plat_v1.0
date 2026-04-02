"""Traffic analysis service: bot detection, anomaly detection, injection patterns."""
from __future__ import annotations

import re
import statistics
from collections import Counter


# ---- Bot detection (pure) ----


def classify_visit(
    ua: str, ip: str, referer: str, bot_patterns: list[dict]
) -> dict:
    """Classify a visit as bot or human based on patterns.

    Returns {is_bot, source, bot_reason}.
    """
    ua_lower = (ua or "").lower()

    # Check UA against bot patterns
    for p in bot_patterns:
        if p.get("pattern_type") == "ua" and p.get("is_active", True):
            if p["pattern_value"].lower() in ua_lower:
                return {
                    "is_bot": True,
                    "source": "bot_suspected",
                    "bot_reason": f"UA match: {p['pattern_value']}",
                }

    # Check for empty or suspicious UA
    if not ua or len(ua) < 10:
        return {"is_bot": True, "source": "bot_suspected", "bot_reason": "Empty or very short UA"}

    # Check for known bot-like UA patterns
    bot_indicators = ["bot", "crawler", "spider", "scraper", "curl", "wget", "python-requests", "headless"]
    for indicator in bot_indicators:
        if indicator in ua_lower:
            return {"is_bot": True, "source": "bot_suspected", "bot_reason": f"UA contains '{indicator}'"}

    return {"is_bot": False, "source": "organic", "bot_reason": None}


# ---- Anomaly detection (pure) ----


def detect_anomalies(visits_by_day: list[dict]) -> dict:
    """Detect anomalous traffic spikes in daily visit data.

    visits_by_day: [{date, visits}] sorted by date.
    Returns {anomaly_detected, anomaly_days, baseline_avg, std_dev}.
    """
    if len(visits_by_day) < 7:
        return {"anomaly_detected": False, "anomaly_days": [], "baseline_avg": 0, "std_dev": 0}

    values = [d["visits"] for d in visits_by_day]
    avg = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0
    threshold = avg + 2 * std

    anomaly_days = []
    for d in visits_by_day:
        if d["visits"] > threshold and threshold > 0:
            anomaly_days.append({
                "date": d["date"],
                "visits": d["visits"],
                "expected": round(avg),
                "deviation": round((d["visits"] - avg) / std, 1) if std > 0 else 0,
            })

    return {
        "anomaly_detected": len(anomaly_days) > 0,
        "anomaly_days": anomaly_days,
        "baseline_avg": round(avg, 1),
        "std_dev": round(std, 1),
    }


# ---- Traffic source analysis (pure) ----


def analyze_traffic_sources(visits: list[dict]) -> dict:
    """Group visits by source type.

    Returns {organic, direct, referral, bot, injection, by_referer, by_landing}.
    """
    source_counts: Counter = Counter()
    referer_counts: Counter = Counter()
    landing_counts: Counter = Counter()

    for v in visits:
        source = v.get("source", "organic")
        source_counts[source] += 1

        ref = v.get("referer", "")
        if ref:
            # Normalize referer to domain
            try:
                from urllib.parse import urlparse
                domain = urlparse(ref).netloc
                if domain:
                    referer_counts[domain] += 1
            except Exception:
                pass

        landing = v.get("page_url", "")
        if landing:
            landing_counts[landing] += 1

    return {
        "organic": source_counts.get("organic", 0),
        "direct": source_counts.get("direct", 0),
        "referral": source_counts.get("referral", 0),
        "bot": source_counts.get("bot_suspected", 0),
        "injection": source_counts.get("injection_suspected", 0),
        "by_referer": dict(referer_counts.most_common(20)),
        "by_landing": dict(landing_counts.most_common(20)),
    }


# ---- Injection pattern detection (pure) ----


def detect_injection_patterns(visits: list[dict]) -> list[dict]:
    """Detect traffic injection patterns.

    Returns list of {pattern, evidence, confidence}.
    """
    patterns = []

    # Pattern 1: Same referer with many different IPs
    referer_ips: dict[str, set] = {}
    for v in visits:
        ref = v.get("referer", "")
        ip = v.get("ip_address", "")
        if ref and ip:
            referer_ips.setdefault(ref, set()).add(ip)

    for ref, ips in referer_ips.items():
        if len(ips) > 50:
            patterns.append({
                "pattern": "Массовый реферальный трафик",
                "evidence": f"Реферер {ref}: {len(ips)} уникальных IP",
                "confidence": min(0.9, len(ips) / 100),
            })

    # Pattern 2: Burst from unusual geo
    geo_counts: Counter = Counter()
    for v in visits:
        geo = v.get("geo_country", "")
        if geo:
            geo_counts[geo] += 1

    total = len(visits)
    if total > 0:
        for geo, count in geo_counts.items():
            ratio = count / total
            if ratio > 0.5 and geo not in ("Россия", "Russia", "RU", ""):
                patterns.append({
                    "pattern": "Подозрительная география",
                    "evidence": f"{geo}: {count} визитов ({ratio:.0%} от общего)",
                    "confidence": ratio,
                })

    # Pattern 3: Very high bounce with specific referer
    ref_bounces: dict[str, int] = {}
    ref_total: dict[str, int] = {}
    for v in visits:
        ref = v.get("referer", "")
        if ref:
            ref_total[ref] = ref_total.get(ref, 0) + 1
            # Simplification: if no page_depth or duration data, skip this check

    return patterns


# ---- Access log parser ----


_LOG_PATTERN = re.compile(
    r'(?P<ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<url>\S+) \S+" (?P<status>\d+) \S+ '
    r'"(?P<referer>[^"]*)" "(?P<ua>[^"]*)"'
)


def parse_access_log(content: str, limit: int = 50000) -> list[dict]:
    """Parse Apache/Nginx combined log format."""
    results = []
    for line in content.splitlines()[:limit]:
        m = _LOG_PATTERN.match(line)
        if m:
            results.append({
                "ip_address": m.group("ip"),
                "timestamp": m.group("timestamp"),
                "method": m.group("method"),
                "page_url": m.group("url"),
                "status": int(m.group("status")),
                "referer": m.group("referer") if m.group("referer") != "-" else "",
                "user_agent": m.group("ua"),
            })
    return results
