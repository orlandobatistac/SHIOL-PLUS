"""
SHIOL+ Batch Ticket API Endpoints
=================================
API endpoints for retrieving pre-generated (cached) lottery tickets.

These endpoints provide fast (<10ms) access to tickets that were
pre-generated in the background by the BatchTicketGenerator.

Endpoints:
- GET /api/v1/tickets/cached - Retrieve cached tickets
- GET /api/v1/tickets/batch-status - Get batch generation status
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from loguru import logger
import time

from src.database import get_cached_tickets, get_batch_ticket_stats

# Create router
batch_router = APIRouter()


class CachedTicketResponse(BaseModel):
    """Response model for cached tickets endpoint."""
    mode: str = Field(..., description="Prediction mode used")
    count: int = Field(..., description="Number of tickets returned")
    tickets: List[Dict[str, Any]] = Field(..., description="List of cached tickets")
    cached: bool = Field(True, description="Always True for this endpoint")
    response_time_ms: float = Field(..., description="Response time in milliseconds")
    db_stats: Optional[Dict[str, Any]] = Field(None, description="Database statistics")


class BatchStatusResponse(BaseModel):
    """Response model for batch status endpoint."""
    total_tickets: int = Field(..., description="Total cached tickets in database")
    by_mode: Dict[str, int] = Field(..., description="Ticket count by mode")
    oldest_ticket: Optional[str] = Field(None, description="Oldest ticket creation time")
    newest_ticket: Optional[str] = Field(None, description="Newest ticket creation time")


@batch_router.get(
    "/cached",
    response_model=CachedTicketResponse,
    summary="Get cached pre-generated tickets",
    description="""
    Retrieve pre-generated tickets from cache for fast response (<10ms).
    
    These tickets are generated in the background by the batch generation system
    and stored in the database for quick retrieval.
    
    If no cached tickets are available for the requested mode, returns empty list.
    Use the POST /api/v1/predictions/generate endpoint for on-demand generation.
    """
)
async def get_cached_tickets_endpoint(
    mode: str = Query(
        "random_forest",
        description="Prediction mode (random_forest, lstm, v1, v2, hybrid)"
    ),
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Maximum number of tickets to return"
    ),
    include_stats: bool = Query(
        False,
        description="Include database statistics in response"
    )
):
    """
    Get pre-generated tickets from cache.
    
    This endpoint provides extremely fast response times (<10ms) by retrieving
    tickets that were pre-generated in the background.
    
    Args:
        mode: Prediction mode to retrieve tickets for
        limit: Maximum number of tickets to return (1-100)
        include_stats: Whether to include database statistics
    
    Returns:
        CachedTicketResponse with tickets and metadata
        
    Raises:
        HTTPException: If database error occurs
    """
    start_time = time.time()
    
    try:
        # Validate mode
        valid_modes = ['random_forest', 'lstm', 'v1', 'v2', 'hybrid']
        if mode not in valid_modes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode '{mode}'. Valid modes: {valid_modes}"
            )
        
        # Retrieve cached tickets
        tickets = get_cached_tickets(mode=mode, limit=limit)
        
        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000
        
        # Get database stats if requested
        db_stats = None
        if include_stats:
            try:
                db_stats = get_batch_ticket_stats()
            except Exception as e:
                logger.warning(f"Failed to get DB stats: {e}")
        
        logger.info(
            f"Cached tickets endpoint: mode={mode}, limit={limit}, "
            f"returned={len(tickets)}, response_time={response_time_ms:.2f}ms"
        )
        
        return CachedTicketResponse(
            mode=mode,
            count=len(tickets),
            tickets=tickets,
            cached=True,
            response_time_ms=round(response_time_ms, 2),
            db_stats=db_stats
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving cached tickets: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve cached tickets: {str(e)}"
        )


@batch_router.get(
    "/batch-status",
    response_model=BatchStatusResponse,
    summary="Get batch generation status",
    description="""
    Get statistics about the batch ticket pre-generation system.
    
    Returns information about:
    - Total cached tickets in database
    - Ticket count by prediction mode
    - Age of oldest and newest tickets
    """
)
async def get_batch_status_endpoint():
    """
    Get batch generation system status.
    
    Returns statistics about pre-generated tickets in the database.
    
    Returns:
        BatchStatusResponse with statistics
        
    Raises:
        HTTPException: If database error occurs
    """
    try:
        stats = get_batch_ticket_stats()
        
        return BatchStatusResponse(
            total_tickets=stats['total_tickets'],
            by_mode=stats['by_mode'],
            oldest_ticket=stats['oldest_ticket'],
            newest_ticket=stats['newest_ticket']
        )
        
    except Exception as e:
        logger.error(f"Error retrieving batch status: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve batch status: {str(e)}"
        )
