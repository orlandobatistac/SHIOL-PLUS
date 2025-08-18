
#!/usr/bin/env python3
"""
SHIOL+ Pipeline Validation Script (v2.0)
Sistema de validación refactorizado con diagnósticos avanzados
"""

import sys
import os
import sqlite3
import json
import traceback
import asyncio
import importlib
from datetime import datetime
from pathlib import Path

# Setup logging first
try:
    from loguru import logger
    logger.remove()  # Remove default handler
    logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

def check_environment():
    """Verificar el entorno básico"""
    logger.info("🔍 Verificando entorno básico...")
    
    issues = []
    
    # Check Python version
    python_version = sys.version_info
    if python_version < (3, 8):
        issues.append(f"❌ Python version too old: {python_version.major}.{python_version.minor}")
    else:
        logger.info(f"✅ Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # Check project structure
    required_dirs = ['src', 'models', 'data', 'config', 'scripts']
    for dir_name in required_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists():
            logger.info(f"✅ Directory exists: {dir_name}/")
        else:
            issues.append(f"❌ Missing directory: {dir_name}/")
    
    # Check critical files
    critical_files = [
        'src/orchestrator.py',
        'src/database.py',
        'src/predictor.py',
        'src/api.py',
        'config/config.ini',
        'main.py'
    ]
    
    for file_path in critical_files:
        full_path = project_root / file_path
        if full_path.exists():
            logger.info(f"✅ File exists: {file_path}")
        else:
            issues.append(f"❌ Missing file: {file_path}")
    
    return issues

def check_dependencies():
    """Verificar dependencias críticas"""
    logger.info("📦 Verificando dependencias...")
    
    issues = []
    
    # Core dependencies
    core_deps = [
        'numpy', 'pandas', 'scikit-learn', 'joblib',
        'fastapi', 'uvicorn', 'sqlite3', 'psutil'
    ]
    
    for dep in core_deps:
        try:
            module = importlib.import_module(dep)
            if hasattr(module, '__version__'):
                version = module.__version__
                logger.info(f"✅ {dep}: {version}")
            else:
                logger.info(f"✅ {dep}: available")
        except ImportError:
            issues.append(f"❌ Missing dependency: {dep}")
            logger.error(f"❌ Cannot import {dep}")
    
    # Optional dependencies
    optional_deps = ['loguru', 'schedule']
    for dep in optional_deps:
        try:
            importlib.import_module(dep)
            logger.info(f"✅ {dep}: available (optional)")
        except ImportError:
            logger.warning(f"⚠️ Optional dependency missing: {dep}")
    
    return issues

def check_database():
    """Verificar conectividad y estructura de base de datos"""
    logger.info("🗄️ Verificando base de datos...")
    
    issues = []
    
    try:
        # Import database module
        from database import get_db_connection, get_db_path
        
        db_path = get_db_path()
        logger.info(f"Database path: {db_path}")
        
        if not os.path.exists(db_path):
            issues.append(f"❌ Database file not found: {db_path}")
            return issues
        
        # Test connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = [
                'powerball_draws', 'predictions_log', 
                'pipeline_executions', 'system_config'
            ]
            
            for table in required_tables:
                if table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    logger.info(f"✅ Table {table}: {count} records")
                else:
                    issues.append(f"❌ Missing table: {table}")
            
            # Check data integrity
            cursor.execute("SELECT COUNT(*) FROM powerball_draws")
            draws_count = cursor.fetchone()[0]
            
            if draws_count == 0:
                issues.append("⚠️ No historical data in powerball_draws")
            elif draws_count < 10:
                issues.append(f"⚠️ Limited historical data: {draws_count} draws")
            else:
                logger.info(f"✅ Historical data: {draws_count} draws")
                
    except Exception as e:
        issues.append(f"❌ Database error: {e}")
        logger.error(f"Database check failed: {traceback.format_exc()}")
    
    return issues

def check_model_files():
    """Verificar archivos de modelo"""
    logger.info("🤖 Verificando archivos de modelo...")
    
    issues = []
    
    model_path = project_root / "models" / "shiolplus.pkl"
    
    if not model_path.exists():
        issues.append(f"❌ Model file not found: {model_path}")
        return issues
    
    try:
        import joblib
        
        # Test model loading
        model_data = joblib.load(model_path)
        
        if isinstance(model_data, dict):
            logger.info(f"✅ Model file loaded: {list(model_data.keys())}")
            
            # Check model components
            expected_keys = ['model', 'scaler', 'version']
            for key in expected_keys:
                if key in model_data:
                    logger.info(f"  ✅ Component: {key}")
                else:
                    logger.warning(f"  ⚠️ Missing component: {key}")
        else:
            logger.warning("⚠️ Model has unexpected structure")
            
    except Exception as e:
        issues.append(f"❌ Model loading error: {e}")
        logger.error(f"Model check failed: {e}")
    
    return issues

def check_orchestrator():
    """Verificar el orchestrator principal"""
    logger.info("🎭 Verificando orchestrator...")
    
    issues = []
    
    try:
        # Import orchestrator
        from orchestrator import PipelineOrchestrator
        
        # Test initialization
        orchestrator = PipelineOrchestrator()
        logger.info("✅ PipelineOrchestrator initialized")
        
        # Check required methods
        required_methods = [
            'run_full_pipeline_async',
            'is_running',
            'get_current_execution_id'
        ]
        
        for method in required_methods:
            if hasattr(orchestrator, method):
                logger.info(f"  ✅ Method: {method}")
            else:
                issues.append(f"❌ Missing method: {method}")
        
        # Test basic functionality
        is_running = orchestrator.is_running()
        logger.info(f"✅ Pipeline running status: {is_running}")
        
        execution_id = orchestrator.get_current_execution_id()
        logger.info(f"✅ Current execution ID: {execution_id or 'None'}")
        
    except Exception as e:
        issues.append(f"❌ Orchestrator error: {e}")
        logger.error(f"Orchestrator check failed: {traceback.format_exc()}")
    
    return issues

def check_predictor():
    """Verificar el sistema de predicción"""
    logger.info("🔮 Verificando predictor...")
    
    issues = []
    
    try:
        from predictor import Predictor
        
        predictor = Predictor()
        logger.info("✅ Predictor initialized")
        
        # Test basic prediction capability
        if hasattr(predictor, 'predict_probabilities'):
            logger.info("✅ Prediction method available")
        else:
            issues.append("❌ Missing predict_probabilities method")
            
    except Exception as e:
        issues.append(f"❌ Predictor error: {e}")
        logger.error(f"Predictor check failed: {e}")
    
    return issues

def check_intelligent_generator():
    """Verificar el generador inteligente"""
    logger.info("🧠 Verificando intelligent generator...")
    
    issues = []
    
    try:
        from intelligent_generator import IntelligentGenerator
        from loader import get_data_loader
        
        # Load data for generator
        data_loader = get_data_loader()
        historical_data = data_loader.load_historical_data()
        
        if historical_data is not None and len(historical_data) > 0:
            generator = IntelligentGenerator(historical_data)
            logger.info("✅ IntelligentGenerator initialized")
            
            # Test generation
            if hasattr(generator, 'generate_play'):
                test_play = generator.generate_play()
                if test_play and 'numbers' in test_play:
                    logger.info("✅ Test play generation successful")
                else:
                    issues.append("❌ Play generation returned invalid data")
            else:
                issues.append("❌ Missing generate_play method")
        else:
            issues.append("❌ No historical data available for generator")
            
    except Exception as e:
        issues.append(f"❌ Generator error: {e}")
        logger.error(f"Generator check failed: {e}")
    
    return issues

def check_api_server():
    """Verificar la configuración del servidor API"""
    logger.info("🌐 Verificando API server...")
    
    issues = []
    
    try:
        from api import app
        logger.info("✅ FastAPI app imported successfully")
        
        # Check if app has required routes
        routes = [route.path for route in app.routes]
        
        required_routes = [
            '/api/pipeline/status',
            '/api/pipeline/execute',
            '/api/predictions/latest'
        ]
        
        for route in required_routes:
            if any(r.startswith(route) for r in routes):
                logger.info(f"  ✅ Route available: {route}")
            else:
                issues.append(f"❌ Missing route: {route}")
                
    except Exception as e:
        issues.append(f"❌ API server error: {e}")
        logger.error(f"API server check failed: {e}")
    
    return issues

async def check_async_functionality():
    """Verificar funcionalidad asíncrona"""
    logger.info("⚡ Verificando funcionalidad async...")
    
    issues = []
    
    try:
        from orchestrator import PipelineOrchestrator
        
        orchestrator = PipelineOrchestrator()
        
        # Test async method existence
        if hasattr(orchestrator, 'run_full_pipeline_async'):
            logger.info("✅ Async pipeline method available")
            
            # Test if it's actually async
            import inspect
            if inspect.iscoroutinefunction(orchestrator.run_full_pipeline_async):
                logger.info("✅ Method is properly async")
            else:
                issues.append("❌ Pipeline method is not async")
        else:
            issues.append("❌ Missing async pipeline method")
            
    except Exception as e:
        issues.append(f"❌ Async functionality error: {e}")
        logger.error(f"Async check failed: {e}")
    
    return issues

def check_configuration():
    """Verificar configuración del sistema"""
    logger.info("⚙️ Verificando configuración...")
    
    issues = []
    
    try:
        config_path = project_root / "config" / "config.ini"
        
        if config_path.exists():
            logger.info("✅ Config file exists")
            
            import configparser
            config = configparser.ConfigParser()
            config.read(config_path)
            
            required_sections = ['paths', 'pipeline', 'weights']
            for section in required_sections:
                if config.has_section(section):
                    logger.info(f"  ✅ Section: {section}")
                else:
                    issues.append(f"❌ Missing config section: {section}")
        else:
            issues.append("❌ Config file not found")
            
    except Exception as e:
        issues.append(f"❌ Configuration error: {e}")
        logger.error(f"Configuration check failed: {e}")
    
    return issues

async def run_comprehensive_validation():
    """Ejecutar validación completa del sistema"""
    logger.info("🚀 SHIOL+ Pipeline Validation v2.0")
    logger.info("=" * 60)
    
    all_issues = []
    
    # Lista de validaciones
    validations = [
        ("Environment Check", check_environment),
        ("Dependencies", check_dependencies),
        ("Database", check_database),
        ("Model Files", check_model_files),
        ("Configuration", check_configuration),
        ("Orchestrator", check_orchestrator),
        ("Predictor", check_predictor),
        ("Intelligent Generator", check_intelligent_generator),
        ("API Server", check_api_server),
        ("Async Functionality", check_async_functionality)
    ]
    
    # Ejecutar validaciones
    for name, validation_func in validations:
        logger.info(f"\n🔍 Ejecutando: {name}")
        try:
            if asyncio.iscoroutinefunction(validation_func):
                issues = await validation_func()
            else:
                issues = validation_func()
                
            if not issues:
                logger.info(f"✅ {name}: PASSED")
            else:
                logger.warning(f"⚠️ {name}: {len(issues)} problemas encontrados")
                for issue in issues:
                    logger.warning(f"  {issue}")
                all_issues.extend(issues)
                
        except Exception as e:
            error_msg = f"❌ {name} validation crashed: {e}"
            logger.error(error_msg)
            all_issues.append(error_msg)
    
    # Resumen final
    logger.info("\n" + "=" * 60)
    logger.info("📊 RESUMEN DE VALIDACIÓN")
    logger.info("=" * 60)
    
    if not all_issues:
        logger.info("🎯 ¡Sistema completamente funcional!")
        logger.info("💡 Todos los componentes validados exitosamente")
        logger.info("🚀 El pipeline está listo para ejecutarse")
        return True
    else:
        logger.warning(f"⚠️ Se encontraron {len(all_issues)} problemas:")
        
        # Categorizar problemas
        critical_issues = [i for i in all_issues if i.startswith("❌")]
        warning_issues = [i for i in all_issues if i.startswith("⚠️")]
        
        if critical_issues:
            logger.error(f"\n🚨 PROBLEMAS CRÍTICOS ({len(critical_issues)}):")
            for i, issue in enumerate(critical_issues, 1):
                logger.error(f"  {i}. {issue}")
        
        if warning_issues:
            logger.warning(f"\n⚠️ ADVERTENCIAS ({len(warning_issues)}):")
            for i, issue in enumerate(warning_issues, 1):
                logger.warning(f"  {i}. {issue}")
        
        # Recomendaciones
        logger.info("\n🔧 RECOMENDACIONES:")
        logger.info("  1. Corrige los problemas críticos primero")
        logger.info("  2. Verifica que todas las dependencias estén instaladas")
        logger.info("  3. Ejecuta: pip install -r requirements.txt")
        logger.info("  4. Reinicia el servidor si es necesario")
        logger.info("  5. Contacta soporte si persisten los problemas")
        
        return len(critical_issues) == 0  # Return True if only warnings

def main():
    """Función principal"""
    try:
        success = asyncio.run(run_comprehensive_validation())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⛔ Validación interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Error fatal durante la validación: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
