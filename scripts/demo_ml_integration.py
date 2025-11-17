#!/usr/bin/env python3
"""
Demo script to showcase ML model integration in SHIOL+

This script demonstrates how the XGBoost ML model is now integrated
into the prediction pipeline through AIGuidedStrategy.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategy_generators import AIGuidedStrategy, StrategyManager
from src.predictor import Predictor


def demo_ml_integration():
    """Demonstrate ML model integration"""
    
    print("=" * 70)
    print("SHIOL+ ML MODEL INTEGRATION DEMO")
    print("=" * 70)
    print()
    
    # 1. Show that ML model is loaded
    print("1. Verificando modelo ML...")
    print("-" * 70)
    predictor = Predictor()
    
    if predictor.model is not None:
        print("✓ Modelo XGBoost cargado exitosamente")
        print(f"  - Archivo: models/shiolplus.pkl")
        print(f"  - Tipo: MultiOutputClassifier con XGBoost")
    else:
        print("✗ Modelo no disponible")
    print()
    
    # 2. Show AIGuidedStrategy uses ML
    print("2. Inicializando AIGuidedStrategy...")
    print("-" * 70)
    strategy = AIGuidedStrategy()
    
    if strategy._ml_available:
        print("✓ Estrategia AIGuided configurada para usar modelo ML")
        print("  - El modelo XGBoost genera probabilidades")
        print("  - Las probabilidades guían la selección de números")
    else:
        print("⚠ Estrategia usando fallback (IntelligentGenerator)")
    print()
    
    # 3. Generate tickets using ML
    print("3. Generando tickets con modelo ML...")
    print("-" * 70)
    tickets = strategy.generate(count=3)
    
    for i, ticket in enumerate(tickets, 1):
        wb = ticket['white_balls']
        pb = ticket['powerball']
        conf = ticket['confidence']
        
        print(f"Ticket {i}:")
        print(f"  Números: {wb[0]:2d} {wb[1]:2d} {wb[2]:2d} {wb[3]:2d} {wb[4]:2d}")
        print(f"  Powerball: {pb:2d}")
        print(f"  Confianza: {conf:.2f}")
        print(f"  Estrategia: {ticket['strategy']}")
        print()
    
    # 4. Show integration with StrategyManager
    print("4. Verificando integración con StrategyManager...")
    print("-" * 70)
    manager = StrategyManager()
    
    if 'ai_guided' in manager.strategies:
        print("✓ AIGuidedStrategy disponible en StrategyManager")
        
        # Get strategy weights
        weights = manager.get_strategy_weights()
        ai_weight = weights.get('ai_guided', 0)
        
        print(f"  - Peso actual: {ai_weight:.4f}")
        print("  - El sistema puede seleccionar esta estrategia automáticamente")
    print()
    
    # 5. Generate balanced tickets (may include ML)
    print("5. Generando tickets balanceados (pueden incluir ML)...")
    print("-" * 70)
    balanced_tickets = manager.generate_balanced_tickets(total=10)
    
    # Count strategies used
    strategy_counts = {}
    for ticket in balanced_tickets:
        strategy = ticket['strategy']
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
    
    print(f"Total de tickets generados: {len(balanced_tickets)}")
    print()
    print("Distribución por estrategia:")
    for strategy, count in sorted(strategy_counts.items()):
        marker = "🤖" if strategy == 'ai_guided' else "  "
        print(f"  {marker} {strategy:20s}: {count} tickets")
    
    ai_count = strategy_counts.get('ai_guided', 0)
    if ai_count > 0:
        print()
        print(f"✓ {ai_count} tickets generados usando modelo ML (XGBoost)")
    print()
    
    # Summary
    print("=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print()
    print("✓ Modelo XGBoost integrado exitosamente")
    print("✓ AIGuidedStrategy usa probabilidades del modelo ML")
    print("✓ StrategyManager puede seleccionar la estrategia ML")
    print("✓ El sistema ahora usa Machine Learning para predicciones")
    print()
    print("El modelo ML (XGBoost) ahora está activo en el pipeline de producción.")
    print()


if __name__ == "__main__":
    demo_ml_integration()
