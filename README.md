# IT Jobs Intelligence Dashboard

Live market intelligence dashboard for the tech job market. Aggregates real-time data from multiple sources and provides an API for automated market data updates.

## Architecture

```
Flask App (Gunicorn) ← Nginx reverse proxy ← Internet
    ├── /api/jobs.py     → Remotive, RemoteOK, Arbeitnow
    ├── /api/news.py     → TechCrunch, HN, Dice, The Verge RSS
    ├── /api/update.py   → POST endpoint for Hunter agent data pushes
    └── /                → Static dashboard frontend (5-page SPA)
```

## Deployment

Auto-deploys to DigitalOcean Droplet via GitHub Actions on push to `main`.

### Required GitHub Secrets
- `DROPLET_IP` — DigitalOcean Droplet public IP
- `SSH_PRIVATE_KEY` — SSH private key for root access

### Manual deploy
```bash
ssh root@DROPLET_IP
cd /opt/dashboard/app
git pull
systemctl restart dashboard
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/jobs.py` | None | Live job listings (Remotive, RemoteOK, Arbeitnow) |
| GET | `/api/news.py` | None | Tech news from RSS feeds |
| GET | `/api/update.py` | None | Current dashboard intelligence data |
| POST | `/api/update.py` | Bearer token | Push market data (Hunter agent) |
| GET | `/health` | None | Service health check |

## Stack
- **Backend:** Python 3 / Flask / Gunicorn
- **Frontend:** Vanilla JS SPA, Bloomberg terminal aesthetic
- **Server:** Nginx reverse proxy on Ubuntu 24.04
- **CI/CD:** GitHub Actions → SSH deploy
- **Data:** OpenClaw Hunter agent pushes hourly via API
