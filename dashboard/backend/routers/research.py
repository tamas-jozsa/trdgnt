"""Research API endpoints."""

from fastapi import APIRouter
from typing import Optional

from ..models.schemas import ResearchFindingsResponse, WatchlistResponse, QuotaResponse
from ..services import research_service

router = APIRouter()


@router.get("/findings", response_model=ResearchFindingsResponse)
async def get_findings(date: Optional[str] = None):
    """Get research findings for a date (defaults to latest)."""
    data = research_service.get_findings(date)
    return ResearchFindingsResponse(**data)


@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist():
    """Get current watchlist state including dynamic overrides."""
    data = research_service.get_watchlist()
    return WatchlistResponse(**data)


@router.get("/quota", response_model=QuotaResponse)
async def get_quota():
    """Get buy quota enforcement history."""
    data = research_service.get_quota_history()
    return QuotaResponse(**data)
