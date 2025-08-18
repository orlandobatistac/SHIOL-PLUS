
# Plan de Unificación de Pipelines SHIOL+ - RESOLUCIÓN CRÍTICA

## 🚨 OBJETIVO CRÍTICO
**Eliminar la dualidad de pipelines que está comprometiendo la consistencia y confiabilidad del sistema.**

## 📋 DECISIÓN ESTRATÉGICA: Pipeline Main como Único

**SELECCIÓN**: `main.py` (6 pasos) como pipeline único y oficial
**RAZÓN**: Mayor granularidad, mejor control, logging detallado, y es el que actualmente ejecuta el scheduler

## 🗂️ FASE 1: PREPARACIÓN (1-2 días)

### 1.1 Backup Crítico
- ✅ Respaldar `src/orchestrator.py` como `src/orchestrator_deprecated.py`
- ✅ Documentar funcionalidades únicas del orchestrator que deben migrarse
- ✅ Backup completo de la base de datos

### 1.2 Análisis de Funcionalidades Únicas
**Funcionalidades del Orchestrator a migrar:**
- Manejo async optimizado
- Ejecución por lotes (batch processing)
- Mejor manejo de timeouts
- Tracking de estado más detallado

## 🔄 FASE 2: MIGRACIÓN DE FUNCIONALIDADES (3-4 días)

### 2.1 Mejorar `main.py` con Features del Orchestrator

#### A. Agregar Execution Tracking Avanzado
```python
# Migrar a main.py
self.steps_completed = 0
self.current_step = ""
async def _update_execution_status(self):
    """Migrado desde orchestrator.py"""
```

#### B. Optimizar Timeouts y Resource Management
```python
# Migrar sistema de timeouts del orchestrator
signal.alarm(1800)  # 30 min timeout (vs 15 min actual)
```

#### C. Mejorar Batch Processing
```python
# Migrar generación por lotes del orchestrator
batch_size = 50  # Lotes más grandes
```

### 2.2 Unificar Execution IDs
**CAMBIO CRÍTICO**: Estandarizar formato de execution_id
```python
# ANTES (Inconsistente):
# main.py: f"main_{str(uuid.uuid4())[:8]}"
# orchestrator.py: f"orch_{str(uuid.uuid4())[:8]}"

# DESPUÉS (Unificado):
execution_id = f"exec_{str(uuid.uuid4())[:8]}"
```

## 🗑️ FASE 3: DEPRECACIÓN GRADUAL (2-3 días)

### 3.1 Modificar API para Usar Solo Main.py
**ARCHIVO**: `src/api_pipeline_endpoints.py`
```python
# CAMBIO CRÍTICO: Eliminar referencias al orchestrator
# Todas las llamadas deben ir a main.py subprocess
```

### 3.2 Actualizar Scheduler
**ARCHIVO**: `src/api.py`
```python
# Asegurar que scheduler SOLO ejecute main.py
cmd = ["python", "main.py"]  # ÚNICO PUNTO DE EJECUCIÓN
```

### 3.3 Añadir Warnings de Deprecación
```python
# En src/orchestrator.py (temporal)
@deprecated("Use main.py pipeline instead")
def run_full_pipeline_async():
    logger.warning("DEPRECATED: orchestrator.py pipeline. Use main.py instead")
```

## 🔧 FASE 4: OPTIMIZACIÓN DEL PIPELINE UNIFICADO (2-3 días)

### 4.1 Mejorar Performance en Main.py
- Implementar async donde sea beneficioso
- Optimizar generación de predicciones
- Mejorar manejo de memoria

### 4.2 Estandarizar Logging
```python
# Formato único de logging para todo el pipeline
logger.info(f"STEP {step_num}/6: {step_name} - Status: {status}")
```

### 4.3 Unified Database Schema
```sql
-- Asegurar que todos los registros usen el mismo formato
ALTER TABLE pipeline_executions ADD COLUMN pipeline_version TEXT DEFAULT 'unified_v1.0';
```

## 🧪 FASE 5: TESTING Y VALIDACIÓN (2 días)

### 5.1 Tests de Integración
- Validar que el pipeline unificado produce resultados consistentes
- Probar ejecuciones desde scheduler, API y CLI
- Verificar backward compatibility

### 5.2 Performance Benchmarking
- Comparar tiempos de ejecución
- Validar uso de recursos
- Asegurar que no hay degradación

## 🚀 FASE 6: DESPLIEGUE Y LIMPIEZA (1 día)

### 6.1 Deployment Final
- Remover `src/orchestrator.py` completamente
- Limpiar imports y referencias
- Actualizar documentación

### 6.2 Monitoring Post-Despliegue
- Monitorear primeras 24 horas
- Validar métricas de performance
- Verificar consistencia de resultados

## 📊 CRONOGRAMA TOTAL: 10-15 días

```
Día 1-2:   FASE 1 (Preparación)
Día 3-6:   FASE 2 (Migración)
Día 7-9:   FASE 3 (Deprecación)
Día 10-12: FASE 4 (Optimización)
Día 13-14: FASE 5 (Testing)
Día 15:    FASE 6 (Despliegue)
```

## 🎯 RESULTADOS ESPERADOS

### ✅ Problemas Resueltos
1. **Consistencia Garantizada**: Un solo pipeline = resultados consistentes
2. **Debugging Simplificado**: Un solo flujo de código
3. **Mantenimiento Reducido**: Una sola implementación
4. **Confusion Eliminada**: Claridad total sobre qué se ejecuta cuándo

### 📈 Mejoras de Performance
- Timeout optimizado: 30 min (vs 15 min actual)
- Batch processing mejorado
- Resource management más eficiente
- Logging unificado y más detallado

## 🚨 RIESGOS Y MITIGACIONES

### Riesgo 1: Pérdida de Performance del Orchestrator
**Mitigación**: Migrar todas las optimizaciones antes de deprecar

### Riesgo 2: Interrupciones en Producción
**Mitigación**: Deployment gradual con rollback plan

### Riesgo 3: Compatibility Issues
**Mitigación**: Extensive testing en environment separado

## 🔍 MONITOREO POST-UNIFICACIÓN

### KPIs a Monitorear:
1. **Execution Time**: Debe mantenerse o mejorar
2. **Success Rate**: Debe ser >= 95%
3. **Consistency**: 100% de resultados consistentes
4. **Resource Usage**: Uso eficiente de memoria/CPU

### Alertas Críticas:
- Pipeline failure > 2 veces consecutivas
- Execution time > 35 minutos
- Memory usage > 90%
- Inconsistent results detected

## 📝 CHECKLIST DE IMPLEMENTACIÓN

### Preparación
- [ ] Backup completo del sistema
- [ ] Documentar estado actual
- [ ] Crear environment de testing

### Migración
- [ ] Migrar execution tracking
- [ ] Migrar batch processing
- [ ] Migrar timeout management
- [ ] Unificar execution IDs

### Deprecación
- [ ] Actualizar API endpoints
- [ ] Modificar scheduler
- [ ] Añadir deprecation warnings
- [ ] Actualizar documentación

### Testing
- [ ] Tests de integración
- [ ] Performance benchmarks
- [ ] Consistency validation
- [ ] Error handling verification

### Deployment
- [ ] Remove orchestrator.py
- [ ] Clean imports
- [ ] Update documentation
- [ ] Monitor 24h post-deployment

## 🎉 CONCLUSIÓN

Esta unificación resolverá completamente la **crisis arquitectural** identificada, garantizando:
- ✅ **Consistencia Total** en resultados
- ✅ **Confiabilidad Operacional** mejorada
- ✅ **Mantenibilidad** simplificada
- ✅ **Performance** optimizado
- ✅ **Experiencia de Usuario** unificada

**ACCIÓN INMEDIATA REQUERIDA**: Aprobar este plan e iniciar FASE 1 inmediatamente.
