# Skill: Run & test the IT Dashboard (Cloud-agent starter)

A practical, opinionated runbook for Cloud agents working in this repo. Read
the section that matches the area you are touching, run the matching test
workflow, and capture evidence (logs, curl output, screenshots) before you
hand back.

If something here is wrong or missing, **update this file** — see
[Updating this skill](#updating-this-skill) at the bottom.

---

## 0. Repo map at a glance

| Path | What it is | Touch when… |
|---|---|---|
| `app.py` | Flask app: jobs / news / update API + static serving | Backend logic changes, new endpoints, auth, data merge |
| `static/index.html`, `static/css/`, `static/js/` | Vanilla-JS SPA (5 hash routes: `dashboard`, `jobs`, `trends`, `news`, `insights`) | UI/UX, fetch wiring, rendering |
| `data/` | Runtime cache + state (`jobs_cache.json`, `news_cache.json`, `dashboard_data.json`). Gitignored. | Never commit; safe to delete to reset state |
| `requirements.txt` | `flask`, `gunicorn`, `requests` | Adding deps |
| `setup-droplet.sh` | One-shot droplet bootstrap (systemd unit, nginx, ufw) | Production setup changes |
| `.github/workflows/deploy.yml` | SSH deploy to droplet on push to `main` | CI/deploy changes |
| `openclaw/SKILL.md` + `openclaw/scripts/` | External "Hunter" agent skill that POSTs data to `/api/update.py` | Data ingestion / agent contract changes |

There is **no auth/login UI**. The only "credential" in the system is the
Bearer token used by `POST /api/update.py`.

---

## 1. Local environment & startup

The repo ships with a working venv at `venv/` (Python 3.12, Flask 3, Gunicorn,
requests). Use it directly — don't `pip install` globally.

### Start the app (preferred — matches production)

```bash
# from /workspace
DASHBOARD_UPDATE_TOKEN=test-token \
  ./venv/bin/gunicorn -w 1 -b 127.0.0.1:8765 app:app \
  --pid /tmp/gunicorn.pid --daemon \
  --error-logfile /tmp/gunicorn.err \
  --access-logfile /tmp/gunicorn.access
sleep 2 && curl -s http://127.0.0.1:8765/health
```

Stop it with: `kill $(cat /tmp/gunicorn.pid)`.

### Start the app (foreground, for quick iteration)

```bash
DASHBOARD_UPDATE_TOKEN=test-token ./venv/bin/python app.py
# binds 0.0.0.0:5000 in dev mode
```

### Reset all runtime state

```bash
rm -f data/jobs_cache.json data/news_cache.json data/dashboard_data.json data/dashboard_data.json.tmp
```

Do this before tests that depend on a clean dashboard, and after pushing
test payloads so you don't leave junk behind.

### Environment variables you may need

| Var | Purpose | Local default |
|---|---|---|
| `DASHBOARD_UPDATE_TOKEN` | Bearer token required for `POST /api/update.py` | falls back to `FALLBACK_SECRET` constant in `app.py` if unset — **always set it explicitly** so tests are deterministic |
| `JOBS_MAX_AGE_DAYS` | Hide job postings older than N days (default 10) | leave unset unless testing freshness filter |

There are no real "feature flags" — behaviour is toggled via query params
(`?force=1`) or env vars above. To "mock" the auth token in tests, just
set `DASHBOARD_UPDATE_TOKEN=test-token` in the gunicorn invocation and
send `Authorization: Bearer test-token`.

### Network reality

The jobs and news endpoints make outbound calls to remotive.com,
remoteok.com, arbeitnow.com, and several RSS feeds. They **fail silently**
(empty list) if the network is blocked. Two consequences:

- A "0 jobs" / "0 news" response on a clean cache does not necessarily mean
  the code is broken — check `/tmp/gunicorn.err` for upstream errors before
  debugging app logic.
- For deterministic backend tests, prefer driving the API via `POST
  /api/update.py` (which writes `dashboard_data.json` directly) rather than
  forcing fresh fetches with `?force=1`.

---

## 2. Backend / API (`app.py`)

Single file, ~850 lines. Three logical groups:

- **Jobs** — `GET /api/jobs.py?query=&location=&type=&page=&force=`. Prefers
  the Hunter snapshot stored in `dashboard_data.json` (≤6h old), then falls
  back to upstream APIs cached for 30 min in `jobs_cache.json`.
- **News** — `GET /api/news.py?force=`. RSS aggregation with 30-min cache in
  `news_cache.json`.
- **Update** — `GET /api/update.py` (no auth, returns full state) and `POST
  /api/update.py` (Bearer auth, merges partial payload into
  `dashboard_data.json`, keeps last 50 history entries, caps trend_alerts at
  100 and insights at 50).

Plus `/health` and static fallback under `/`.

### Test workflow — backend

1. Start the app with a known token (see §1).
2. Smoke-test each route with curl. Save outputs to `/tmp/` so you can
   include them as evidence.

   ```bash
   curl -s http://127.0.0.1:8765/health | tee /tmp/health.json
   curl -s 'http://127.0.0.1:8765/api/update.py' | jq . | tee /tmp/update_get.json

   # Auth: must be 401 without token, 200 with token
   curl -s -o /tmp/post_unauth.json -w '%{http_code}\n' \
     -X POST http://127.0.0.1:8765/api/update.py \
     -H 'Content-Type: application/json' -d '{}'

   curl -s -X POST http://127.0.0.1:8765/api/update.py \
     -H 'Authorization: Bearer test-token' \
     -H 'Content-Type: application/json' \
     -d '{"market_status":"Stable","kpi_updates":{"x":"1"},"new_insights":["hello"]}' \
     | tee /tmp/post_ok.json

   # Verify merge persisted
   curl -s http://127.0.0.1:8765/api/update.py | jq '.data.market_status, .data.new_insights'
   ```

3. If you changed jobs/news fetch or filtering logic, also exercise:

   ```bash
   curl -s 'http://127.0.0.1:8765/api/jobs.py?force=1&type=remote' | jq '.total, .from_cache, .data_source'
   curl -s 'http://127.0.0.1:8765/api/news.py?force=1' | jq '.total, .from_cache'
   ```

   If the network is blocked, instead inject a snapshot via `POST
   /api/update.py` with a `jobs_snapshot` payload and verify `GET
   /api/jobs.py` returns it with `data_source: "hunter_snapshot"`.

4. Reset state when done (see §1).

There is **no test framework** in this repo. Don't add pytest scaffolding
unless the user explicitly asks. Curl-based smoke tests + log inspection are
the standard.

---

## 3. Frontend SPA (`static/`)

Vanilla JS, no build step. Three modules: `api.js` (fetch wrappers, card
renderers), `router.js` (hash routing across 5 pages), `charts.js`. CSS is a
single `static/css/styles.css` ("Bloomberg terminal" aesthetic).

The page calls the backend with **relative** paths (`/api/jobs.py`,
`/api/news.py`, `/api/update.py`), so it only works when served by the
Flask/Gunicorn process — opening `index.html` directly will get CORS-clean
404s.

### Test workflow — frontend

1. Start the app per §1 on `127.0.0.1:8765`.
2. Use the `computerUse` subagent to open the page in Chrome and exercise
   each of the 5 hash routes (`#dashboard`, `#jobs`, `#trends`, `#news`,
   `#insights`). Confirm:
   - The header/ticker render (no JS errors in DevTools console).
   - At least one job card and one news card render, OR — if upstream APIs
     are blocked — the page degrades gracefully to empty states.
   - Hash navigation animates between pages without leaving stale content.
3. **Always record a screen recording** for non-trivial UI changes and save
   it to `/opt/cursor/artifacts/`.
4. For backend-only changes that still touch a page (e.g. a new field on a
   card), take a single before/after screenshot of the affected page.

### Mocking data for the SPA

Cleanest approach: don't hit the live upstreams. POST a synthetic snapshot
through the update API:

```bash
curl -s -X POST http://127.0.0.1:8765/api/update.py \
  -H 'Authorization: Bearer test-token' \
  -H 'Content-Type: application/json' \
  -d '{
        "market_status":"Cautious Recovery",
        "kpi_updates":{"Active Job Postings":"12,847"},
        "new_insights":["test insight"],
        "jobs_snapshot":{
          "fetched_at":"2026-04-27T12:00:00+00:00",
          "sources":["test"],
          "jobs":[{"title":"Senior Backend Engineer","company":"Acme",
                    "location":"Remote","url":"https://example.com/x",
                    "tags":["python","aws"],"posted":"2026-04-27T12:00:00+00:00",
                    "source":"Hunter"}]
        }
      }'
```

Then load `/#jobs` — the SPA will see `data_source: "hunter_snapshot"`
and render your fixture without touching the internet.

---

## 4. Deploy workflow (`.github/workflows/deploy.yml`)

GitHub Actions SSHes into the droplet, `git reset --hard origin/main`,
re-installs deps, restarts the `dashboard` systemd unit, and curls
`/health`. Required GitHub secrets: `DROPLET_IP`, `SSH_PRIVATE_KEY`.

### Test workflow — deploy

You cannot run a full deploy from a Cloud agent (no droplet access). Limit
yourself to:

- `actionlint` if available, otherwise a YAML lint via `python -c "import
  yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))"`.
- Mentally / manually walk through the `<<ENDSSH` heredoc — be especially
  careful about quoting and `set -euo pipefail` interactions.
- For systemd / nginx changes in `setup-droplet.sh`, validate by running
  `bash -n setup-droplet.sh` and grepping for obvious typos. Do not execute
  it; it mutates system state.

If you change either file, call this out in your PR description and ask
the user to verify on the droplet (or trigger `workflow_dispatch`).

---

## 5. OpenClaw skill (`openclaw/`)

This is a **separate** skill that runs on a Hunter agent host (not in this
repo) and POSTs to the dashboard's update API. The artifacts here are:

- `openclaw/SKILL.md` — instructions consumed by the Hunter agent.
- `openclaw/scripts/*` — bash/python helpers Hunter runs.
- `openclaw/install-skill.sh` — fetches the skill from a Perplexity-hosted
  URL into `~/.openclaw/skills/it-dashboard-manager/`.

### Test workflow — openclaw

- For shell scripts: `bash -n openclaw/scripts/<file>.sh` for syntax,
  `shellcheck` if installed.
- For `collect-trends.py` / `push-jobs-snapshot.py`: `python3 -m py_compile
  openclaw/scripts/<file>.py`, plus a dry run if the script supports one.
- For end-to-end: run the script locally with `DASHBOARD_URL=http://127.0.0.1:8765`
  and `DASHBOARD_UPDATE_TOKEN=test-token` against a locally running app
  (§1), then `GET /api/update.py` and confirm the merged shape.

Do **not** point any test runs at the production droplet
(`http://45.55.191.125`).

---

## 6. Quick decision tree

- Touched only `static/css/` or trivial `static/js/` → start app, take a
  before/after screenshot per affected page.
- Touched routing or rendering in `static/js/` → start app, record a video
  walking through all 5 hash routes.
- Touched `app.py` API handlers → run the §2 curl smoke tests, paste the
  outputs into the PR. Add a UI screenshot if the change is user-visible.
- Touched merge / persistence logic → reset `data/`, POST a sequence of
  partial payloads, GET and verify history + caps (50 history, 100 alerts,
  50 insights).
- Touched `setup-droplet.sh` or `deploy.yml` → syntax-check only, flag for
  human verification.

---

## Updating this skill

Treat this file as a living runbook. Whenever you discover something that
would have saved you time on this task, edit it in **the same PR**:

1. Add the new tip to the most specific section (jobs / news / update /
   frontend / deploy / openclaw). Create a new H3 if none fits.
2. If the trick is environmental (a new env var, a port collision, a new
   dependency, a flaky upstream), put it in §1 *and* mention it in the
   relevant per-area section.
3. If a documented step turned out to be wrong, fix it — don't just append
   a contradicting note.
4. Keep entries terse: the exact command, what it proves, and the failure
   mode you observed. Avoid prose.
5. If a tip is specific to one PR / bug, link the PR or issue inline so
   future agents can find context.

Rule of thumb: if you ran a command more than once during a task and it
isn't already in this file, it belongs here.
