---
name: it-dashboard-cloud-runbook
description: Run, test, and debug the IT Jobs Intelligence Dashboard — local setup, API checks, cache and env behavior, OpenClaw scripts, and CI deploy notes for Cloud agents.
version: 1.0.0
author: Cloud runbook (repo-maintained)
metadata:
  openclaw:
    emoji: "🧪"
    bins:
      - python3
      - curl
      - bash
    env:
      - DASHBOARD_UPDATE_TOKEN
      - JOBS_MAX_AGE_DAYS
tags: [dashboard, dev, testing, runbook, cloud-agents]
user-invocable: true
---

# IT Dashboard — Cloud agent runbook

Minimal instructions to run and verify this repo. There is **no automated test suite** (no `pytest` / `npm test`); use HTTP checks, log inspection, and optional one-off Python snippets.

## One-time setup (any area)

From the repo root (`/workspace` or your clone):

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
mkdir -p data
```

**Auth for POST `/api/update.py`:** set `DASHBOARD_UPDATE_TOKEN` to a non-empty secret. If unset, the app falls back to a **hardcoded placeholder** in `app.py` (`FALLBACK_SECRET`) — fine for local smoke tests only; never rely on that in production.

**Job freshness window:** `JOBS_MAX_AGE_DAYS` (default `10`) controls which listings pass the `is_recent_job` filter on the jobs endpoint.

**No feature-flag system** exists in this codebase. “Toggles” are: environment variables above, `?force=1` on GET APIs, and deleting or editing files under `data/` (see below).

---

## Area: Flask app and HTTP API (`app.py`, `/health`, `/api/*`)

**Start (production-like):**

```bash
source venv/bin/activate
gunicorn -w 2 -b 127.0.0.1:8000 app:app
```

**Start (quick dev, port 5000):**

```bash
source venv/bin/activate
python3 app.py
```

**Headless check (no server on a port):** from repo root with venv active:

```bash
python3 -c "import app; c=app.app.test_client(); print(c.get('/health').get_json())"
```

**Smoke test workflow (server running):**

1. `curl -sS http://127.0.0.1:8000/health` — expect JSON with `"status": "ok"`.
2. `curl -sS 'http://127.0.0.1:8000/api/jobs.py?page=1'` — expect JSON with `jobs`, `total`, `data_source` (`hunter_snapshot` vs `market_apis`).
3. `curl -sS http://127.0.0.1:8000/api/news.py` — expect `news` array and `fetched_at`.
4. `curl -sS http://127.0.0.1:8000/api/update.py` — unauthenticated read of persisted dashboard state; expect `ok`, `data`, `age_seconds`.

**Cache-bypass (live upstream / RSS):**

```bash
curl -sS 'http://127.0.0.1:8000/api/jobs.py?force=1' | head -c 500
curl -sS 'http://127.0.0.1:8000/api/news.py?force=1' | head -c 500
```

**POST update (requires token):**

```bash
export DASHBOARD_UPDATE_TOKEN='your-secret'
curl -sS -X POST http://127.0.0.1:8000/api/update.py \
  -H "Authorization: Bearer ${DASHBOARD_UPDATE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"market_status":"Stable","kpi_updates":{"Smoke":"ok"}}'
```

Invalid or missing Bearer → `401` with a JSON error body. Valid → `200` and `ok: true`.

---

## Area: Data directory (`data/`)

Runtime JSON lives here (see `.gitignore` for generated names). Agents can **reset** behavior by removing caches while the app is stopped (or accept brief races if not stopped).

| File | Role |
|------|------|
| `data/jobs_cache.json` | Cached aggregated jobs from market APIs (TTL ~30 min). |
| `data/news_cache.json` | Cached news fetch. |
| `data/dashboard_data.json` | Merged intelligence from GET/POST update + optional Hunter `jobs_snapshot`. |

**Test workflow (isolated jobs list):** clear snapshot influence by ensuring `data/dashboard_data.json` has no recent `jobs_snapshot` (or stop server and move the file aside), clear `data/jobs_cache.json`, then GET `/api/jobs.py?force=1` to repopulate from public APIs.

**Test workflow (Hunter path):** POST a payload with `jobs_snapshot` (and optional `fetched_at` / `sources`) using a valid token, then GET `/api/jobs.py` *without* `force=1` and confirm `data_source: "hunter_snapshot"` when the snapshot is within the max-age window (see `JOBS_SNAPSHOT_MAX_AGE_SECONDS` in `app.py`).

---

## Area: Static dashboard (`static/`)

The UI is a vanilla JS SPA; `app.py` serves `static/index.html` at `/` and other assets from `static/`.

**Manual test:** open `http://127.0.0.1:8000/` in a browser (or a headless browser in automation). Confirm jobs/news load without console errors. The client calls same-origin `/api/jobs.py`, `/api/news.py`, etc. (`static/js/api.js`).

**No separate frontend build** — edit JS/CSS/HTML and refresh.

---

## Area: OpenClaw scripts (`openclaw/scripts/`)

These support the Hunter / OpenClaw workflows (job collection, trends, snapshots). They may need extra dependencies beyond `requirements.txt` (e.g. `collect-trends.py` may expect `requests` and other packages—install as errors indicate).

**Typical checks:**

```bash
bash openclaw/scripts/collect-jobs.sh --help 2>/dev/null || bash openclaw/scripts/collect-jobs.sh
python3 openclaw/scripts/collect-trends.py
```

**Install published skill copy** (optional, for `~/.openclaw` layout): `bash openclaw/install-skill.sh` — see `openclaw/SKILL.md` for the full “manager” skill and Discord-related ops.

**Integration test with local API:** run the Flask/gunicorn app, set `DASHBOARD_UPDATE_TOKEN`, then use `curl` POST (above) or `openclaw/scripts/push-jobs-snapshot.py` if configured for your target URL and token.

---

## Area: CI and deploy (`.github/workflows/`)

`deploy.yml` runs on push to `main` (and `workflow_dispatch`). It SSHes to a droplet, syncs the repo, `pip install -r requirements.txt`, and `systemctl restart dashboard`. It is **not** a test job—there is no lint or test step.

**What Cloud agents need:** changing deploy behavior means editing the workflow; validating YAML locally is limited—use the Actions tab on push or `workflow_dispatch` for a real run. Health check on the server: `curl -sf http://localhost:8000/health` (as in the workflow).

**Secrets (GitHub only, not in repo):** `DROPLET_IP`, `SSH_PRIVATE_KEY` — required for deploy; agents cannot “log in” to GitHub without user OAuth; document for humans when opening deploy issues.

---

## Updating this skill

When you discover a new runbook fact (new env var, new endpoint, script flag, or manual test sequence):

1. **Edit** `openclaw/SKILL-cloud-runbook.md` in the same PR as the code change, if possible, so the runbook stays truthful.
2. **Bump** the `version` in the YAML frontmatter when behavior changes in a way that would mislead old instructions.
3. **Prefer concrete commands** (curl one-liners, file paths) over abstract descriptions.
4. If a **feature flag system** is added later, add a short subsection under “One-time setup” and link to the canonical list (env or config file).

This file is the **Cloud-agent-oriented** counterpart to the task-specific `openclaw/SKILL.md` (Hunter/Discord workflows).
