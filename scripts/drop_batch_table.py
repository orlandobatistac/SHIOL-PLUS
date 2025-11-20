"""
Script to drop pre_generated_tickets table from database.
Part of PHASE 1 Task 1.2: Batch System Elimination.
"""
import sqlite3
import os
from loguru import logger

# Path to database
db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'shiolplus.db')

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pre_generated_tickets'")
    exists = cursor.fetchone()
    
    if exists:
        logger.info("Table pre_generated_tickets found, dropping...")
        cursor.execute("DROP TABLE pre_generated_tickets")
        conn.commit()
        logger.info("✅ Table pre_generated_tickets dropped successfully")
    else:
        logger.info("⚠ Table pre_generated_tickets does not exist (already dropped or never created)")
    
    # Verify table is gone
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pre_generated_tickets'")
    still_exists = cursor.fetchone()
    
    if still_exists:
        logger.error("❌ FAILED: Table still exists after DROP command")
    else:
        logger.info("✅ VERIFIED: Table pre_generated_tickets successfully removed from database")
    
    conn.close()
    
except Exception as e:
    logger.error(f"❌ Error dropping table: {e}")
    raise

print("\n✅ Batch table elimination completed successfully")
