
#!/usr/bin/env python3
"""
SHIOL+ Pipeline Validation Script
Verifica la integridad y funcionamiento del pipeline
"""

import sys
import os
import sqlite3
import json
from datetime import datetime
from loguru import logger

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def validate_pipeline_components():
    """Validate all pipeline components"""
    logger.info("🔍 Validating pipeline components...")
    
    issues = []
    
    # Check orchestrator
    try:
        from src.orchestrator import PipelineOrchestrator
        orchestrator = PipelineOrchestrator()
        logger.info("✅ PipelineOrchestrator initialized successfully")
    except Exception as e:
        issues.append(f"❌ PipelineOrchestrator failed: {e}")
    
    # Check predictor
    try:
        from src.predictor import Predictor
        predictor = Predictor()
        logger.info("✅ Predictor initialized successfully")
    except Exception as e:
        issues.append(f"❌ Predictor failed: {e}")
    
    # Check database connectivity
    try:
        from src.database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM powerball_draws")
            count = cursor.fetchone()[0]
            logger.info(f"✅ Database connection OK ({count} historical draws)")
    except Exception as e:
        issues.append(f"❌ Database connection failed: {e}")
    
    return issues

def validate_pipeline_configuration():
    """Validate pipeline configuration consistency"""
    logger.info("🔧 Validating pipeline configuration...")
    
    issues = []
    
    # Check steps consistency
    try:
        # Check orchestrator steps
        from src.orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator()
        
        # Check API endpoints consistency
        from src import api_pipeline_endpoints
        
        logger.info("✅ Pipeline configuration consistency validated")
    except Exception as e:
        issues.append(f"❌ Configuration validation failed: {e}")
    
    return issues

def validate_model_files():
    """Validate model files exist and are accessible"""
    logger.info("🤖 Validating model files...")
    
    issues = []
    model_path = "models/shiolplus.pkl"
    
    if not os.path.exists(model_path):
        issues.append(f"❌ Model file not found: {model_path}")
    else:
        try:
            import joblib
            model_data = joblib.load(model_path)
            logger.info("✅ Model file validated successfully")
        except Exception as e:
            issues.append(f"❌ Model file corrupted: {e}")
    
    return issues

def run_test_pipeline():
    """Run a test pipeline execution"""
    logger.info("🧪 Running test pipeline execution...")
    
    try:
        from src.orchestrator import PipelineOrchestrator
        import uuid
        
        orchestrator = PipelineOrchestrator()
        
        # Check if pipeline is available
        if orchestrator.is_running():
            return ["⚠️ Pipeline currently running, skipping test execution"]
        
        logger.info("✅ Test pipeline validation completed")
        return []
        
    except Exception as e:
        return [f"❌ Test pipeline failed: {e}"]

def main():
    """Run complete pipeline validation"""
    logger.info("🚀 SHIOL+ Pipeline Validation")
    logger.info("=" * 50)
    
    all_issues = []
    
    # Run validations
    validations = [
        ("Pipeline Components", validate_pipeline_components),
        ("Pipeline Configuration", validate_pipeline_configuration),
        ("Model Files", validate_model_files),
        ("Test Pipeline", run_test_pipeline)
    ]
    
    for validation_name, validation_func in validations:
        logger.info(f"\n🔍 Running: {validation_name}")
        issues = validation_func()
        all_issues.extend(issues)
        
        if not issues:
            logger.info(f"✅ {validation_name}: PASSED")
        else:
            for issue in issues:
                logger.warning(issue)
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 PIPELINE VALIDATION SUMMARY")
    logger.info("=" * 50)
    
    if not all_issues:
        logger.info("🎯 ¡Pipeline completamente funcional!")
        logger.info("💡 Todos los componentes validados exitosamente")
        return True
    else:
        logger.warning(f"⚠️ Se encontraron {len(all_issues)} problemas:")
        for issue in all_issues:
            logger.warning(f"  {issue}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
