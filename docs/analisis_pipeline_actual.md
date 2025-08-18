
# Análisis del Pipeline Actual SHIOL+ v5.0

## Resumen Ejecutivo

El sistema SHIOL+ utiliza un **pipeline optimizado de 5 pasos** diseñado para generar predicciones de lotería Powerball usando inteligencia artificial y análisis adaptativo. El sistema se ejecuta automáticamente tres veces por semana y está desplegado en Replit con acceso público.

## Arquitectura del Pipeline

### Pipeline Optimizado: 5 Pasos

El sistema ha evolucionado de un pipeline original de 7 pasos a uno optimizado de 5 pasos para mejorar rendimiento y eficiencia:

#### **Paso 1: Data Update & Evaluation**
- **Método**: `_run_data_update_and_evaluation()`
- **Duración**: 2-5 minutos
- **Función**: 
  - Actualiza base de datos con nuevos resultados de sorteos
  - Evalúa predicciones anteriores contra resultados reales
  - Calcula premios ganados y estadísticas de rendimiento
  - Detecta nuevos sorteos para procesar

#### **Paso 2: Model Prediction (Ensemble Only)**
- **Método**: `_run_model_prediction()`
- **Duración**: 30-60 segundos
- **Función**:
  - Ejecuta solo el modelo ensemble (más efectivo)
  - Genera probabilidades para números (1-69) y powerball (1-26)
  - Calcula métricas de entropía para confianza
  - Omite modelos individuales por eficiencia

#### **Paso 3: Scoring & Selection**
- **Método**: `_score_and_select()`
- **Duración**: 10-20 segundos
- **Función**:
  - Aplica sistema de scoring multi-criterio:
    - **Probability** (40%): Basado en predicciones del modelo
    - **Diversity** (25%): Balance par/impar, distribución por rangos
    - **Historical** (20%): Frecuencias históricas y recencia
    - **Risk-adjusted** (15%): Evita patrones obvios

#### **Paso 4: Prediction Generation**
- **Método**: `_generate_predictions_optimized()`
- **Duración**: 1-3 minutos
- **Función**:
  - Genera número solicitado de predicciones (default: 100)
  - Usa `IntelligentGenerator` con probabilidades del modelo
  - Procesa en lotes de 50 predicciones
  - Aplica scoring determinístico para ranking

#### **Paso 5: Save & Serve**
- **Método**: `_save_and_serve()`
- **Duración**: 30-60 segundos
- **Función**:
  - Guarda predicciones en base de datos
  - Prepara top 10 predicciones para dashboard
  - Actualiza metadatos de ejecución
  - Optimiza datos para frontend

## Componentes del Sistema

### Core Pipeline
- **Orchestrator** (`src/orchestrator.py`): Coordina ejecución de 5 pasos
- **Intelligent Generator** (`src/intelligent_generator.py`): Sistema de scoring y generación
- **Predictor** (`src/predictor.py`): Motor de predicción principal
- **Database** (`src/database.py`): Gestión de datos SQLite optimizada

### APIs y Frontend
- **API Principal** (`src/api.py`): Router principal FastAPI
- **Public API** (`src/api_public_endpoints.py`): Endpoints públicos
- **Dashboard API** (`src/api_dashboard_endpoints.py`): Endpoints admin
- **Pipeline API** (`src/api_pipeline_endpoints.py`): Control de pipeline
- **Frontend** (`frontend/`): Interfaz web completa

### Modelos y Scoring
- **Ensemble Predictor** (`src/ensemble_predictor.py`): Sistema ensemble
- **Model Pool Manager** (`src/model_pool_manager.py`): Gestión de modelos
- **Adaptive Feedback** (`src/adaptive_feedback.py`): Sistema adaptativo

## Programación Automática

### Scheduler Configurado
```python
# Días y horarios de ejecución
scheduler.add_job(
    func=trigger_full_pipeline_automatically,
    trigger="cron",
    day_of_week="mon,wed,sat",  # Lunes, Miércoles, Sábado
    hour=23, minute=29,         # 11:29 PM ET
    timezone="America/New_York"
)
```

### Timing Strategy
- **30 minutos después del sorteo** oficial (10:59 PM ET)
- **Timezone fijo**: America/New_York con manejo DST automático
- **Prevención de solapamiento**: Solo una ejecución a la vez

## Flujo de Datos

### Input → Processing → Output
```
Sorteos Oficiales → Data Update → Feature Engineering → 
Ensemble Model → Multi-Criteria Scoring → Top Predictions → 
Database Storage → API Endpoints → Frontend Display
```

### Base de Datos Optimizada
```sql
-- Tablas principales
powerball_draws       -- Resultados históricos
predictions_log       -- Predicciones con scoring
pipeline_executions   -- Historial de ejecución
adaptive_weights      -- Pesos dinámicos de scoring
```

## Performance Metrics

### Tiempos de Ejecución
- **Pipeline completo**: 5-10 minutos (antes: 30 minutos)
- **Generación 100 predicciones**: 1-3 minutos
- **API response time**: < 2 segundos
- **Data update**: 30-60 segundos

### Recursos del Sistema
- **CPU**: 60-80% durante pipeline
- **Memoria**: 70-90% durante generación
- **Storage**: < 100MB base de datos completa
- **Uptime**: > 99% disponibilidad

## Endpoints Críticos

### API Pública
- `GET /` - Interfaz principal
- `GET /api/v1/public/next-drawing` - Cuenta regresiva
- `GET /api/v1/public/featured-predictions` - Top predicciones

### API de Control
- `GET /api/v1/pipeline/status` - Estado del pipeline
- `POST /api/v1/pipeline/trigger` - Ejecución manual
- `GET /api/v1/pipeline/health` - Health check

### API de Predicciones
- `GET /api/v1/predict-deterministic` - Predicción individual
- `GET /api/v1/prediction-history` - Historial de predicciones

## Configuración del Sistema

### Pipeline Settings (`config/config.ini`)
```ini
[pipeline]
execution_days = 0,2,5          # Lun, Mié, Sáb
execution_time = 23:29          # 11:29 PM ET
timezone = America/New_York
auto_execution_enabled = true
default_predictions_count = 100

[scoring]
probability_weight = 40
diversity_weight = 25
historical_weight = 20
risk_adjusted_weight = 15
```

## Estado Actual del Sistema

### Componentes Operativos ✅
- **Pipeline Orchestrator**: Funcional con 5 pasos optimizados
- **Intelligent Generator**: Generando 100 predicciones por ejecución
- **Database Manager**: SQLite optimizada
- **API Server**: FastAPI en puerto 3000
- **Dashboard Frontend**: Interfaz web completa
- **Scheduler**: APScheduler con timezone ET
- **Subprocess Execution**: Ejecución robusta

### Deployment en Replit
- **URL Pública**: https://shiolplus.replit.app
- **Puerto**: 3000 (configurado para acceso público)
- **Servidor**: Uvicorn ASGI con auto-reload
- **Workflows**: Configurados para reinicio automático

## Optimizaciones Implementadas

### Performance
1. **Reducción de pasos**: 7 → 5 pasos
2. **Ensemble only**: Solo modelo más efectivo
3. **Batch processing**: Lotes optimizados
4. **Async execution**: Operaciones no bloqueantes
5. **Memory management**: Liberación proactiva

### Database
1. **Índices optimizados**: En columnas frecuentes
2. **Query optimization**: Consultas eficientes
3. **Data retention**: Limpieza automática
4. **Connection pooling**: Gestión de conexiones

### Frontend
1. **API consolidation**: Menos llamadas
2. **Caching strategy**: Datos temporales
3. **Progressive loading**: Carga incremental
4. **Error handling**: Manejo robusto

## Monitoreo y Logs

### Sistema de Logging
- **Archivo principal**: `logs/shiolplus.log`
- **Niveles**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Rotación**: Automática por tamaño
- **Retention**: 30 días de historial

### Health Monitoring
- **Pipeline status**: Estado en tiempo real
- **System resources**: CPU, memoria, disco
- **API performance**: Tiempos de respuesta
- **Database health**: Conexiones y queries

## Próximas Mejoras Planificadas

### v6.0 Roadmap
1. **Model enhancement**: Nuevos algoritmos ensemble
2. **Real-time updates**: WebSocket para updates
3. **Performance analytics**: Métricas avanzadas
4. **Multi-lottery support**: Expansión a otros juegos
5. **Mobile optimization**: Interfaz responsive mejorada

---

**Documento generado**: Agosto 2025  
**Versión del sistema**: SHIOL+ v5.0  
**Estado**: Producción activa en Replit  
**Próxima actualización**: v6.0 (Q4 2025)
