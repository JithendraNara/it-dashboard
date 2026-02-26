#!/usr/bin/env bash
# =============================================================================
# collect-jobs-agent-browser.sh
# Diversified targeted job collector for Hunter.
#
# Sources (diversified):
# - Greenhouse board APIs (curated company list)
# - Remotive API
# - RemoteOK API
# - Arbeitnow API
#
# Browser use:
# - Optional agent-browser fetch path for RemoteOK when env
#   USE_AGENT_BROWSER_REMOTEOK=1.
# =============================================================================

set -euo pipefail

TARGET_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --target-only) TARGET_ONLY=true ;;
    --help|-h)
      echo "Usage: collect-jobs-agent-browser.sh [--target-only]"
      exit 0
      ;;
  esac
done

TIMESTAMP="$(date -Iseconds)"

python3 - "$TARGET_ONLY" "$TIMESTAMP" <<'PY'
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen

TARGET_ONLY = (sys.argv[1].lower() == "true")
TIMESTAMP = sys.argv[2]

# -----------------------------------------------------------------------------
# Tunables
# -----------------------------------------------------------------------------
MAX_AGE_DAYS = int(os.environ.get("JOBS_COLLECT_MAX_AGE_DAYS", "10"))
PER_SOURCE_LIMIT = int(os.environ.get("JOBS_PER_SOURCE_LIMIT", "60"))
PER_GREENHOUSE_BOARD_LIMIT = int(os.environ.get("JOBS_PER_GREENHOUSE_BOARD_LIMIT", "15"))
USE_AGENT_BROWSER_REMOTEOK = os.environ.get("USE_AGENT_BROWSER_REMOTEOK", "0") == "1"
USE_AGGREGATOR_SOURCES = os.environ.get("USE_AGGREGATOR_SOURCES", "0") == "1"

DEFAULT_GREENHOUSE_BOARDS = [
    "stripe",
    "airtable",
    "datadog",
    "cloudflare",
    "anthropic",
    "figma",
    "coinbase",
    "roblox",
    "amazon",
    "microsoft",
    "google",
    "meta",
    "apple",
    "nvidia",
    "tesla",
    "netflix",
    "uber",
    "lyft",
    "spotify",
    "snap",
    "pinterest",
    "reddit",
    "snapchat",
    "twitter",
    "discord",
    "twitch",
]

# Lever boards (different from Greenhouse)
DEFAULT_LEVER_BOARDS = [
    "plaid",
    "notion",
    "twilio",
    "lyft",
    "airbnb",
    "doordash",
    "square",
    "snowflake",
    "hashicorp",
    "robinhood",
]

greenhouse_boards = [
    b.strip() for b in os.environ.get("GREENHOUSE_BOARDS", ",".join(DEFAULT_GREENHOUSE_BOARDS)).split(",") if b.strip()
]

lever_boards = [
    b.strip() for b in os.environ.get("LEVER_BOARDS", ",".join(DEFAULT_LEVER_BOARDS)).split(",") if b.strip()
]

UA = "Mozilla/5.0 (OpenClaw Hunter Collector)"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", str(text))
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:240]


def fetch_json(url: str, timeout: int = 20):
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def fetch_json_with_agent_browser(url: str):
    """Optional browser-based JSON fetch for bot-sensitive endpoints."""
    try:
        subprocess.run(["agent-browser", "close"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        opened = subprocess.run(["agent-browser", "open", url], capture_output=True, text=True, check=False)
        if opened.returncode != 0:
            return None
        body = subprocess.run(["agent-browser", "get", "text", "body"], capture_output=True, text=True, check=False)
        subprocess.run(["agent-browser", "close"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if body.returncode != 0:
            return None
        return json.loads(body.stdout)
    except Exception:
        return None


def parse_dt(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    if s.isdigit():
        try:
            ts = int(s)
            if ts > 1_000_000_000_000:
                ts = ts / 1000
            if ts > 1_000_000_000:
                return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            pass

    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def is_recent(posted_value, max_age_days=MAX_AGE_DAYS):
    dt = parse_dt(posted_value)
    if dt is None:
        return True
    age = datetime.now(timezone.utc) - dt
    if age < timedelta(days=-2):
        return False
    return age <= timedelta(days=max_age_days)


def normalize_job(job):
    title = str(job.get("title") or "").strip()
    url = str(job.get("url") or "").strip()
    if not title or not url:
        return None

    tags = job.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    return {
        "title": title,
        "company": str(job.get("company") or "").strip(),
        "location": str(job.get("location") or "Remote").strip(),
        "salary": str(job.get("salary") or ""),
        "url": url,
        "posted_at": str(job.get("posted_at") or ""),
        "tags": tags[:10],
        "description_snippet": clean_html(job.get("description_snippet") or ""),
        "source": str(job.get("source") or "Unknown"),
    }


TARGET_TITLES = [
    "software engineer", "software developer", "backend", "front end", "frontend", "full stack", "fullstack",
    "data engineer", "data analyst", "data scientist", "analytics engineer", "ml engineer", "machine learning",
    "ai engineer", "devops", "site reliability", "sre", "cloud engineer", "platform engineer", "python",
    "node", "react", "typescript", "java", "golang", "rust", "security engineer", "devsecops",
]

EXCLUDE_TITLES = [
    "account director", "account manager", "office assistant", "recruiter", "sales", "customer support",
    "talent acquisition", "copywriter", "social media", "nurse", "pharmacist", "teacher",
    "legal", "counsel", "attorney", "compliance", "hr ", "human resources", "marketing",
]


def matches_target(job):
    title = f"{job.get('title','')}".lower()
    tags_text = " ".join(job.get('tags', [])).lower()
    text = f"{title} {tags_text}"
    if any(x in text for x in EXCLUDE_TITLES):
        return False
    # Prefer explicit role-title matching
    if any(x in title for x in TARGET_TITLES):
        return True
    # Allow tech-tag fallback for sparse titles
    tech_tag_fallback = ["python", "backend", "frontend", "full-stack", "devops", "machine-learning", "data-engineering"]
    return any(x in tags_text for x in tech_tag_fallback)


# -----------------------------------------------------------------------------
# Source adapters
# -----------------------------------------------------------------------------
def collect_greenhouse():
    out = []
    for board in greenhouse_boards:
        try:
            data = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
            jobs = data.get("jobs", [])
            board_hits = 0
            for j in jobs:
                title = j.get("title", "")
                metadata = j.get("metadata", {})
                company_from_meta = metadata.get("company_name") if isinstance(metadata, dict) else None
                company = company_from_meta or board.replace("-", " ").title()
                location = (j.get("location") or {}).get("name", "")
                dept_names = [d.get("name", "") for d in j.get("departments", []) if isinstance(d, dict) and d.get("name")]
                candidate = {
                    "title": title,
                    "company": company,
                    "location": location or "Unknown",
                    "salary": "",
                    "url": j.get("absolute_url", ""),
                    "posted_at": j.get("updated_at") or j.get("updatedAt") or j.get("created_at") or "",
                    "tags": (dept_names + [board])[:6],
                    "description_snippet": clean_html(j.get("content", "")),
                    "source": f"Greenhouse:{board}",
                }
                if TARGET_ONLY and not matches_target(candidate):
                    continue
                out.append(candidate)
                board_hits += 1
                if board_hits >= PER_GREENHOUSE_BOARD_LIMIT:
                    break
        except Exception:
            continue
    return out


def collect_remotive():
    out = []
    categories = ["software-dev", "data", "devops-sysadmin", "cyber-security"]
    for cat in categories:
        try:
            data = fetch_json(f"https://remotive.com/api/remote-jobs?category={cat}&limit={PER_SOURCE_LIMIT}")
            for j in data.get("jobs", [])[:PER_SOURCE_LIMIT]:
                out.append({
                    "title": j.get("title", ""),
                    "company": j.get("company_name", ""),
                    "location": j.get("candidate_required_location", "Remote"),
                    "salary": j.get("salary", ""),
                    "url": j.get("url", ""),
                    "posted_at": j.get("publication_date", ""),
                    "tags": j.get("tags", [])[:6] if isinstance(j.get("tags", []), list) else [],
                    "description_snippet": clean_html(j.get("description", "")),
                    "source": "Remotive",
                })
        except Exception:
            continue
    return out


def collect_remoteok():
    out = []
    data = None
    if USE_AGENT_BROWSER_REMOTEOK:
        data = fetch_json_with_agent_browser("https://remoteok.com/api")
    if data is None:
        try:
            data = fetch_json("https://remoteok.com/api")
        except Exception:
            data = []

    if isinstance(data, list):
        for j in data:
            if not isinstance(j, dict) or "position" not in j:
                continue
            tags = j.get("tags", [])
            if not isinstance(tags, list):
                tags = []
            out.append({
                "title": j.get("position", ""),
                "company": j.get("company", ""),
                "location": j.get("location", "Remote") or "Remote",
                "salary": "",
                "url": j.get("url", ""),
                "posted_at": j.get("date", ""),
                "tags": tags[:6],
                "description_snippet": clean_html(j.get("description", "")),
                "source": "RemoteOK",
            })
    return out[:PER_SOURCE_LIMIT]


def collect_arbeitnow():
    out = []
    try:
        data = fetch_json("https://www.arbeitnow.com/api/job-board-api")
        for j in data.get("data", [])[:PER_SOURCE_LIMIT]:
            tags = j.get("tags", [])
            if not isinstance(tags, list):
                tags = []
            out.append({
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": "Remote" if j.get("remote") else j.get("location", ""),
                "salary": "",
                "url": j.get("url", ""),
                "posted_at": str(j.get("created_at", "")),
                "tags": tags[:6],
                "description_snippet": clean_html(j.get("description", "")),
                "source": "Arbeitnow",
            })
    except Exception:
        pass
    return out


def collect_lever():
    """Collect jobs from Lever API."""
    out = []
    for board in lever_boards:
        try:
            data = fetch_json(f"https://api.lever.co/v0/postings/{board}")
            if not isinstance(data, list):
                continue
            for j in data[:PER_GREENHOUSE_BOARD_LIMIT]:
                categories = j.get("categories", {})
                posted = j.get("createdAt")
                out.append({
                    "title": j.get("text", ""),
                    "company": board.replace("-", " ").title(),
                    "location": categories.get("location", "Unknown") or categories.get("team", "Unknown"),
                    "salary": categories.get("salary", ""),
                    "url": j.get("applyUrl", ""),
                    "posted_at": str(posted) if posted else "",
                    "tags": [categories.get("team", ""), categories.get("location", "")][:5],
                    "description_snippet": clean_html(j.get("description", "")),
                    "source": f"Lever:{board}",
                })
        except Exception:
            continue
    return out


# -----------------------------------------------------------------------------
# Collect + normalize + filter
# -----------------------------------------------------------------------------
collected = []
# Tier 1: first-party ATS feeds (preferred)
collected.extend(collect_greenhouse())
collected.extend(collect_lever())

# Tier 2: aggregator feeds (optional fallback)
if USE_AGGREGATOR_SOURCES:
    collected.extend(collect_remotive())
    collected.extend(collect_remoteok())
    collected.extend(collect_arbeitnow())

normalized = []
for j in collected:
    nj = normalize_job(j)
    if nj:
        normalized.append(nj)

# Deduplicate (url first, then title+company)
seen = set()
unique = []
for j in normalized:
    key = (
        (j.get("url") or "").strip().lower(),
        (j.get("title") or "").strip().lower(),
        (j.get("company") or "").strip().lower(),
    )
    if key in seen:
        continue
    seen.add(key)
    unique.append(j)

# Freshness
unique = [j for j in unique if is_recent(j.get("posted_at"))]

# Targeted role filter
if TARGET_ONLY:
    unique = [j for j in unique if matches_target(j)]

# Keep deterministic order by newest posted date where possible
unique.sort(key=lambda j: parse_dt(j.get("posted_at")) or datetime(1970,1,1,tzinfo=timezone.utc), reverse=True)

source_counts = {}
for j in unique:
    src = j.get("source", "Unknown")
    source_counts[src] = source_counts.get(src, 0) + 1

output = {
    "fetched_at": TIMESTAMP,
    "sources": sorted(list(source_counts.keys())),
    "source_counts": source_counts,
    "fresh_window_days": MAX_AGE_DAYS,
    "aggregator_sources_enabled": USE_AGGREGATOR_SOURCES,
    "total": len(unique),
    "jobs": unique,
}

print(json.dumps(output, indent=2, default=str))
PY
