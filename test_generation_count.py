#!/usr/bin/env python3
"""
Test script to verify that ticket generation respects the count parameter.
"""
import sys
sys.path.insert(0, '.')

from src.strategy_generators import StrategyManager

# Test StrategyManager.generate_balanced_tickets with count=100
print("Testing StrategyManager.generate_balanced_tickets with count=100...")
manager = StrategyManager()
tickets = manager.generate_balanced_tickets(total=100)
print(f"Generated {len(tickets)} tickets")
print(f"Expected: 100 tickets")
print(f"Result: {'✓ PASS' if len(tickets) == 100 else '✗ FAIL'}")

if len(tickets) != 100:
    print(f"\nDEBUG: First ticket: {tickets[0] if tickets else None}")
    print(f"DEBUG: Last ticket: {tickets[-1] if len(tickets) > 0 else None}")
    print(f"DEBUG: All ticket count: {len(tickets)}")
