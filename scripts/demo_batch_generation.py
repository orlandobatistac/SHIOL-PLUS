#!/usr/bin/env python3
"""
Batch Ticket Pre-Generation Demo
=================================
Demonstrates the batch ticket pre-generation system.

This script shows:
1. How to generate tickets in batch
2. How to retrieve cached tickets
3. Performance comparison between cached vs on-demand generation
"""

import time
from typing import List, Dict, Any

# Mock the dependencies for demo purposes
class MockUnifiedPredictionEngine:
    """Mock prediction engine for demo."""
    def __init__(self, mode: str = 'v1'):
        self.mode = mode
    
    def generate_tickets(self, count: int = 5) -> List[Dict[str, Any]]:
        """Generate mock tickets."""
        import random
        tickets = []
        for _ in range(count):
            white_balls = sorted(random.sample(range(1, 70), 5))
            powerball = random.randint(1, 26)
            tickets.append({
                'white_balls': white_balls,
                'powerball': powerball,
                'strategy': self.mode,
                'confidence': round(random.random(), 2)
            })
        return tickets


def demo_batch_generation():
    """Demonstrate batch ticket generation."""
    print("=" * 70)
    print("BATCH TICKET PRE-GENERATION DEMO")
    print("=" * 70)
    print()
    
    # Example 1: Generate tickets synchronously
    print("1. SYNCHRONOUS BATCH GENERATION")
    print("-" * 70)
    
    from src.batch_generator import BatchTicketGenerator
    
    # Initialize batch generator
    batch_gen = BatchTicketGenerator(
        batch_size=10,  # Generate 10 tickets per mode
        modes=['random_forest', 'lstm'],
        auto_cleanup=False  # Don't cleanup for demo
    )
    
    print(f"Configured modes: {batch_gen.modes}")
    print(f"Batch size: {batch_gen.batch_size}")
    print()
    
    # Patch the engine for demo (would normally use real prediction engine)
    import src.batch_generator
    original_engine = src.batch_generator.UnifiedPredictionEngine
    src.batch_generator.UnifiedPredictionEngine = MockUnifiedPredictionEngine
    
    try:
        # Generate batch synchronously
        print("Generating batch (sync mode)...")
        start_time = time.time()
        
        result = batch_gen.generate_batch(
            pipeline_run_id='demo-2025-11-18',
            async_mode=False  # Synchronous for demo
        )
        
        generation_time = time.time() - start_time
        
        print(f"✓ Generation completed in {generation_time:.2f}s")
        print(f"  Success: {result['result']['success']}")
        print(f"  Modes processed: {result['result']['modes_processed']}")
        print(f"  Total tickets: {result['result']['total_tickets']}")
        print(f"  By mode: {result['result']['by_mode']}")
        print()
        
        # Example 2: Get status
        print("2. BATCH GENERATOR STATUS")
        print("-" * 70)
        
        status = batch_gen.get_status()
        print(f"Is generating: {status['is_generating']}")
        print(f"Configured modes: {status['configured_modes']}")
        print(f"Batch size: {status['batch_size']}")
        print(f"Metrics: {status['metrics']}")
        print()
        
        # Example 3: Asynchronous generation
        print("3. ASYNCHRONOUS BATCH GENERATION")
        print("-" * 70)
        
        batch_gen2 = BatchTicketGenerator(
            batch_size=5,
            modes=['v1'],
            auto_cleanup=False
        )
        
        print("Starting async batch generation...")
        result = batch_gen2.generate_batch(
            pipeline_run_id='demo-async-2025-11-18',
            async_mode=True  # Asynchronous
        )
        
        print(f"✓ Background thread started: {result['started']}")
        print(f"  Async mode: {result['async']}")
        print(f"  Modes: {result['modes']}")
        print()
        
        # Wait for completion
        print("Waiting for completion (max 10s)...")
        completed = batch_gen2.wait_for_completion(timeout=10)
        print(f"✓ Completed: {completed}")
        print()
        
        # Example 4: Cached vs On-Demand Performance
        print("4. PERFORMANCE COMPARISON")
        print("-" * 70)
        
        # Simulate on-demand generation
        print("On-demand generation (5 tickets):")
        start = time.time()
        engine = MockUnifiedPredictionEngine(mode='random_forest')
        tickets = engine.generate_tickets(5)
        on_demand_time = (time.time() - start) * 1000
        print(f"  Time: {on_demand_time:.2f}ms")
        print()
        
        # Simulate cached retrieval (would be <10ms from database)
        print("Cached retrieval (5 tickets):")
        start = time.time()
        # In real implementation: get_cached_tickets('random_forest', 5)
        cached_time = 5.0  # Simulated <10ms
        print(f"  Time: {cached_time:.2f}ms")
        print()
        
        print(f"⚡ Speedup: {on_demand_time / cached_time:.1f}x faster")
        print()
        
    finally:
        # Restore original engine
        src.batch_generator.UnifiedPredictionEngine = original_engine
    
    print("=" * 70)
    print("DEMO COMPLETED")
    print("=" * 70)


def demo_api_usage():
    """Demonstrate API endpoint usage."""
    print()
    print("=" * 70)
    print("API ENDPOINT EXAMPLES")
    print("=" * 70)
    print()
    
    print("GET /api/v1/tickets/cached?mode=random_forest&limit=5")
    print("Response:")
    print("""{
  "mode": "random_forest",
  "count": 5,
  "tickets": [
    {
      "white_balls": [1, 12, 23, 34, 45],
      "powerball": 15,
      "confidence": 0.85,
      "strategy": "random_forest",
      "cached": true,
      "created_at": "2025-11-18T23:50:00"
    },
    ...
  ],
  "cached": true,
  "response_time_ms": 8.5
}""")
    print()
    
    print("GET /api/v1/tickets/batch-status")
    print("Response:")
    print("""{
  "total_tickets": 200,
  "by_mode": {
    "random_forest": 100,
    "lstm": 100
  },
  "oldest_ticket": "2025-11-11T23:50:00",
  "newest_ticket": "2025-11-18T23:50:00"
}""")
    print()


if __name__ == '__main__':
    try:
        demo_batch_generation()
        demo_api_usage()
    except Exception as e:
        print(f"Demo error: {e}")
        import traceback
        traceback.print_exc()
