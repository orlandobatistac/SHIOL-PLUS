# ML Model Integration - November 2025

## Summary

El modelo de Machine Learning (XGBoost) ahora está **activamente integrado** en el pipeline de predicciones de SHIOL+ a través de la estrategia `AIGuidedStrategy`.

## Cambios Realizados

### 1. Código Modificado

**`src/strategy_generators.py`** - Clase `AIGuidedStrategy`
- ✅ Reescrita completamente para usar el modelo XGBoost
- ✅ Método `_initialize_ml_predictor()` carga el modelo desde `models/shiolplus.pkl`
- ✅ Método `generate()` obtiene probabilidades del modelo ML
- ✅ Usa `np.random.choice()` con probabilidades ML para seleccionar números
- ✅ Fallback automático a IntelligentGenerator si el modelo no está disponible
- ✅ Confianza aumentada a 0.85 cuando usa ML (vs 0.70 con frecuencias)

### 2. Tests Agregados

**`tests/test_ml_integration.py`** - Suite de tests comprehensiva
- ✅ Test 1: Verifica que AIGuidedStrategy usa modelo ML
- ✅ Test 2: Verifica inicialización de Predictor
- ✅ Test 3: Verifica generación de probabilidades ML
- ✅ Test 4: Verifica integración con StrategyManager
- ✅ Test 5: Verifica generación de tickets balanceados con ML

**Resultado:** Todos los tests pasan ✓

### 3. Script de Demo

**`scripts/demo_ml_integration.py`** - Demostración interactiva
- Muestra que el modelo XGBoost está cargado
- Genera tickets usando probabilidades ML
- Compara con otras estrategias
- Demuestra integración con StrategyManager

### 4. Documentación Actualizada

**`docs/TECHNICAL.md`** - Secciones actualizadas:
- Sección 4.6: AIGuidedStrategy ahora documenta uso de ML
- Sección 11.3: Arquitectura ML detallada
- Sección 11.7: Improvement 1 marcado como COMPLETADO
- Diagrama de flujo actualizado con "ML-POWERED"

## Arquitectura del Sistema ML

```
User Request
    ↓
StrategyManager.generate_balanced_tickets()
    ↓
AIGuidedStrategy.generate() [Peso: 1/6]
    ↓
Predictor.predict_probabilities()
    ↓
ModelTrainer.predict_probabilities()
    ↓
XGBoost MultiOutputClassifier
    ├─ Input: 15 features engineered
    ├─ Processing: 95 binary classifiers (69 WB + 26 PB)
    └─ Output: Probability distributions
        ↓
np.random.choice(range(1,70), p=wb_probs)  # White balls
np.random.choice(range(1,27), p=pb_probs)  # Powerball
    ↓
Ticket generado con confianza 0.85
```

## Detalles Técnicos del Modelo

### Archivo del Modelo
- **Ubicación**: `models/shiolplus.pkl`
- **Tamaño**: 18.2 MB
- **Tipo**: `sklearn.multioutput.MultiOutputClassifier`
- **Estimador base**: XGBoost binary classifier
- **Número de estimadores**: 95 (uno por cada target)

### Features (15 total)
1. `even_count` - Cantidad de números pares
2. `odd_count` - Cantidad de números impares
3. `sum` - Suma total de números
4. `spread` - Rango (max - min)
5. `consecutive_count` - Números consecutivos
6. `avg_delay` - Retraso promedio desde última aparición
7. `max_delay` - Retraso máximo
8. `min_delay` - Retraso mínimo
9. `dist_to_recent` - Distancia a sorteos recientes
10. `avg_dist_to_top_n` - Distancia a números frecuentes
11. `dist_to_centroid` - Distancia al centroide
12. `time_weight` - Peso temporal
13. `increasing_trend_count` - Tendencia creciente
14. `decreasing_trend_count` - Tendencia decreciente
15. `stable_trend_count` - Tendencia estable

### Targets (95 total)
- 69 binarios para white balls (wb_1 a wb_69)
- 26 binarios para powerball (pb_1 a pb_26)

### Proceso de Predicción

1. **Feature Engineering**: Se generan 15 features desde datos históricos
2. **Inferencia**: Modelo predice probabilidad para cada número (0-1)
3. **Normalización**: Probabilidades se normalizan para sumar 1.0
4. **Muestreo**: Se usan las probabilidades para selección guiada por ML

## Cómo Usar

### Generar Tickets con ML

```python
from src.strategy_generators import AIGuidedStrategy

# Inicializar estrategia (carga modelo automáticamente)
strategy = AIGuidedStrategy()

# Verificar si ML está disponible
if strategy._ml_available:
    print("✓ Modelo ML cargado")
else:
    print("⚠ Usando fallback (IntelligentGenerator)")

# Generar tickets con ML
tickets = strategy.generate(count=5)

for ticket in tickets:
    print(f"Números: {ticket['white_balls']}")
    print(f"Powerball: {ticket['powerball']}")
    print(f"Confianza: {ticket['confidence']}")
```

### Usar con StrategyManager

```python
from src.strategy_generators import StrategyManager

# StrategyManager ya incluye AIGuidedStrategy
manager = StrategyManager()

# Generar tickets balanceados (puede incluir ML)
tickets = manager.generate_balanced_tickets(total=10)

# Verificar cuántos usan ML
ml_tickets = [t for t in tickets if t['strategy'] == 'ai_guided']
print(f"{len(ml_tickets)} tickets generados con modelo ML")
```

### Ejecutar Demo

```bash
python scripts/demo_ml_integration.py
```

### Ejecutar Tests

```bash
python tests/test_ml_integration.py
```

## Resultados de Tests

```
Test 1: AIGuidedStrategy uses ML model
✓ PASSED

Test 2: ML Predictor initialization
✓ PASSED

Test 3: ML model generates probabilities
✓ PASSED

Test 4: StrategyManager includes ML
✓ PASSED

Test 5: Balanced tickets can use ML
✓ PASSED

All tests passed! ✓
```

## Ejemplo de Salida

```
======================================================================
SHIOL+ ML MODEL INTEGRATION DEMO
======================================================================

1. Verificando modelo ML...
----------------------------------------------------------------------
✓ Modelo XGBoost cargado exitosamente
  - Archivo: models/shiolplus.pkl
  - Tipo: MultiOutputClassifier con XGBoost

3. Generando tickets con modelo ML...
----------------------------------------------------------------------
Ticket 1:
  Números: 11 26 42 51 66
  Powerball:  5
  Confianza: 0.85
  Estrategia: ai_guided

5. Generando tickets balanceados (pueden incluir ML)...
----------------------------------------------------------------------
Total de tickets generados: 10

Distribución por estrategia:
  🤖 ai_guided           : 2 tickets  ← Usando ML!
     frequency_weighted  : 3 tickets
     random_baseline     : 2 tickets
     range_balanced      : 2 tickets
     cooccurrence        : 1 tickets

✓ 2 tickets generados usando modelo ML (XGBoost)
```

## Comparación: Antes vs Ahora

### Antes (hasta Octubre 2025)
```
AIGuidedStrategy
  └─> IntelligentGenerator
      └─> Análisis de frecuencia simple
      └─> Confianza: 0.70
      └─> NO usa modelo XGBoost
```

### Ahora (Noviembre 2025)
```
AIGuidedStrategy
  └─> Predictor.predict_probabilities()
      └─> XGBoost ML Model ✓
      └─> 15 features engineered
      └─> 95 probability outputs
      └─> Confianza: 0.85
  └─> Fallback: IntelligentGenerator (si ML no disponible)
      └─> Confianza: 0.70
```

## Impacto en Producción

### Estrategias Disponibles (6 total)
1. **frequency_weighted** - Frecuencia con pesos
2. **cooccurrence** - Pares frecuentes
3. **coverage_optimizer** - Cobertura de números
4. **range_balanced** - Distribución balanceada
5. **ai_guided** - 🤖 **ML-POWERED con XGBoost** ✓
6. **random_baseline** - Control aleatorio

### Sistema Adaptativo
- StrategyManager selecciona estrategias según `current_weight`
- AIGuidedStrategy tiene peso inicial 1/6 (0.1667)
- El sistema adaptativo ajusta pesos según performance
- ML puede ganar más peso si tiene mejor ROI

## Próximos Pasos Sugeridos

1. **Monitoreo**: Rastrear performance de ai_guided vs otras estrategias
2. **Reentrenamiento**: Proceso para reentrenar modelo con nuevos datos
3. **A/B Testing**: Comparar resultados ML vs frecuencias simples
4. **Optimización**: Ajustar hiperparámetros del modelo si es necesario
5. **Métricas**: Dashboard para visualizar uso y performance del ML

## Notas Importantes

⚠️ **Disclaimer**: El sistema de lotería Powerball es fundamentalmente aleatorio. El modelo ML proporciona selección informada por patrones históricos, pero **no puede predecir resultados futuros** con certeza. El ML mejora la diversidad y sofisticación de las predicciones, no garantiza victorias.

✅ **Buenas Prácticas**: El modelo se usa como una de 6 estrategias en un portfolio balanceado, lo cual es la mejor práctica para sistemas de predicción en contextos aleatorios.

---

**Autor**: GitHub Copilot + Orlando B.  
**Fecha**: Noviembre 2025  
**Versión**: SHIOL+ v6.5+
