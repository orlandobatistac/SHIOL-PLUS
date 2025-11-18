"""
API v3 Endpoints for Prediction Engine
========================================
Advanced prediction endpoints with mode selection, auto-selection,
performance tracking, and comparison capabilities.

Features:
- POST /api/v3/predict - Auto-select best mode
- POST /api/v3/predict/{mode} - Force specific mode (v1/v2/hybrid)
- GET /api/v3/compare - Compare all modes
- GET /api/v3/metrics - Performance statistics
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Literal
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from loguru import logger

from src.prediction_engine import UnifiedPredictionEngine
from src.database import get_db_connection


# API v3 Router
router = APIRouter(
    prefix="/api/v3",
    tags=["prediction_v3"]
)


# Pydantic Models
class PredictionMode(str, Enum):
    """Available prediction modes"""
    v1 = "v1"
    v2 = "v2"
    hybrid = "hybrid"


class PredictRequest(BaseModel):
    """Request model for ticket generation"""
    count: int = Field(default=5, ge=1, le=200, description="Number of tickets to generate")
    include_metadata: bool = Field(default=True, description="Include generation metadata")


class TicketResponse(BaseModel):
    """Individual ticket in the response"""
    white_balls: List[int] = Field(..., description="5 white ball numbers (1-69)")
    powerball: int = Field(..., description="Powerball number (1-26)")
    strategy: str = Field(..., description="Strategy used to generate this ticket")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)")
    source: Optional[str] = Field(None, description="Source mode (v1_strategy/v2_ml)")


class PredictResponse(BaseModel):
    """Response model for prediction endpoint"""
    success: bool = Field(..., description="Whether the request was successful")
    mode: str = Field(..., description="Mode used for generation")
    mode_selected: Optional[str] = Field(None, description="How mode was selected (auto/manual)")
    tickets: List[TicketResponse] = Field(..., description="Generated tickets")
    count: int = Field(..., description="Number of tickets generated")
    metadata: Optional[Dict] = Field(None, description="Generation metadata")
    error: Optional[str] = Field(None, description="Error message if failed")


class ModeMetrics(BaseModel):
    """Performance metrics for a specific mode"""
    mode: str = Field(..., description="Mode name")
    total_generations: int = Field(..., description="Total times this mode has been used")
    avg_generation_time: float = Field(..., description="Average generation time in seconds")
    last_generation_time: Optional[float] = Field(None, description="Last generation time in seconds")
    success_rate: Optional[float] = Field(None, description="Success rate (0.0-1.0)")
    available: bool = Field(..., description="Whether this mode is currently available")


class MetricsResponse(BaseModel):
    """Response model for metrics endpoint"""
    timestamp: str = Field(..., description="Current timestamp")
    modes: List[ModeMetrics] = Field(..., description="Metrics for each mode")
    recommended_mode: str = Field(..., description="Currently recommended mode")


class ComparisonTickets(BaseModel):
    """Tickets from one mode in comparison"""
    mode: str = Field(..., description="Mode name")
    tickets: List[TicketResponse] = Field(..., description="Generated tickets")
    generation_time: float = Field(..., description="Time taken to generate in seconds")
    success: bool = Field(..., description="Whether generation succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")


class CompareResponse(BaseModel):
    """Response model for comparison endpoint"""
    timestamp: str = Field(..., description="Comparison timestamp")
    count: int = Field(..., description="Number of tickets requested from each mode")
    comparisons: List[ComparisonTickets] = Field(..., description="Results from each mode")
    recommendation: str = Field(..., description="Recommended mode based on comparison")


# Helper Functions
def _select_best_mode() -> str:
    """
    Auto-select the best prediction mode based on recent performance.
    
    Selection logic:
    1. Check if v2 (XGBoost) is available
    2. If v2 available and performing well, use v2
    3. If v2 has issues, use hybrid
    4. Fallback to v1 (always available)
    
    Returns:
        Mode name: 'v1', 'v2', or 'hybrid'
    """
    # Try to check v2 availability
    try:
        # Quick test to see if v2 can initialize
        test_engine = UnifiedPredictionEngine(mode='v2')
        v2_available = test_engine.get_mode() == 'v2'
        
        if v2_available:
            # Check v2 performance from metrics
            metrics = test_engine.get_generation_metrics()
            total_gens = metrics.get('total_generations', 0)
            
            # If v2 has been used successfully, prefer it
            if total_gens > 0:
                logger.info("Auto-selected v2 mode (ML predictor) based on availability and history")
                return 'v2'
            else:
                # First time using v2, use hybrid to be safe
                logger.info("Auto-selected hybrid mode (first v2 usage)")
                return 'hybrid'
    except Exception as e:
        logger.debug(f"v2 not available: {e}")
    
    # Check if we should use hybrid or v1
    try:
        # If we've successfully used hybrid before, keep using it
        test_hybrid = UnifiedPredictionEngine(mode='hybrid')
        hybrid_metrics = test_hybrid.get_generation_metrics()
        if hybrid_metrics.get('total_generations', 0) > 0:
            logger.info("Auto-selected hybrid mode based on usage history")
            return 'hybrid'
    except Exception as e:
        logger.debug(f"Hybrid mode check failed: {e}")
    
    # Default to v1 (always available)
    logger.info("Auto-selected v1 mode (strategy-based) as default")
    return 'v1'


def _get_mode_metrics(mode: str) -> ModeMetrics:
    """
    Get performance metrics for a specific mode.
    
    Args:
        mode: Mode name ('v1', 'v2', or 'hybrid')
        
    Returns:
        ModeMetrics with performance data
    """
    try:
        engine = UnifiedPredictionEngine(mode=mode)
        metrics = engine.get_generation_metrics()
        
        # Check if mode is actually available (not fallen back)
        actual_mode = engine.get_mode()
        available = (actual_mode == mode)
        
        return ModeMetrics(
            mode=mode,
            total_generations=metrics.get('total_generations', 0),
            avg_generation_time=metrics.get('avg_generation_time', 0.0),
            last_generation_time=metrics.get('last_generation_time'),
            success_rate=1.0 if available else 0.0,  # Simplified: actual mode = success
            available=available
        )
    except Exception as e:
        logger.error(f"Error getting metrics for mode {mode}: {e}")
        return ModeMetrics(
            mode=mode,
            total_generations=0,
            avg_generation_time=0.0,
            last_generation_time=None,
            success_rate=0.0,
            available=False
        )


def _generate_tickets_with_fallback(mode: str, count: int) -> Dict:
    """
    Generate tickets with automatic fallback on error.
    
    Args:
        mode: Requested mode
        count: Number of tickets to generate
        
    Returns:
        Dict with success, mode, tickets, and metadata
    """
    import time
    
    start_time = time.time()
    
    try:
        # Initialize engine with requested mode
        engine = UnifiedPredictionEngine(mode=mode)
        
        # Generate tickets
        tickets = engine.generate_tickets(count)
        
        generation_time = time.time() - start_time
        actual_mode = engine.get_mode()
        
        # Check if fallback occurred
        fallback_occurred = (actual_mode != mode)
        
        return {
            'success': True,
            'mode': actual_mode,
            'requested_mode': mode,
            'fallback_occurred': fallback_occurred,
            'tickets': tickets,
            'generation_time': generation_time,
            'backend_info': engine.get_backend_info()
        }
        
    except Exception as e:
        logger.error(f"Error generating tickets with mode {mode}: {e}")
        
        # Fallback to v1
        if mode != 'v1':
            logger.warning(f"Falling back to v1 mode after {mode} failure")
            try:
                engine = UnifiedPredictionEngine(mode='v1')
                tickets = engine.generate_tickets(count)
                generation_time = time.time() - start_time
                
                return {
                    'success': True,
                    'mode': 'v1',
                    'requested_mode': mode,
                    'fallback_occurred': True,
                    'tickets': tickets,
                    'generation_time': generation_time,
                    'backend_info': engine.get_backend_info(),
                    'fallback_reason': str(e)
                }
            except Exception as fallback_error:
                logger.error(f"Fallback to v1 also failed: {fallback_error}")
                return {
                    'success': False,
                    'mode': mode,
                    'requested_mode': mode,
                    'fallback_occurred': True,
                    'tickets': [],
                    'generation_time': time.time() - start_time,
                    'error': str(fallback_error),
                    'original_error': str(e)
                }
        
        # v1 failed - nothing more to fallback to
        return {
            'success': False,
            'mode': mode,
            'requested_mode': mode,
            'fallback_occurred': False,
            'tickets': [],
            'generation_time': time.time() - start_time,
            'error': str(e)
        }


# API Endpoints
@router.post("/predict", response_model=PredictResponse)
async def predict_auto_mode(
    request: PredictRequest = PredictRequest()
) -> PredictResponse:
    """
    Generate prediction tickets with automatic mode selection.
    
    This endpoint automatically selects the best available prediction mode
    based on recent performance and availability.
    
    **Auto-selection logic:**
    1. Prefer v2 (ML) if available and performing well
    2. Use hybrid if v2 is new or has mixed performance
    3. Fallback to v1 (strategy-based) if v2 unavailable
    
    **Request:**
    ```json
    {
        "count": 5,
        "include_metadata": true
    }
    ```
    
    **Response:**
    - success: Whether generation succeeded
    - mode: Mode that was used
    - mode_selected: "auto"
    - tickets: List of generated tickets
    - metadata: Generation details (if requested)
    """
    try:
        # Auto-select best mode
        selected_mode = _select_best_mode()
        logger.info(f"Auto-selected mode: {selected_mode} for {request.count} tickets")
        
        # Generate tickets with fallback
        result = _generate_tickets_with_fallback(selected_mode, request.count)
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate predictions: {result.get('error', 'Unknown error')}"
            )
        
        # Build response
        tickets = [
            TicketResponse(
                white_balls=t['white_balls'],
                powerball=t['powerball'],
                strategy=t.get('strategy', 'unknown'),
                confidence=t.get('confidence', 0.5),
                source=t.get('source')
            )
            for t in result['tickets']
        ]
        
        metadata = None
        if request.include_metadata:
            metadata = {
                'requested_mode': result.get('requested_mode'),
                'actual_mode': result['mode'],
                'fallback_occurred': result.get('fallback_occurred', False),
                'generation_time': result['generation_time'],
                'backend_info': result.get('backend_info', {})
            }
            if result.get('fallback_reason'):
                metadata['fallback_reason'] = result['fallback_reason']
        
        return PredictResponse(
            success=True,
            mode=result['mode'],
            mode_selected='auto',
            tickets=tickets,
            count=len(tickets),
            metadata=metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in auto-mode prediction: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during prediction: {str(e)}"
        )


@router.post("/predict/{mode}", response_model=PredictResponse)
async def predict_specific_mode(
    mode: PredictionMode,
    request: PredictRequest = PredictRequest()
) -> PredictResponse:
    """
    Generate prediction tickets using a specific mode.
    
    Force the use of a specific prediction mode (v1, v2, or hybrid).
    Falls back to v1 if the requested mode fails.
    
    **Modes:**
    - **v1**: Strategy-based prediction (always available)
    - **v2**: ML-based prediction (requires XGBoost)
    - **hybrid**: Combination of v1 and v2 (70% v2, 30% v1 by default)
    
    **Request:**
    ```json
    {
        "count": 10,
        "include_metadata": true
    }
    ```
    
    **Response:**
    - success: Whether generation succeeded
    - mode: Actual mode used (may differ if fallback occurred)
    - mode_selected: "manual"
    - tickets: List of generated tickets
    - metadata: Generation details including fallback info
    """
    try:
        mode_str = mode.value
        logger.info(f"Generating {request.count} tickets with mode: {mode_str}")
        
        # Generate tickets with fallback
        result = _generate_tickets_with_fallback(mode_str, request.count)
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate predictions: {result.get('error', 'Unknown error')}"
            )
        
        # Build response
        tickets = [
            TicketResponse(
                white_balls=t['white_balls'],
                powerball=t['powerball'],
                strategy=t.get('strategy', 'unknown'),
                confidence=t.get('confidence', 0.5),
                source=t.get('source')
            )
            for t in result['tickets']
        ]
        
        metadata = None
        if request.include_metadata:
            metadata = {
                'requested_mode': result.get('requested_mode'),
                'actual_mode': result['mode'],
                'fallback_occurred': result.get('fallback_occurred', False),
                'generation_time': result['generation_time'],
                'backend_info': result.get('backend_info', {})
            }
            if result.get('fallback_reason'):
                metadata['fallback_reason'] = result['fallback_reason']
        
        return PredictResponse(
            success=True,
            mode=result['mode'],
            mode_selected='manual',
            tickets=tickets,
            count=len(tickets),
            metadata=metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in mode-specific prediction: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during prediction: {str(e)}"
        )


@router.get("/compare", response_model=CompareResponse)
async def compare_modes(
    count: int = Query(default=5, ge=1, le=50, description="Number of tickets to generate from each mode")
) -> CompareResponse:
    """
    Compare predictions from all available modes.
    
    Generates tickets using v1, v2, and hybrid modes simultaneously
    for direct comparison. Useful for evaluating mode performance.
    
    **Response includes:**
    - Tickets from each mode
    - Generation time for each mode
    - Success/failure status per mode
    - Recommended mode based on results
    
    **Example:**
    ```
    GET /api/v3/compare?count=3
    ```
    """
    try:
        logger.info(f"Comparing all modes with {count} tickets each")
        
        modes = ['v1', 'v2', 'hybrid']
        comparisons = []
        
        for mode in modes:
            result = _generate_tickets_with_fallback(mode, count)
            
            tickets = []
            if result['success']:
                tickets = [
                    TicketResponse(
                        white_balls=t['white_balls'],
                        powerball=t['powerball'],
                        strategy=t.get('strategy', 'unknown'),
                        confidence=t.get('confidence', 0.5),
                        source=t.get('source')
                    )
                    for t in result['tickets']
                ]
            
            comparisons.append(
                ComparisonTickets(
                    mode=mode,
                    tickets=tickets,
                    generation_time=result['generation_time'],
                    success=result['success'],
                    error=result.get('error')
                )
            )
        
        # Determine recommendation based on success and performance
        recommendation = 'v1'  # Default
        for comp in comparisons:
            if comp.success and comp.mode == 'v2':
                recommendation = 'v2'
                break
            elif comp.success and comp.mode == 'hybrid':
                recommendation = 'hybrid'
        
        return CompareResponse(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            count=count,
            comparisons=comparisons,
            recommendation=recommendation
        )
        
    except Exception as e:
        logger.error(f"Error in mode comparison: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during comparison: {str(e)}"
        )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """
    Get performance metrics for all prediction modes.
    
    Returns statistics about:
    - Generation count per mode
    - Average generation time
    - Success rate
    - Mode availability
    - Recommended mode
    
    **Example:**
    ```
    GET /api/v3/metrics
    ```
    """
    try:
        logger.info("Fetching metrics for all modes")
        
        modes = ['v1', 'v2', 'hybrid']
        mode_metrics = [_get_mode_metrics(mode) for mode in modes]
        
        # Determine recommended mode
        recommended = _select_best_mode()
        
        return MetricsResponse(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            modes=mode_metrics,
            recommended_mode=recommended
        )
        
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error fetching metrics: {str(e)}"
        )
