#!/usr/bin/env python3
"""
Script de optimización de base de datos para SHIOL+ v6.1
Elimina tablas no utilizadas y optimiza el esquema
"""

import sqlite3
import os
from loguru import logger
from datetime import datetime

def optimize_database():
    """Optimizar esquema de base de datos eliminando tablas no utilizadas"""

    db_path = "data/shiolplus.db"
    if not os.path.exists(db_path):
        logger.error("Database not found")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Obtener lista de tablas actuales
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Existing tables: {existing_tables}")

        # Tablas a eliminar (no utilizadas en frontend)
        tables_to_remove = [
            'model_performance',
            'validation_results', 
            'adaptive_weights',
            'system_diagnostics',
            'security_logs',
            'weight_optimization_history'
        ]

        # Eliminar tablas no utilizadas
        removed_count = 0
        for table in tables_to_remove:
            if table in existing_tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"✅ Removed unused table: {table}")
                removed_count += 1

        # Crear índices optimizados si no existen
        optimization_queries = [
            "CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions_log(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_predictions_active ON predictions_log(timestamp, score_total)",
            "CREATE INDEX IF NOT EXISTS idx_powerball_date ON powerball_draws(draw_date)",
            "CREATE INDEX IF NOT EXISTS idx_pipeline_status ON pipeline_executions(status, start_time)"
        ]

        for query in optimization_queries:
            cursor.execute(query)
            logger.info(f"✅ Applied optimization: {query.split('ON')[0]}...")

        # Clean old data
        cleanup_queries = [
            "DELETE FROM predictions_log WHERE timestamp < datetime('now', '-30 days')",
            "DELETE FROM pipeline_executions WHERE start_time < datetime('now', '-30 days')"
        ]

        cleanup_count = 0
        for query in cleanup_queries:
            cursor.execute(query)
            cleanup_count += cursor.rowcount
            logger.info(f"✅ Applied cleanup: {query.split('WHERE')[0]}...")
        
        logger.info(f"✅ Cleaned {cleanup_count} old records")

        conn.commit()
        conn.close()  # Close connection before VACUUM

        # VACUUM must be run outside of transaction
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("VACUUM")
            conn.close()
            logger.info("✅ Applied optimization: VACUUM - Database compacted")
        except Exception as vacuum_error:
            logger.warning(f"VACUUM optimization skipped: {vacuum_error}")

    except Exception as e:
        logger.error(f"Database optimization failed: {e}")
        return False

    logger.info(f"🎯 Database optimization complete:")
    logger.info(f"   - Removed {removed_count} unused tables")
    logger.info(f"   - Applied performance indexes")
    logger.info(f"   - Database cleanup completed")

    return True


if __name__ == "__main__":
    optimize_database()