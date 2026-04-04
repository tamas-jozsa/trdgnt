"""Agents API endpoints."""

from fastapi import APIRouter, Query
from typing import Optional

from ..models.schemas import (
    AgentReportResponse, ReportListResponse, OverrideListResponse, AgentMemoryResponse
)
from ..services import agent_service

router = APIRouter()


@router.get("/reports", response_model=ReportListResponse)
async def list_reports(
    ticker: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    """List available agent analysis reports."""
    data = agent_service.list_reports(ticker, date, limit)
    return ReportListResponse(reports=data)


@router.get("/report/{ticker}/{date}", response_model=AgentReportResponse)
async def get_report(ticker: str, date: str):
    """Get full agent analysis report for a ticker on a given date."""
    data = agent_service.get_report(ticker, date)
    return AgentReportResponse(**data)


@router.get("/overrides", response_model=OverrideListResponse)
async def get_overrides(
    days: int = Query(7, ge=1, le=90),
    severity: Optional[str] = None,
):
    """Get signal override history."""
    data = agent_service.get_overrides(days, severity)
    return OverrideListResponse(**data)


@router.get("/memory/{ticker}", response_model=AgentMemoryResponse)
async def get_memory(
    ticker: str,
    agent: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
):
    """Get agent memory entries for a ticker."""
    data = agent_service.get_memory(ticker, agent, limit)
    return AgentMemoryResponse(**data)
