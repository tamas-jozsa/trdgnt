"""
trdagnt Dashboard -- FastAPI Backend

Entry point: uvicorn dashboard.backend.main:app --reload --port 8080
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIST_DIR, PROJECT_ROOT
from .routers import portfolio, trades, agents, research, control
from .services.log_streamer import setup_websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    print(f"[Dashboard] Project root: {PROJECT_ROOT}")
    print(f"[Dashboard] Serving API at /api/")
    if FRONTEND_DIST_DIR.exists():
        print(f"[Dashboard] Serving frontend from {FRONTEND_DIST_DIR}")
    yield


app = FastAPI(
    title="trdagnt Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS -- allow local development origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(trades.router, prefix="/api/trades", tags=["trades"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(control.router, prefix="/api/control", tags=["control"])

# WebSocket
setup_websocket(app)


# Health check
@app.get("/api/health")
async def health():
    return {"status": "ok", "project_root": str(PROJECT_ROOT)}


# Serve frontend static files in production
if FRONTEND_DIST_DIR.exists():
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="assets")

    # SPA fallback -- serve index.html for all non-API routes
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        from fastapi.responses import FileResponse
        index = FRONTEND_DIST_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"error": "Frontend not built. Run: cd dashboard/frontend && npm run build"}
