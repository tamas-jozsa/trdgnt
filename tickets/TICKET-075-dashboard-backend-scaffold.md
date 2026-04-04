# TICKET-075 -- Dashboard FastAPI Backend Scaffold

**Priority:** HIGH
**Effort:** 2 hours
**Status:** DONE
**Depends on:** None
**Files:**
- `dashboard/backend/main.py`
- `dashboard/backend/config.py`
- `dashboard/backend/requirements.txt`
- `dashboard/backend/routers/__init__.py`
- `dashboard/backend/services/__init__.py`
- `dashboard/backend/models/__init__.py`

## Description

Create the FastAPI application scaffold with:

1. `main.py` -- FastAPI app with CORS middleware, lifespan handler, router includes,
   static file serving for production (mounts `frontend/dist/` if it exists)
2. `config.py` -- Path constants pointing to project root, trading_loop_logs/,
   results/, positions.json. Auto-detect project root relative to dashboard/.
3. `requirements.txt` -- fastapi, uvicorn[standard], websockets, pydantic, aiofiles
4. Empty router and service modules with `__init__.py`

## Acceptance Criteria

- [ ] `uvicorn dashboard.backend.main:app --reload --port 8080` starts without error
- [ ] `GET /api/health` returns `{"status": "ok"}`
- [ ] CORS allows localhost origins (3000, 5173, 8080)
- [ ] Config correctly resolves all data paths from any CWD
