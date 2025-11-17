#!/usr/bin/env python3
"""
SHIOL+ v2 Demonstration Script
================================

This script demonstrates the capabilities of the SHIOL+ v2 prediction engine:
- Statistical analysis (temporal, momentum, gap, pattern)
- New v2 strategies
- Multi-dimensional scoring
- Analytics generation

Usage:
    python scripts/demo_v2.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from src.database import get_all_draws
from src.v2 import (
    TemporalDecayModel,
    MomentumAnalyzer,
    GapAnalyzer,
    PatternEngine,
    TemporalFrequencyStrategy,
    MomentumStrategy,
    GapTheoryStrategy,
    PatternStrategy,
    HybridSmartStrategy,
    ScoringEngine
)


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def demo_statistical_core():
    """Demonstrate statistical core components"""
    print_section("Statistical Core Analysis")
    
    # Load historical draws
    logger.info("Loading historical draws...")
    draws_df = get_all_draws()
    
    if draws_df.empty:
        logger.error("No historical data available")
        return None
    
    logger.info(f"Loaded {len(draws_df)} historical draws")
    
    # 1. Temporal Decay Analysis
    print("1. Temporal Decay Model")
    print("-" * 70)
    temporal_model = TemporalDecayModel(decay_factor=0.05)
    weights = temporal_model.calculate_weights(draws_df)
    
    # Get top 10 hot numbers
    import numpy as np
    top_indices = np.argsort(weights.white_ball_weights)[-10:][::-1]
    hot_numbers = [int(i + 1) for i in top_indices]
    
    print(f"Window Size: {weights.window_size} draws")
    print(f"Decay Factor: {weights.decay_factor}")
    print(f"Top 10 Hot Numbers: {hot_numbers}")
    
    # 2. Momentum Analysis
    print("\n2. Momentum Analyzer")
    print("-" * 70)
    momentum_analyzer = MomentumAnalyzer(short_window=10, long_window=50)
    momentum = momentum_analyzer.analyze(draws_df)
    
    print(f"Rising Numbers (Top 10): {momentum.hot_numbers[:10]}")
    print(f"Falling Numbers (Top 10): {momentum.cold_numbers[:10]}")
    
    # 3. Gap Analysis
    print("\n3. Gap/Drought Analyzer")
    print("-" * 70)
    gap_analyzer = GapAnalyzer()
    gaps = gap_analyzer.analyze(draws_df)
    
    print(f"Overdue Numbers (Top 10): {gaps.overdue_numbers[:10]}")
    print(f"Average Gap: {gaps.avg_gap:.1f} draws")
    
    # 4. Pattern Analysis
    print("\n4. Pattern Engine")
    print("-" * 70)
    pattern_engine = PatternEngine()
    patterns = pattern_engine.analyze(draws_df)
    
    mean_sum, std_sum = patterns.sum_range
    print(f"Typical Sum Range: {mean_sum:.1f} ± {std_sum:.1f}")
    print(f"Odd/Even Distribution: {patterns.odd_even_distribution}")
    
    # Test pattern scoring
    test_ticket = [5, 15, 25, 35, 45]
    conformity = pattern_engine.score_pattern_conformity(test_ticket)
    print(f"\nSample Ticket {test_ticket}")
    print(f"Pattern Conformity Score: {conformity:.3f}")
    
    return draws_df


def demo_strategies(draws_df):
    """Demonstrate v2 strategies"""
    print_section("SHIOL+ v2 Strategies")
    
    strategies = [
        ("Temporal Frequency Strategy", TemporalFrequencyStrategy()),
        ("Momentum Strategy", MomentumStrategy()),
        ("Gap Theory Strategy", GapTheoryStrategy()),
        ("Pattern Strategy", PatternStrategy()),
        ("Hybrid Smart Strategy", HybridSmartStrategy()),
    ]
    
    for name, strategy in strategies:
        print(f"\n{name}")
        print("-" * 70)
        
        # Override draws_df if empty
        if strategy.draws_df.empty and draws_df is not None:
            strategy.draws_df = draws_df
        
        # Generate sample tickets
        tickets = strategy.generate(count=3)
        
        for i, ticket in enumerate(tickets, 1):
            print(f"Ticket {i}: {ticket['white_balls']} | PB: {ticket['powerball']:2d} "
                  f"(Confidence: {ticket['confidence']:.2f})")


def demo_scoring(draws_df):
    """Demonstrate scoring engine"""
    print_section("Multi-Dimensional Scoring Engine")
    
    # Initialize scoring engine
    scoring_engine = ScoringEngine(draws_df=draws_df)
    
    # Create sample tickets
    test_tickets = [
        {'white_balls': [5, 15, 25, 35, 45], 'powerball': 10, 'name': 'Balanced Spread'},
        {'white_balls': [1, 2, 3, 4, 5], 'powerball': 1, 'name': 'Sequential Low'},
        {'white_balls': [10, 20, 30, 40, 50], 'powerball': 15, 'name': 'Even Spacing'},
        {'white_balls': [8, 17, 28, 42, 61], 'powerball': 22, 'name': 'Random Mix'},
    ]
    
    print("Scoring Sample Tickets:\n")
    
    for ticket in test_tickets:
        score = scoring_engine.score_ticket(ticket['white_balls'], ticket['powerball'])
        
        print(f"{ticket['name']}: {ticket['white_balls']} | PB: {ticket['powerball']}")
        print(f"  Overall Score: {score.overall_score:.3f}")
        print(f"  - Diversity:   {score.diversity_score:.3f}")
        print(f"  - Balance:     {score.balance_score:.3f}")
        print(f"  - Pattern:     {score.pattern_score:.3f}")
        print(f"  - Similarity:  {score.similarity_score:.3f}")
        print()
    
    # Rank tickets
    ranked = scoring_engine.rank_tickets(test_tickets)
    
    print("Rankings (Best to Worst):")
    print("-" * 70)
    for i, (ticket, score) in enumerate(ranked, 1):
        print(f"{i}. {ticket['name']}: {score.overall_score:.3f}")


def demo_quality_metrics(draws_df):
    """Demonstrate quality metrics"""
    print_section("Quality Metrics for Strategy Sets")
    
    scoring_engine = ScoringEngine(draws_df=draws_df)
    
    # Generate tickets from Hybrid Smart Strategy
    strategy = HybridSmartStrategy()
    if strategy.draws_df.empty and draws_df is not None:
        strategy.draws_df = draws_df
        # Re-initialize components
        strategy.weights = strategy.temporal_model.calculate_weights(draws_df)
        strategy.momentum = strategy.momentum_analyzer.analyze(draws_df)
        strategy.gaps = strategy.gap_analyzer.analyze(draws_df)
        strategy.patterns = strategy.pattern_engine.analyze(draws_df)
    
    tickets = strategy.generate(count=10)
    
    # Get quality summary
    summary = scoring_engine.get_quality_summary(tickets)
    
    print(f"Hybrid Smart Strategy - 10 Tickets Analysis:\n")
    print(f"Average Diversity:   {summary['avg_diversity']:.3f}")
    print(f"Average Balance:     {summary['avg_balance']:.3f}")
    print(f"Average Pattern:     {summary['avg_pattern']:.3f}")
    print(f"Average Similarity:  {summary['avg_similarity']:.3f}")
    print(f"\nOverall Quality:     {summary['avg_overall']:.3f} ± {summary['std_overall']:.3f}")
    print(f"Range: [{summary['min_overall']:.3f}, {summary['max_overall']:.3f}]")


def main():
    """Main demonstration function"""
    logger.info("Starting SHIOL+ v2 Demonstration")
    
    # Run demonstrations
    draws_df = demo_statistical_core()
    
    if draws_df is not None:
        demo_strategies(draws_df)
        demo_scoring(draws_df)
        demo_quality_metrics(draws_df)
    
    print("\n" + "=" * 70)
    print("  Demonstration Complete!")
    print("=" * 70 + "\n")
    
    logger.info("SHIOL+ v2 demonstration complete")


if __name__ == "__main__":
    main()
