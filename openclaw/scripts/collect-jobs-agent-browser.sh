#!/usr/bin/env bash
# =============================================================================
# collect-jobs-agent-browser.sh — Agent Browser based targeted job collector
# =============================================================================
# Outputs JSON:
# {
#   "fetched_at": "ISO8601",
#   "sources": ["Remotive", "RemoteOK", ...],
#   "total": 24,
#   "jobs": [ ...normalized jobs... ]
# }
#
# Primary sources are fetched via agent-browser (browser context), with HTTP
# fallback where needed. This avoids brittle shell JSON interpolation.
# =============================================================================

set -euo pipefail

DASHBOARD_URL="${DASHBOARD_URL:-http://45.55.191.125}"
TIMEOUT="${COLLECT_TIMEOUT:-25}"
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
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

log() { echo "[collect-jobs-agent-browser] $*" >&2; }

write_json_or_empty() {
  local out="$1"
  cat > "$out" || true
  python3 - "$out" <<'PY' >/dev/null 2>&1 || echo '{}' > "$out"
import json,sys
p=sys.argv[1]
with open(p,'r',encoding='utf-8',errors='ignore') as f:
    json.load(f)
PY
}

fetch_agent_browser_json() {
  local url="$1"
  local out="$2"

  if ! command -v agent-browser >/dev/null 2>&1; then
    log "agent-browser missing; writing empty JSON for $url"
    echo '{}' > "$out"
    return 0
  fi

  # Reset browser session to reduce stuck-context errors.
  agent-browser close >/dev/null 2>&1 || true

  if ! agent-browser open "$url" >/dev/null 2>&1; then
    log "WARNING: agent-browser open failed for $url"
    echo '{}' > "$out"
    agent-browser close >/dev/null 2>&1 || true
    return 0
  fi

  # Body text from JSON endpoints is valid JSON text.
  agent-browser get text body 2>/dev/null | write_json_or_empty "$out"
  agent-browser close >/dev/null 2>&1 || true
}

fetch_http_json() {
  local url="$1"
  local out="$2"
  curl -s --max-time "$TIMEOUT" -H "Accept: application/json" "$url" | write_json_or_empty "$out"
}

log "Starting collection at $TIMESTAMP"

# 1) Dashboard API (already role-filtered in app.py)
fetch_http_json "${DASHBOARD_URL}/api/jobs.py?force=1" "$WORKDIR/dashboard.json"

# 2) Remotive via agent-browser
fetch_agent_browser_json "https://remotive.com/api/remote-jobs?category=software-dev&limit=50" "$WORKDIR/remotive.json"

# 3) RemoteOK via agent-browser
fetch_agent_browser_json "https://remoteok.com/api" "$WORKDIR/remoteok.json"

# 4) Arbeitnow via HTTP
fetch_http_json "https://www.arbeitnow.com/api/job-board-api" "$WORKDIR/arbeitnow.json"

python3 - "$WORKDIR" "$TIMESTAMP" "$TARGET_ONLY" <<'PY'
import json,sys
from pathlib import Path

workdir=Path(sys.argv[1])
timestamp=sys.argv[2]
target_only=sys.argv[3].lower()=="true"

def load(name):
    p=workdir/name
    try:
        return json.loads(p.read_text(encoding='utf-8',errors='ignore'))
    except Exception:
        return {}

dashboard=load('dashboard.json')
remotive=load('remotive.json')
remoteok=load('remoteok.json')
arbeitnow=load('arbeitnow.json')

jobs=[]

# dashboard /api/jobs.py shape
for j in dashboard.get('jobs',[]) if isinstance(dashboard,dict) else []:
    if isinstance(j,dict):
        jobs.append({
            'title': j.get('title',''),
            'company': j.get('company',''),
            'location': j.get('location','Remote'),
            'salary': j.get('salary',''),
            'url': j.get('url',''),
            'posted_at': j.get('posted','') or j.get('posted_at',''),
            'tags': j.get('tags',[]) if isinstance(j.get('tags',[]),list) else [],
            'description_snippet': j.get('snippet','')[:220],
            'source': j.get('source','Dashboard'),
        })

# remotive shape
for j in remotive.get('jobs',[]) if isinstance(remotive,dict) else []:
    if isinstance(j,dict):
        jobs.append({
            'title': j.get('title',''),
            'company': j.get('company_name',''),
            'location': j.get('candidate_required_location','Remote'),
            'salary': j.get('salary',''),
            'url': j.get('url',''),
            'posted_at': j.get('publication_date',''),
            'tags': j.get('tags',[]) if isinstance(j.get('tags',[]),list) else [],
            'description_snippet': (j.get('description','') or '')[:220],
            'source': 'Remotive',
        })

# remoteok shape (first entry is metadata)
if isinstance(remoteok,list):
    for j in remoteok:
        if not isinstance(j,dict) or 'position' not in j:
            continue
        jobs.append({
            'title': j.get('position',''),
            'company': j.get('company',''),
            'location': j.get('location','Remote') or 'Remote',
            'salary': '',
            'url': j.get('url',''),
            'posted_at': j.get('date',''),
            'tags': j.get('tags',[]) if isinstance(j.get('tags',[]),list) else [],
            'description_snippet': (j.get('description','') or '')[:220],
            'source': 'RemoteOK',
        })

# arbeitnow shape
for j in arbeitnow.get('data',[]) if isinstance(arbeitnow,dict) else []:
    if not isinstance(j,dict):
        continue
    jobs.append({
        'title': j.get('title',''),
        'company': j.get('company_name',''),
        'location': 'Remote' if j.get('remote',False) else j.get('location',''),
        'salary': '',
        'url': j.get('url',''),
        'posted_at': str(j.get('created_at','')),
        'tags': j.get('tags',[]) if isinstance(j.get('tags',[]),list) else [],
        'description_snippet': (j.get('description','') or '')[:220],
        'source': 'Arbeitnow',
    })

# dedupe by title+company+url
seen=set()
unique=[]
for j in jobs:
    title=(j.get('title') or '').strip()
    company=(j.get('company') or '').strip()
    url=(j.get('url') or '').strip()
    if not title or not url:
        continue
    key=(title.lower(),company.lower(),url.lower())
    if key in seen:
        continue
    seen.add(key)
    unique.append(j)

if target_only:
    target_titles=[
      'software engineer','software developer','backend','full stack','fullstack',
      'data engineer','data analyst','data scientist','analytics engineer',
      'ml engineer','machine learning','ai engineer','python developer',
      'devops','sre','cloud engineer','platform engineer','bi engineer','bi developer'
    ]
    target_locs=['remote','usa','united states','fort wayne','indiana','indianapolis','dallas','irving','texas','worldwide']
    def keep(j):
        t=(j.get('title') or '').lower()
        l=(j.get('location') or '').lower()
        return any(x in t for x in target_titles) and (any(x in l for x in target_locs) or not l)
    unique=[j for j in unique if keep(j)]

sources=sorted(list({(j.get('source') or 'Unknown') for j in unique}))
print(json.dumps({
  'fetched_at': timestamp,
  'sources': sources,
  'total': len(unique),
  'jobs': unique
}, indent=2, default=str))
PY

log "Collection complete"
