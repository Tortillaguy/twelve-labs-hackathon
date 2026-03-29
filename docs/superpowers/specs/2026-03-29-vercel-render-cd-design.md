# Continuous Deployment: Vercel + Render

**Date:** 2026-03-29

## Goal

Deploy the Dota Intel app (React frontend + FastAPI backend) with automatic continuous deployment triggered by pushes to `main`.

## Architecture

```
GitHub (main branch)
  ├── push → Vercel detects dota-intel/frontend/ → npm run build → serves SPA via CDN
  └── push → Render detects dota-intel/ → restarts uvicorn FastAPI server
```

- **Frontend (Vercel):** Static SPA, globally distributed via Vercel's CDN. Free tier. Auto-deploys on every push to `main`.
- **Backend (Render):** Python web service running FastAPI/uvicorn. Free tier (cold starts ~30s after inactivity). Auto-deploys on every push to `main`.
- **Data:** Pre-ingested JSON files in `dota-intel/data/`, committed to the repo. No external database. Read-only at runtime.

## Code Changes

### 1. Frontend API client (`dota-intel/frontend/src/utils/api.ts`)

Create a shared axios instance that reads `VITE_API_URL` at build time:

```ts
import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '',
})

export default api
```

- In local dev: `VITE_API_URL` is unset → `baseURL` is `''` → relative paths like `/api/leaderboard` work via Vite's dev proxy.
- In production: `VITE_API_URL` is set to the Render URL → requests go to `https://your-app.onrender.com/api/leaderboard`.

### 2. Update pages to use shared api instance

Replace `axios` imports in `Leaderboard.tsx` and `PlayerDetail.tsx` with the shared `api` instance.

### 3. Render config (`dota-intel/render.yaml`)

```yaml
services:
  - type: web
    name: dota-intel-api
    runtime: python
    rootDir: dota-intel
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: TWELVELABS_API_KEY
        sync: false
      - key: TWELVELABS_INDEX_ID
        sync: false
      - key: OPENDOTA_BASE_URL
        value: https://api.opendota.com/api
      - key: ESL_LEAGUE_NAME
        value: ESL Pro Circuit
```

`sync: false` means the value must be set manually in the Render dashboard (keeps secrets out of the repo).

### 4. Vercel config (`dota-intel/frontend/vercel.json`)

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite"
}
```

`VITE_API_URL` is set in the Vercel dashboard (not in this file, since it contains the Render URL which is known after first deploy).

## Deployment Order

1. Deploy backend to Render first → get the service URL (e.g. `https://dota-intel-api.onrender.com`)
2. Deploy frontend to Vercel → set `VITE_API_URL` to the Render URL
3. Trigger a Vercel redeploy so the env var is baked into the build

## Environment Variables

| Variable | Where set | Value |
|---|---|---|
| `TWELVELABS_API_KEY` | Render dashboard | secret |
| `TWELVELABS_INDEX_ID` | Render dashboard | secret |
| `OPENDOTA_BASE_URL` | render.yaml | `https://api.opendota.com/api` |
| `ESL_LEAGUE_NAME` | render.yaml | `ESL Pro Circuit` |
| `VITE_API_URL` | Vercel dashboard | `https://<your-render-service>.onrender.com` |

## What's Not Covered

- CORS: Already set to `allow_origins=["*"]` in `main.py` — no changes needed.
- The Render free tier sleeps after 15 minutes of inactivity, causing ~30s cold starts. Acceptable for a hackathon demo.
