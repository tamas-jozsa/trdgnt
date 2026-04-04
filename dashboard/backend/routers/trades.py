"""Trades API endpoints."""

from fastapi import APIRouter, Query
from typing import Optional

from ..models.schemas import TradeListResponse, PerformanceResponse
from ..services import trade_service

router = APIRouter()


@router.get("", response_model=TradeListResponse)
async def get_trades(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    ticker: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get paginated trade log with filtering."""
    data = trade_service.get_all_trades(date_from, date_to, ticker, action, limit, offset)
    return TradeListResponse(**data)


@router.get("/performance", response_model=PerformanceResponse)
async def get_performance(days: int = Query(30, ge=1, le=365)):
    """Get aggregate performance metrics."""
    data = trade_service.get_performance(days)
    return PerformanceResponse(**data)
