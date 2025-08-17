
# SHIOL+ v6.1: Sistema de Análisis de Lotería con IA Optimizado

Un sistema inteligente y optimizado diseñado para analizar datos históricos de Powerball y generar predicciones usando técnicas avanzadas de Machine Learning con un pipeline optimizado y una interfaz web moderna.

**🌐 Demo en Vivo**: [https://shiolplus.replit.app](https://shiolplus.replit.app)

## 🚀 Descripción del Proyecto

**SHIOL+ (System for Hybrid Intelligence Optimization and Learning)** es una plataforma de IA optimizada que analiza datos históricos de la lotería Powerball para identificar patrones estadísticos y generar predicciones inteligentes. El sistema combina modelos de machine learning con algoritmos adaptativos, proporcionando un pipeline completo de 7 pasos para procesamiento de datos, generación de predicciones, evaluación y análisis de rendimiento.

La versión 6.1 introduce **optimización del pipeline** con un código optimizado, rendimiento mejorado y enfoque en el flujo principal de predicciones que alimenta la interfaz frontend.

> **Importante**: Esta herramienta está creada para fines educativos, de investigación y entretenimiento. La lotería es un juego de azar, y SHIOL+ **no garantiza premios o ganancias**. Siempre juega responsablemente.

## ✨ Características Principales

### 🤖 Sistema de Pipeline con IA Optimizado
- **Pipeline Automatizado de 7 Pasos**: Actualización de datos, análisis adaptativo, optimización de pesos, generación de predicciones, evaluación, validación y análisis de rendimiento
- **Predicciones Inteligentes**: 100 predicciones optimizadas por ejecución usando ensemble machine learning
- **Programación Automática**: Se ejecuta 30 minutos después de cada sorteo de Powerball (Lun/Mié/Sáb a las 11:29 PM ET)
- **Aprendizaje Adaptativo**: Mejora continua basada en datos de rendimiento histórico
- **Evaluación con Resultados Reales**: Compara predicciones contra sorteos oficiales y calcula premios ganados

### 🌐 Interfaz Web Moderna
- **Dashboard en Tiempo Real**: Estado del pipeline en vivo, visualización de predicciones y monitoreo del sistema
- **Interfaz Pública**: Diseño limpio y responsive para ver las últimas predicciones
- **Contador Regresivo**: Cuenta regresiva en tiempo real al próximo sorteo de Powerball
- **Análisis de Evaluación**: Métricas de evaluación de predicciones, tasas de acierto y premios ganados
- **API RESTful**: Suite completa de API para integración y automatización

### 📊 Motor de Predicción Inteligente
- **Modelo Ensemble**: Múltiples algoritmos de ML trabajando juntos para máxima precisión
- **Ingeniería de Features**: 15+ características engineered de datos históricos de lotería
- **Pesos Dinámicos**: Optimización adaptativa de pesos basada en rendimiento reciente
- **Validación de Calidad**: Validación automática del modelo y reentrenamiento cuando es necesario
- **Evaluación Automática**: Sistema que evalúa predicciones contra resultados oficiales

### 🔧 Arquitectura del Sistema
- **Código Optimizado**: Optimizado para rendimiento y mantenibilidad
- **Base de Datos SQLite**: Almacenamiento eficiente con limpieza y optimización automática
- **Backend FastAPI**: API de alto rendimiento con documentación automática
- **Programación Automatizada**: APScheduler para ejecución confiable y consciente de zona horaria
- **Logging Comprehensivo**: Seguimiento detallado de ejecución y manejo de errores

## 🏃‍♂️ Inicio Rápido

### Configuración Simple y Ejecución

```bash
# Instalar dependencias
pip install -r requirements.txt

# Inicializar el sistema
python src/database.py

# Ejecutar el pipeline completo
python main.py

# Iniciar el servidor web
python main.py --server --host 0.0.0.0 --port 3000
```

### Acceder al Sistema

Después de iniciar el servidor:

- **Interfaz Pública**: `http://localhost:3000/` - Ver últimas predicciones y cuenta regresiva
- **Demo en Vivo**: [https://shiolplus.replit.app](https://shiolplus.replit.app) - Demostración pública

## 🔄 Flujo de Trabajo del Pipeline

El sistema SHIOL+ sigue un pipeline optimizado de 7 pasos:

### Paso 1: Actualización de Datos
- Descarga los últimos resultados de sorteos de Powerball
- Valida y almacena nuevos datos en la base de datos SQLite
- Carga datos históricos para análisis

### Paso 2: Análisis Adaptativo
- Analiza el rendimiento de predicciones recientes
- Identifica patrones en combinaciones ganadoras
- Actualiza parámetros de aprendizaje adaptativo

### Paso 3: Optimización de Pesos
- Optimiza pesos de scoring basado en datos de rendimiento
- Usa algoritmo de evolución diferencial para optimización
- Balancea factores de probabilidad, diversidad, históricos y de riesgo

### Paso 4: Generación de Predicciones ⭐
- **Función Principal**: Genera 100 predicciones Smart AI
- **Target Dating**: Calcula automáticamente la fecha del próximo sorteo
- **Scoring Ensemble**: Evaluación multi-criterio de cada combinación
- **Aseguramiento de Calidad**: Validación del modelo y reentrenamiento automático si es necesario

### Paso 5: Evaluación de Predicciones 🎯
- **Evaluación Automática**: Compara predicciones contra resultados oficiales de sorteos
- **Cálculo de Premios**: Determina premios ganados según las reglas de Powerball
- **Actualización de Base de Datos**: Marca predicciones como evaluadas con resultados
- **Análisis de Rendimiento**: Rastrea tasas de acierto y métricas de precisión

### Paso 6: Validación Histórica
- Valida predicciones recientes contra resultados reales
- Alimenta resultados de vuelta al sistema de aprendizaje adaptativo
- Proporciona métricas para optimización del sistema

### Paso 7: Análisis de Rendimiento
- Genera métricas comprehensivas de rendimiento
- Analiza tendencias en períodos de 1, 7 y 30 días
- Proporciona insights para optimización del sistema

## 🌐 Características de la Interfaz Web

### Dashboard Público
- **Cuenta Regresiva al Próximo Sorteo**: Cuenta regresiva en tiempo real con manejo de zona horaria
- **Últimas Predicciones**: Predicciones con mayor puntuación y ratings de confianza
- **Resultados de Evaluación**: Muestra premios ganados en predicciones evaluadas
- **Estado del Sistema**: Salud del pipeline y tiempo de última ejecución
- **Responsive Móvil**: Optimizado para todos los tamaños de dispositivo

### Endpoints de API
- `GET /api/v1/public/featured-predictions` - Últimas predicciones de IA
- `GET /api/v1/public/next-drawing` - Información del próximo sorteo
- `GET /api/v1/pipeline/status` - Estado de ejecución del pipeline
- `GET /api/v1/system/stats` - Métricas de salud del sistema

## 📈 Evaluación y Análisis de Rendimiento

### Estado Actual del Sistema
- **Base de Datos**: 36+ sorteos históricos de Powerball
- **Modelo**: Ensemble entrenado con múltiples algoritmos de ML
- **Predicciones**: Smart AI genera 100 predicciones por ejecución
- **Ejecución**: Automática 30 minutos después de cada sorteo
- **Evaluación**: Seguimiento continuo de predicciones vs resultados reales

### Calidad de Predicciones y Evaluación
- **Algoritmo de Scoring**: Sistema de evaluación multi-criterio
- **Umbrales de Calidad**: Filtrado automático de predicciones de baja calidad
- **Optimización de Diversidad**: Asegura combinaciones de números variadas
- **Evaluación de Premios**: Calcula premios reales ganados según reglas de Powerball
- **Análisis de ROI**: Seguimiento de retorno de inversión en predicciones

## 🛠️ Especificaciones Técnicas

### Tecnologías Core
- **Backend**: Python 3.8+, FastAPI, SQLite
- **Machine Learning**: Scikit-learn, XGBoost, Pandas, NumPy
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Programación**: APScheduler con consciencia de zona horaria
- **API**: Diseño RESTful con documentación automática

### Requerimientos del Sistema
- **Mínimo**: Python 3.8+, 2GB RAM, 1GB espacio en disco
- **Recomendado**: Python 3.10+, 4GB RAM, almacenamiento SSD
- **Red**: Conexión a internet para actualizaciones de datos
- **Navegador**: Navegador moderno para interfaz web

### Esquema de Base de Datos
```sql
-- Tablas principales (optimizadas)
powerball_draws       -- Resultados históricos de sorteos
predictions_log       -- Predicciones generadas con scores y evaluaciones
pipeline_executions   -- Historial de ejecuciones y estado
adaptive_weights      -- Parámetros dinámicos de scoring
```

## 🚀 Opciones de Deployment

### Desarrollo Local
```bash
# Clonar repositorio
git clone <repository-url>
cd shiol-plus

# Instalar dependencias
pip install -r requirements.txt

# Inicializar base de datos
python src/database.py

# Ejecutar pipeline completo
python main.py

# Iniciar servidor web
python main.py --server --host 0.0.0.0 --port 3000
```

### Deployment en Replit (Recomendado)
El sistema está optimizado para deployment en Replit con:
- Gestión automática de dependencias
- Port forwarding (puerto 3000)
- Generación automática de URL pública
- Programación automática
- Persistencia de base de datos

**Demo en Vivo**: [https://shiolplus.replit.app](https://shiolplus.replit.app)

## 📋 Interfaz de Línea de Comandos

### Operaciones del Pipeline
```bash
# Ejecución completa del pipeline
python main.py

# Pasos específicos
python main.py --step data          # Solo actualización de datos
python main.py --step prediction    # Solo generación de predicciones
python main.py --step evaluation    # Solo evaluación de predicciones

# Estado del sistema
python main.py --status

# Servidor web
python main.py --server --host 0.0.0.0 --port 3000
```

## 🔧 Configuración

### Configuración del Sistema (`config/config.ini`)
```ini
[pipeline]
execution_days = 0,2,5  # Lunes, Miércoles, Sábado
execution_time = 23:29   # 11:29 PM ET (30 min después del sorteo)
timezone = America/New_York
auto_execution_enabled = true

[predictions]
default_count = 100
method = smart_ai

[scoring]
probability_weight = 40
diversity_weight = 25
historical_weight = 20
risk_weight = 15

[evaluation]
prize_thresholds = 4,7,100,50000  # Umbrales de premios de Powerball
auto_evaluation_enabled = true
```

## 📊 Documentación de API

### Endpoints Públicos
- `GET /` - Interfaz web principal
- `GET /api/v1/public/featured-predictions` - Últimas predicciones
- `GET /api/v1/public/next-drawing` - Cuenta regresiva del sorteo
- `GET /api/v1/system/info` - Información del sistema

### Endpoints del Pipeline
- `GET /api/v1/pipeline/status` - Estado actual del pipeline
- `POST /api/v1/pipeline/trigger` - Ejecución manual del pipeline
- `GET /api/v1/pipeline/health` - Verificación de salud del sistema

### Ejemplo de Integración
```python
import requests

# Obtener últimas predicciones
response = requests.get('https://shiolplus.replit.app/api/v1/public/featured-predictions')
predictions = response.json()

# Verificar próximo sorteo
response = requests.get('https://shiolplus.replit.app/api/v1/public/next-drawing')
next_drawing = response.json()

# Ver evaluaciones de predicciones
for pred in predictions['predictions']:
    if 'prize_won' in pred:
        print(f"Predicción {pred['prediction_id']}: Premio ganado ${pred['prize_won']}")
```

## 🧠 Detalles de Machine Learning

### Arquitectura del Modelo
- **Enfoque Ensemble**: Múltiples algoritmos con votación ponderada
- **Ingeniería de Features**: 15+ características calculadas de datos históricos
- **Datos de Entrenamiento**: Todo el historial disponible de sorteos de Powerball
- **Validación**: Cross-validation con splits históricos
- **Optimización**: Ajuste continuo de parámetros basado en rendimiento

### Proceso de Evaluación
1. **Comparación Automática**: Predicciones vs resultados oficiales de sorteos
2. **Cálculo de Premios**: Determinación de premios según reglas de Powerball
3. **Actualización de Datos**: Marcado de predicciones como evaluadas
4. **Análisis de Rendimiento**: Cálculo de métricas de precisión y ROI
5. **Feedback al Sistema**: Alimentación de resultados para mejora continua

## 🔄 Automatización y Programación

### Ejecución Automática
- **Horario**: 30 minutos después de cada sorteo de Powerball
- **Días de Sorteo**: Lunes, Miércoles, Sábado a las 10:59 PM ET
- **Ejecuciones del Pipeline**: Lunes 11:29 PM, Miércoles 11:29 PM, Sábado 11:29 PM ET
- **Zona Horaria**: America/New_York (maneja DST automáticamente)
- **Protección de Solapamiento**: Previene múltiples ejecuciones simultáneas

### Ejecución Manual
- **CLI**: `python main.py` para pipeline completo
- **API**: `POST /api/v1/pipeline/trigger` para ejecución programática

## 📈 Monitoreo de Rendimiento

### Métricas en Tiempo Real
- **Estado del Pipeline**: Estado actual de ejecución y progreso
- **Calidad de Predicciones**: Distribuciones de scoring y niveles de confianza
- **Resultados de Evaluación**: Premios ganados, tasas de acierto, análisis de ROI
- **Salud del Sistema**: Estado de base de datos, validez del modelo, historial de ejecución

### Dashboard de Análisis
- **Historial de Ejecución**: Tasas de éxito, timing, seguimiento de errores
- **Rendimiento de Predicciones**: Tasas de acierto, categorías de premios, análisis de ROI
- **Recursos del Sistema**: Tamaño de base de datos, rendimiento del modelo, tiempos de respuesta de API

## 🔒 Seguridad y Confiabilidad

### Seguridad de Datos
- **Almacenamiento Local**: Todos los datos almacenados localmente en base de datos SQLite
- **Sin Dependencias Externas**: Predicciones generadas completamente de forma local
- **API Segura**: Configuración CORS para acceso controlado
- **Validación de Entrada**: Validación comprehensiva de todas las entradas

### Confiabilidad del Sistema
- **Manejo de Errores**: Manejo comprehensivo de excepciones con recuperación
- **Logging**: Logs detallados de ejecución para debugging y monitoreo
- **Sistema de Backup**: Backups automáticos de base de datos antes de operaciones importantes
- **Verificaciones de Salud**: Monitoreo continuo de componentes del sistema

## 📝 Contribuir

¡Agradecemos contribuciones a SHIOL+ v6.1! Por favor sigue estas directrices:

### Proceso de Desarrollo
1. Fork del repositorio
2. Crear rama de feature
3. Hacer cambios con tests
4. Enviar pull request

### Estándares de Código
- Seguir PEP 8 para código Python
- Usar nombres significativos para variables y funciones
- Agregar docstrings comprehensivos
- Incluir tests para nuevas características
- Actualizar documentación para cambios

## 📄 Licencia

Uso privado – Todos los derechos reservados.

## 🏆 Créditos

- **Creador**: Orlando Batista
- **Versión**: 6.1 (Pipeline Optimizado con Evaluación)
- **Última Actualización**: Agosto 2025
- **Demo en Vivo**: [https://shiolplus.replit.app](https://shiolplus.replit.app)

---

**SHIOL+ v6.1** - Análisis de lotería con IA optimizado con rendimiento optimizado, predicciones inteligentes y evaluación automática de resultados.

**🌐 Experimenta SHIOL+ en Vivo**: [https://shiolplus.replit.app](https://shiolplus.replit.app)

Para soporte, documentación y actualizaciones, visita el repositorio del proyecto.

**⚡ Optimizado para Rendimiento • 🤖 Powered by AI • 🎯 Built for Accuracy • 🏆 Evaluación Automática**
