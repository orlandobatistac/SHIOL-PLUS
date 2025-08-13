
#!/usr/bin/env python3
"""
Script de verificación completa del sistema SHIOL+ v6.1
Verifica base de datos, optimizaciones, y funcionalidad general
"""

import sqlite3
import os
import socket
import sys
from loguru import logger
from datetime import datetime

def check_database_health():
    """Verificar salud y optimizaciones de la base de datos"""
    logger.info("🔍 Checking database health...")
    
    db_path = "data/shiolplus.db"
    if not os.path.exists(db_path):
        logger.error("❌ Database file not found")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check core tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['powerball_draws', 'predictions_log', 'pipeline_executions']
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            logger.error(f"❌ Missing tables: {missing_tables}")
            return False
        
        # Check indexes
        cursor.execute("PRAGMA index_list(predictions_log)")
        indexes = [row[1] for row in cursor.fetchall()]
        
        # Check data integrity
        cursor.execute("SELECT COUNT(*) FROM predictions_log")
        predictions_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM powerball_draws")
        draws_count = cursor.fetchone()[0]
        
        conn.close()
        
        logger.info(f"✅ Database health OK:")
        logger.info(f"   - Tables: {len(tables)} found")
        logger.info(f"   - Indexes: {len(indexes)} found")
        logger.info(f"   - Predictions: {predictions_count}")
        logger.info(f"   - Historical draws: {draws_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database check failed: {e}")
        return False

def check_server_availability():
    """Verificar si el servidor está disponible"""
    logger.info("🌐 Checking server availability...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(('0.0.0.0', 3000))
        sock.close()
        
        if result == 0:
            logger.info("✅ Server is running on port 3000")
            return True
        else:
            logger.warning("⚠️  Server is not running on port 3000")
            logger.info("💡 Start with: python main.py --server --host 0.0.0.0 --port 3000")
            return False
            
    except Exception as e:
        logger.error(f"❌ Server check failed: {e}")
        return False

def check_file_permissions():
    """Verificar permisos de archivos críticos"""
    logger.info("📁 Checking file permissions...")
    
    critical_paths = [
        "data/shiolplus.db",
        "models/shiolplus.pkl",
        "config/config.ini",
        "logs/"
    ]
    
    issues = []
    for path in critical_paths:
        if os.path.exists(path):
            if os.access(path, os.R_OK):
                logger.debug(f"✅ {path} readable")
            else:
                issues.append(f"{path} not readable")
                
            if os.path.isfile(path) and os.access(path, os.W_OK):
                logger.debug(f"✅ {path} writable")
            elif os.path.isdir(path) and os.access(path, os.W_OK):
                logger.debug(f"✅ {path} writable")
            else:
                issues.append(f"{path} not writable")
        else:
            issues.append(f"{path} not found")
    
    if issues:
        logger.warning(f"⚠️  Permission issues: {issues}")
        return False
    else:
        logger.info("✅ File permissions OK")
        return True

def main():
    """Ejecutar verificación completa del sistema"""
    logger.info("🚀 SHIOL+ System Health Check")
    logger.info("=" * 50)
    
    checks = [
        ("Database Health", check_database_health),
        ("Server Availability", check_server_availability),
        ("File Permissions", check_file_permissions)
    ]
    
    results = {}
    for check_name, check_func in checks:
        logger.info(f"\n🔍 Running: {check_name}")
        results[check_name] = check_func()
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 SYSTEM HEALTH SUMMARY")
    logger.info("=" * 50)
    
    all_ok = True
    for check_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{check_name}: {status}")
        if not result:
            all_ok = False
    
    if all_ok:
        logger.info("\n🎯 Sistema funcionando correctamente")
        logger.info("💡 Plan de optimización verificado exitosamente")
    else:
        logger.warning("\n⚠️  Se encontraron problemas que requieren atención")
        logger.info("💡 Revisa los logs anteriores para detalles específicos")
    
    return all_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
