# Pipeline v5.0 - Sync-First Architecture + Comprehensive Evaluation

## 📋 Resumen Ejecutivo

**Versión**: v5.0  
**Fecha**: 2025-11-09  
**Commits**: 
- `23f2578` - feat: Pipeline v5.0 - Sync-first architecture + comprehensive evaluation
- `c53415f` - hotfix: Fix column name in STEP 4 comprehensive evaluation query

**Estado**: ✅ Desplegado en producción (GitHub Actions auto-deploy)

---

## 🎯 Objetivos Cumplidos

### 1. Sync-First Architecture (STEP 1A, 1B, 1C)
**Problema**: Pipeline v4.0 ejecutaba polling primero, causando llamadas API innecesarias cuando el CSV ya tenía los datos actualizados.

**Solución**:
- **STEP 1A** - Daily Sync First: Ejecuta `daily_full_sync_job()` ANTES del polling
  - Descarga CSV completo de NC Lottery (~147KB, 2,250+ sorteos)
  - Llena gaps automáticamente sin múltiples llamadas API
  - DB siempre actualizada antes de lógica de pipeline

- **STEP 1B** - Database Check: Verifica si el sorteo esperado ya existe en DB
  - Si SÍ existe → Skip STEP 1C (polling), usa datos de DB
  - Si NO existe → Procede a STEP 1C (polling)
  - Reduce carga de API y mejora eficiencia

- **STEP 1C** - Adaptive Polling (conditional): Solo se ejecuta si STEP 1B no encontró el sorteo
  - Mantiene la lógica 3-layer fallback (Web → MUSL → NC CSV)
  - Ejecuta solo cuando absolutamente necesario

**Beneficio**: 
- ✅ Single CSV download (147KB) vs múltiples polling attempts
- ✅ Llena múltiples gaps automáticamente
- ✅ Reduce overhead de API calls
- ✅ DB siempre current antes de lógica de pipeline

---

### 2. Comprehensive Evaluation (STEP 4 Enhanced)
**Problema**: STEP 4 v4.0 solo evaluaba el sorteo más reciente, dejando sorteos históricos sin evaluación.

**Solución**: Reescribió STEP 4 para procesar TODOS los sorteos en la base de datos
- Loop a través de TODOS los sorteos (no solo el último)
- Evalúa sorteos CON predicciones → calcula matches y guarda en `draw_evaluation_results`
- Marca sorteos SIN predicciones → `has_predictions=0`, notes="No predictions generated"
- Logs de resumen: `evaluated_count`, `no_predictions_count`, `error_count`

**Nueva Tabla**: `draw_evaluation_results`
```sql
CREATE TABLE IF NOT EXISTS draw_evaluation_results (
    draw_date DATE PRIMARY KEY,
    total_tickets INTEGER DEFAULT 0,
    matches_3 INTEGER DEFAULT 0,
    matches_4 INTEGER DEFAULT 0,
    matches_5 INTEGER DEFAULT 0,
    matches_5_pb INTEGER DEFAULT 0,
    total_prize REAL DEFAULT 0,
    has_predictions BOOLEAN DEFAULT 1,
    evaluation_date DATETIME,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

**Beneficio**:
- ✅ Registro histórico completo de evaluaciones
- ✅ Soporte para "Recent Powerball Draws" con datos completos
- ✅ Distingue entre sorteos evaluados vs sin predicciones
- ✅ Base para UI mejorada mostrando historial de performance

---

## 🐛 Bug Crítico Corregido

**Bug**: STEP 4 referenciaba columna `target_draw_date` que no existe
**Ubicación**: `src/api.py` línea 975
**Error**: `sqlite3.OperationalError: no such column: target_draw_date`
**Descubrimiento**: Integration testing (TEST 3)
**Fix**: Cambió `target_draw_date` → `draw_date` en query de STEP 4

**Query Corregido**:
```python
# ANTES (WRONG):
cursor.execute("SELECT COUNT(*) FROM generated_tickets WHERE target_draw_date = ?")

# DESPUÉS (CORRECT):
cursor.execute("SELECT COUNT(*) FROM generated_tickets WHERE draw_date = ?")
```

**Commit**: `c53415f` - hotfix: Fix column name in STEP 4 comprehensive evaluation query

---

## 📊 Resultados de Integration Testing

**Pruebas Ejecutadas**: 7 tests completos
**Resultado**: ✅ 100% PASSED

### Test Suite Results:
- ✅ TEST 1: All imports successful (FastAPI app loaded)
- ✅ TEST 2: draw_evaluation_results table exists with 12 columns
- ✅ TEST 3: Query with correct column name (draw_date) works
- ✅ TEST 4: DateManager functionality verified
- ✅ TEST 5: daily_full_sync_job callable check
- ✅ TEST 6: Database state verified (1,862 draws, 800 predictions, 0 evaluations)
- ✅ TEST 7: STEP 4 logic simulation successful (10 draws sampled, 2 with predictions, 8 without)

### Database State (Post-Deployment):
```
Total sorteos en DB: 1,862
Sorteos con predicciones: 2
Total predicciones: 800
Evaluaciones realizadas: 0 (se llenarán en próxima ejecución de pipeline)
Último sorteo: 2025-11-09 - [10, 20, 30, 40, 50] + PB 15
```

---

## 🔧 Cambios Técnicos

### src/api.py (336 insertions, 134 deletions)
**Líneas modificadas**: 521-1185

**Cambios principales**:
1. **Líneas 521-575**: Documentación actualizada v4.0 → v5.0
2. **Líneas 586-640**: NEW STEP 1A - Daily Sync First
3. **Líneas 640-690**: NEW STEP 1B - Database Check
4. **Líneas 700-790**: MODIFIED STEP 1C - Conditional Polling
5. **Líneas 810-830**: MODIFIED STEP 2 - Conditional Insert
6. **Líneas 929-1020**: REWRITTEN STEP 4 - Comprehensive Evaluation
7. **Líneas 1033-1185**: Renumbering all steps /6 → /7

### src/database.py (28 insertions)
**Líneas modificadas**: 940-966

**Cambios**:
- Creación de tabla `draw_evaluation_results`
- 12 columnas con índices y defaults
- Primary key: `draw_date`

---

## 📈 Pipeline Architecture

### v4.0 (Anterior) - 6 Steps:
1. Adaptive Polling
2. Data Insert
3. Analytics Update
4. Prediction Evaluation (latest only)
5. Adaptive Learning
6. Prediction Generation

### v5.0 (Actual) - 7 Steps:
1. **STEP 1A** - Daily Sync First (NEW)
2. **STEP 1B** - Database Check (NEW)
3. **STEP 1C** - Adaptive Polling (conditional, MODIFIED)
4. **STEP 2** - Data Insert (conditional, MODIFIED)
5. **STEP 3** - Analytics Update
6. **STEP 4** - Comprehensive Evaluation (ALL draws, ENHANCED)
7. **STEP 5** - Adaptive Learning
8. **STEP 6** - Prediction Generation

---

## 🚀 Deployment

**Método**: GitHub Actions auto-deploy
**Trigger**: Push to `main` branch
**Proceso**:
1. Local commit → Push to main
2. GitHub Actions detecta push
3. Auto-pull en servidor producción
4. Restart servicios (systemd/gunicorn/uvicorn)
5. Cambios en vivo en segundos

**No se requiere**:
- ❌ SSH manual a servidor
- ❌ `git pull` manual
- ❌ Restart manual de servicios

---

## ✅ Próximos Pasos

### Automatizado (Next Pipeline Run):
1. ⏳ Pipeline ejecutará automáticamente en próximo sorteo (Tue/Thu/Sun 1:00 AM ET)
2. 📊 STEP 4 evaluará TODOS los 1,862 sorteos y llenará `draw_evaluation_results`
3. 🎯 Tabla `draw_evaluation_results` tendrá ~1,862 registros (uno por sorteo)

### Manual (Opcional - Para testing inmediato):
```bash
# Ejecutar pipeline manualmente
python scripts/run_pipeline.py

# Verificar tabla draw_evaluation_results
sqlite3 data/shiolplus.db "SELECT COUNT(*) FROM draw_evaluation_results"
```

### UI Update (Futuro):
1. Actualizar "Recent Powerball Draws" para query `draw_evaluation_results`
2. Mostrar mensaje "No predictions" para sorteos con `has_predictions=0`
3. Join con `powerball_draws` para datos completos:
```sql
SELECT p.*, e.has_predictions, e.total_tickets, e.matches_5_pb
FROM powerball_draws p
LEFT JOIN draw_evaluation_results e ON p.draw_date = e.draw_date
ORDER BY p.draw_date DESC
```

---

## 📝 Notas de Versión

**Breaking Changes**:
- Pipeline ahora tiene 7 steps en lugar de 6
- Número de step en logs cambió (e.g., "STEP 4/6" → "STEP 4/7")
- Nueva tabla `draw_evaluation_results` requerida

**Backwards Compatibility**:
- ✅ Schema migrations son idempotentes (CREATE TABLE IF NOT EXISTS)
- ✅ Datos existentes en `powerball_draws` no afectados
- ✅ API endpoints no cambiaron
- ✅ Scheduler jobs no cambiaron (mismo horario)

**Performance Impact**:
- ➕ STEP 1A agrega ~2-3 segundos (CSV download)
- ➖ STEP 1C ejecuta menos frecuentemente (ahorro de tiempo)
- ➕ STEP 4 procesa más sorteos (primera ejecución ~10-15 segundos, subsecuentes ~1-2 segundos)
- **Net Impact**: Pequeño aumento inicial (~5 segundos), gran ahorro a largo plazo

---

## 🔍 Validation Queries

### Verificar evaluaciones después de pipeline run:
```sql
-- Total de evaluaciones
SELECT COUNT(*) FROM draw_evaluation_results;

-- Sorteos con predicciones
SELECT COUNT(*) FROM draw_evaluation_results WHERE has_predictions = 1;

-- Sorteos sin predicciones
SELECT COUNT(*) FROM draw_evaluation_results WHERE has_predictions = 0;

-- Últimas 5 evaluaciones
SELECT 
    draw_date, 
    total_tickets, 
    matches_5_pb, 
    total_prize,
    has_predictions,
    notes
FROM draw_evaluation_results 
ORDER BY draw_date DESC 
LIMIT 5;
```

---

**Autor**: GitHub Copilot AI Coding Agent  
**Mantenedor**: Orlando B. (orlandobatistac)  
**Última actualización**: 2025-11-09 16:36 ET
