#!/usr/bin/env python3
"""
push-jobs-snapshot.py
Push collected Hunter jobs JSON to dashboard /api/update.py as jobs_snapshot.

Usage:
  python3 push-jobs-snapshot.py /tmp/hunter_target_jobs.json
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://45.55.191.125")
TOKEN = os.getenv("DASHBOARD_UPDATE_TOKEN", "")
DEFAULT_TOKEN = "f2e10ce9e211948c6eeacf1b13c0fcf631ec4b70f706f03fe930f647a5013466"
MAX_JOBS = 500


def normalize(job: dict) -> dict:
    if not isinstance(job, dict):
        return {}

    title = str(job.get("title") or job.get("job_title") or "").strip()
    url = str(job.get("url") or job.get("job_url") or "").strip()
    if not title or not url:
        return {}

    return {
        "title": title,
        "company": str(job.get("company") or job.get("company_name") or "").strip(),
        "location": str(job.get("location") or job.get("candidate_required_location") or "Remote"),
        "salary": str(job.get("salary") or ""),
        "url": url,
        "posted_at": str(job.get("posted_at") or job.get("posted") or job.get("publication_date") or job.get("date") or ""),
        "tags": job.get("tags", []) if isinstance(job.get("tags", []), list) else [],
        "description_snippet": str(job.get("description_snippet") or job.get("snippet") or "")[:220],
        "source": str(job.get("source") or "Hunter"),
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: push-jobs-snapshot.py <jobs_json_path>", file=sys.stderr)
        return 2

    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    jobs_raw = data.get("jobs", []) if isinstance(data, dict) else []
    normalized = [normalize(j) for j in jobs_raw[:MAX_JOBS]]
    jobs = [j for j in normalized if j]

    fetched_at = data.get("fetched_at") if isinstance(data, dict) else None
    sources = data.get("sources", []) if isinstance(data, dict) else []

    payload = {
        "update_source": "hunter",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kpi_updates": {
            "Hunter Targeted Jobs": str(len(jobs)),
            "Hunter Last Jobs Sync": fetched_at or datetime.now(timezone.utc).isoformat(),
        },
        "jobs_snapshot": {
            "fetched_at": fetched_at,
            "sources": sources if isinstance(sources, list) else [],
            "jobs": jobs,
        },
    }

    body = json.dumps(payload).encode("utf-8")
    token = TOKEN or DEFAULT_TOKEN
    req = urllib.request.Request(
        f"{DASHBOARD_URL}/api/update.py",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        resp_body = resp.read().decode("utf-8", errors="ignore")

    out = json.loads(resp_body)
    print(json.dumps(out))
    if not out.get("ok"):
        return 1
    if int(out.get("jobs_count", 0)) <= 0 and len(jobs) > 0:
        # Server did not accept jobs correctly
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
