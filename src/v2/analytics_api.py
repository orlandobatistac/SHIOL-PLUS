"""
SHIOL+ v2 - Analytics API Endpoint
===================================

Provides comprehensive analytics for PredictLottoPro integration:
- Hot/cold numbers analysis
- Gap reports
- Momentum indicators
- Pattern statistics
- Co-occurrence data
- ASCII visualizations
- Strategy performance metrics
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
import numpy as np

from src.database import get_all_draws, get_db_connection
from .statistical_core import (
    TemporalDecayModel,
    MomentumAnalyzer,
    GapAnalyzer,
    PatternEngine
)


# Pydantic models for response
class HotColdNumbers(BaseModel):
    hot_numbers: List[int] = Field(..., description="Numbers with highest recency weight")
    cold_numbers: List[int] = Field(..., description="Numbers with lowest recency weight")
    hot_powerball: List[int] = Field(..., description="Hot powerball numbers")
    cold_powerball: List[int] = Field(..., description="Cold powerball numbers")


class MomentumReport(BaseModel):
    rising_numbers: List[int] = Field(..., description="Numbers with positive momentum")
    falling_numbers: List[int] = Field(..., description="Numbers with negative momentum")
    momentum_chart: str = Field(..., description="ASCII chart of momentum")


class GapReport(BaseModel):
    overdue_numbers: List[int] = Field(..., description="Numbers with longest gaps")
    recent_numbers: List[int] = Field(..., description="Numbers that appeared recently")
    avg_gap: float = Field(..., description="Average gap across all numbers")
    gap_chart: str = Field(..., description="ASCII chart of gaps")


class PatternStats(BaseModel):
    odd_even_distribution: Dict[str, float] = Field(..., description="Historical odd/even distribution")
    sum_stats: Dict[str, float] = Field(..., description="Sum range statistics")
    decade_distribution: Dict[str, float] = Field(..., description="Tens clustering distribution")
    typical_spread: float = Field(..., description="Typical number spread (max-min)")


class CooccurrencePair(BaseModel):
    number_a: int
    number_b: int
    count: int
    deviation_pct: float


class AnalyticsOverview(BaseModel):
    """Complete analytics overview response"""
    hot_cold: HotColdNumbers
    momentum: MomentumReport
    gaps: GapReport
    patterns: PatternStats
    top_cooccurrences: List[CooccurrencePair]
    summary_commentary: str
    total_draws: int
    last_updated: str


# Router for v3 analytics
analytics_router = APIRouter(prefix="/api/v3/analytics", tags=["Analytics v3"])


@analytics_router.get(
    "/overview",
    response_model=AnalyticsOverview,
    summary="Get comprehensive lottery analytics",
    description="Returns multi-dimensional analytics including hot/cold analysis, momentum, gaps, patterns, and visualizations."
)
async def get_analytics_overview() -> AnalyticsOverview:
    """
    Get comprehensive analytics overview for PredictLottoPro.
    
    Provides:
    - Hot/cold number analysis (temporal weighting)
    - Momentum indicators (rising/falling trends)
    - Gap analysis (overdue numbers)
    - Pattern statistics (odd/even, sum, clustering)
    - Co-occurrence pairs
    - ASCII visualizations
    - Summary commentary
    """
    try:
        # Load historical draws
        draws_df = get_all_draws()
        
        if draws_df.empty:
            raise HTTPException(
                status_code=503,
                detail="No historical data available for analytics"
            )
        
        logger.info(f"Generating analytics for {len(draws_df)} draws")
        
        # Initialize analytical components
        temporal_model = TemporalDecayModel(decay_factor=0.05)
        momentum_analyzer = MomentumAnalyzer(short_window=10, long_window=50)
        gap_analyzer = GapAnalyzer()
        pattern_engine = PatternEngine()
        
        # Perform analyses
        weights = temporal_model.calculate_weights(draws_df)
        momentum = momentum_analyzer.analyze(draws_df)
        gaps = gap_analyzer.analyze(draws_df)
        patterns = pattern_engine.analyze(draws_df)
        
        # Build hot/cold analysis
        hot_cold = _build_hot_cold_analysis(weights)
        
        # Build momentum report
        momentum_report = _build_momentum_report(momentum)
        
        # Build gap report
        gap_report = _build_gap_report(gaps)
        
        # Build pattern stats
        pattern_stats = _build_pattern_stats(patterns)
        
        # Get top co-occurrences
        cooccurrences = _get_top_cooccurrences(limit=10)
        
        # Generate summary commentary
        commentary = _generate_summary_commentary(
            len(draws_df),
            hot_cold,
            momentum_report,
            gap_report
        )
        
        # Get current timestamp
        from datetime import datetime
        last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        logger.info("Analytics overview generated successfully")
        
        return AnalyticsOverview(
            hot_cold=hot_cold,
            momentum=momentum_report,
            gaps=gap_report,
            patterns=pattern_stats,
            top_cooccurrences=cooccurrences,
            summary_commentary=commentary,
            total_draws=len(draws_df),
            last_updated=last_updated
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analytics generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate analytics: {str(e)}"
        )


def _build_hot_cold_analysis(weights) -> HotColdNumbers:
    """Build hot/cold numbers from temporal weights"""
    # Get indices sorted by weight
    wb_indices = np.argsort(weights.white_ball_weights)
    pb_indices = np.argsort(weights.powerball_weights)
    
    # Hot = top 10 highest weights
    hot_wb = [int(i + 1) for i in wb_indices[-10:][::-1]]
    hot_pb = [int(i + 1) for i in pb_indices[-5:][::-1]]
    
    # Cold = bottom 10 lowest weights
    cold_wb = [int(i + 1) for i in wb_indices[:10]]
    cold_pb = [int(i + 1) for i in pb_indices[:5]]
    
    return HotColdNumbers(
        hot_numbers=hot_wb,
        cold_numbers=cold_wb,
        hot_powerball=hot_pb,
        cold_powerball=cold_pb
    )


def _build_momentum_report(momentum) -> MomentumReport:
    """Build momentum report with ASCII chart"""
    # Rising = hot numbers (positive momentum)
    rising = momentum.hot_numbers[:10]
    
    # Falling = cold numbers (negative momentum)
    falling = momentum.cold_numbers[:10]
    
    # Create ASCII chart
    chart = _create_momentum_chart(momentum.white_ball_momentum)
    
    return MomentumReport(
        rising_numbers=rising,
        falling_numbers=falling,
        momentum_chart=chart
    )


def _create_momentum_chart(momentum: np.ndarray) -> str:
    """Create ASCII bar chart of top momentum values"""
    # Get top 10 positive and negative
    indices = np.argsort(momentum)
    
    top_negative = [(int(i+1), float(momentum[i])) for i in indices[:5]]
    top_positive = [(int(i+1), float(momentum[i])) for i in indices[-5:][::-1]]
    
    lines = ["Momentum Chart (Top 5 Rising/Falling):", ""]
    
    # Rising
    lines.append("Rising:")
    for num, mom in top_positive:
        bar_len = int(abs(mom) * 20) + 1
        bar = "█" * bar_len
        lines.append(f"  {num:2d}: {bar} {mom:+.3f}")
    
    lines.append("")
    
    # Falling
    lines.append("Falling:")
    for num, mom in top_negative:
        bar_len = int(abs(mom) * 20) + 1
        bar = "░" * bar_len
        lines.append(f"  {num:2d}: {bar} {mom:+.3f}")
    
    return "\n".join(lines)


def _build_gap_report(gaps) -> GapReport:
    """Build gap report with ASCII chart"""
    # Overdue = top 15
    overdue = gaps.overdue_numbers[:15]
    
    # Recent = numbers with gap 0-2
    recent_indices = [i for i, gap in enumerate(gaps.white_ball_gaps) if gap <= 2]
    recent = [int(i + 1) for i in recent_indices]
    
    # Average gap
    avg_gap = float(np.mean(gaps.white_ball_gaps))
    
    # Create ASCII chart
    chart = _create_gap_chart(gaps.white_ball_gaps, overdue)
    
    return GapReport(
        overdue_numbers=overdue,
        recent_numbers=recent[:10],  # Limit to 10
        avg_gap=avg_gap,
        gap_chart=chart
    )


def _create_gap_chart(gaps: np.ndarray, overdue: List[int]) -> str:
    """Create ASCII chart of gap distribution"""
    lines = ["Gap Distribution (Top 10 Overdue):", ""]
    
    # Show top 10 overdue with gap bars
    for num in overdue[:10]:
        gap = int(gaps[num - 1])
        bar_len = min(gap // 5, 40)  # Scale down for display
        bar = "▓" * bar_len
        lines.append(f"  {num:2d}: {bar} {gap} draws")
    
    return "\n".join(lines)


def _build_pattern_stats(patterns) -> PatternStats:
    """Build pattern statistics"""
    # Calculate typical spread from patterns
    spreads = [p['spread'] for p in patterns.typical_patterns if 'spread' in p]
    typical_spread = float(np.mean(spreads)) if spreads else 50.0
    
    # Sum stats
    sum_mean, sum_std = patterns.sum_range
    
    return PatternStats(
        odd_even_distribution=patterns.odd_even_distribution,
        sum_stats={
            'mean': float(sum_mean),
            'std': float(sum_std),
            'min': float(sum_mean - 2 * sum_std),
            'max': float(sum_mean + 2 * sum_std)
        },
        decade_distribution=patterns.tens_clustering,
        typical_spread=typical_spread
    )


def _get_top_cooccurrences(limit: int = 10) -> List[CooccurrencePair]:
    """Get top co-occurrence pairs from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT number_a, number_b, count, deviation_pct
            FROM cooccurrences
            WHERE is_significant = TRUE
            ORDER BY deviation_pct DESC
            LIMIT ?
        """, (limit,))
        
        pairs = []
        for row in cursor.fetchall():
            pairs.append(CooccurrencePair(
                number_a=row[0],
                number_b=row[1],
                count=row[2],
                deviation_pct=float(row[3])
            ))
        
        conn.close()
        return pairs
        
    except Exception as e:
        logger.error(f"Failed to get co-occurrences: {e}")
        return []


def _generate_summary_commentary(
    total_draws: int,
    hot_cold: HotColdNumbers,
    momentum: MomentumReport,
    gaps: GapReport
) -> str:
    """Generate human-readable summary commentary"""
    lines = [
        f"Analysis based on {total_draws} historical Powerball draws.",
        "",
        "Hot Numbers (Recent Activity):",
        f"  White Balls: {', '.join(map(str, hot_cold.hot_numbers[:5]))}",
        f"  Powerball: {', '.join(map(str, hot_cold.hot_powerball[:3]))}",
        "",
        "Momentum Trends:",
        f"  Rising: {', '.join(map(str, momentum.rising_numbers[:5]))}",
        f"  Falling: {', '.join(map(str, momentum.falling_numbers[:5]))}",
        "",
        "Overdue Numbers (Gap Analysis):",
        f"  Top 5: {', '.join(map(str, gaps.overdue_numbers[:5]))}",
        f"  Average Gap: {gaps.avg_gap:.1f} draws",
        "",
        "Recommendation:",
        "  Consider balancing hot numbers (recent activity) with overdue numbers",
        "  (gap theory) for optimal coverage. Momentum indicators suggest trending",
        "  patterns worth monitoring."
    ]
    
    return "\n".join(lines)
