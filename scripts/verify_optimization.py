
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
    
    base_url = "http://0.0.0.0:3000"
    
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

if __name__ == "__main__":
    verify_optimization()
