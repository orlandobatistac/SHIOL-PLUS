#!/usr/bin/env python3
"""
Diagnostic script to measure performance of the hot/cold numbers endpoint.
Identifies bottlenecks in the analytics overview calculation.

Usage:
    python scripts/diagnose_hot_cold_endpoint.py
"""

import time
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger


def measure_time(func_name: str):
    """Decorator to measure function execution time"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            print(f"  ⏱️  {func_name}: {elapsed_ms:.2f}ms")
            return result, elapsed_ms
        return wrapper
    return decorator


def diagnose_analytics_endpoint():
    """Run detailed performance diagnosis on the analytics endpoint"""

    print("\n" + "=" * 60)
    print("🔍 DIAGNOSTICO DE RENDIMIENTO: /api/v3/analytics/overview")
    print("=" * 60 + "\n")

    timings = {}
    total_start = time.perf_counter()

    # ============================================================
    # STEP 1: Database - Get All Draws
    # ============================================================
    print("📊 PASO 1: Carga de datos históricos desde SQLite")
    print("-" * 50)

    start = time.perf_counter()
    try:
        from src.database import get_all_draws
        draws_df = get_all_draws()
        elapsed = (time.perf_counter() - start) * 1000
        timings['db_get_all_draws'] = elapsed
        print(f"  ⏱️  get_all_draws(): {elapsed:.2f}ms")
        print(f"  📈 Filas cargadas: {len(draws_df)}")
        print(f"  📋 Columnas: {list(draws_df.columns)}")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return

    if draws_df.empty:
        print("  ⚠️  No hay datos en la base de datos!")
        return

    print()

    # ============================================================
    # STEP 2: Initialize Analysis Components
    # ============================================================
    print("🧠 PASO 2: Inicialización de componentes de análisis")
    print("-" * 50)

    start = time.perf_counter()
    from src.v2.statistical_core import (
        TemporalDecayModel,
        MomentumAnalyzer,
        GapAnalyzer,
        PatternEngine
    )
    elapsed = (time.perf_counter() - start) * 1000
    timings['import_modules'] = elapsed
    print(f"  ⏱️  Import modules: {elapsed:.2f}ms")

    start = time.perf_counter()
    temporal_model = TemporalDecayModel(decay_factor=0.05)
    elapsed = (time.perf_counter() - start) * 1000
    timings['init_temporal_model'] = elapsed
    print(f"  ⏱️  TemporalDecayModel.__init__(): {elapsed:.2f}ms")

    start = time.perf_counter()
    momentum_analyzer = MomentumAnalyzer(short_window=10, long_window=50)
    elapsed = (time.perf_counter() - start) * 1000
    timings['init_momentum'] = elapsed
    print(f"  ⏱️  MomentumAnalyzer.__init__(): {elapsed:.2f}ms")

    start = time.perf_counter()
    gap_analyzer = GapAnalyzer()
    elapsed = (time.perf_counter() - start) * 1000
    timings['init_gap'] = elapsed
    print(f"  ⏱️  GapAnalyzer.__init__(): {elapsed:.2f}ms")

    start = time.perf_counter()
    pattern_engine = PatternEngine()
    elapsed = (time.perf_counter() - start) * 1000
    timings['init_pattern'] = elapsed
    print(f"  ⏱️  PatternEngine.__init__(): {elapsed:.2f}ms")

    print()

    # ============================================================
    # STEP 3: Perform Analysis (THE HEAVY LIFTING)
    # ============================================================
    print("🔬 PASO 3: Ejecución de análisis (CÁLCULOS PESADOS)")
    print("-" * 50)

    start = time.perf_counter()
    weights = temporal_model.calculate_weights(draws_df)
    elapsed = (time.perf_counter() - start) * 1000
    timings['temporal_weights'] = elapsed
    print(f"  ⏱️  temporal_model.calculate_weights(): {elapsed:.2f}ms")
    print(f"      → Window size: {weights.window_size} draws")

    start = time.perf_counter()
    momentum = momentum_analyzer.analyze(draws_df)
    elapsed = (time.perf_counter() - start) * 1000
    timings['momentum_analysis'] = elapsed
    print(f"  ⏱️  momentum_analyzer.analyze(): {elapsed:.2f}ms")

    start = time.perf_counter()
    gaps = gap_analyzer.analyze(draws_df)
    elapsed = (time.perf_counter() - start) * 1000
    timings['gap_analysis'] = elapsed
    print(f"  ⏱️  gap_analyzer.analyze(): {elapsed:.2f}ms")

    start = time.perf_counter()
    patterns = pattern_engine.analyze(draws_df)
    elapsed = (time.perf_counter() - start) * 1000
    timings['pattern_analysis'] = elapsed
    print(f"  ⏱️  pattern_engine.analyze(): {elapsed:.2f}ms")

    print()

    # ============================================================
    # STEP 4: Build Response Objects
    # ============================================================
    print("📦 PASO 4: Construcción de objetos de respuesta")
    print("-" * 50)

    import numpy as np
    from src.v2.analytics_api import (
        HotColdNumbers,
        MomentumReport,
        GapReport,
        PatternStats
    )

    start = time.perf_counter()
    # Hot/cold analysis
    wb_indices = np.argsort(weights.white_ball_weights)
    pb_indices = np.argsort(weights.powerball_weights)
    hot_wb = [int(i + 1) for i in wb_indices[-10:][::-1]]
    cold_wb = [int(i + 1) for i in wb_indices[:10]]
    hot_pb = [int(i + 1) for i in pb_indices[-5:][::-1]]
    cold_pb = [int(i + 1) for i in pb_indices[:5]]
    elapsed = (time.perf_counter() - start) * 1000
    timings['build_hot_cold'] = elapsed
    print(f"  ⏱️  Build hot/cold analysis: {elapsed:.2f}ms")
    print(f"      → Hot white balls: {hot_wb[:5]}")
    print(f"      → Cold white balls: {cold_wb[:5]}")

    print()

    # ============================================================
    # STEP 5: Co-occurrences from Database
    # ============================================================
    print("🔗 PASO 5: Obtener co-ocurrencias desde DB")
    print("-" * 50)

    start = time.perf_counter()
    from src.database import get_db_connection
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT number_a, number_b, count, deviation_pct
            FROM cooccurrences
            WHERE is_significant = TRUE
            ORDER BY deviation_pct DESC
            LIMIT 10
        """)
        cooccurrences = cursor.fetchall()
        conn.close()
        elapsed = (time.perf_counter() - start) * 1000
        timings['get_cooccurrences'] = elapsed
        print(f"  ⏱️  Query cooccurrences: {elapsed:.2f}ms")
        print(f"      → Pairs found: {len(cooccurrences)}")
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        timings['get_cooccurrences'] = elapsed
        print(f"  ⚠️  Cooccurrences query failed: {e} ({elapsed:.2f}ms)")

    print()

    # ============================================================
    # SUMMARY
    # ============================================================
    total_elapsed = (time.perf_counter() - total_start) * 1000

    print("=" * 60)
    print("📊 RESUMEN DE RENDIMIENTO")
    print("=" * 60)

    # Sort by time descending
    sorted_timings = sorted(timings.items(), key=lambda x: x[1], reverse=True)

    print("\n🔴 TOP CUELLOS DE BOTELLA (ordenado por tiempo):")
    print("-" * 50)
    for name, elapsed in sorted_timings:
        pct = (elapsed / total_elapsed) * 100
        bar_len = int(pct / 2)
        bar = "█" * bar_len
        status = "🔴" if elapsed > 100 else "🟡" if elapsed > 50 else "🟢"
        print(f"  {status} {name:30s} {elapsed:8.2f}ms ({pct:5.1f}%) {bar}")

    print("\n" + "-" * 50)
    print(f"⏱️  TIEMPO TOTAL: {total_elapsed:.2f}ms")

    if total_elapsed > 500:
        print("🔴 LENTO: Más de 500ms - Necesita optimización")
    elif total_elapsed > 200:
        print("🟡 MODERADO: Entre 200-500ms - Considerar cache")
    else:
        print("🟢 RÁPIDO: Menos de 200ms - Buen rendimiento")

    print("\n" + "=" * 60)
    print("💡 RECOMENDACIONES:")
    print("=" * 60)

    # Analyze bottlenecks
    if timings.get('db_get_all_draws', 0) > 100:
        print("  1. 📊 get_all_draws() es lento → Considerar LIMIT o cache")
        print("     - Usar cache en memoria con TTL de 5 minutos")
        print("     - O calcular solo sobre últimos 200 draws")

    if timings.get('temporal_weights', 0) > 100:
        print("  2. 🧮 Cálculo temporal es pesado → Pre-calcular en pipeline")
        print("     - Guardar hot/cold en tabla analytics_cache")
        print("     - Actualizar solo después de cada sorteo")

    if timings.get('momentum_analysis', 0) > 100:
        print("  3. 📈 Análisis de momentum costoso → Simplificar algoritmo")

    if timings.get('gap_analysis', 0) > 100:
        print("  4. 📉 Gap analysis costoso → Optimizar numpy ops")

    if total_elapsed > 200:
        print("\n  🚀 SOLUCIÓN RECOMENDADA: Implementar cache con TTL")
        print("     - Los datos solo cambian 3 veces por semana (Lun/Mie/Sab)")
        print("     - Cache de 5-10 minutos elimina 99% del trabajo")

    print()


def test_cache_performance():
    """Test the cache implementation performance"""

    print("\n" + "=" * 60)
    print("🧪 TEST DE RENDIMIENTO CON CACHE")
    print("=" * 60 + "\n")

    from src.v2.analytics_api import (
        get_analytics_overview,
        invalidate_analytics_cache,
        _is_cache_valid
    )
    import asyncio

    # Invalidate cache first
    print("1️⃣  Invalidando cache...")
    invalidate_analytics_cache()
    print(f"   Cache válido: {_is_cache_valid()}")

    # First call - should calculate
    print("\n2️⃣  Primera llamada (cálculo completo)...")
    start = time.perf_counter()
    result1 = asyncio.run(get_analytics_overview())
    time1 = (time.perf_counter() - start) * 1000
    print(f"   ⏱️  Tiempo: {time1:.2f}ms")
    print(f"   📊 from_cache: {result1.from_cache}")
    print(f"   📊 calculation_time_ms: {result1.calculation_time_ms}")
    print(f"   📊 Hot numbers: {result1.hot_cold.hot_numbers[:5]}")

    # Second call - should use cache
    print("\n3️⃣  Segunda llamada (desde cache)...")
    start = time.perf_counter()
    result2 = asyncio.run(get_analytics_overview())
    time2 = (time.perf_counter() - start) * 1000
    print(f"   ⏱️  Tiempo: {time2:.2f}ms")
    print(f"   📊 from_cache: {result2.from_cache}")
    print(f"   📊 cache_age_seconds: {result2.cache_age_seconds}")

    # Third call - also from cache
    print("\n4️⃣  Tercera llamada (desde cache)...")
    start = time.perf_counter()
    result3 = asyncio.run(get_analytics_overview())
    time3 = (time.perf_counter() - start) * 1000
    print(f"   ⏱️  Tiempo: {time3:.2f}ms")
    print(f"   📊 from_cache: {result3.from_cache}")
    print(f"   📊 cache_age_seconds: {result3.cache_age_seconds}")

    # Summary
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE RENDIMIENTO CON CACHE")
    print("=" * 60)
    print(f"\n  Primera llamada (sin cache): {time1:,.2f}ms")
    print(f"  Segunda llamada (con cache): {time2:,.2f}ms")
    print(f"  Tercera llamada (con cache): {time3:,.2f}ms")

    speedup = time1 / time2 if time2 > 0 else 0
    print(f"\n  🚀 MEJORA DE RENDIMIENTO: {speedup:,.0f}x más rápido")
    print(f"  💾 Ahorro por request cacheado: {time1 - time2:,.2f}ms")

    if time2 < 10:
        print("\n  ✅ CACHE FUNCIONANDO CORRECTAMENTE")
        print("     Requests cacheados responden en <10ms")
    else:
        print("\n  ⚠️  Cache puede necesitar ajustes")

    print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--cache":
        test_cache_performance()
    else:
        diagnose_analytics_endpoint()
        print("\n" + "-" * 60)
        print("💡 Para probar el cache ejecuta:")
        print("   python scripts/diagnose_hot_cold_endpoint.py --cache")
        print("-" * 60 + "\n")
