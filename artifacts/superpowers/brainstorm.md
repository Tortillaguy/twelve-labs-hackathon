## Goal
Set up a zero-touch CI/CD pipeline so every `git push` to the main branch automatically deploys the React/Vite frontend to **Vercel** and the FastAPI backend to **Render**, with proper environment variable wiring, CORS configuration, and stable data layer for the hackathon demo.

---

## Constraints
- **Free tier only** — no paid plans
- **Render free tier sleeps** after 15 min of inactivity (cold start ~30s)
- **Render ephemeral filesystem** — `data/` cache must be committed to git or otherwise persisted
- **TwelveLabs API key** is secret — must be injected via env vars, never committed
- Frontend currently hardcodes `localhost:8000` — must be parameterized before deploying
- CORS `allow_origins=["*"]` is fine for now but should be locked to the Vercel domain post-launch
- Monorepo layout (`dota-intel/frontend`, `dota-intel/backend`) — both platforms need root directory config

---

## Known Context
- **Frontend**: React 19 + Vite + TypeScript, builds to `dota-intel/frontend/dist`
- **Backend**: FastAPI + Uvicorn, entrypoint `backend.main:app`, `requirements.txt` at `dota-intel/requirements.txt`
- **Data**: File-based JSON cache in `dota-intel/data/` — read at runtime, written by `seed_index.py` offline
- **Env vars needed**: `TWELVELABS_API_KEY`, `TWELVELABS_INDEX_ID`, `OPENDOTA_BASE_URL`
- **Repo**: `/Users/cacho/Documents/repos/twelve-labs-hackathon` — assumed to be (or will be) a GitHub repo

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| `VITE_API_URL` not set → frontend hits localhost in prod | 🔴 High | Use `import.meta.env.VITE_API_URL` with fallback, set in Vercel dashboard |
| `data/` not in git → 404 on leaderboard endpoint | 🔴 High | Explicitly `git add data/` and commit before first deploy |
| Render cold starts on free tier (~30s delay) | 🟡 Medium | Accept for hackathon; add a `/healthcheck` ping or note in demo |
| CORS wildcard `*` exposes API | 🟡 Medium | Narrow to Vercel domain after first deploy (cosmetic risk for demo) |
| `render.yaml` missing → manual config every time | 🟡 Medium | Add `render.yaml` to repo for infrastructure-as-code |
| Secrets accidentally committed | 🔴 High | Confirm `.env` is in `.gitignore` before push |

---

## Options

### Option A — Manual Dashboard Setup (no config files)
Configure Vercel and Render entirely via their web UIs. Set root dirs, build commands, and env vars by hand. Easy first time, but fragile — settings live only in dashboards and can drift.

### Option B — `render.yaml` + `vercel.json` (IaC, recommended)
Add declarative config files to the repo. Render reads `render.yaml` on first connection; Vercel reads `vercel.json`. Settings are version-controlled, reproducible, and self-documenting. Requires one-time dashboard connection but auto-deploys from git forever after.

### Option C — Docker + Render Docker Deploy
Containerize the backend with a `Dockerfile`. More portable, but overkill for a hackathon — adds complexity with no free-tier benefit over Option B.

### Option D — Vercel Serverless Functions for Backend
Rewrite FastAPI routes as Vercel serverless functions (Python). Eliminates Render cold starts but **not feasible** — requires significant refactoring of the FastAPI app and loses uvicorn streaming benefits.

---

## Recommendation

**Option B — `render.yaml` + `vercel.json`**

This gives you repeatable, one-push deploys with minimal ongoing maintenance. The concrete steps:

1. Ensure `dota-intel/data/` is committed to git (with the seeded JSON cache)
2. Confirm `.env` is gitignored
3. Add `render.yaml` at repo root declaring the backend web service
4. Add `vercel.json` at repo root pointing to the frontend
5. Parameterize the frontend API URL via `VITE_API_URL` env var
6. Push to GitHub → connect both platforms to the repo once → all future pushes auto-deploy

---

## Acceptance Criteria
- [ ] `git push origin main` triggers a Vercel build of `dota-intel/frontend` and a Render deploy of `dota-intel/backend` automatically
- [ ] Frontend successfully calls the Render backend URL (no localhost references in production builds)
- [ ] `/api/leaderboard` returns data (confirms `data/` is committed and readable)
- [ ] `/api/players/{id}` returns player data with highlights
- [ ] No secrets (`.env` files) appear in the git history
- [ ] `render.yaml` and `vercel.json` exist in the repo and are the source of truth for deploy config
- [ ] CORS accepts requests from the Vercel deployment URL
