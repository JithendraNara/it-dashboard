---
name: it-dashboard-manager
description: Manage the IT Jobs Intelligence Dashboard — collect jobs, analyze trends, push live updates, and send Discord alerts for matches and market shifts.
version: 1.1.0
author: Jithendra Nara
metadata:
  openclaw:
    emoji: "📊"
    bins:
      - curl
      - python3
      - jq
      - bash
    env: []
tags: [dashboard, jobs, monitoring, analytics, career]
user-invocable: true
---

# IT Dashboard Manager

Push live job market data to the dashboard at `http://45.55.191.125`.

## Quick Reference

- **Dashboard**: `http://45.55.191.125`
- **Update endpoint**: `POST /api/update.py` (Bearer token from `$DASHBOARD_UPDATE_TOKEN`)
- **GET endpoint**: `GET /api/update.py` (no auth, returns current data)
- **Scripts dir**: `~/.openclaw/skills/it-dashboard-manager/scripts/`
- **Discord channels**: `#job-hunt`, `#monitoring`, `#openclaw-ops`

## Data Collection

### Collect jobs
```bash
bash ~/.openclaw/skills/it-dashboard-manager/scripts/collect-jobs.sh > /tmp/jobs_raw.json
```
Fetches from Remotive, RemoteOK, Arbeitnow. Use `--target-only` to pre-filter.

### Collect trends
```bash
python3 ~/.openclaw/skills/it-dashboard-manager/scripts/collect-trends.py > /tmp/trends.json
```
Gets layoffs.fyi data, BLS unemployment, AI job share, remote ratio, news signals.

### Force-refresh dashboard caches
```bash
curl -s "${DASHBOARD_URL}/api/jobs.py?force=1" > /tmp/jobs_cgi.json
curl -s "${DASHBOARD_URL}/api/news.py?force=1" > /tmp/news_cgi.json
```

## Push Update

Build a JSON payload and POST it:
```bash
curl -s -X POST "${DASHBOARD_URL}/api/update.py" \
  -H "Authorization: Bearer ${DASHBOARD_UPDATE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d @/tmp/update_payload.json
```

Payload shape (all fields optional, partial updates merge):
```json
{
  "market_status": "Cautious Recovery",
  "kpi_updates": { "Active Job Postings": "12,847", "Last Atlas Scan": "2026-02-26 08:00 EST" },
  "trend_alerts": [{ "type": "layoff", "severity": "high", "title": "...", "body": "...", "source": "...", "url": "..." }],
  "new_insights": ["insight string"],
  "timestamp": "ISO8601"
}
```

Market status options: `Active Hiring` | `Cautious Recovery` | `Stable` | `Cooling` | `Significant Layoffs` | `Market Contraction`

## Job Matching

**Target roles** (partial match, case-insensitive): Software Engineer, Data Analyst, Data Engineer, ML Engineer, AI Engineer, Full Stack, Backend Engineer, Python Developer, Analytics Engineer, BI Engineer/Developer.

**Target locations**: Remote/USA, Fort Wayne IN, Indianapolis IN, Dallas/Irving TX, Indiana, Texas.

**Salary threshold**: >$120K annual (alert), >$150K (immediate alert). Unlisted = don't filter out.

**Priority skills** (+1 each, max 3): Python, SQL, AWS, AI/ML, Data Engineering (Spark/Kafka/Airflow/dbt), React/Next.js, Node/TypeScript, Azure/GCP, Tableau/Power BI.

**Scoring (0-10)**: Exact target role +3, related +1, Remote +2, local area +2, salary match +1, skill matches +1 each (max 3). Score ≥8 = alert `#job-hunt` immediately. 6-7 = daily briefing. 4-5 = weekly summary.

**Watch companies** (alert regardless of score): Luxoft, Capital One, Ascension Health, Tech Mahindra, Sloka Technologies, Cognizant.

## Discord Alerts

### Job match → #job-hunt
```
📊 **IT DASHBOARD — Job Match Alert** | {SCORE}/10
🔥 **{TITLE}** @ **{COMPANY}**
📍 {LOCATION} | 💰 {SALARY}
**Why this matches:** {REASONS}
🔗 Apply: {URL}
```

### Market shift → #monitoring
```
📊 **IT DASHBOARD — Market Alert** | Severity: {LEVEL}
⚠️ **{TITLE}**
{BODY}
**Impact on your search:** {ANALYSIS}
```

### Daily briefing → #job-hunt (8 AM EST)
Top 5 matches, market pulse, action items for the day.

### Weekly report → #monitoring (Monday 9 AM EST)
Week-over-week trends, skills demand table, local market summary, strategic recommendations.

### Ops alerts → #openclaw-ops
Send when: all APIs fail 2+ cycles, update endpoint fails 3+ times, data >6h stale.

## Scheduled Tasks

1. **Hourly job scan** (7AM-11PM EST): Run collect-jobs.sh, filter, score, alert on 8+ matches, push KPI update.
2. **6-hourly trends sweep**: Run collect-trends.py, scan news, classify market status, alert if changed or high severity.
3. **Daily briefing** (8AM EST): Full collection + briefing to #job-hunt.
4. **Weekly intel** (Monday 9AM EST): 7-day analysis + report to #monitoring.

## Failure Handling

- API fail → fallback to other sources, never wipe existing dashboard data
- 401 from update endpoint → alert #openclaw-ops, stop retries until token confirmed
- 500 → retry once after 30s, then alert after 3 consecutive fails
- Stale data (>6h) → emergency collection run + alert #openclaw-ops

## Timezone

All times: America/Indianapolis (EST winter, EDT summer). Always include timezone in messages.
