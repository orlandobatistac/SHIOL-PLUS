#!/usr/bin/env python3
"""
Script para inicializar las 11 estrategias en strategy_performance
Añade las 5 estrategias ML nuevas con pesos iniciales balanceados
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import sqlite3
from datetime import datetime

def initialize_strategies():
    """Inicializa las 11 estrategias con pesos balanceados"""
    
    db_path = "data/shiolplus.db"
    
    # Las 11 estrategias con sus configuraciones
    strategies = [
        # 6 estrategias originales (ya existen)
        ("frequency_weighted", 0.091, 0.70),
        ("cooccurrence", 0.091, 0.65),
        ("coverage_optimizer", 0.091, 0.60),
        ("range_balanced", 0.091, 0.65),
        ("ai_guided", 0.091, 0.75),
        ("random_baseline", 0.091, 0.50),
        
        # 5 estrategias ML nuevas (PHASE 2)
        ("xgboost_ml", 0.091, 0.85),
        ("random_forest_ml", 0.091, 0.80),
        ("lstm_neural", 0.091, 0.78),
        ("hybrid_ensemble", 0.091, 0.82),
        ("intelligent_scoring", 0.091, 0.75)
    ]
    
    print("🔧 Inicializando 11 estrategias en strategy_performance...\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verificar estado actual
    cursor.execute("SELECT COUNT(*) FROM strategy_performance")
    current_count = cursor.fetchone()[0]
    print(f"📊 Estado actual: {current_count} estrategias en DB")
    
    # Insertar o actualizar estrategias
    for strategy_name, weight, confidence in strategies:
        # Verificar si ya existe
        cursor.execute("SELECT strategy_name FROM strategy_performance WHERE strategy_name = ?", (strategy_name,))
        exists = cursor.fetchone()
        
        if exists:
            # Actualizar peso inicial si es necesario
            cursor.execute("""
                UPDATE strategy_performance 
                SET current_weight = ?, confidence = ?, last_updated = ?
                WHERE strategy_name = ? AND total_plays = 0
            """, (weight, confidence, datetime.now().isoformat(), strategy_name))
            print(f"   ✓ Actualizado: {strategy_name:25} (weight: {weight:.3f}, confidence: {confidence:.2f})")
        else:
            # Insertar nueva estrategia
            cursor.execute("""
                INSERT INTO strategy_performance (
                    strategy_name, total_plays, total_wins, win_rate, roi, 
                    avg_prize, current_weight, confidence, last_updated
                ) VALUES (?, 0, 0, 0.0, 0.0, 0.0, ?, ?, ?)
            """, (strategy_name, weight, confidence, datetime.now().isoformat()))
            print(f"   + Añadido:     {strategy_name:25} (weight: {weight:.3f}, confidence: {confidence:.2f})")
    
    conn.commit()
    
    # Verificar resultado final
    cursor.execute("SELECT COUNT(*) FROM strategy_performance")
    final_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT strategy_name, current_weight, confidence FROM strategy_performance ORDER BY strategy_name")
    all_strategies = cursor.fetchall()
    
    conn.close()
    
    print(f"\n✅ Completado: {final_count} estrategias registradas\n")
    print("📋 Estrategias en base de datos:")
    for name, weight, conf in all_strategies:
        print(f"   {name:25} | weight: {weight:.4f} | confidence: {conf:.2f}")
    
    if final_count == 11:
        print(f"\n🎉 ¡Éxito! Las 11 estrategias están correctamente inicializadas")
        return True
    else:
        print(f"\n⚠️  Advertencia: Se esperaban 11 estrategias, pero hay {final_count}")
        return False

if __name__ == "__main__":
    success = initialize_strategies()
    sys.exit(0 if success else 1)
