
#!/usr/bin/env python3
"""
Script rápido para limpiar predicciones de la base de datos
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import get_db_connection
from loguru import logger

def clear_predictions():
    """Limpia solo la tabla de predicciones"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Contar antes
            cursor.execute("SELECT COUNT(*) FROM predictions_log")
            count_before = cursor.fetchone()[0]
            
            # Limpiar
            cursor.execute("DELETE FROM predictions_log")
            deleted = cursor.rowcount
            
            conn.commit()
            
            print(f"✅ Eliminadas {deleted:,} predicciones de la base de datos")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def clear_pipeline_executions():
    """Limpia historial de ejecuciones del pipeline"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM pipeline_executions")
            count_before = cursor.fetchone()[0]
            
            cursor.execute("DELETE FROM pipeline_executions")
            deleted = cursor.rowcount
            
            conn.commit()
            
            print(f"✅ Eliminadas {deleted:,} ejecuciones del pipeline")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🧹 Quick Clear - SHIOL+")
    print("Limpiando predicciones y pipeline executions...")
    
    success1 = clear_predictions()
    success2 = clear_pipeline_executions()
    
    if success1 and success2:
        print("🎉 Limpieza completada exitosamente")
    else:
        print("❌ Hubo errores durante la limpieza")
        sys.exit(1)
