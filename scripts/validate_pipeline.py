
#!/usr/bin/env python3
"""
SHIOL+ Pipeline Validation Script
Verifica la integridad y funcionamiento del pipeline con diagnósticos detallados
"""

import sys
import os
import sqlite3
import json
import traceback
import asyncio
from datetime import datetime
from loguru import logger

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def validate_pipeline_components():
    """Validate all pipeline components with detailed error reporting"""
    logger.info("🔍 Validating pipeline components...")
    
    issues = []
    
    # Check orchestrator
    try:
        from src.orchestrator import PipelineOrchestrator
        orchestrator = PipelineOrchestrator()
        logger.info("✅ PipelineOrchestrator initialized successfully")
        
        # Test orchestrator methods
        if not hasattr(orchestrator, 'run_full_pipeline_async'):
            issues.append("❌ PipelineOrchestrator missing run_full_pipeline_async method")
        
        if not hasattr(orchestrator, 'is_running'):
            issues.append("❌ PipelineOrchestrator missing is_running method")
            
    except ImportError as e:
        issues.append(f"❌ PipelineOrchestrator import failed: {e}")
    except Exception as e:
        issues.append(f"❌ PipelineOrchestrator initialization failed: {e}")
        logger.error(f"Orchestrator error details: {traceback.format_exc()}")
    
    # Check predictor
    try:
        from src.predictor import Predictor
        predictor = Predictor()
        logger.info("✅ Predictor initialized successfully")
    except ImportError as e:
        issues.append(f"❌ Predictor import failed: {e}")
    except Exception as e:
        issues.append(f"❌ Predictor initialization failed: {e}")
        logger.error(f"Predictor error details: {traceback.format_exc()}")
    
    # Check database connectivity
    try:
        from src.database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM powerball_draws")
            count = cursor.fetchone()[0]
            logger.info(f"✅ Database connection OK ({count} historical draws)")
            
            # Check required tables
            required_tables = ['powerball_draws', 'powerball_numbers', 'pipeline_executions', 'predictions_log']
            for table in required_tables:
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if not cursor.fetchone():
                    issues.append(f"❌ Required table missing: {table}")
                    
    except ImportError as e:
        issues.append(f"❌ Database module import failed: {e}")
    except Exception as e:
        issues.append(f"❌ Database connection failed: {e}")
        logger.error(f"Database error details: {traceback.format_exc()}")
    
    # Check intelligent generator
    try:
        from src.intelligent_generator import IntelligentGenerator
        from src.loader import get_data_loader
        data_loader = get_data_loader()
        historical_data = data_loader.load_historical_data()
        generator = IntelligentGenerator(historical_data)
        logger.info("✅ IntelligentGenerator initialized successfully")
    except Exception as e:
        issues.append(f"❌ IntelligentGenerator failed: {e}")
        logger.error(f"Generator error details: {traceback.format_exc()}")
    
    return issues

def validate_pipeline_configuration():
    """Validate pipeline configuration consistency"""
    logger.info("🔧 Validating pipeline configuration...")
    
    issues = []
    
    try:
        # Check orchestrator steps configuration
        from src.orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator()
        
        # Check API endpoints consistency
        from src import api_pipeline_endpoints
        
        # Validate async methods exist
        required_methods = [
            'run_full_pipeline_async',
            '_run_data_update_and_evaluation',
            '_run_model_prediction',
            '_score_and_select',
            '_generate_predictions_optimized_step',
            '_save_and_serve_step'
        ]
        
        for method in required_methods:
            if not hasattr(orch, method):
                issues.append(f"❌ Missing required method: {method}")
        
        logger.info("✅ Pipeline configuration consistency validated")
        
    except Exception as e:
        issues.append(f"❌ Configuration validation failed: {e}")
        logger.error(f"Configuration error details: {traceback.format_exc()}")
    
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
            
            # Validate model structure
            if not isinstance(model_data, dict):
                issues.append(f"❌ Model file has invalid structure")
            else:
                logger.info(f"✅ Model file validated successfully (keys: {list(model_data.keys())})")
                
        except Exception as e:
            issues.append(f"❌ Model file corrupted or unreadable: {e}")
    
    return issues

def validate_async_functionality():
    """Test async functionality"""
    logger.info("⚡ Validating async functionality...")
    
    issues = []
    
    try:
        async def test_async():
            from src.orchestrator import PipelineOrchestrator
            orch = PipelineOrchestrator()
            
            # Test if pipeline can check running status
            is_running = orch.is_running()
            logger.info(f"Pipeline running status: {is_running}")
            
            return True
        
        # Run async test
        result = asyncio.run(test_async())
        if result:
            logger.info("✅ Async functionality test passed")
        else:
            issues.append("❌ Async functionality test failed")
            
    except Exception as e:
        issues.append(f"❌ Async functionality test failed: {e}")
        logger.error(f"Async test error details: {traceback.format_exc()}")
    
    return issues

def run_dependency_check():
    """Check all required dependencies"""
    logger.info("📦 Checking dependencies...")
    
    issues = []
    required_modules = [
        'numpy', 'pandas', 'scikit-learn', 'joblib', 
        'loguru', 'fastapi', 'uvicorn', 'psutil',
        'sqlite3', 'asyncio', 'datetime'
    ]
    
    for module in required_modules:
        try:
            __import__(module)
            logger.info(f"✅ {module} available")
        except ImportError:
            issues.append(f"❌ Missing required module: {module}")
    
    return issues

def main():
    """Run complete pipeline validation with enhanced diagnostics"""
    logger.info("🚀 SHIOL+ Enhanced Pipeline Validation")
    logger.info("=" * 60)
    
    all_issues = []
    
    # Run validations with enhanced diagnostics
    validations = [
        ("Dependencies", run_dependency_check),
        ("Pipeline Components", validate_pipeline_components),
        ("Pipeline Configuration", validate_pipeline_configuration),
        ("Model Files", validate_model_files),
        ("Async Functionality", validate_async_functionality)
    ]
    
    for validation_name, validation_func in validations:
        logger.info(f"\n🔍 Running: {validation_name}")
        try:
            issues = validation_func()
            all_issues.extend(issues)
            
            if not issues:
                logger.info(f"✅ {validation_name}: PASSED")
            else:
                logger.warning(f"⚠️ {validation_name}: {len(issues)} issues found")
                for issue in issues:
                    logger.warning(f"  {issue}")
                    
        except Exception as e:
            error_msg = f"❌ {validation_name} validation crashed: {e}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")
            all_issues.append(error_msg)
    
    # Summary with recommendations
    logger.info("\n" + "=" * 60)
    logger.info("📊 PIPELINE VALIDATION SUMMARY")
    logger.info("=" * 60)
    
    if not all_issues:
        logger.info("🎯 ¡Pipeline completamente funcional!")
        logger.info("💡 Todos los componentes validados exitosamente")
        logger.info("🚀 El pipeline está listo para ejecutarse")
        return True
    else:
        logger.warning(f"⚠️ Se encontraron {len(all_issues)} problemas:")
        logger.info("\n📋 PROBLEMAS IDENTIFICADOS:")
        for i, issue in enumerate(all_issues, 1):
            logger.warning(f"  {i}. {issue}")
        
        logger.info("\n🔧 RECOMENDACIONES:")
        logger.info("  1. Revisa los logs de error detallados arriba")
        logger.info("  2. Verifica que todas las dependencias estén instaladas")
        logger.info("  3. Asegúrate de que los archivos de modelo existen")
        logger.info("  4. Revisa la configuración de la base de datos")
        logger.info("  5. Ejecuta: pip install -r requirements.txt")
        
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
