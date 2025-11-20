#!/usr/bin/env python3
"""
Populate predictions for all Recent Powerball Draws shown in the frontend.

DEFAULT BEHAVIOR (FULL REPOPULATION):
1. DELETES ALL existing predictions from generated_tickets table
2. Gets the 50 most recent Powerball draws (what frontend displays)
3. Generates 500 predictions for each draw
4. Processes in CHRONOLOGICAL ORDER (oldest → newest) for proper adaptive learning

This ensures a clean slate and proper adaptive learning progression.

Usage:
    # DEFAULT: Full repopulation (deletes all, regenerates 50 most recent)
    python scripts/populate_recent_draws.py
    
    # Custom limit (delete all, regenerate X most recent)
    python scripts/populate_recent_draws.py --limit 100
    
    # Custom tickets per draw
    python scripts/populate_recent_draws.py --tickets 300
    
    # INCREMENTAL MODE: Only generate for draws without predictions (no deletion)
    python scripts/populate_recent_draws.py --incremental
    
    # Dry run (see what would happen without executing)
    python scripts/populate_recent_draws.py --dry-run
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_connection
from loguru import logger
import argparse
import subprocess


def delete_all_predictions() -> int:
    """
    Delete ALL predictions from generated_tickets table.
    
    Returns:
        Number of tickets deleted
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Count existing tickets
        cursor.execute("SELECT COUNT(*) FROM generated_tickets")
        total_tickets = cursor.fetchone()[0]
        
        if total_tickets == 0:
            logger.info("Database is already empty (0 tickets)")
            return 0
        
        logger.warning("=" * 80)
        logger.warning(f"🗑️  DELETING ALL {total_tickets:,} PREDICTIONS FROM DATABASE")
        logger.warning("=" * 80)
        
        # Delete all tickets
        cursor.execute("DELETE FROM generated_tickets")
        conn.commit()
        
        logger.info(f"✅ Successfully deleted {total_tickets:,} tickets")
        logger.info("Database is now clean and ready for repopulation")
        
        return total_tickets


def get_recent_draws_without_predictions(limit: int = 50) -> list[str]:
    """
    Get recent draws that don't have predictions, in CHRONOLOGICAL ORDER.
    
    Args:
        limit: Number of recent draws to check (default: 50, matches frontend)
        
    Returns:
        List of draw dates in YYYY-MM-DD format, OLDEST FIRST (chronological order)
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get the 50 most recent draws
        cursor.execute("""
            SELECT draw_date 
            FROM powerball_draws 
            ORDER BY draw_date DESC 
            LIMIT ?
        """, (limit,))
        
        recent_draws = [row[0] for row in cursor.fetchall()]
        
        if not recent_draws:
            logger.warning("No draws found in database")
            return []
        
        logger.info(f"Found {len(recent_draws)} recent draws (from {recent_draws[-1]} to {recent_draws[0]})")
        
        # Check which draws have predictions
        draws_without_predictions = []
        draws_with_predictions = []
        
        for draw_date in recent_draws:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM generated_tickets 
                WHERE draw_date = ?
            """, (draw_date,))
            
            count = cursor.fetchone()[0]
            
            if count == 0:
                draws_without_predictions.append(draw_date)
            else:
                draws_with_predictions.append(draw_date)
        
        logger.info(f"✅ {len(draws_with_predictions)} draws already have predictions")
        logger.info(f"❌ {len(draws_without_predictions)} draws need predictions")
        
        # Return in CHRONOLOGICAL ORDER (oldest → newest) for adaptive learning
        draws_without_predictions.sort()  # Sort ascending (oldest first)
        
        return draws_without_predictions


def get_all_recent_draws(limit: int = 50) -> list[str]:
    """
    Get ALL recent draws in CHRONOLOGICAL ORDER, regardless of prediction status.
    
    Args:
        limit: Number of recent draws to retrieve (default: 50, matches frontend)
        
    Returns:
        List of draw dates in YYYY-MM-DD format, OLDEST FIRST (chronological order)
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT draw_date 
            FROM powerball_draws 
            ORDER BY draw_date DESC 
            LIMIT ?
        """, (limit,))
        
        draws = [row[0] for row in cursor.fetchall()]
        
        if not draws:
            logger.warning("No draws found in database")
            return []
        
        # Return in CHRONOLOGICAL ORDER (oldest → newest)
        draws.sort()  # Sort ascending (oldest first)
        
        logger.info(f"Found {len(draws)} recent draws (from {draws[0]} to {draws[-1]})")
        
        return draws


def run_regenerate_script(draw_date: str, tickets: int = 500) -> bool:
    """
    Execute regenerate_predictions_for_draw.py for a specific date.
    
    Args:
        draw_date: Draw date in YYYY-MM-DD format
        tickets: Number of tickets to generate
        
    Returns:
        True if successful, False otherwise
    """
    script_path = Path(__file__).parent / "regenerate_predictions_for_draw.py"
    
    try:
        # Use the same Python interpreter that's running this script
        cmd = [
            sys.executable,
            str(script_path),
            "--draw-date", draw_date,
            "--tickets", str(tickets)
        ]
        
        logger.info(f"Executing: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Log output
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                logger.info(f"  {line}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to generate predictions for {draw_date}")
        logger.error(f"Exit code: {e.returncode}")
        if e.stdout:
            logger.error(f"STDOUT: {e.stdout}")
        if e.stderr:
            logger.error(f"STDERR: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error for {draw_date}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Populate predictions for Recent Powerball Draws shown in frontend",
        epilog="DEFAULT: Deletes ALL predictions and regenerates from scratch (cleanest approach)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of recent draws to process (default: 50, matches frontend)"
    )
    parser.add_argument(
        "--tickets",
        type=int,
        default=500,
        help="Number of tickets to generate per draw (default: 500)"
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="INCREMENTAL MODE: Only generate for draws without predictions (no deletion)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which draws would be processed without actually running"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("POPULATE RECENT POWERBALL DRAWS - Full Repopulation")
    logger.info("=" * 80)
    logger.info(f"Frontend displays: {args.limit} most recent draws")
    logger.info(f"Tickets per draw: {args.tickets}")
    logger.info(f"Mode: {'INCREMENTAL (no deletion)' if args.incremental else 'FULL REPOPULATION (delete all first)'}")
    logger.info(f"Dry run: {'YES' if args.dry_run else 'NO'}")
    logger.info("=" * 80)
    
    # FULL REPOPULATION MODE (DEFAULT)
    if not args.incremental:
        if not args.dry_run:
            logger.info("\n🔥 FULL REPOPULATION MODE: Deleting ALL existing predictions first...")
            deleted_count = delete_all_predictions()
            logger.info(f"Deleted {deleted_count:,} tickets. Starting fresh.\n")
        else:
            logger.info("\n🔍 DRY RUN: Would delete ALL existing predictions first")
        
        # Get all recent draws (they will all need predictions now)
        draws_to_process = get_all_recent_draws(args.limit)
        
    # INCREMENTAL MODE (optional)
    else:
        logger.info("\n📊 INCREMENTAL MODE: Only generating for draws without predictions")
        draws_to_process = get_recent_draws_without_predictions(args.limit)
    
    if not draws_to_process:
        if args.incremental:
            logger.info("✅ All recent draws already have predictions! Nothing to do.")
        else:
            logger.warning("⚠️  No draws found to process!")
        return
    
    logger.info("\n" + "=" * 80)
    logger.info(f"PROCESSING {len(draws_to_process)} DRAWS IN CHRONOLOGICAL ORDER")
    logger.info("(oldest → newest for proper adaptive learning)")
    logger.info("=" * 80)
    logger.info(f"Date range: {draws_to_process[0]} (oldest) → {draws_to_process[-1]} (newest)")
    logger.info(f"Total predictions to generate: {len(draws_to_process) * args.tickets:,}")
    logger.info("=" * 80)
    
    if args.dry_run:
        logger.info("\n🔍 DRY RUN - Would process these draws:")
        for i, draw_date in enumerate(draws_to_process, 1):
            logger.info(f"  {i:3d}. {draw_date}")
        logger.info(f"\nTotal: {len(draws_to_process)} draws × {args.tickets} tickets = {len(draws_to_process) * args.tickets:,} total predictions")
        return
    
    # Process each draw
    success_count = 0
    failed_draws = []
    
    for i, draw_date in enumerate(draws_to_process, 1):
        logger.info("\n" + "-" * 80)
        logger.info(f"Processing draw {i}/{len(draws_to_process)}: {draw_date}")
        logger.info("-" * 80)
        
        success = run_regenerate_script(draw_date, args.tickets)
        
        if success:
            success_count += 1
            logger.info(f"✅ [{i}/{len(draws_to_process)}] Completed {draw_date}")
        else:
            failed_draws.append(draw_date)
            logger.error(f"❌ [{i}/{len(draws_to_process)}] Failed {draw_date}")
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total draws processed: {len(draws_to_process)}")
    logger.info(f"✅ Successful: {success_count}")
    logger.info(f"❌ Failed: {len(failed_draws)}")
    logger.info(f"Total predictions generated: {success_count * args.tickets:,}")
    
    if failed_draws:
        logger.error("\nFailed draws:")
        for draw_date in failed_draws:
            logger.error(f"  - {draw_date}")
        logger.error("\nYou can retry failed draws with:")
        for draw_date in failed_draws:
            logger.error(f"  python scripts/regenerate_predictions_for_draw.py --draw-date {draw_date} --tickets {args.tickets}")
    else:
        logger.info("\n🎉 All draws processed successfully!")
    
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
