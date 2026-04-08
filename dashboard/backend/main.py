"""
trdagnt Dashboard -- FastAPI Backend

Entry point: uvicorn dashboard.backend.main:app --reload --port 8888
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from .config import FRONTEND_DIST_DIR, PROJECT_ROOT
    from .routers import portfolio, trades, agents, research, control, news_monitor
    from .services.log_streamer import setup_websocket
except ImportError:
    # Fallback for running directly
    from config import FRONTEND_DIST_DIR, PROJECT_ROOT
    from routers import portfolio, trades, agents, research, control, news_monitor
    from services.log_streamer import setup_websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    print(f"[Dashboard] Project root: {PROJECT_ROOT}")
    print(f"[Dashboard] Serving API at /api/")
    if FRONTEND_DIST_DIR.exists():
        print(f"[Dashboard] Serving frontend from {FRONTEND_DIST_DIR}")

    # Start news monitor background task
    try:
        from dashboard.backend.news_monitor_compat import get_news_monitor
    except ImportError:
        from news_monitor import get_news_monitor
    monitor = get_news_monitor()
    monitor_task = None
    if monitor:
        monitor_task = asyncio.create_task(monitor.poll_loop())
        print(f"[Dashboard] News monitor started (enabled={monitor.enabled})")
    else:
        print("[Dashboard] News monitor not available")

    yield

    # Shutdown: stop news monitor
    if monitor:
        monitor.running = False
    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        print("[Dashboard] News monitor stopped")


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
        "http://localhost:8888",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8888",
        "http://trdagnt:8888",
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
app.include_router(news_monitor.router, prefix="/api/news-monitor", tags=["news-monitor"])

# WebSocket
setup_websocket(app)


# Health check
@app.get("/api/health")
async def health():
    return {"status": "ok", "project_root": str(PROJECT_ROOT)}


# Serve frontend static files in production
if FRONTEND_DIST_DIR.exists():
    from fastapi.responses import FileResponse

    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="assets")

    # Serve favicon
    @app.get("/favicon.svg")
    async def favicon():
        favicon_file = FRONTEND_DIST_DIR / "favicon.svg"
        if favicon_file.exists():
            return FileResponse(favicon_file, media_type="image/svg+xml")
        return {"error": "Favicon not found"}

    # SPA fallback -- serve index.html for all non-API routes
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        index = FRONTEND_DIST_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"error": "Frontend not built. Run: cd dashboard/frontend && npm run build"}
