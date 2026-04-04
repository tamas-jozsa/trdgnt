# TICKET-089 -- Dashboard Production Build + Static Serving

**Priority:** MEDIUM
**Effort:** 1 hour
**Status:** DONE
**Depends on:** TICKET-075, TICKET-083
**Files:**
- `dashboard/backend/main.py` (static file mount)
- `dashboard/frontend/vite.config.ts` (build config)
- `dashboard/run.sh` (convenience script)

## Description

Enable single-process production mode:

1. `npm run build` in frontend produces `dashboard/frontend/dist/`
2. FastAPI mounts `frontend/dist/` as static files at `/`
3. SPA fallback: any non-`/api` and non-`/ws` route serves `index.html`
4. Create `dashboard/run.sh`:
   ```bash
   #!/bin/bash
   cd "$(dirname "$0")"
   cd frontend && npm run build && cd ..
   cd backend && uvicorn main:app --host 0.0.0.0 --port 8080
   ```

## Acceptance Criteria

- [ ] `bash dashboard/run.sh` builds frontend and starts server
- [ ] `http://localhost:8080` serves the React SPA
- [ ] `http://localhost:8080/api/health` still works
- [ ] Client-side routing works (refresh on `/trades` serves index.html)
