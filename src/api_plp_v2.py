"""
PLP v2 API Router (non-breaking adapter over existing v1 logic)

Endpoints are mounted under /api/v2 only when PLP_API_ENABLED=true.
They require Authorization: Bearer <PREDICTLOTTOPRO_API_KEY>.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, UploadFile, File, Request
from pydantic import BaseModel, Field
from loguru import logger

from src.plp_api_key import verify_plp_api_key
from src.prediction_engine import UnifiedPredictionEngine
from src.database import save_prediction_log, calculate_next_drawing_date
from src.ticket_processor import create_ticket_processor
from src.ticket_verifier import create_ticket_verifier

# Import existing v1 endpoint functions for reuse
from src.api_prediction_endpoints import (
    get_predictions_only_by_date as v1_get_predictions_only_by_date,
    get_public_predictions_by_draw_date as v1_get_public_predictions_by_draw_date,
)

# Import new analytics engines for PLP v2 (Task 4.5.2)
from src.analytics_engine import get_analytics_overview
from src.ticket_scorer import TicketScorer
from src.strategy_generators import CustomInteractiveGenerator, StrategyManager


router = APIRouter(
    prefix="/api/v2",
    tags=["plp_v2"],
    dependencies=[Depends(verify_plp_api_key)],
)


def _parse_date_str(date_str: str) -> str:
    """Strict YYYY-MM-DD validation and normalization.

    Returns normalized string or raises HTTPException 400.
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Use YYYY-MM-DD")


@router.get("/health")
async def plp_health(request: Request) -> Dict[str, Any]:
    """Lightweight health check for PLP v2. Useful for auth and rate limit testing.

    Returns minimal status payload; headers include X-RateLimit-* from dependency.
    """
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat() + "Z",
        "path": str(request.url.path),
        "source": "shiol+",
    }


def _transform_predictions_only_v2(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Transform v1 'predictions-only' shape to PLP v2 contract.

    Expected v1 keys:
    - draw_date
    - predictions: [{ numbers, powerball, score/confidence_score, method/strategy_used, created_at }]
    """
    predictions_v1 = payload.get("predictions", []) or []

    # Build v2 predictions list
    predictions_v2: List[Dict[str, Any]] = []
    for p in predictions_v1:
        # Accept multiple possible field names from v1
        numbers = p.get("numbers")
        if not numbers:
            # Some contexts may have n1..n5 (safety)
            numbers = [p.get("n1"), p.get("n2"), p.get("n3"), p.get("n4"), p.get("n5")]
            numbers = [int(n or 0) for n in numbers if isinstance(n, (int, float)) or (isinstance(n, str) and n.isdigit())]
            if len(numbers) != 5:
                continue

        strategy = p.get("method") or p.get("strategy") or p.get("generator_type") or "unknown"
        score = p.get("score")
        if score is None:
            score = p.get("confidence_score", 0.0)

        predictions_v2.append({
            "numbers": numbers,
            "powerball": p.get("powerball") or p.get("pb"),
            "strategy": strategy,
            "score": float(score) if isinstance(score, (int, float)) else 0.0,
        })

    # Metadata: generated_at from first prediction created_at if present
    generated_at = None
    if predictions_v1:
        first = predictions_v1[0]
        generated_at = first.get("created_at") or first.get("prediction_date")

    return {
        "draw_date": payload.get("draw_date"),
        "predictions": predictions_v2,
        "metadata": {
            "generated_at": generated_at,
            "source": "shiol+",
        },
    }


@router.get("/public/predictions-only/{draw_date}")
async def plp_predictions_only(
    draw_date: str = Path(..., description="Target draw date in YYYY-MM-DD")
) -> Dict[str, Any]:
    """Return predictions for a date without requiring official results (PLP v2 shape)."""
    normalized = _parse_date_str(draw_date)

    # Delegate to v1 endpoint function (non-breaking reuse)
    v1_payload = await v1_get_predictions_only_by_date(normalized, limit=100)

    # If v1 returns no predictions, adapt to 404 per PLP contract
    preds = v1_payload.get("predictions") or []
    if not preds:
        raise HTTPException(status_code=404, detail=f"No predictions found for date {normalized}")

    return _transform_predictions_only_v2(v1_payload)


def _transform_by_draw_grouped_v2(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Transform v1 'by-draw' predictions into PLP v2 grouped schema.

    Input (v1) keys of interest:
    - draw_date
    - predictions: [{ numbers, powerball, score, method, rank, ... }]

    Output (v2):
    {
      draw_date,
      strategies: [
        { name, predictions: [{ numbers, powerball, score, rank }] }
      ],
      metadata: { source, total_predictions }
    }
    """
    preds = payload.get("predictions") or []
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for p in preds:
        name = p.get("method") or p.get("strategy") or p.get("ai_method") or "unknown"
        item = {
            "numbers": p.get("numbers") or p.get("numbers_predicted"),
            "powerball": p.get("powerball") or p.get("powerball_predicted"),
            "score": p.get("score") if isinstance(p.get("score"), (int, float)) else float(p.get("score") or 0),
            "rank": p.get("rank") or 0,
        }
        grouped.setdefault(name, []).append(item)

    strategies = [
        {"name": name, "predictions": items}
        for name, items in grouped.items()
    ]

    return {
        "draw_date": payload.get("draw_date"),
        "strategies": strategies,
        "metadata": {
            "source": "shiol+",
            "total_predictions": sum(len(v) for v in grouped.values()),
        },
    }


@router.get("/public/by-draw/{draw_date}")
async def plp_by_draw_grouped(
    draw_date: str = Path(..., description="Target draw date in YYYY-MM-DD")
) -> Dict[str, Any]:
    """Return predictions grouped by strategy for a given draw date (PLP v2 shape)."""
    normalized = _parse_date_str(draw_date)

    # Delegate to v1 public endpoint for by-draw predictions
    v1_payload = await v1_get_public_predictions_by_draw_date(normalized, min_matches=0, limit=200)

    preds = v1_payload.get("predictions") or []
    if not preds:
        raise HTTPException(status_code=404, detail=f"No predictions found for date {normalized}")

    return _transform_by_draw_grouped_v2(v1_payload)


# ==== Generate Multi-Strategy (PLP v2) ====
class GenerateRequest(BaseModel):
    count: int = Field(5, ge=1, le=50, description="Number of tickets to generate (1-50)")
    strategies: Optional[List[str]] = Field(None, description="Subset of strategies to use; default uses adaptive weights across all")
    draw_date: Optional[str] = Field(None, description="Target draw date YYYY-MM-DD (required if persist=true; otherwise optional)")
    persist: bool = Field(False, description="If true, save tickets to database under draw_date (or next drawing date if omitted)")


def _ensure_unique_powerballs(tickets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure Powerball numbers are unique across the batch (best-effort)."""
    used = set()
    import random
    for t in tickets:
        pb = int(t.get("powerball") or 0)
        attempts = 0
        while pb in used and attempts < 26:
            pb = random.randint(1, 26)
            attempts += 1
        t["powerball"] = pb
        used.add(pb)
    return tickets


def _validate_and_normalize_strategies(req_strategies: Optional[List[str]], manager: StrategyManager) -> List[str]:
    available = set(manager.strategies.keys())
    if not req_strategies:
        return list(available)
    requested = [s.strip() for s in req_strategies if isinstance(s, str) and s.strip()]
    if not requested:
        raise HTTPException(status_code=400, detail="strategies must be a non-empty list of strings")
    unknown = [s for s in requested if s not in available]
    if unknown:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_strategies",
            "unknown": unknown,
            "allowed": sorted(list(available)),
        })
    return requested


def _transform_generated_tickets_v2(draw_date: Optional[str], tickets: List[Dict[str, Any]], persisted_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    strategies_used: Dict[str, int] = {}
    items = []
    for idx, t in enumerate(tickets, start=1):
        name = t.get("strategy") or "unknown"
        strategies_used[name] = strategies_used.get(name, 0) + 1
        
        # Convert numpy types to native Python types for JSON serialization
        numbers = t.get("white_balls") or t.get("numbers")
        if numbers:
            numbers = [int(n) for n in numbers]
        powerball = t.get("powerball")
        if powerball is not None:
            powerball = int(powerball)
        
        items.append({
            "numbers": numbers,
            "powerball": powerball,
            "strategy": name,
            "confidence": float(t.get("confidence") or 0.5),
            "rank": idx,
            "id": (persisted_ids[idx-1] if persisted_ids and len(persisted_ids) >= idx else None),
        })

    # Decide draw_date for response (echo provided or next draw)
    resp_draw_date = draw_date
    if not resp_draw_date:
        try:
            resp_draw_date = calculate_next_drawing_date()
        except Exception:
            resp_draw_date = None

    return {
        "draw_date": resp_draw_date,
        "tickets": items,
        "metadata": {
            "total_tickets": len(items),
            "strategies_used": strategies_used,
            "persisted": bool(persisted_ids),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "source": "shiol+",
        }
    }


@router.post("/generate-multi-strategy")
async def plp_generate_multi_strategy(req: GenerateRequest) -> Dict[str, Any]:
    """Generate tickets using the project's pipeline strategies (StrategyManager).

    - If `strategies` is omitted: use adaptive weights across all strategies.
    - If `strategies` is provided: distribute tickets evenly among that subset.
    - If `persist` is true: save to DB (requires valid draw_date or will use next drawing date).
    """
    # Validate draw_date if provided
    if req.draw_date:
        req.draw_date = _parse_date_str(req.draw_date)

    engine = UnifiedPredictionEngine()
    manager = engine.get_strategy_manager()  # Get StrategyManager for direct strategy access
    allowed = _validate_and_normalize_strategies(req.strategies, manager)

    tickets: List[Dict[str, Any]] = []

    try:
        if req.strategies and len(allowed) > 0:
            # Even distribution across selected strategies
            base = req.count // len(allowed)
            remainder = req.count % len(allowed)

            for name in allowed:
                try:
                    gen = manager.strategies[name].generate(base)
                    tickets.extend(gen)
                except Exception as e:
                    logger.error(f"Strategy {name} failed during generation: {e}")
                    tickets.extend([])

            # Distribute remainder one by one
            for i in range(remainder):
                name = allowed[i % len(allowed)]
                try:
                    gen = manager.strategies[name].generate(1)
                    tickets.extend(gen)
                except Exception as e:
                    logger.error(f"Strategy {name} failed on remainder: {e}")
        else:
            # Use adaptive weights across all strategies
            tickets = engine.generate_tickets(req.count)
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Ticket generation failed: {str(e)}")

    # Ensure unique PBs best-effort and trim to requested count
    tickets = _ensure_unique_powerballs(tickets)[: req.count]

    # Optionally persist
    persisted_ids: List[int] = []
    if req.persist:
        for t in tickets:
            # Map to save_prediction_log format
            payload = {
                "numbers": t.get("white_balls") or t.get("numbers"),
                "powerball": t.get("powerball"),
                "score_total": float(t.get("confidence") or 0.5),
                "model_version": t.get("strategy") or "pipeline",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            if req.draw_date:
                payload["draw_date"] = req.draw_date

            new_id = save_prediction_log(payload, allow_simulation=False, execution_source="pipeline_execution")
            if new_id:
                persisted_ids.append(int(new_id))

    return _transform_generated_tickets_v2(req.draw_date, tickets, persisted_ids if persisted_ids else None)


# ==== Ticket Preview (image OCR only, no limits) ====
@router.post("/ticket/preview")
async def plp_ticket_preview(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Extract ticket plays from an image without verification (PLP v2 shape)."""
    # Validate file
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_data = await file.read()
    if not image_data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(image_data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 25MB)")

    try:
        processor = create_ticket_processor()
        ticket_data = processor.process_ticket_image(image_data)
    except Exception as e:
        logger.error(f"Ticket processor initialization/processing failed: {e}")
        raise HTTPException(status_code=503, detail="Ticket processing service unavailable")

    if not ticket_data or not ticket_data.get("success", False):
        raise HTTPException(status_code=422, detail={
            "error": "ocr_failed",
            "details": ticket_data.get("error") if ticket_data else "Unknown processing error",
        })

    plays = ticket_data.get("plays", []) or []
    extracted = []
    for idx, p in enumerate(plays, start=1):
        extracted.append({
            "line": idx,
            "numbers": sorted(p.get("main_numbers", []) or []),
            "powerball": p.get("powerball"),
            "is_valid": (len(p.get("main_numbers", [])) == 5 and 1 <= int(p.get("powerball") or 0) <= 26),
        })

    return {
        "extracted_tickets": extracted,
        "quality": {
            "confidence": float(ticket_data.get("confidence", 0) or 0),
            "total_lines_extracted": len(ticket_data.get("raw_text_lines", []) or []),
            "extraction_method": ticket_data.get("extraction_method", "unknown"),
        },
        "metadata": {
            "draw_date_detected": ticket_data.get("draw_date"),
            "source": "shiol+",
            "filename": file.filename,
        },
    }


# ==== Ticket Verify (image -> OCR + verify) ====
@router.post("/ticket/verify")
async def plp_ticket_verify(file: UploadFile = File(...), draw_date: Optional[str] = None) -> Dict[str, Any]:
    """Verify a ticket image against official results (PLP v2 shape)."""
    if draw_date:
        draw_date = _parse_date_str(draw_date)

    # Validate file
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_data = await file.read()
    if not image_data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(image_data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 25MB)")

    try:
        processor = create_ticket_processor()
        verifier = create_ticket_verifier()
        ticket_data = processor.process_ticket_image(image_data)
    except Exception as e:
        logger.error(f"Ticket verify init failed: {e}")
        raise HTTPException(status_code=503, detail="Ticket verification service unavailable")

    if not ticket_data or not ticket_data.get("success", False):
        raise HTTPException(status_code=422, detail="Could not process ticket image")

    # Optional override draw date
    if draw_date:
        ticket_data["draw_date"] = draw_date

    verification_result = verifier.verify_ticket(ticket_data)
    if not verification_result or not verification_result.get("success", False):
        raise HTTPException(status_code=422, detail={
            "error": "verification_failed",
            "details": (verification_result or {}).get("error", "Unknown verification error"),
        })

    plays_out = []
    for r in verification_result.get("verification_results", []) or []:
        plays_out.append({
            "line": r.get("line"),
            "numbers": r.get("play_numbers", []),
            "powerball": r.get("powerball"),
            "matches": {
                "main": r.get("main_matches", 0),
                "powerball": r.get("powerball_match", False),
            },
            "prize": {
                "amount": r.get("prize_amount", 0),
                "tier": r.get("prize_tier", "No Prize"),
            },
            "is_winner": r.get("is_winner", False),
        })

    return {
        "draw_date": verification_result.get("draw_date") or draw_date,
        "official": {
            "numbers": verification_result.get("official_numbers", []),
            "powerball": verification_result.get("official_powerball"),
        },
        "plays": plays_out,
        "summary": {
            "total_plays": verification_result.get("total_plays", 0),
            "winners": verification_result.get("total_winning_plays", 0),
            "total_prize": verification_result.get("total_prize_amount", 0),
        },
        "metadata": {
            "processed_at": verification_result.get("processed_at"),
            "source": "shiol+",
            "filename": file.filename,
        },
    }


# ==== Ticket Verify Manual (JSON) ====
class PlpManualPlay(BaseModel):
    line: int
    numbers: List[int]
    powerball: int

class PlpManualVerifyRequest(BaseModel):
    draw_date: str
    plays: List[PlpManualPlay]


@router.post("/ticket/verify-manual")
async def plp_ticket_verify_manual(req: PlpManualVerifyRequest) -> Dict[str, Any]:
    """Verify manually provided plays against official results (PLP v2 shape)."""
    # Validate date
    req.draw_date = _parse_date_str(req.draw_date)

    # Basic validation of plays
    if not req.plays or len(req.plays) > 15:
        raise HTTPException(status_code=400, detail="plays must contain 1..15 items")
    valid_plays = []
    for p in req.plays:
        nums = sorted(p.numbers or [])
        if len(nums) != 5 or any(not (1 <= n <= 69) for n in nums):
            raise HTTPException(status_code=400, detail=f"Invalid numbers in line {p.line}")
        if not (1 <= int(p.powerball) <= 26):
            raise HTTPException(status_code=400, detail=f"Invalid powerball in line {p.line}")
        valid_plays.append({"line": p.line, "main_numbers": nums, "powerball": int(p.powerball)})

    # Build ticket_data and verify
    try:
        verifier = create_ticket_verifier()
        ticket_data = {
            "success": True,
            "plays": valid_plays,
            "draw_date": req.draw_date,
            "total_plays": len(valid_plays),
            "extraction_method": "manual_plp_v2",
        }
        verification_result = verifier.verify_ticket(ticket_data)
    except Exception as e:
        logger.error(f"Manual verify failed: {e}")
        raise HTTPException(status_code=503, detail="Verification service unavailable")

    if not verification_result or not verification_result.get("success", False):
        raise HTTPException(status_code=422, detail={
            "error": "verification_failed",
            "details": (verification_result or {}).get("error", "Unknown verification error"),
        })

    plays_out = []
    for r in verification_result.get("verification_results", []) or []:
        plays_out.append({
            "line": r.get("line"),
            "numbers": r.get("play_numbers", []),
            "powerball": r.get("powerball"),
            "matches": {
                "main": r.get("main_matches", 0),
                "powerball": r.get("powerball_match", False),
            },
            "prize": {
                "amount": r.get("prize_amount", 0),
                "tier": r.get("prize_tier", "No Prize"),
            },
            "is_winner": r.get("is_winner", False),
        })

    return {
        "draw_date": verification_result.get("draw_date") or req.draw_date,
        "official": {
            "numbers": verification_result.get("official_numbers", []),
            "powerball": verification_result.get("official_powerball"),
        },
        "plays": plays_out,
        "summary": {
            "total_plays": verification_result.get("total_plays", 0),
            "winners": verification_result.get("total_winning_plays", 0),
            "total_prize": verification_result.get("total_prize_amount", 0),
        },
        "metadata": {
            "processed_at": verification_result.get("processed_at"),
            "source": "shiol+",
        },
    }


# ==== PLP V2 Analytics Endpoints (Task 4.5.2) ====

@router.get("/analytics/context")
async def plp_analytics_context() -> Dict[str, Any]:
    """
    Get analytics context for PLP dashboard (hot/cold numbers, momentum, gaps).
    
    This endpoint provides pre-computed analytics data for the gamified experience,
    including hot numbers, cold numbers, momentum trends, and gap analysis.
    
    Returns:
        Dict with success, data (hot_numbers, cold_numbers, momentum, gaps), timestamp
    """
    try:
        # Get comprehensive analytics overview
        overview = get_analytics_overview()
        
        # Extract gap analysis for hot/cold numbers
        gap_analysis = overview.get('gap_analysis', {})
        white_balls_gaps = gap_analysis.get('white_balls', {})
        powerball_gaps = gap_analysis.get('powerball', {})
        
        # Extract momentum scores
        momentum_scores = overview.get('momentum_scores', {})
        white_balls_momentum = momentum_scores.get('white_balls', {})
        powerball_momentum = momentum_scores.get('powerball', {})
        
        # Identify hot numbers (low gap = recently drawn)
        white_balls_gaps_sorted = sorted(white_balls_gaps.items(), key=lambda x: x[1])
        hot_numbers = [int(num) for num, gap in white_balls_gaps_sorted[:10]]
        
        # Identify cold numbers (high gap = overdue)
        cold_numbers = [int(num) for num, gap in white_balls_gaps_sorted[-10:]]
        
        # Identify rising momentum numbers (positive momentum)
        rising_numbers = sorted(
            [(int(num), score) for num, score in white_balls_momentum.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Identify falling momentum numbers (negative momentum)
        falling_numbers = sorted(
            [(int(num), score) for num, score in white_balls_momentum.items()],
            key=lambda x: x[1]
        )[:10]
        
        # Build response with expected key names
        data = {
            'hot_numbers': {
                'white_balls': hot_numbers[:10],
                'powerball': sorted(
                    [(int(num), score) for num, score in powerball_gaps.items()],
                    key=lambda x: x[1]
                )[:5]
            },
            'cold_numbers': {
                'white_balls': cold_numbers[:10],
                'powerball': sorted(
                    [(int(num), score) for num, score in powerball_gaps.items()],
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
            },
            'momentum_trends': {
                'rising_numbers': [{'number': num, 'score': round(score, 2)} for num, score in rising_numbers],
                'falling_numbers': [{'number': num, 'score': round(score, 2)} for num, score in falling_numbers],
            },
            'gap_patterns': {
                'white_balls': {int(k): int(v) for k, v in white_balls_gaps.items()},
                'powerball': {int(k): int(v) for k, v in powerball_gaps.items()},
            },
            'data_summary': overview.get('data_summary', {}),
        }
        
        return {
            'success': True,
            'data': data,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'error': None,
        }
        
    except Exception as e:
        logger.error(f"Analytics context endpoint failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve analytics context: {str(e)}"
        )


# ==== Ticket Analyzer (Task 4.5.2) ====

class AnalyzeTicketRequest(BaseModel):
    """Request model for ticket analysis"""
    white_balls: List[int] = Field(..., min_length=5, max_length=5, description="5 white ball numbers (1-69)")
    powerball: int = Field(..., ge=1, le=26, description="Powerball number (1-26)")


@router.post("/analytics/analyze-ticket")
async def plp_analyze_ticket(req: AnalyzeTicketRequest) -> Dict[str, Any]:
    """
    Score a user's ticket based on statistical quality (0-100 scale).
    
    Analyzes tickets based on:
    - Diversity: Spread across number ranges
    - Balance: Sum range and odd/even ratio
    - Potential: Alignment with hot numbers and rising momentum
    
    Args:
        req: Request with white_balls (5 numbers) and powerball
        
    Returns:
        Dict with success, data (total_score, details, recommendation), timestamp
    """
    try:
        # Validate white balls
        if len(req.white_balls) != 5:
            raise HTTPException(status_code=400, detail="Must provide exactly 5 white ball numbers")
        
        if len(set(req.white_balls)) != 5:
            raise HTTPException(status_code=400, detail="White ball numbers must be unique")
        
        if not all(1 <= n <= 69 for n in req.white_balls):
            raise HTTPException(status_code=400, detail="White ball numbers must be between 1 and 69")
        
        # Get analytics context
        context = get_analytics_overview()
        
        # Initialize scorer and score the ticket
        scorer = TicketScorer()
        score_result = scorer.score_ticket(req.white_balls, req.powerball, context)
        
        return {
            'success': True,
            'data': score_result,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'error': None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ticket analyzer endpoint failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze ticket: {str(e)}"
        )


# ==== Interactive Generator (Task 4.5.2) ====

class InteractiveGeneratorRequest(BaseModel):
    """Request model for interactive ticket generation"""
    risk: str = Field("med", description="Risk level: 'low', 'med', or 'high'")
    temperature: str = Field("neutral", description="Temperature preference: 'hot', 'cold', or 'neutral'")
    exclude_numbers: List[int] = Field(default_factory=list, max_length=20, description="Numbers to exclude from generation (max 20)")
    count: int = Field(5, ge=1, le=10, description="Number of tickets to generate (1-10)")


@router.post("/generator/interactive")
async def plp_interactive_generator(req: InteractiveGeneratorRequest) -> Dict[str, Any]:
    """
    Generate tickets based on user's risk and temperature preferences.
    
    This endpoint provides an interactive generation experience where users can
    control the strategy through sliders:
    - Risk: How much to deviate from statistical norms
    - Temperature: Favor hot (recent) or cold (overdue) numbers
    - Exclusions: Numbers to avoid in generation
    
    Args:
        req: Request with risk, temperature, exclude list, and count
        
    Returns:
        Dict with success, data (generated tickets), timestamp
    """
    try:
        # Validate risk level
        risk = req.risk.lower()
        if risk not in ['low', 'med', 'high']:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid risk level '{req.risk}'. Must be 'low', 'med', or 'high'"
            )
        
        # Validate temperature
        temperature = req.temperature.lower()
        if temperature not in ['hot', 'cold', 'neutral']:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid temperature '{req.temperature}'. Must be 'hot', 'cold', or 'neutral'"
            )
        
        # Validate exclusions
        if req.exclude_numbers:
            if len(req.exclude_numbers) > 20:
                raise HTTPException(
                    status_code=400,
                    detail="Too many exclusions. Maximum 20 numbers allowed."
                )
            invalid_exclusions = [n for n in req.exclude_numbers if not (1 <= n <= 69)]
            if invalid_exclusions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid exclusion numbers: {invalid_exclusions}. Must be between 1 and 69"
                )
        
        # Validate count
        if req.count > 10:
            raise HTTPException(
                status_code=400,
                detail="Too many tickets requested. Maximum 10 allowed."
            )
        
        # Get analytics context
        context = get_analytics_overview()
        
        # Initialize generator
        generator = CustomInteractiveGenerator()
        
        # Build parameters
        params = {
            'count': req.count,
            'risk': risk,
            'temperature': temperature,
            'exclude': req.exclude_numbers,
        }
        
        # Generate tickets
        tickets = generator.generate_custom(params, context)
        
        # Format response tickets
        formatted_tickets = []
        for idx, ticket in enumerate(tickets, start=1):
            # Convert numpy types to native Python types for JSON serialization
            white_balls = ticket.get('white_balls') or ticket.get('numbers') or []
            white_balls = [int(n) for n in white_balls]
            
            powerball = ticket.get('powerball')
            if powerball is not None:
                powerball = int(powerball)
            
            formatted_tickets.append({
                'rank': idx,
                'white_balls': white_balls,
                'powerball': powerball,
                'strategy': ticket.get('strategy', 'custom_interactive'),
                'confidence': float(ticket.get('confidence', 0.5)),
            })
        
        return {
            'success': True,
            'data': {
                'tickets': formatted_tickets,
                'parameters': {
                    'risk': risk,
                    'temperature': temperature,
                    'excluded_count': len(req.exclude_numbers),
                    'requested_count': req.count,
                    'generated_count': len(formatted_tickets),
                },
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'error': None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Interactive generator endpoint failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate tickets: {str(e)}"
        )
