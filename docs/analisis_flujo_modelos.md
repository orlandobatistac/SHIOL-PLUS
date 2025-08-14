# Análisis del Flujo Actual del Sistema SHIOL+ v6.1

## Resumen Ejecutivo

SHIOL+ v6.1 es un sistema optimizado de machine learning para predicción de lotería que implementa un **pipeline de 5 pasos** con arquitectura de microservicios, sistema adaptativo de retroalimentación, y capacidades de auto-optimización. El sistema está diseñado específicamente para funcionar de manera eficiente en el entorno Replit con recursos limitados.

## Arquitectura del Sistema Actual

### Stack Tecnológico Implementado
- **Backend**: Python 3.12, FastAPI, Uvicorn ASGI
- **Machine Learning**: XGBoost, Scikit-learn, NumPy, Pandas
- **Base de Datos**: SQLite (optimizada para Replit)
- **Frontend**: HTML5, CSS3, JavaScript ES6+ (sin frameworks)
- **API**: RESTful endpoints con documentación automática
- **Deployment**: Replit Cloud Infrastructure
- **Scheduling**: APScheduler con timezone America/New_York

### Componentes Principales Activos
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Loader   │    │ Orchestrator    │    │ Smart AI Engine │
│   (loader.py)   │───▶│(orchestrator.py)│───▶│(predictor.py +  │
│                 │    │                 │    │ intelligent_    │
└─────────────────┘    └─────────────────┘    │ generator.py)   │
         │                       │             └─────────────────┘
         ▼                       ▼                       │
┌─────────────────┐    ┌─────────────────┐             ▼
│   Database      │    │   API Server    │    ┌─────────────────┐
│ (database.py)   │    │   (api.py)      │    │ Dashboard UI    │
│                 │    │                 │    │ (dashboard.html)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Pipeline Optimizado de 5 Pasos (Flujo Actual)

### Implementación en `src/orchestrator.py`

El sistema actual utiliza un **pipeline optimizado de 5 pasos** implementado en el método `run_full_pipeline_async()`:

```python
# Pipeline actual optimizado para Replit
OPTIMIZED_PIPELINE_STEPS = [
    'data_update_validation',    # Paso 1: Actualización y validación de datos
    'model_prediction',          # Paso 2: Predicción del modelo ensemble
    'scoring_selection',         # Paso 3: Scoring y selección optimizada
    'prediction_generation',     # Paso 4: Generación de predicciones (50 plays)
    'save_serve'                # Paso 5: Guardado y preparación para frontend
]
```

### Paso 1: Data Update & Validation
**Método**: `_update_and_validate_data()`
**Tiempo estimado**: < 30 segundos

**Funcionalidades**:
- Actualiza la base de datos desde la fuente CSV
- Valida integridad de datos recientes (últimos 30 días)
- Verifica conectividad de base de datos
- Retorna conteo de registros válidos

**Código actual**:
```python
async def _update_and_validate_data(self) -> Dict[str, Any]:
    try:
        from src.loader import update_database_from_source
        await asyncio.get_event_loop().run_in_executor(None, update_database_from_source)

        # Validación básica - verificar datos recientes
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM powerball_numbers WHERE date >= date('now', '-30 days')")
        recent_count = cursor.fetchone()[0]
        conn.close()

        return {
            "status": "success", 
            "message": "Data updated and validated",
            "recent_records": recent_count,
            "validation_passed": recent_count > 0
        }
```

### Paso 2: Model Prediction (Ensemble Only)
**Método**: `_run_model_prediction()`
**Tiempo estimado**: < 1 minuto

**Funcionalidades**:
- Ejecuta únicamente el modelo ensemble para optimizar velocidad
- Calcula probabilidades para números principales y powerball
- Genera métricas de entropía para validación
- Se enfoca en predicción ensemble para máxima eficiencia

**Código actual**:
```python
async def _run_model_prediction(self) -> Dict[str, Any]:
    try:
        if self.predictor:
            wb_probs, pb_probs = await asyncio.get_event_loop().run_in_executor(
                None, self.predictor.predict_probabilities, True  # Force ensemble
            )
            return {
                "status": "success",
                "wb_prob_entropy": float(-np.sum(wb_probs * np.log(wb_probs + 1e-10))),
                "pb_prob_entropy": float(-np.sum(pb_probs * np.log(pb_probs + 1e-10))),
                "method": "ensemble_only"
            }
```

### Paso 3: Scoring & Selection (Optimizado)
**Método**: `_score_and_select()`
**Tiempo estimado**: < 10 segundos

**Funcionalidades**:
- Scoring simplificado enfocado en criterios core
- Optimización de alto nivel para Replit
- Criterios: probability, diversity, historical
- Procesamiento mínimo para máxima velocidad

### Paso 4: Prediction Generation (50 Predicciones)
**Método**: `_generate_predictions_optimized()`
**Tiempo estimado**: < 2 minutos

**Funcionalidades**:
- Genera exactamente **50 predicciones Smart AI** (optimizado para Replit)
- Utiliza `intelligent_generator` directamente para máxima velocidad
- Procesa en batches de 50 para eficiencia
- Calcula fecha del próximo sorteo automáticamente
- Incluye sistema de ranking y scoring detallado

**Código actual**:
```python
async def _generate_predictions_optimized(self, num_predictions: int, scoring_result: Dict) -> list:
    try:
        predictions = []

        # Usa intelligent generator directamente para velocidad
        batch_size = 50  # Batches más grandes para eficiencia
        for i in range(0, num_predictions, batch_size):
            batch_end = min(i + batch_size, num_predictions)
            batch_size_actual = batch_end - i

            # Genera batch usando intelligent generator
            batch_predictions = await asyncio.get_event_loop().run_in_executor(
                None, self._generate_batch_intelligent, batch_size_actual, i
            )
            predictions.extend(batch_predictions)
```

### Paso 5: Save & Serve
**Método**: `_save_and_serve()`
**Tiempo estimado**: < 30 segundos

**Funcionalidades**:
- Guarda todas las predicciones en la base de datos
- Prepara top 10 predicciones para el frontend
- Optimiza datos para compatibilidad con dashboard
- Retorna estadísticas de guardado

## Flujo de Datos Actual

### 1. Trigger Automático (Scheduler)
El sistema utiliza APScheduler con la siguiente configuración:

```python
# Configuración actual del scheduler en src/api.py
scheduler.add_job(
    func=trigger_full_pipeline_automatically,
    trigger="cron",
    day_of_week="mon,wed,sat",  # Solo días de sorteo de Powerball
    hour=23,                    # 11 PM ET
    minute=29,                  # 11:29 PM - 30 minutos después del sorteo
    timezone="America/New_York",
    id="post_drawing_pipeline",
    max_instances=1,
    coalesce=True
)
```

### 2. Ejecución del Pipeline
El pipeline se ejecuta de forma **asíncrona** utilizando subprocess para máxima estabilidad:

```python
# Ejecuta main.py en subprocess para producción
cmd = ["python", "main.py"]
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=900,  # 15 minutos timeout para Replit
    cwd=os.getcwd()
)
```

### 3. Monitoreo en Tiempo Real
El sistema incluye monitoreo completo del estado del pipeline:

```python
# Variables globales de monitoreo en src/api.py
pipeline_executions = {}  # Track running pipeline executions
pipeline_logs = []        # Store recent pipeline logs

# Estado típico de ejecución
pipeline_executions[execution_id] = {
    "execution_id": execution_id,
    "status": "running",
    "start_time": current_time.isoformat(),
    "current_step": "prediction_generation",
    "steps_completed": 4,
    "total_steps": 5,
    "num_predictions": 50
}
```

## Sistema de Generación de Predicciones

### IntelligentGenerator Optimizado
El sistema actual utiliza el `IntelligentGenerator` como motor principal:

**Características implementadas**:
- **15 features estándar** de machine learning
- **Multi-criteria scoring** con 4 componentes principales
- **Pesos adaptativos** basados en performance histórica
- **Generación determinística** para consistencia

**Implementación actual**:
```python
class IntelligentGenerator:
    def generate_play(self) -> dict:
        # Genera una jugada usando scoring multi-criterio
        candidates = self._generate_candidates(2500)  # 2500 candidatos
        scored_candidates = []

        for candidate in candidates:
            score = self.calculate_multi_criteria_score(
                candidate['numbers'], 
                candidate['powerball']
            )
            scored_candidates.append({
                'numbers': candidate['numbers'],
                'powerball': candidate['powerball'],
                'score': score['score_total'],
                'score_details': score['score_details']
            })

        # Retorna el mejor candidato
        return max(scored_candidates, key=lambda x: x['score'])
```

### Sistema de Scoring Multi-Criterio Actual
```python
DEFAULT_WEIGHTS = {
    'probability': 0.40,      # 40% - Probabilidades del modelo ML
    'diversity': 0.25,        # 25% - Diversidad y balance
    'historical': 0.20,       # 20% - Patrones históricos
    'risk_adjusted': 0.15     # 15% - Ajuste por riesgo
}
```

## API y Dashboard Integration

### Endpoints Principales Activos
```python
# Endpoints implementados en src/api_pipeline_endpoints.py
POST /api/v1/pipeline/execute       # Ejecutar pipeline manual
GET  /api/v1/pipeline/status        # Estado del pipeline
GET  /api/v1/pipeline/history       # Historial de ejecuciones

# Endpoints de predicciones en src/api_prediction_endpoints.py
GET  /api/v1/predictions/history    # Historial de predicciones
GET  /api/v1/predictions/latest     # Últimas predicciones

# Dashboard endpoints en src/api_dashboard_endpoints.py
GET  /api/v1/dashboard/next-drawing # Próximo sorteo
GET  /api/v1/dashboard/predictions  # Predicciones para dashboard
```

### Dashboard Frontend Actual
El dashboard (`frontend/dashboard.html`) muestra:

1. **Próximo Sorteo**: Countdown timer con información en tiempo real
2. **Predicciones AI**: Top 10 predicciones con scoring detallado
3. **Execution History**: Historial completo de ejecuciones del pipeline
4. **System Health**: CPU, memoria, y estado de componentes

**Actualización en tiempo real**:
```javascript
// Actualización cada 30 segundos
setInterval(async () => {
    await Promise.all([
        updateNextDrawing(),
        updatePredictions(),
        updateExecutionHistory(),
        updateSystemHealth()
    ]);
}, 30000);
```

## Optimizaciones para Replit

### 1. Gestión de Recursos
- **Timeout de 15 minutos** para evitar timeouts de Replit
- **Batches de 50 predicciones** para optimizar memoria
- **Subprocess execution** para estabilidad
- **Async/await** para operaciones no-bloqueantes

### 2. Base de Datos Optimizada
- **SQLite local** para máxima velocidad
- **Índices optimizados** en tablas principales
- **Cleanup automático** de datos antiguos
- **Backup automático** antes de operaciones críticas

### 3. Pipeline Simplificado
- **5 pasos en lugar de 7** para reducir tiempo de ejecución
- **Ensemble único** en lugar de múltiples modelos
- **Scoring optimizado** con criterios esenciales
- **Validación mínima** para velocidad

## Métricas de Performance Actual

### Tiempos de Ejecución Típicos
- **Pipeline completo**: 3-5 minutos
- **Generación de 50 predicciones**: 1-2 minutos
- **Data update**: 10-30 segundos
- **API response time**: < 2 segundos

### Recursos Utilizados
- **CPU**: 60-80% durante ejecución del pipeline
- **Memoria**: 70-90% durante generación de predicciones
- **Almacenamiento**: < 100MB para base de datos completa

### Programación Automática
- **Ejecución automática**: Lunes, Miércoles, Sábado a las 11:29 PM ET
- **30 minutos después del sorteo** para incluir resultados más recientes
- **Timezone fijo**: America/New_York para consistencia

## Estado del Sistema Actual

### Componentes Operativos
✅ **Pipeline Orchestrator** - Funcional con 5 pasos optimizados  
✅ **Intelligent Generator** - Generando 50 predicciones por ejecución  
✅ **Database Manager** - SQLite optimizada funcionando  
✅ **API Server** - FastAPI en puerto 3000  
✅ **Dashboard Frontend** - Interfaz web completa  
✅ **Scheduler** - APScheduler con timezone ET configurado  
✅ **Subprocess Execution** - Ejecución robusta del pipeline  

### Arquitectura de Deployment
- **Replit Cloud**: Deployment principal en https://replit.com/@orlandobatistac/SHIOL
- **Port 3000**: Configurado para acceso público
- **Uvicorn ASGI**: Servidor de producción
- **Auto-restart**: Configuración de workflows para reinicio automático

---

## Flujo Actual Completo (Resumen)

1. **Trigger**: Scheduler ejecuta automáticamente después de cada sorteo
2. **Pipeline**: 5 pasos optimizados en < 5 minutos
3. **Predicciones**: Genera exactamente 50 Smart AI predictions
4. **Storage**: Guarda en SQLite con metadata completo
5. **Frontend**: Dashboard muestra resultados en tiempo real
6. **Monitoring**: Sistema de logs y métricas de performance

**Próxima ejecución programada**: Sábado 13 de agosto a las 11:29 PM ET

---

*Documento actualizado reflejando el estado actual del sistema SHIOL+ v6.1*  
*Última actualización: 2025-01-09*  
*Replit Deployment: https://replit.com/@orlandobatistac/SHIOL*