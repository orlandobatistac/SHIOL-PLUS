
#!/usr/bin/env python3
"""
Script para vaciar tablas específicas de la base de datos SHIOL+
Utiliza los endpoints de limpieza ya implementados en el sistema.
"""

import sys
import os
import argparse
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import get_db_connection
from loguru import logger
import sqlite3

class DatabaseCleaner:
    """Clase para limpiar tablas específicas de la base de datos"""
    
    def __init__(self):
        self.safe_operations = {
            'predictions': {
                'tables': ['predictions_log'],
                'description': 'Predicciones generadas por el sistema'
            },
            'performance': {
                'tables': ['performance_tracking'],
                'description': 'Datos de rendimiento y tracking'
            },
            'adaptive': {
                'tables': ['adaptive_weights', 'model_feedback', 'reliable_plays'],
                'description': 'Datos del sistema adaptivo y AI models'
            },
            'patterns': {
                'tables': ['pattern_analysis'],
                'description': 'Análisis de patrones'
            },
            'pipeline': {
                'tables': ['pipeline_executions'],
                'description': 'Historial de ejecuciones del pipeline'
            },
            'all_generated': {
                'tables': [
                    'predictions_log', 
                    'performance_tracking', 
                    'adaptive_weights', 
                    'model_feedback', 
                    'reliable_plays',
                    'pattern_analysis',
                    'pipeline_executions'
                ],
                'description': 'Todas las tablas de datos generados (mantiene draws históricos)'
            }
        }
    
    def list_available_options(self):
        """Lista las opciones disponibles para limpiar"""
        print("📋 Opciones disponibles para limpiar:")
        print("=" * 50)
        
        for option, config in self.safe_operations.items():
            print(f"• {option:15} - {config['description']}")
            print(f"  {'':15}   Tablas: {', '.join(config['tables'])}")
            print()
    
    def get_table_counts(self):
        """Obtiene el conteo actual de registros en cada tabla"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                counts = {}
                all_tables = set()
                for config in self.safe_operations.values():
                    all_tables.update(config['tables'])
                
                for table in all_tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        counts[table] = cursor.fetchone()[0]
                    except sqlite3.Error:
                        counts[table] = "N/A"
                
                return counts
                
        except Exception as e:
            logger.error(f"Error obteniendo conteos: {e}")
            return {}
    
    def show_current_status(self):
        """Muestra el estado actual de las tablas"""
        counts = self.get_table_counts()
        
        print("📊 Estado actual de las tablas:")
        print("=" * 40)
        
        for table, count in counts.items():
            status = "🟢 Vacía" if count == 0 else f"🔵 {count:,} registros"
            print(f"{table:20} - {status}")
        print()
    
    def clear_tables(self, option: str, confirm: bool = True):
        """
        Limpia las tablas especificadas por la opción
        
        Args:
            option: Opción de limpieza
            confirm: Si requiere confirmación del usuario
        """
        if option not in self.safe_operations:
            print(f"❌ Opción '{option}' no válida")
            self.list_available_options()
            return False
        
        config = self.safe_operations[option]
        tables_to_clear = config['tables']
        
        print(f"🧹 Preparando limpieza: {config['description']}")
        print(f"📋 Tablas a limpiar: {', '.join(tables_to_clear)}")
        
        if confirm:
            response = input("\n¿Continuar con la limpieza? (s/N): ").lower().strip()
            if response not in ['s', 'si', 'sí', 'y', 'yes']:
                print("❌ Operación cancelada")
                return False
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                total_deleted = 0
                
                for table in tables_to_clear:
                    try:
                        # Obtener conteo antes de borrar
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count_before = cursor.fetchone()[0]
                        
                        # Ejecutar limpieza
                        cursor.execute(f"DELETE FROM {table}")
                        deleted = cursor.rowcount
                        total_deleted += deleted
                        
                        status = "✅" if deleted > 0 else "ℹ️"
                        print(f"{status} {table}: {count_before:,} registros eliminados")
                        
                    except sqlite3.Error as e:
                        print(f"❌ Error limpiando {table}: {e}")
                        continue
                
                conn.commit()
                
                print(f"\n🎉 Limpieza completada exitosamente")
                print(f"📊 Total de registros eliminados: {total_deleted:,}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error durante limpieza: {e}")
            print(f"❌ Error durante limpieza: {e}")
            return False
    
    def reset_complete_system(self, confirm: bool = True):
        """Reseteo completo del sistema (mantiene draws históricos y configuración)"""
        
        print("🚨 RESETEO COMPLETO DEL SISTEMA")
        print("=" * 40)
        print("⚠️  Esto eliminará TODOS los datos generados por el sistema")
        print("✅ Mantendrá: draws históricos (powerball_draws) y configuración")
        print("❌ Eliminará: todas las predicciones, performance, modelos adaptativos, etc.")
        
        if confirm:
            print("\n🛑 Esta operación NO se puede deshacer")
            response = input("Escriba 'RESETEAR SISTEMA' para continuar: ").strip()
            if response != "RESETEAR SISTEMA":
                print("❌ Operación cancelada")
                return False
        
        return self.clear_tables('all_generated', confirm=False)


def main():
    parser = argparse.ArgumentParser(
        description="Script para limpiar tablas específicas de la base de datos SHIOL+"
    )
    
    parser.add_argument(
        'action',
        choices=[
            'list', 'status', 'clear', 'reset-system'
        ],
        help='Acción a realizar'
    )
    
    parser.add_argument(
        '--option',
        choices=[
            'predictions', 'performance', 'adaptive', 'patterns', 
            'pipeline', 'all_generated'
        ],
        help='Opción específica para limpiar (requerido con action=clear)'
    )
    
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='Saltar confirmación (usar con precaución)'
    )
    
    args = parser.parse_args()
    
    cleaner = DatabaseCleaner()
    
    if args.action == 'list':
        cleaner.list_available_options()
    
    elif args.action == 'status':
        cleaner.show_current_status()
    
    elif args.action == 'clear':
        if not args.option:
            print("❌ Error: --option es requerido para action=clear")
            cleaner.list_available_options()
            sys.exit(1)
        
        success = cleaner.clear_tables(args.option, confirm=not args.no_confirm)
        sys.exit(0 if success else 1)
    
    elif args.action == 'reset-system':
        success = cleaner.reset_complete_system(confirm=not args.no_confirm)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    print("🧹 SHIOL+ Database Cleaner")
    print("=" * 30)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Operación interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        sys.exit(1)
