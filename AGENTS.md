# Agent guidelines for `it-dashboard`

This repo is a small Flask app (the IT Jobs Intelligence Dashboard) plus a static
SPA frontend, deployed to a DigitalOcean droplet via GitHub Actions, and an
"OpenClaw" skill that pushes data into the API. It is small, self-contained, and
easy to run locally.

## Skills

A starter skill for Cloud agents lives at `.cursor/skills/run-and-test.md`.
Read it before starting any task that involves running, testing, or modifying
the app, the API, the frontend, the deploy workflow, or the `openclaw/` skill.
It describes how to run the app locally, exercise each API, mock the auth
token, and what to do per codebase area.

When you discover new testing tricks, runbook steps, or environment quirks
while working on a task, update `.cursor/skills/run-and-test.md` (see the
"Updating this skill" section at the bottom of that file).

## General rules

- Do not commit runtime files under `data/` — `jobs_cache.json`,
  `news_cache.json`, and `dashboard_data.json` are gitignored. The only
  tracked file there is `data/.gitkeep`.
- Do not commit real tokens. The `DASHBOARD_UPDATE_TOKEN` baked into
  `setup-droplet.sh` is the deployed value; for local work always export your
  own throwaway token and rely on it via the env var.
- The Python venv at `venv/` is checked in for convenience on this machine —
  use `./venv/bin/python` and `./venv/bin/gunicorn` rather than installing
  globally.
