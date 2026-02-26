#!/usr/bin/env python3
"""
IT Jobs Intelligence Dashboard — Flask Application
Converted from CGI-bin scripts for deployment on DigitalOcean Droplet.
Run with: gunicorn -w 2 -b 0.0.0.0:8000 app:app
"""
import json
import logging
import os
import re
import html
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
from xml.etree import ElementTree

from flask import Flask, request, jsonify, send_from_directory, abort

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ─── App Setup ────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", static_url_path="/static")

# Data directory for cache and dashboard_data files
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

JOBS_CACHE_FILE    = DATA_DIR / "jobs_cache.json"
NEWS_CACHE_FILE    = DATA_DIR / "news_cache.json"
DASHBOARD_DATA_FILE = DATA_DIR / "dashboard_data.json"

CACHE_TTL = 1800   # 30 minutes
MAX_BODY_SIZE = 1_048_576  # 1 MB
JOBS_SNAPSHOT_MAX_AGE_SECONDS = 6 * 3600  # Hunter snapshot freshness window
JOBS_SNAPSHOT_MAX_ITEMS = 1000
FALLBACK_SECRET = "REPLACE_ME_WITH_A_RANDOM_SECRET_STRING_32_CHARS_MINIMUM"


# ─── CORS helper ──────────────────────────────────────────────────────────────
def cors_response(data, status=200):
    resp = jsonify(data)
    resp.status_code = status
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    return resp


# ══════════════════════════════════════════════════════════════════════════════
#  JOBS LOGIC  (ported from cgi-bin/jobs.py)
# ══════════════════════════════════════════════════════════════════════════════

def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', str(text))
    text = html.unescape(text)
    return text[:250].strip()


def fetch_remotive(query="", timeout=15):
    jobs = []
    try:
        cats = ["software-dev", "data", "devops-sysadmin", "cyber-security"]
        for cat in cats[:2]:
            url = f"https://remotive.com/api/remote-jobs?category={cat}&limit=25"
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            for j in data.get("jobs", []):
                jobs.append({
                    "title":    j.get("title", ""),
                    "company":  j.get("company_name", ""),
                    "location": j.get("candidate_required_location", "Anywhere"),
                    "salary":   j.get("salary", ""),
                    "type":     "Remote",
                    "posted":   j.get("publication_date", ""),
                    "url":      j.get("url", ""),
                    "tags":     j.get("tags", [])[:6],
                    "source":   "Remotive",
                    "snippet":  clean_html(j.get("description", "")),
                })
    except Exception:
        pass
    return jobs


def fetch_remoteok(timeout=15):
    jobs = []
    try:
        url = "https://remoteok.com/api"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        for j in data[1:30]:  # First item is metadata
            if isinstance(j, dict):
                tags = j.get("tags", [])
                if isinstance(tags, list):
                    tags = tags[:6]
                else:
                    tags = []
                jobs.append({
                    "title":    j.get("position", ""),
                    "company":  j.get("company", ""),
                    "location": j.get("location", "Remote"),
                    "salary":   "",
                    "type":     "Remote",
                    "posted":   j.get("date", ""),
                    "url":      j.get("url", f"https://remoteOK.com/remote-jobs/{j.get('slug', '')}"),
                    "tags":     tags,
                    "source":   "RemoteOK",
                    "snippet":  clean_html(j.get("description", "")),
                })
    except Exception:
        pass
    return jobs


def fetch_arbeitnow(timeout=15):
    jobs = []
    try:
        url = "https://www.arbeitnow.com/api/job-board-api"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        for j in data.get("data", [])[:25]:
            tags = j.get("tags", [])
            if isinstance(tags, list):
                tags = tags[:6]
            else:
                tags = []
            jobs.append({
                "title":    j.get("title", ""),
                "company":  j.get("company_name", ""),
                "location": j.get("location", ""),
                "salary":   "",
                "type":     "Full-time" if not j.get("remote", False) else "Remote",
                "posted":   str(j.get("created_at", "")),
                "url":      j.get("url", ""),
                "tags":     tags,
                "source":   "Arbeitnow",
                "snippet":  clean_html(j.get("description", "")),
            })
    except Exception:
        pass
    return jobs


def normalize_ingested_job(job: dict) -> dict:
    """Normalize incoming Hunter-provided jobs to dashboard schema."""
    if not isinstance(job, dict):
        return {}

    source_raw = str(job.get("source", "") or "")
    source_lower = source_raw.lower()
    if "remotive" in source_lower:
        source = "Remotive"
    elif "remoteok" in source_lower:
        source = "RemoteOK"
    elif "arbeitnow" in source_lower:
        source = "Arbeitnow"
    else:
        source = source_raw or "Hunter"

    location = str(
        job.get("location")
        or job.get("candidate_required_location")
        or "Remote"
    )
    type_value = str(job.get("type") or "")
    if not type_value:
        type_value = "Remote" if "remote" in location.lower() else "Full-time"

    tags = job.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    return {
        "title": str(job.get("title") or job.get("job_title") or "").strip(),
        "company": str(job.get("company") or job.get("company_name") or "").strip(),
        "location": location,
        "salary": str(job.get("salary") or ""),
        "type": type_value,
        "posted": str(
            job.get("posted")
            or job.get("posted_at")
            or job.get("publication_date")
            or job.get("date")
            or job.get("created_at")
            or ""
        ),
        "url": str(job.get("url") or job.get("job_url") or ""),
        "tags": tags[:8],
        "source": source,
        "snippet": clean_html(
            job.get("snippet")
            or job.get("description_snippet")
            or job.get("description")
            or ""
        ),
    }


# ── Role relevance filter ─────────────────────────────────────────────────────
# Only show IT / engineering / data roles on the dashboard
TARGET_ROLE_KEYWORDS = [
    "software engineer", "software developer", "data engineer", "data analyst",
    "data scientist", "ml engineer", "machine learning", "ai engineer",
    "full stack", "fullstack", "front end", "frontend", "front-end",
    "back end", "backend", "back-end", "python", "java developer",
    "devops", "sre", "site reliability", "cloud engineer", "platform engineer",
    "analytics engineer", "bi engineer", "bi developer", "business intelligence",
    "systems engineer", "infrastructure", "security engineer", "devsecops",
    "react", "node", "golang", "rust developer", "typescript",
    "database", "etl", "data pipeline", "airflow", "spark",
    "aws", "azure", "gcp", "kubernetes", "docker",
    "qa engineer", "test engineer", "sdet", "automation engineer",
    "solutions architect", "technical lead", "tech lead", "engineering manager",
]

EXCLUDE_ROLE_KEYWORDS = [
    "account director", "account manager", "account executive",
    "office assistant", "office manager", "receptionist",
    "sales rep", "sales manager", "sales associate",
    "customer success", "customer support", "customer service",
    "copywriter", "content writer", "social media manager",
    "hr manager", "recruiter", "talent acquisition",
    "graphic designer", "interior designer",
    "nurse", "doctor", "pharmacist", "dental",
    "teacher", "tutor", "instructor",
    "driver", "warehouse", "janitor", "cleaner",
    "bookkeeper", "payroll", "billing specialist",
]

def is_relevant_role(job):
    """Check if a job is an IT/engineering role."""
    title = job.get("title", "").lower()
    tags  = " ".join(job.get("tags", [])).lower()
    text  = f"{title} {tags}"

    # Exclude obvious non-tech roles
    for kw in EXCLUDE_ROLE_KEYWORDS:
        if kw in title:
            return False

    # Include if title or tags match target keywords
    for kw in TARGET_ROLE_KEYWORDS:
        if kw in text:
            return True

    # Also include if common tech tags are present
    tech_tags = {"python", "javascript", "react", "node", "aws", "docker",
                 "kubernetes", "sql", "typescript", "java", "golang", "rust",
                 "devops", "machine-learning", "data", "ai", "ml", "cloud",
                 "backend", "frontend", "full-stack", "engineering"}
    job_tags_lower = {t.lower() for t in job.get("tags", [])}
    if job_tags_lower & tech_tags:
        return True

    return False


def filter_jobs(jobs, query="", location="", job_type=""):
    # Always apply role relevance filter first
    relevant = [j for j in jobs if is_relevant_role(j)]

    if not query and not location and not job_type:
        return relevant
    filtered = []
    q   = query.lower()
    loc = location.lower()
    for j in relevant:
        text = f"{j['title']} {j['company']} {' '.join(j['tags'])} {j['snippet']}".lower()
        if q and q not in text:
            continue
        if loc and loc != "all" and loc not in j.get("location", "").lower() and loc not in text:
            continue
        if job_type and job_type != "all":
            if job_type == "remote" and "remote" not in j.get("type", "").lower() and "remote" not in j.get("location", "").lower():
                continue
        filtered.append(j)
    return filtered


# ══════════════════════════════════════════════════════════════════════════════
#  NEWS LOGIC  (ported from cgi-bin/news.py)
# ══════════════════════════════════════════════════════════════════════════════

RSS_FEEDS = {
    "TechCrunch Layoffs": "https://techcrunch.com/tag/layoffs/feed/",
    "Hacker News Best":   "https://hnrss.org/best?q=hiring+OR+layoffs+OR+AI+jobs&count=15",
    "Dice Insights":      "https://www.dice.com/career-advice/feed",
    "The Verge Tech":     "https://www.theverge.com/rss/tech/index.xml",
}

NEWS_KEYWORDS = [
    "tech", "ai", "layoff", "hiring", "job", "engineer", "developer",
    "software", "data", "machine learning", "startup", "cloud", "cyber",
    "openai", "google", "meta", "amazon", "microsoft", "salary", "remote",
]


def fetch_rss(url, source_name, timeout=12):
    items = []
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 ITJobsDashboard/2.0"})
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        root = ElementTree.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # RSS 2.0
        for item in root.findall(".//item")[:10]:
            title = item.findtext("title", "")
            link  = item.findtext("link", "")
            pub   = item.findtext("pubDate", "")
            desc  = item.findtext("description", "")
            text  = (title + " " + desc).lower()
            if any(k in text for k in NEWS_KEYWORDS):
                items.append({
                    "title":     title.strip(),
                    "url":       link.strip(),
                    "published": pub.strip(),
                    "source":    source_name,
                    "snippet":   desc[:300].replace("<![CDATA[", "").replace("]]>", "").strip(),
                })

        # Atom
        for entry in root.findall("atom:entry", ns)[:10]:
            title   = entry.findtext("atom:title", "", ns)
            link_el = entry.find("atom:link", ns)
            link    = link_el.get("href", "") if link_el is not None else ""
            pub     = (entry.findtext("atom:published", "", ns)
                       or entry.findtext("atom:updated", "", ns))
            desc    = (entry.findtext("atom:summary", "", ns)
                       or entry.findtext("atom:content", "", ns) or "")
            text    = (title + " " + desc).lower()
            if any(k in text for k in NEWS_KEYWORDS):
                items.append({
                    "title":     title.strip(),
                    "url":       link.strip(),
                    "published": pub.strip(),
                    "source":    source_name,
                    "snippet":   desc[:300].strip(),
                })
    except Exception:
        pass  # Fail silently per source
    return items


def get_news_cached():
    if NEWS_CACHE_FILE.exists():
        try:
            cache = json.loads(NEWS_CACHE_FILE.read_text())
            if time.time() - cache.get("ts", 0) < CACHE_TTL:
                return cache
        except Exception:
            pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  UPDATE LOGIC  (ported from cgi-bin/update.py)
# ══════════════════════════════════════════════════════════════════════════════

def get_auth_token() -> str:
    return os.environ.get("DASHBOARD_UPDATE_TOKEN", FALLBACK_SECRET)


def _ct_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to mitigate timing attacks."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a.encode(), b.encode()):
        result |= x ^ y
    return result == 0


def validate_bearer(env_token: str) -> bool:
    """Check Authorization header contains a valid Bearer token."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    provided = auth_header[len("Bearer "):].strip()
    return _ct_compare(provided, env_token)


def load_current_data() -> dict:
    """Load existing dashboard_data.json or return a default skeleton."""
    if DASHBOARD_DATA_FILE.exists():
        try:
            with open(DASHBOARD_DATA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass  # fall through to default

    return {
        "meta": {
            "schema_version": "1.0",
            "created_at": datetime.now().astimezone().isoformat(),
            "last_updated": None,
            "update_source": None,
        },
        "market_status": "Initializing",
        "kpi_updates":   {},
        "trend_alerts":  [],
        "new_insights":  [],
        "jobs_snapshot": {
            "fetched_at": None,
            "updated_at": None,
            "source": None,
            "sources": [],
            "total": 0,
            "jobs": [],
        },
        "history":       [],  # rolling log of past updates (last 50 kept)
    }


def save_data(data: dict):
    """Write data dict to dashboard_data.json atomically."""
    tmp_file = str(DASHBOARD_DATA_FILE) + ".tmp"
    with open(tmp_file, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp_file, str(DASHBOARD_DATA_FILE))  # atomic on POSIX


def merge_update(current: dict, payload: dict) -> dict:
    """
    Merge an incoming payload into current data.
    Only fields present in the payload are updated — partial updates are safe.
    """
    now_iso = payload.get("timestamp") or datetime.now().astimezone().isoformat()

    # Record history entry (keep last 50)
    history_entry = {
        "timestamp":     now_iso,
        "market_status": payload.get("market_status"),
        "kpi_snapshot":  payload.get("kpi_updates", {}),
        "alert_count":   len(payload.get("trend_alerts", [])),
        "insight_count": len(payload.get("new_insights", [])),
    }
    history = current.get("history", [])
    history.append(history_entry)
    if len(history) > 50:
        history = history[-50:]

    # Build merged data
    merged = dict(current)
    update_source = payload.get("update_source") or current.get("meta", {}).get("update_source") or "atlas"

    merged["meta"] = {
        "schema_version": "1.0",
        "created_at":     current.get("meta", {}).get("created_at", now_iso),
        "last_updated":   now_iso,
        "update_source":  update_source,
    }

    if "market_status" in payload:
        merged["market_status"] = payload["market_status"]

    if "kpi_updates" in payload:
        existing_kpis = dict(current.get("kpi_updates", {}))
        existing_kpis.update(payload["kpi_updates"])
        merged["kpi_updates"] = existing_kpis

    if "trend_alerts" in payload:
        # Prepend new alerts, cap at 100 total
        existing_alerts = current.get("trend_alerts", [])
        merged["trend_alerts"] = (payload["trend_alerts"] + existing_alerts)[:100]

    if "new_insights" in payload:
        # Prepend new insights, cap at 50 total
        existing_insights = current.get("new_insights", [])
        merged["new_insights"] = (payload["new_insights"] + existing_insights)[:50]

    if "jobs_snapshot" in payload:
        incoming_snapshot = payload.get("jobs_snapshot", {})
        incoming_jobs = incoming_snapshot.get("jobs", []) if isinstance(incoming_snapshot, dict) else []
        normalized_jobs = [normalize_ingested_job(j) for j in incoming_jobs[:JOBS_SNAPSHOT_MAX_ITEMS]]
        normalized_jobs = [j for j in normalized_jobs if j.get("title") and j.get("url")]

        merged["jobs_snapshot"] = {
            "fetched_at": incoming_snapshot.get("fetched_at") or now_iso,
            "updated_at": now_iso,
            "source": update_source,
            "sources": incoming_snapshot.get("sources", []),
            "total": len(normalized_jobs),
            "jobs": normalized_jobs,
        }

    merged["history"] = history
    return merged


# ══════════════════════════════════════════════════════════════════════════════
#  FLASK ROUTES
# ══════════════════════════════════════════════════════════════════════════════

# ── CORS preflight for all /api/* routes ──────────────────────────────────────
@app.route("/api/<path:path>", methods=["OPTIONS"])
def api_options(path):
    resp = app.make_response("")
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    return resp, 200


# ── GET /api/jobs.py ───────────────────────────────────────────────────────────
@app.route("/api/jobs.py", methods=["GET"])
def api_jobs():
    query    = request.args.get("query", "").strip()
    location = request.args.get("location", "").strip()
    job_type = request.args.get("type", "all")
    page     = int(request.args.get("page", "1"))
    force    = request.args.get("force", "0") == "1"
    page_size = 20

    # Prefer Hunter-provided snapshot unless force refresh is requested
    all_jobs      = []
    from_cache    = False
    from_snapshot = False
    fetched_at    = datetime.now(timezone.utc).isoformat()

    if not force:
        try:
            current_data = load_current_data()
            snapshot = current_data.get("jobs_snapshot", {})
            snapshot_jobs = snapshot.get("jobs", []) if isinstance(snapshot, dict) else []
            snapshot_updated_at = snapshot.get("updated_at")
            snapshot_age_ok = False
            if snapshot_updated_at:
                try:
                    su = datetime.fromisoformat(snapshot_updated_at)
                    if su.tzinfo is None:
                        su = su.replace(tzinfo=timezone.utc)
                    snapshot_age_ok = (datetime.now(timezone.utc) - su).total_seconds() <= JOBS_SNAPSHOT_MAX_AGE_SECONDS
                except Exception:
                    snapshot_age_ok = False

            if snapshot_jobs and snapshot_age_ok:
                all_jobs = [normalize_ingested_job(j) for j in snapshot_jobs]
                all_jobs = [j for j in all_jobs if j.get("title") and j.get("url")]
                from_snapshot = True
                fetched_at = snapshot.get("fetched_at") or fetched_at
        except Exception:
            pass

    # Fallback to local cache of upstream market APIs
    if not all_jobs and not force and JOBS_CACHE_FILE.exists():
        try:
            cache = json.loads(JOBS_CACHE_FILE.read_text())
            if time.time() - cache.get("ts", 0) < CACHE_TTL:
                all_jobs   = cache.get("all_jobs", [])
                from_cache = True
        except Exception:
            pass

    if not all_jobs:
        logger.info("Fetching fresh jobs from APIs")
        all_jobs = fetch_remotive(query) + fetch_remoteok() + fetch_arbeitnow()
        try:
            JOBS_CACHE_FILE.write_text(json.dumps({"all_jobs": all_jobs, "ts": time.time()}))
        except Exception:
            pass

    # Filter
    filtered = filter_jobs(all_jobs, query, location, job_type)

    # Pagination
    start     = (page - 1) * page_size
    end       = start + page_size
    page_jobs = filtered[start:end]

    # Stats
    source_counts = {}
    remote_count  = 0
    tag_counts    = {}
    for j in filtered:
        src = j.get("source", "Unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
        if "remote" in j.get("type", "").lower() or "remote" in j.get("location", "").lower():
            remote_count += 1
        for t in j.get("tags", []):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:12]

    result = {
        "jobs":          page_jobs,
        "total":         len(filtered),
        "page":          page,
        "page_size":     page_size,
        "total_pages":   (len(filtered) + page_size - 1) // page_size,
        "source_counts": source_counts,
        "remote_count":  remote_count,
        "onsite_count":  len(filtered) - remote_count,
        "top_tags":      [t[0] for t in top_tags],
        "from_cache":    from_cache,
        "from_snapshot": from_snapshot,
        "data_source":   "hunter_snapshot" if from_snapshot else "market_apis",
        "fetched_at":    fetched_at,
    }
    return cors_response(result)


# ── GET /api/news.py ───────────────────────────────────────────────────────────
@app.route("/api/news.py", methods=["GET"])
def api_news():
    force = request.args.get("force", "0") == "1"

    # Try cache first
    if not force:
        cached = get_news_cached()
        if cached:
            cached["from_cache"] = True
            return cors_response(cached)

    # Fetch fresh
    logger.info("Fetching fresh news from RSS feeds")
    all_items = []
    for name, url in RSS_FEEDS.items():
        all_items.extend(fetch_rss(url, name))

    # Deduplicate by title similarity
    seen   = set()
    unique = []
    for item in all_items:
        key = item["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    result = {
        "news":       unique[:30],
        "total":      len(unique),
        "sources":    list(RSS_FEEDS.keys()),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ts":         time.time(),
        "from_cache": False,
    }

    # Save cache
    try:
        NEWS_CACHE_FILE.write_text(json.dumps(result))
    except Exception:
        pass

    return cors_response(result)


# ── GET /api/update.py — return current dashboard data ────────────────────────
@app.route("/api/update.py", methods=["GET"])
def api_update_get():
    data = load_current_data()

    last_updated = data.get("meta", {}).get("last_updated")
    age_seconds  = None
    if last_updated:
        try:
            lu = datetime.fromisoformat(last_updated)
            if lu.tzinfo is None:
                lu = lu.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age_seconds = int((now - lu).total_seconds())
        except Exception:
            pass

    return cors_response({
        "ok":          True,
        "data":        data,
        "age_seconds": age_seconds,
    })


# ── POST /api/update.py — push new market intelligence data ───────────────────
@app.route("/api/update.py", methods=["POST"])
def api_update_post():
    # Validate auth
    expected_token = get_auth_token()
    if not validate_bearer(expected_token):
        return cors_response({
            "ok":    False,
            "error": "Unauthorized — invalid or missing Bearer token",
            "hint":  "Set Authorization: Bearer <DASHBOARD_UPDATE_TOKEN> header",
        }, 401)

    # Read body (honour Content-Length; fall back to reading up to MAX_BODY_SIZE)
    content_length_str = request.headers.get("Content-Length", "0")
    try:
        content_length = int(content_length_str)
    except ValueError:
        content_length = 0

    if content_length > MAX_BODY_SIZE:
        return cors_response({"ok": False, "error": "Request body too large"}, 413)

    raw_body = request.get_data(as_text=False)
    if len(raw_body) > MAX_BODY_SIZE:
        return cors_response({"ok": False, "error": "Request body too large"}, 413)

    # Parse JSON payload
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return cors_response({"ok": False, "error": f"Invalid JSON: {e}"}, 400)

    if not isinstance(payload, dict):
        return cors_response({"ok": False, "error": "Payload must be a JSON object"}, 400)

    # Validate types of optional fields
    if "kpi_updates" in payload and not isinstance(payload["kpi_updates"], dict):
        return cors_response({"ok": False, "error": "'kpi_updates' must be an object"}, 400)
    if "trend_alerts" in payload and not isinstance(payload["trend_alerts"], list):
        return cors_response({"ok": False, "error": "'trend_alerts' must be an array"}, 400)
    if "new_insights" in payload and not isinstance(payload["new_insights"], list):
        return cors_response({"ok": False, "error": "'new_insights' must be an array"}, 400)
    if "market_status" in payload and not isinstance(payload["market_status"], str):
        return cors_response({"ok": False, "error": "'market_status' must be a string"}, 400)
    if "update_source" in payload and not isinstance(payload["update_source"], str):
        return cors_response({"ok": False, "error": "'update_source' must be a string"}, 400)
    if "jobs_snapshot" in payload:
        if not isinstance(payload["jobs_snapshot"], dict):
            return cors_response({"ok": False, "error": "'jobs_snapshot' must be an object"}, 400)
        jobs = payload["jobs_snapshot"].get("jobs", [])
        if not isinstance(jobs, list):
            return cors_response({"ok": False, "error": "'jobs_snapshot.jobs' must be an array"}, 400)
        if len(jobs) > JOBS_SNAPSHOT_MAX_ITEMS:
            return cors_response({"ok": False, "error": f"'jobs_snapshot.jobs' exceeds max {JOBS_SNAPSHOT_MAX_ITEMS}"}, 400)

    # Merge and persist
    try:
        current = load_current_data()
        updated = merge_update(current, payload)
        save_data(updated)
        logger.info("Dashboard data updated successfully")
    except IOError as e:
        return cors_response({"ok": False, "error": f"Failed to write data file: {e}"}, 500)

    return cors_response({
        "ok":            True,
        "message":       "Dashboard data updated successfully",
        "timestamp":     updated["meta"]["last_updated"],
        "kpi_count":     len(payload.get("kpi_updates", {})),
        "alert_count":   len(payload.get("trend_alerts", [])),
        "insight_count": len(payload.get("new_insights", [])),
        "jobs_count":    len(payload.get("jobs_snapshot", {}).get("jobs", [])) if isinstance(payload.get("jobs_snapshot"), dict) else 0,
    })


# ── Static frontend ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

# Serve any file under /static/ directly (css, js, fonts, etc.)
# Flask handles this automatically via static_folder, but we add a catch-all
# so that paths like /css/styles.css (without /static/ prefix) also work if
# the HTML references them with ./css/... relative paths when served from /.
@app.route("/<path:filename>")
def serve_static_fallback(filename):
    """Serve static files referenced with relative paths from index.html."""
    static_path = Path(app.static_folder) / filename
    if static_path.exists() and static_path.is_file():
        return send_from_directory(app.static_folder, filename)
    abort(404)


# ── Health check ──────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "ts": datetime.now(timezone.utc).isoformat()})


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # For local dev only; production uses gunicorn
    app.run(host="0.0.0.0", port=5000, debug=False)
