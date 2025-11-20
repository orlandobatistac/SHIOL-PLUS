# SHIOL+ Project Status & Roadmap

**Date:** 2025-11-19  
**Project:** SHIOL-PLUS v8.0  
**Status:** Production - Strategic Realignment in Progress 🎯  
**Vision:** Pipeline-centric adaptive learning system with multi-strategy evaluation

---

## 🎯 PROJECT VISION & PRIORITIES

### Core Mission

SHIOL+ es un **motor de predicciones con aprendizaje adaptativo** que evalúa continuamente el rendimiento de múltiples estrategias de generación de tickets de lotería, ajustando automáticamente sus pesos según ROI real.

### Strategic Priorities (Orden de Importancia)

1. **🧠 Pipeline como Cerebro del Sistema (PRIORIDAD #1)**

   - Generar 200 predicciones evaluables por sorteo (3x semana)
   - Expandir de 6 a 11 estrategias (añadir modelos ML del batch)
   - Adaptive learning automático basado en performance real
   - Métricas de ROI y win_rate por estrategia
   - Frontend sirve ESTAS predicciones a usuarios internos

2. **🌐 API para Proyecto Externo (PRIORIDAD #2)**

   - Endpoint simple que sirve las predicciones del pipeline
   - NO generar predicciones adicionales (reutilizar pipeline)
   - Filtros por estrategia, confianza, cantidad
   - Performance: <10ms (lectura de DB)
   - Propósito: Servir a otro proyecto con usuarios premium

3. **🔬 Evaluación y Mejora Continua (PRIORIDAD #3)**

   - Sistema de evaluación post-sorteo (STEP 4 del pipeline)
   - Adaptive learning ajusta pesos automáticamente (STEP 5)
   - Estrategias con bajo ROI → reducen peso → eventualmente eliminadas
   - Estrategias exitosas → aumentan peso → más tickets generados

4. **📊 Analytics y Monitoreo (PRIORIDAD #4)**
   - Dashboard de performance por estrategia
   - Tracking histórico de ROI
   - Alertas de degradación de performance
   - Métricas de consistencia y accuracy

### What This Means

✅ **SÍ hacer:**

- Añadir nuevas estrategias al Pipeline para evaluación
- Mejorar algoritmos de predicción existentes
- Optimizar sistema de adaptive learning
- Crear API ligera para servir predicciones del pipeline
- Refactorizar código para mantenibilidad

❌ **NO hacer:**

- Crear sistemas paralelos separados del pipeline
- Generar predicciones duplicadas sin evaluación
- Complicar arquitectura con tablas/servicios innecesarios
- Priorizar "servir usuarios" sobre "mejorar predicciones"

---

## 📋 CURRENT ARCHITECTURE

### Pipeline v5.0 (Cerebro del Sistema)

**Flujo Completo:**

```
STEP 1: update_database_from_source()      → Fetch nuevo draw MUSL/NY API
STEP 2: update_analytics()                 → Calcular co-occurrences, patterns
STEP 3: evaluate_predictions_for_draw()    → Comparar predicciones vs resultado
STEP 4: adaptive_learning_update()         → Ajustar pesos según performance
STEP 5: generate_balanced_tickets(200)     → Generar predicciones para próximo draw
STEP 6: [FUTURO] Batch generation (eliminable)
```

**Estrategias Actuales (6):**

1. `frequency_weighted` - Basada en frecuencia histórica de números
2. `cooccurrence` - Análisis de co-ocurrencia de pares de números
3. `ai_guided` - XGBoost ML con IntelligentGenerator
4. `range_balanced` - Distribución equilibrada por rangos
5. `random_baseline` - Control aleatorio para benchmark
6. `coverage_optimizer` - Maximiza cobertura de rangos

**Datos Clave:**

- Base de datos: 1,864 draws históricos (2009-2025)
- Tabla principal: `generated_tickets` (predicciones evaluables)
- Scheduler: APScheduler (3 jobs: post_drawing_pipeline, maintenance, daily_full_sync)
- Performance: ~60s para generar 200 tickets

### Sistema Batch (A ELIMINAR/REFACTORIZAR)

**Estado Actual:**

- Tabla: `pre_generated_tickets` (cache de ML)
- Modos: random_forest, lstm, v1, v2, hybrid (5 modos × 100 tickets = 500 total)
- Propósito original: Cache de alta velocidad para API pública
- **Problema:** Genera predicciones NO evaluables (sin draw_date)
- **Decisión:** Integrar estrategias ML al Pipeline, eliminar sistema separado

---

## ✅ COMPLETED MILESTONES

### Recent Achievements (Nov 2025)

#### ✅ RandomForest Optimization (Critical Fix)

- **Issue:** Batch generation stuck indefinitely (30+ seconds timeout)
- **Root Cause:** O(n²) complexity in feature engineering (354 features)
- **Solution:** Optimized to 39 features (89% reduction)
- **Impact:** 2.3s generation for 100 tickets (44 tickets/sec)
- **Documentation:** `docs/RANDOM_FOREST_OPTIMIZATION.md`

#### ✅ v1/v2/hybrid Modes Activation

- **Added:** 3 new modes to batch system (v1, v2, hybrid)
- **Bug Fixed:** numpy.int64 validation issue (v2 went from 0% → 100% success)
- **Production:** All 5 modes operational in VPS
- **Performance:** v1=2.0/s, v2=1.6/s, hybrid=1.2/s
- **Commits:** 4a8ac78, 248f719, 052894d

#### ✅ Production Deployment Verification

- **Models Retrained:** RandomForest (348MB), LSTM (1.9MB)
- **Service Status:** systemd active, API responding <50ms
- **Database:** 852 pre-generated tickets across 5 modes
- **Health Check:** All systems operational ✅

#### ✅ Documentation Consolidation

- Archived 7 redundant implementation summaries
- Updated TECHNICAL.md with dual-table architecture
- Updated copilot-instructions.md with current state
- Created RANDOM_FOREST_OPTIMIZATION.md

---

## 🚀 ACTIVE ROADMAP

### ⚡ STRATEGY: "Clean Before You Build"

**Decision:** Eliminar sistema Batch PRIMERO antes de expandir Pipeline

**Razón:**

- Evitar duplicar esfuerzo en código que será eliminado
- Base de código más limpia facilita agregar nuevas estrategias
- Reduce riesgo de errores al trabajar en código enfocado
- Previene confusión entre sistemas batch (deprecated) y pipeline (activo)

**Secuencia:**

1. 🧹 PHASE 1: Eliminar Batch + Código muerto (THIS WEEK - CRITICAL 🔥)
2. 🚀 PHASE 2: Expandir Pipeline a 11 estrategias (AFTER CLEANUP)
3. 🌐 PHASE 3: API para proyecto externo (AFTER EXPANSION)

---

### PHASE 1: ELIMINACIÓN BATCH + CODE CLEANUP (THIS WEEK - CRITICAL 🔥)

**Goal:** Limpiar código legacy antes de expandir pipeline

- [ ] Identificar endpoints que consumen batch (`/batch/*`)
- [ ] Verificar si frontend usa batch (unlikely)
- [ ] Listar archivos a eliminar completos
- [ ] Crear backup de DB antes de DROP table

**Commands:**

```bash
grep -r "pre_generated_tickets" src/ frontend/
grep -r "batch_generator" src/
grep -r "/batch" src/api*.py
sqlite3 data/shiolplus.db ".backup data/backups/before_batch_removal.db"
```

**Time Estimate:** 30 minutos  
**Priority:** CRITICAL  
**Status:** PENDING

#### Task 1.2: Eliminación de Código Batch

- [ ] Eliminar archivo `src/batch_generator.py` completo
- [ ] Eliminar archivo `src/api_batch_endpoints.py` (si existe)
- [ ] Remover imports de batch_generator en `src/api.py`
- [ ] Eliminar STEP 6 del pipeline (batch generation)
- [ ] DROP tabla `pre_generated_tickets` (después de backup)
- [ ] Remover router batch de FastAPI app

**SQL:**

```sql
DROP TABLE IF EXISTS pre_generated_tickets;
```

**Time Estimate:** 2 horas  
**Priority:** CRITICAL  
**Status:** PENDING

#### Task 1.3: Limpieza de Código Muerto (PHASE 6 Task 6.4 adelantado)

- [ ] Ejecutar `ruff check src/ --fix` (auto-fix imports)
- [ ] Buscar funciones no usadas manualmente
- [ ] Eliminar comentarios obsoletos (`# TODO:` completados, `# DEPRECATED:`)
- [ ] Remover código comentado (dead code)
- [ ] Limpiar imports innecesarios que ruff no detectó

**Commands:**

```bash
ruff check src/ --fix
grep -r "# TODO" src/ | grep -i "done\|completed\|fixed"
grep -r "# DEPRECATED" src/
```

**Time Estimate:** 2-3 horas  
**Priority:** HIGH  
**Status:** PENDING

#### Task 1.4: Validación Post-Limpieza

- [ ] Ejecutar pipeline completo manualmente (5 steps)
- [ ] Verificar que genera 200 tickets correctamente
- [ ] Confirmar adaptive learning funciona
- [ ] Tests: `pytest tests/ -v`
- [ ] Verificar scheduler sigue funcionando
- [ ] Commit y push cambios

**Time Estimate:** 1 hora  
**Priority:** CRITICAL  
**Status:** PENDING

---

### PHASE 2: PIPELINE STRATEGY EXPANSION (AFTER CLEANUP)

**Goal:** Integrar estrategias ML del batch al pipeline como estrategias evaluables

#### Task 2.1: Añadir 5 Estrategias ML al Pipeline ⭐

**Estrategias a Añadir:**

1. `xgboost_ml` - XGBoost predictor con DeterministicGenerator
2. `random_forest_ml` - Random Forest (39 features optimizadas)
3. `lstm_neural` - LSTM neural networks
4. `hybrid_ensemble` - 70% XGBoost + 30% Cooccurrence
5. `intelligent_scoring` - Multi-criteria scoring system

**Implementación:**

- [ ] Crear clases `XGBoostMLStrategy`, `RandomForestMLStrategy`, `LSTMNeuralStrategy`, `HybridEnsembleStrategy`, `IntelligentScoringStrategy` en `src/strategy_generators.py`
- [ ] Registrar en `StrategyManager.__init__()`
- [ ] Inicializar 5 filas en `strategy_performance` table (peso inicial: 0.10)
- [ ] Verificar distribución de 200 tickets entre 11 estrategias (~18/estrategia)
- [ ] Test local con todas las estrategias

**Resultado Esperado:**

- Pipeline genera 200 tickets con 11 estrategias
- Todas evaluables con `draw_date` específico
- Adaptive learning ajusta pesos según ROI real

**Time Estimate:** 6-7 horas (reducido por código limpio)  
**Priority:** CRITICAL  
**Status:** PENDING

#### Task 2.2: Testing de Integración

- [ ] Ejecutar pipeline completo con 11 estrategias
- [ ] Verificar distribución de tickets (~18/estrategia)
- [ ] Simular evaluación post-sorteo (STEP 4)
- [ ] Verificar adaptive learning ajusta pesos (STEP 5)
- [ ] Confirmar 200 tickets guardados en `generated_tickets`

**Time Estimate:** 2 horas  
**Status:** PENDING

---

### PHASE 3: API SIMPLIFICADA PARA PROYECTO EXTERNO (AFTER EXPANSION)

**Goal:** Crear endpoint ligero que sirve predicciones del pipeline (NO genera nada nuevo)

#### Task 3.1: Endpoint `/api/v1/predictions/latest`

**Funcionalidad:**

- Sirve las últimas 200 predicciones del pipeline
- Filtros: `limit` (default: 50), `strategy`, `min_confidence`
- Ordenado por confidence DESC
- Performance target: <10ms (solo lectura DB)
- Autenticación: JWT token (para proyecto externo)

**Implementación:**

- [ ] Crear endpoint en `src/api_prediction_endpoints.py`
- [ ] Query optimizado a `generated_tickets` (último pipeline_run_id)
- [ ] Añadir índice a DB si es necesario
- [ ] Tests de performance (<10ms)
- [ ] Documentar en OpenAPI spec

**Time Estimate:** 2 horas  
**Priority:** HIGH  
**Status:** PENDING

#### Task 3.2: Endpoint `/api/v1/predictions/by-strategy`

**Funcionalidad:**

- Agrupa predicciones por estrategia
- Retorna métricas: avg_confidence, total_tickets, recent_roi
- Útil para que proyecto externo vea qué estrategias están funcionando mejor

**Implementación:**

- [ ] Query con GROUP BY strategy
- [ ] Incluir datos de `strategy_performance` (win_rate, roi)
- [ ] Cache de 5 minutos (FastAPI @lru_cache)
- [ ] Tests

**Time Estimate:** 1 hora  
**Status:** PENDING

---

### PHASE 4: MEJORA DE ADAPTIVE LEARNING (DICIEMBRE)

**Goal:** Optimizar algoritmo de ajuste de pesos para maximizar ROI

#### Task 4.1: Análisis de Performance Actual

- [ ] Revisar lógica actual en `adaptive_learning_update()`
- [ ] Analizar histórico de ajustes de pesos
- [ ] Identificar estrategias que mejoran/empeoran con tiempo
- [ ] Documentar comportamiento actual

**Time Estimate:** 3 horas  
**Priority:** MEDIUM  
**Status:** PENDING

#### Task 4.2: Implementar Reinforcement Learning Básico

**Concepto:** Recompensa/castigo basado en aciertos reales

```python
# Pseudocódigo
def rl_weight_update(strategy_name, draw_result):
    predictions = get_strategy_predictions(strategy_name)
    reward = calculate_reward(predictions, draw_result)

    # Gradient-based update (REINFORCE algorithm)
    current_weight = get_weight(strategy_name)
    new_weight = current_weight + learning_rate * reward

    update_weight(strategy_name, new_weight)
```

**Implementación:**

- [ ] Crear función `calculate_reward()` (aciertos → +1, fallos → -0.1)
- [ ] Implementar REINFORCE simple (policy gradient)
- [ ] Testing A/B vs sistema actual
- [ ] Si mejora ROI → deploy, si no → revert

**Time Estimate:** 8 horas  
**Status:** PENDING

#### Task 4.3: Weight Decay y Regularización

- [ ] Añadir decay factor para evitar pesos extremos (0.01 mín, 0.30 máx)
- [ ] Regularización L2 para prevenir overfitting a estrategias
- [ ] Exploración epsilon-greedy (5% del tiempo forzar estrategias bajas)
- [ ] Monitoring de estabilidad de pesos

**Time Estimate:** 4 horas  
**Status:** PENDING

---

### PHASE 5: TRANSFER LEARNING CON DATOS EXTERNOS (DICIEMBRE)

**Goal:** Mejorar modelos ML con históricos completos de Powerball (3,500+ draws)

#### Task 5.1: Obtención de Datos Históricos Completos

- [ ] Investigar fuentes de datos completos Powerball (1992-2025)
- [ ] APIs públicas: Powerball.com, Data.gov, Kaggle datasets
- [ ] Script de scraping si necesario (con rate limiting)
- [ ] Validación de calidad de datos
- [ ] Almacenar en tabla `external_draws_history`

**Time Estimate:** 6 horas  
**Status:** PENDING

#### Task 5.2: Pre-entrenamiento con Dataset Completo

- [ ] Adaptar `RandomForestModel` para pre-training
- [ ] Entrenar con 3,500 draws externos
- [ ] Guardar modelo base pre-entrenado
- [ ] Fine-tuning con 1,864 draws locales
- [ ] Benchmark: modelo pre-entrenado vs from-scratch

**Time Estimate:** 8 horas  
**Status:** PENDING

#### Task 5.3: Transfer Learning para LSTM

- [ ] Similar approach para LSTM networks
- [ ] Pre-train con secuencias largas (3,500 draws)
- [ ] Fine-tune con datos recientes
- [ ] Evaluar mejora en validation loss

**Time Estimate:** 8 horas  
**Status:** PENDING

---

### PHASE 6: CODE REFACTORING & CLEANUP (ONGOING)

**Goal:** Mejorar mantenibilidad, reducir deuda técnica

#### Task 6.1: Consolidar Validación de Tickets

- [ ] Crear módulo `src/validators.py`
- [ ] Mover toda lógica de validación (white_balls 1-69, powerball 1-26)
- [ ] Eliminar duplicación entre database.py, strategy_generators.py, etc.
- [ ] Unit tests para validators

**Time Estimate:** 3 horas  
**Priority:** MEDIUM  
**Status:** PENDING

#### Task 6.2: Type Hints y MyPy Strict

- [ ] Añadir type hints a funciones sin tipado
- [ ] Configurar mypy en modo strict
- [ ] Resolver todos los errores de tipo
- [ ] Integrar en CI/CD (opcional)

**Time Estimate:** 6 horas  
**Priority:** LOW  
**Status:** PENDING

#### Task 6.3: Ruff Linting y Formatting

- [ ] Ejecutar `ruff check src/ --fix`
- [ ] Resolver warnings críticos (F-level)
- [ ] Aplicar formatting automático
- [ ] Configurar pre-commit hook (opcional)

**Time Estimate:** 2 horas  
**Priority:** LOW  
**Status:** PENDING

#### Task 6.4: Eliminar Código Muerto

- [ ] Identificar funciones no usadas (grep + manual review)
- [ ] Eliminar imports innecesarios
- [ ] Remover comentarios obsoletos
- [ ] Limpiar código comentado (dead code)

**Time Estimate:** 4 horas  
**Priority:** LOW  
**Status:** PENDING

#### Task 6.5: Test Coverage Improvement

- [ ] Analizar coverage actual (`pytest --cov`)
- [ ] Identificar funciones críticas sin tests
- [ ] Añadir tests para `adaptive_learning_update()`
- [ ] Tests para nuevas estrategias ML
- [ ] Target: >80% coverage en módulos core

**Time Estimate:** 8 horas  
**Priority:** MEDIUM  
**Status:** PENDING

---

### PHASE 7: MONITORING & ANALYTICS (ENERO 2026)

**Goal:** Visibilidad completa del sistema y decisiones data-driven

#### Task 7.1: Dashboard de Estrategias

- [ ] UI para visualizar performance de 11 estrategias
- [ ] Gráficos de ROI histórico por estrategia
- [ ] Win rate evolution over time
- [ ] Weight adjustments timeline
- [ ] Top predictions by confidence

**Tech Stack:** Chart.js o Plotly.js  
**Time Estimate:** 12 horas  
**Status:** PENDING

#### Task 7.2: Sistema de Alertas

- [ ] Alerta si ROI general cae <0.5 por 5 draws consecutivos
- [ ] Alerta si estrategia tiene win_rate 0% por 10+ draws
- [ ] Alerta si pipeline falla 2+ veces consecutivas
- [ ] Email notifications (SMTP config)

**Time Estimate:** 6 horas  
**Status:** PENDING

#### Task 7.3: Métricas de Negocio

- [ ] Total invertido simulado vs retorno proyectado
- [ ] Break-even analysis por estrategia
- [ ] Ticket cost efficiency ($/ticket generado)
- [ ] Performance vs baseline random

**Time Estimate:** 4 horas  
**Status:** PENDING

---

## 📊 PROJECT STATISTICS

**Repository:** orlandobatistac/SHIOL-PLUS  
**Version:** v8.0 (Strategic Realignment)  
**Active Since:** 2024  
**Total Commits:** 500+  
**Production Uptime:** 99.9%

### Current System State

**Pipeline:**

- Estrategias Activas: 6/11 (expansión pendiente)
- Tickets por Run: 200
- Frecuencia: 3x semana (Lun/Mié/Sáb post-sorteo)
- Performance: ~60s total (STEPS 1-5)
- Última Ejecución: 2025-11-19 02:54:12 UTC ✅

**Database:**

- Draws Históricos: 1,864 (2009-2025)
- Generated Tickets: ~10,000+ evaluables
- Strategy Performance: 6 filas (pronto 11)
- Pipeline Execution Logs: 150+ runs tracked

**Production Environment:**

- Hosting: Contabo VPS ($2/month)
- OS: Ubuntu Server
- Web Server: Nginx + Gunicorn
- SSL: Let's Encrypt
- Domain: shiolplus.com
- API Response Time: <50ms (avg)
- Memory Usage: ~300MB

**Tech Stack:**

- Backend: FastAPI (Python 3.10+)
- ML: XGBoost, Random Forest, LSTM (Keras/TensorFlow)
- Database: SQLite (simple, sufficient para escala actual)
- Scheduler: APScheduler
- Frontend: Vanilla JS + Tailwind CSS
- Auth: JWT + bcrypt
- Payments: Stripe (inactive, para proyecto externo)

---

## 🎯 NEXT 7 DAYS PRIORITY LIST

### Week of Nov 19-26, 2025

**STRATEGY: Clean Before You Build**

**Day 1 (Nov 19): Batch Elimination & Code Cleanup**

1. ✅ Análisis de dependencias batch (Task 1.1) - 30 min
2. ✅ Backup DB antes de cambios - 5 min
3. ✅ Eliminar código batch (Task 1.2) - 2 horas
4. ✅ Limpieza código muerto con ruff (Task 1.3) - 2-3 horas
5. ✅ Validación post-limpieza (Task 1.4) - 1 hora

**Day 2-3 (Nov 20-21): Pipeline Expansion**

6. ✅ Crear 5 clases de estrategia ML (Task 2.1) - 6-7 horas
7. ✅ Testing de integración (Task 2.2) - 2 horas

**Day 4-5 (Nov 22-23): API Externa**

8. ✅ Endpoint `/predictions/latest` (Task 3.1) - 2 horas
9. ✅ Endpoint `/predictions/by-strategy` (Task 3.2) - 1 hora
10. ✅ Tests de performance (<10ms) - 30 min

**Day 6-7 (Nov 24-25): Testing & Deployment**

11. ✅ Pipeline completo con 11 estrategias E2E
12. ✅ Deploy a producción (GitHub Actions auto-deploy)
13. ✅ Verificar 200 tickets con 11 estrategias
14. ✅ Monitorear logs primeras 24h
15. ✅ Documentar en PROJECT_ROADMAP_V8.md

---

## 📚 DOCUMENTATION INDEX

### Core Documentation

- **PROJECT_ROADMAP_V8.md** (este archivo) - Roadmap y estado del proyecto
- **docs/TECHNICAL.md** - Arquitectura técnica detallada
- **.github/copilot-instructions.md** - Guía para AI agents

### Implementation Guides

- **docs/BATCH_GENERATION.md** - Sistema batch (deprecado, a eliminar)
- **docs/RANDOM_FOREST_OPTIMIZATION.md** - Optimización 354→39 features
- **docs/DEPLOYMENT_NGINX.md** - Setup de producción

### API Documentation

- **docs/api/** - OpenAPI specs para todos los endpoints
- **frontend/static/openapi.json** - Auto-generated API schema

### Archived Documentation

- **docs/archive/** - Documentos históricos (no críticos)

---

## 🔧 MAINTENANCE NOTES

### Weekly Tasks

- [ ] Review pipeline execution logs (errores, timeouts)
- [ ] Verificar estrategias con ROI <0.3 (candidatas a eliminar)
- [ ] Backup de database (`shiolplus.db` → S3/local)
- [ ] Check scheduler jobs health
- [ ] Monitor VPS disk space (<80%)

### Monthly Tasks

- [ ] Retrain models con nuevos draws (si hay cambios significativos)
- [ ] Review strategy weights distribution (evitar monopolio)
- [ ] Update dependencies (security patches)
- [ ] Review error logs y patterns
- [ ] Performance analysis (optimización si necesario)

### Quarterly Tasks

- [ ] Full system audit (security, performance, architecture)
- [ ] Review roadmap y adjust priorities
- [ ] Backup strategy review
- [ ] Disaster recovery test
- [ ] Documentation update sweep

---

## 💡 ARCHITECTURAL DECISIONS

### Why Pipeline-Centric Architecture?

**Problema con Sistema Dual (Pipeline + Batch):**

- ❌ Redundancia: v1 se generaba 2 veces (pipeline + batch)
- ❌ Inconsistencia: Usuarios veían predicciones no evaluadas
- ❌ Pérdida de adaptive learning: Batch no mejoraba con tiempo
- ❌ Complejidad innecesaria: 2 sistemas haciendo trabajo similar

**Solución: Pipeline Unificado con 11 Estrategias:**

- ✅ Single source of truth: Pipeline genera TODO
- ✅ Evaluación universal: Todas las estrategias son medibles
- ✅ Adaptive learning completo: Sistema mejora continuamente
- ✅ Simplicidad: Una tabla (`generated_tickets`), un flujo

### Why SQLite (Not PostgreSQL)?

- Escala actual: 1,864 draws, ~10K generated tickets → SQLite es suficiente
- Simplicidad: Zero configuración, backup = copy file
- Performance: <10ms queries con índices apropiados
- Costo: $0 (vs PostgreSQL hosting ~$10-20/mes)
- **Cuándo migrar a PostgreSQL:** >100K tickets, concurrencia alta (50+ usuarios simultáneos)

### Why Not Redis Cache?

- Pipeline genera cada 2-3 días (baja frecuencia)
- Lectura de DB ya es <10ms (cache no crítico)
- Complejidad adicional innecesaria
- **Cuándo añadir Redis:** API >1000 requests/min, latency >50ms

---

## 📞 CONTACTS & RESOURCES

**Project Owner:** Orlando Batista (orlandobatistac)  
**Repository:** https://github.com/orlandobatistac/SHIOL-PLUS  
**Production URL:** https://shiolplus.com  
**API Docs:** https://shiolplus.com/api/docs

**External APIs Used:**

- MUSL Powerball API (primary data source)
- NY State Lottery API (fallback)
- Stripe API (payments, inactive)

**Development Environment:**

- Local: Windows 11 + Python 3.10+
- Production: Ubuntu Server 22.04 LTS
- IDE: VS Code + GitHub Copilot

---

## 🚨 CRITICAL REMINDERS FOR AI AGENTS

1. **READ PROJECT_ROADMAP_V8.md FIRST** before any coding task
2. **NEVER** crear sistemas paralelos sin evaluación
3. **ALWAYS** actualizar PROJECT_ROADMAP_V8.md después de cambios importantes
4. **TEST** en local antes de deployment a producción
5. **DOCUMENT** decisiones arquitectónicas en este archivo
6. **BACKUP** database antes de migraciones
7. **VERIFY** que adaptive learning sigue funcionando después de cambios

---

_Last Updated: 2025-11-19 21:30 ET_  
_Next Review: 2025-11-20 (Post-Phase 1 Task 1.1-1.2 completion)_  
_Status: 🧹 Active Development - Phase 1 (Clean Before You Build) Starting NOW_
