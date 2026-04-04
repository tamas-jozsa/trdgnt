"""Portfolio API endpoints."""

from fastapi import APIRouter, Query

from ..models.schemas import PortfolioResponse, EquityHistoryResponse
from ..services import portfolio_service

router = APIRouter()


@router.get("", response_model=PortfolioResponse)
async def get_portfolio():
    """Get current portfolio state with positions and account summary."""
    data = portfolio_service.get_portfolio()
    return PortfolioResponse(**data)


@router.get("/equity-history", response_model=EquityHistoryResponse)
async def get_equity_history(days: int = Query(30, ge=1, le=365)):
    """Get daily equity snapshots for charting."""
    data = portfolio_service.get_equity_history(days)
    return EquityHistoryResponse(data=data)
