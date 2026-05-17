#!/usr/bin/env python3
"""
Collect a small dashboard trends payload for OpenClaw/Hunter.

This script intentionally emits JSON only; callers can merge it into an
`/api/update.py` payload or use it as an input for a richer agent summary.
"""

import json
import os
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen


DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://45.55.191.125").rstrip("/")
TIMEOUT_SECONDS = int(os.getenv("DASHBOARD_TRENDS_TIMEOUT", "15"))


def fetch_json(url: str):
    req = Request(url, headers={"User-Agent": "OpenClaw IT Dashboard/1.0"})
    with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read())


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    result = {
        "fetched_at": now,
        "dashboard_url": DASHBOARD_URL,
        "market_status": "Stable",
        "kpi_updates": {
            "Last Trends Scan": now,
        },
        "trend_alerts": [],
        "new_insights": [],
        "source_status": {},
    }

    for name, path in {
        "jobs": "/api/jobs.py",
        "news": "/api/news.py",
        "update": "/api/update.py",
    }.items():
        try:
            data = fetch_json(f"{DASHBOARD_URL}{path}")
            result["source_status"][name] = {
                "ok": True,
                "total": data.get("total"),
                "from_cache": data.get("from_cache"),
                "age_seconds": data.get("age_seconds"),
            }
        except (OSError, URLError, json.JSONDecodeError) as exc:
            result["source_status"][name] = {
                "ok": False,
                "error": str(exc)[:180],
            }

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
