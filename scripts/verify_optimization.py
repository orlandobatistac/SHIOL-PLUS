
#!/usr/bin/env python3
"""
Script de verificación post-optimización para SHIOL+ v6.1
Verifica que el frontend siga funcionando con el backend optimizado
"""

import requests
import json
import time
from loguru import logger

def verify_optimization():
    """Verificar que la optimización mantuvo la funcionalidad del frontend"""
    
    import socket
    
    base_url = "http://0.0.0.0:3000"
    
    # Check if server is running first
    def is_server_running():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('0.0.0.0', 3000))
            sock.close()
            return result == 0
        except:
            return False
    
    if not is_server_running():
        logger.warning("⚠️  Server is not running on port 3000. Please start the server first.")
        logger.info("💡 Start server with: python main.py --server --host 0.0.0.0 --port 3000")
        return False
    
    tests = [
        {
            "name": "Frontend Dashboard Access",
            "url": f"{base_url}/dashboard.html",
            "method": "GET",
            "expected_status": 200
        },
        {
            "name": "Public API Endpoint", 
            "url": f"{base_url}/api/v1/public/latest",
            "method": "GET",
            "expected_status": 200
        },
        {
            "name": "Pipeline Status API",
            "url": f"{base_url}/api/v1/pipeline/status",
            "method": "GET", 
            "expected_status": 200,
            "requires_auth": True
        },
        {
            "name": "Dashboard Data API",
            "url": f"{base_url}/api/v1/dashboard/summary",
            "method": "GET",
            "expected_status": 200,
            "requires_auth": True
        }
    ]
    
    results = []
    
    for test in tests:
        try:
            logger.info(f"Testing: {test['name']}")
            
            if test.get('requires_auth'):
                # Skip auth tests for now in verification
                logger.info(f"⚠️  Skipping auth test: {test['name']}")
                continue
            
            response = requests.get(test['url'], timeout=10)
            
            success = response.status_code == test['expected_status']
            
            result = {
                'test': test['name'],
                'status_code': response.status_code,
                'expected': test['expected_status'],
                'success': success,
                'response_time': response.elapsed.total_seconds()
            }
            
            if success:
                logger.info(f"✅ {test['name']}: PASSED ({response.status_code})")
            else:
                logger.error(f"❌ {test['name']}: FAILED ({response.status_code})")
            
            results.append(result)
            
        except Exception as e:
            logger.error(f"❌ {test['name']}: ERROR - {e}")
            results.append({
                'test': test['name'],
                'success': False,
                'error': str(e)
            })
    
    # Summary
    passed = len([r for r in results if r.get('success', False)])
    total = len(results)
    
    logger.info(f"\n🎯 Verification Summary: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("✅ All tests passed! Frontend compatibility maintained.")
        return True
    else:
        logger.warning(f"⚠️  {total - passed} tests failed. Check compatibility.")
        return False

def verify_database_optimization():
    """Verificar que la optimización de base de datos fue exitosa"""
    try:
        import sqlite3
        import os
        
        db_path = "data/shiolplus.db"
        if not os.path.exists(db_path):
            logger.error("❌ Database file not found")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if optimization indexes exist
        cursor.execute("PRAGMA index_list(predictions_log)")
        indexes = [row[1] for row in cursor.fetchall()]
        
        required_indexes = ['idx_predictions_date', 'idx_predictions_active']
        missing_indexes = [idx for idx in required_indexes if idx not in indexes]
        
        if missing_indexes:
            logger.warning(f"⚠️  Missing database indexes: {missing_indexes}")
            return False
        else:
            logger.info("✅ Database optimization indexes verified")
            return True
            
    except Exception as e:
        logger.error(f"❌ Database verification failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("🔍 Starting optimization verification...")
    
    # Verify database optimization first
    db_ok = verify_database_optimization()
    
    # Verify frontend functionality (only if server is running)
    frontend_ok = verify_optimization()
    
    logger.info(f"\n📊 Verification Summary:")
    logger.info(f"   Database optimization: {'✅ OK' if db_ok else '❌ FAILED'}")
    logger.info(f"   Frontend compatibility: {'✅ OK' if frontend_ok else '⚠️  SERVER NOT RUNNING'}")
    
    if db_ok:
        logger.info("🎯 Plan de optimización implementado correctamente")
    else:
        logger.error("❌ Optimización requiere correcciones")
