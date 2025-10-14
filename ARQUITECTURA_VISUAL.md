# 🏗️ ARQUITECTURA VISUAL - SHIOL+ v4.0

## 📐 DIAGRAMA DE ARQUITECTURA DEL SISTEMA

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLIENTE / USUARIO FINAL                             │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Browser    │  │  Mobile PWA  │  │   Desktop    │  │   Tablet     │  │
│  │   Chrome     │  │   Safari     │  │   Firefox    │  │    Edge      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼──────────────────┼──────────────────┼──────────────────┼─────────┘
          │                  │                  │                  │
          └──────────────────┴──────────────────┴──────────────────┘
                                      │
                                   HTTPS
                                      │
┌─────────────────────────────────────┼─────────────────────────────────────┐
│                           CAPA DE FRONTEND                                  │
│                                     │                                       │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │                       Static Files (CDN)                            │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │   │
│  │  │  index.html  │  │  styles.css  │  │   JavaScript Modules    │ │   │
│  │  │  status.html │  │dark-theme.css│  │  • auth-manager.js      │ │   │
│  │  │payment-      │  │              │  │  • public.js            │ │   │
│  │  │ success.html │  └──────────────┘  │  • countdown.js         │ │   │
│  │  └──────────────┘                    │  • device-fingerprint.js│ │   │
│  │                                       └──────────────────────────┘ │   │
│  │  ┌────────────────────────────────────────────────────────────┐   │   │
│  │  │              Service Worker v2.2.4 (PWA)                   │   │   │
│  │  │  • Cache-First Strategy (CSS, JS, Images)                  │   │   │
│  │  │  • Network-First Strategy (API Calls)                      │   │   │
│  │  │  • Offline Support & Fallback                              │   │   │
│  │  └────────────────────────────────────────────────────────────┘   │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────┬───────────────────────────────────┘
                                          │
                                    REST API (JSON)
                                          │
┌─────────────────────────────────────────┼───────────────────────────────────┐
│                         CAPA DE API (FastAPI)                                │
│                                         │                                     │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                       API Gateway / Router                             │  │
│  │                          (main: api.py)                                │  │
│  └───────────────┬───────────────────────────────────────────────────────┘  │
│                  │                                                           │
│  ┌───────────────┴───────────────────────────────────────────────────────┐  │
│  │                         Middleware Layer                               │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐  │  │
│  │  │  CORS        │  │  Auth        │  │  Rate Limiting             │  │  │
│  │  │  Middleware  │  │  Middleware  │  │  (Recomendado - Pendiente) │  │  │
│  │  └──────────────┘  └──────────────┘  └────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                         │                                     │
│  ┌─────────────────────────────────────┴───────────────────────────────┐    │
│  │                      API Endpoint Routers                            │    │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────┐  │    │
│  │  │  /api/v1/auth   │  │  /api/v1/public │  │  /api/v1/billing   │  │    │
│  │  │  • register     │  │  • predictions  │  │  • checkout-session│  │    │
│  │  │  • login        │  │  • draws        │  │  • webhook         │  │    │
│  │  │  • logout       │  │  • jackpot      │  │  • subscription    │  │    │
│  │  │  • status       │  │  • stats        │  │  • cancel          │  │    │
│  │  └─────────────────┘  └─────────────────┘  └────────────────────┘  │    │
│  │                                                                      │    │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────┐  │    │
│  │  │/api/v1/predict  │  │  /api/v1/tickets│  │  /api/v1/draws     │  │    │
│  │  │  • latest       │  │  • verify       │  │  • recent          │  │    │
│  │  │  • by-draw      │  │  • extract      │  │  • by-date         │  │    │
│  │  │  • history      │  │  • history      │  │  • latest          │  │    │
│  │  └─────────────────┘  └─────────────────┘  └────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────┬───────────────────────────────────┘
                                          │
                                          │
┌─────────────────────────────────────────┼───────────────────────────────────┐
│                      CAPA DE LÓGICA DE NEGOCIO                               │
│                                         │                                     │
│  ┌──────────────────────────────────────┴────────────────────────────────┐  │
│  │                    Core Business Services                              │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────┐    │  │
│  │  │  Auth Service  │  │  Billing       │  │  Prediction Service  │    │  │
│  │  │  • JWT         │  │  Service       │  │  • ML Predictor      │    │  │
│  │  │  • Premium Pass│  │  • Stripe      │  │  • Generator         │    │  │
│  │  │  • Sessions    │  │  • Webhooks    │  │  • Evaluator         │    │  │
│  │  │  • Quotas      │  │  • Subs        │  │  • Scoring           │    │  │
│  │  └────────────────┘  └────────────────┘  └──────────────────────┘    │  │
│  │                                                                        │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────┐    │  │
│  │  │  Ticket        │  │  Data Loader   │  │  Date Manager        │    │  │
│  │  │  Processor     │  │  Service       │  │  • Timezone Utils    │    │  │
│  │  │  • OCR Gemini  │  │  • MUSL API    │  │  • Next Draw Calc    │    │  │
│  │  │  • Extraction  │  │  • NY State API│  │  • ET Time Sync      │    │  │
│  │  │  • Verification│  │  • Transform   │  │                      │    │  │
│  │  └────────────────┘  └────────────────┘  └──────────────────────┘    │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                         │                                     │
│  ┌──────────────────────────────────────┴────────────────────────────────┐  │
│  │                  Machine Learning Pipeline                             │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  Pipeline Orchestrator (main.py)                                 │  │  │
│  │  │                                                                   │  │  │
│  │  │  Step 1: Data Update      ─────▶  Update from MUSL API          │  │  │
│  │  │  Step 2: Adaptive Analysis ─────▶ [DEPRECATED in v4.0]          │  │  │
│  │  │  Step 3: Weight Optimization ───▶  Adjust model weights         │  │  │
│  │  │  Step 4: Prediction Generation ─▶  Generate 100 predictions     │  │  │
│  │  │  Step 5: Historical Validation ─▶  Compare vs actual results    │  │  │
│  │  │  Step 6: Performance Analysis ──▶  Calculate metrics            │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  ML Components                                                   │  │  │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │  │  │
│  │  │  │  Predictor   │  │  Feature     │  │  Intelligent         │  │  │  │
│  │  │  │  (XGBoost)   │  │  Engineer    │  │  Generator           │  │  │  │
│  │  │  │  • 5 Models  │  │  • 15 Features│ │  • Deterministic     │  │  │  │
│  │  │  │  • Ensemble  │  │  • Transform  │  │  • Scoring           │  │  │  │
│  │  │  └──────────────┘  └──────────────┘  └──────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────┬───────────────────────────────────┘
                                          │
                                          │
┌─────────────────────────────────────────┼───────────────────────────────────┐
│                       CAPA DE PERSISTENCIA                                   │
│                                         │                                     │
│  ┌──────────────────────────────────────┴────────────────────────────────┐  │
│  │                    Database Layer (database.py)                        │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │  │
│  │  │                      SQLite Database                              │ │  │
│  │  │                   (data/shiolplus.db)                             │ │  │
│  │  │                                                                    │ │  │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐   │ │  │
│  │  │  │ powerball_draws │  │ predictions_log │  │ users          │   │ │  │
│  │  │  │ (2,235+ rows)   │  │ (ML outputs)    │  │ (registered)   │   │ │  │
│  │  │  └─────────────────┘  └─────────────────┘  └────────────────┘   │ │  │
│  │  │                                                                    │ │  │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐   │ │  │
│  │  │  │performance_     │  │stripe_          │  │premium_passes  │   │ │  │
│  │  │  │tracking         │  │subscriptions    │  │(guest premium) │   │ │  │
│  │  │  └─────────────────┘  └─────────────────┘  └────────────────┘   │ │  │
│  │  │                                                                    │ │  │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐   │ │  │
│  │  │  │device_          │  │ticket_          │  │reliable_plays  │   │ │  │
│  │  │  │fingerprints     │  │verifications    │  │(best combos)   │   │ │  │
│  │  │  └─────────────────┘  └─────────────────┘  └────────────────┘   │ │  │
│  │  │                                                                    │ │  │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐   │ │  │
│  │  │  │pattern_analysis │  │adaptive_weights │  │jti_revocation  │   │ │  │
│  │  │  │(ML patterns)    │  │(model weights)  │  │(JWT blacklist) │   │ │  │
│  │  │  └─────────────────┘  └─────────────────┘  └────────────────┘   │ │  │
│  │  │                                                                    │ │  │
│  │  │  • WAL Mode Enabled                                               │ │  │
│  │  │  • Auto Vacuum Configured                                         │ │  │
│  │  │  • Indexed for Performance                                        │ │  │
│  │  └──────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                        │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │  │
│  │  │              Scheduler Database (APScheduler)                     │ │  │
│  │  │                  (data/scheduler.db)                              │ │  │
│  │  │  • Job Definitions                                                │ │  │
│  │  │  • Execution History                                              │ │  │
│  │  │  • Persistent Scheduling                                          │ │  │
│  │  └──────────────────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────┬───────────────────────────────────┘
                                          │
                                          │
┌─────────────────────────────────────────┼───────────────────────────────────┐
│                     CAPA DE INTEGRACIÓN EXTERNA                              │
│                                         │                                     │
│  ┌──────────────────────────────────────┴────────────────────────────────┐  │
│  │                      External Services                                 │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────┐    │  │
│  │  │  MUSL API      │  │  Stripe        │  │  Google Gemini AI    │    │  │
│  │  │  (Primary)     │  │  Payment       │  │  (Ticket OCR)        │    │  │
│  │  │  • /v3/numbers │  │  Processing    │  │  • Image Analysis    │    │  │
│  │  │  • /v3/        │  │  • Checkout    │  │  • Number Extraction │    │  │
│  │  │    grandprize  │  │  • Webhooks    │  │  • Text Recognition  │    │  │
│  │  │  • X-API-Key   │  │  • Subs Mgmt   │  │                      │    │  │
│  │  └────────────────┘  └────────────────┘  └──────────────────────┘    │  │
│  │                                                                        │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────┐    │  │
│  │  │  NY State API  │  │  Email Service │  │  Monitoring          │    │  │
│  │  │  (Fallback)    │  │  (Recomendado) │  │  (Recomendado)       │    │  │
│  │  │  • Open Data   │  │  • SendGrid    │  │  • Sentry            │    │  │
│  │  │  • JSON API    │  │  • Mailgun     │  │  • Uptime Robot      │    │  │
│  │  │  • No Auth Req │  │  • SMTP        │  │  • Prometheus        │    │  │
│  │  └────────────────┘  └────────────────┘  └──────────────────────┘    │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘

                                          │
                                          │
┌─────────────────────────────────────────┼───────────────────────────────────┐
│                      CAPA DE SCHEDULING                                      │
│                                         │                                     │
│  ┌──────────────────────────────────────┴────────────────────────────────┐  │
│  │                   APScheduler (Async)                                  │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │  │
│  │  │  Automated Jobs                                                   │ │  │
│  │  │  ┌────────────────────────────────────────────────────────────┐  │ │  │
│  │  │  │  trigger_full_pipeline_automatically()                     │  │ │  │
│  │  │  │  • Timezone: America/New_York                              │  │ │  │
│  │  │  │  • Days: Monday, Wednesday, Saturday                       │  │ │  │
│  │  │  │  • Time: 23:30 (11:30 PM ET)                               │  │ │  │
│  │  │  │  • 30 minutes after draw (10:59 PM ET)                     │  │ │  │
│  │  │  │  • Coalesce: True (merge missed runs)                      │  │ │  │
│  │  │  │  • Max Instances: 1 (prevent overlap)                      │  │ │  │
│  │  │  └────────────────────────────────────────────────────────────┘  │ │  │
│  │  │                                                                   │ │  │
│  │  │  ┌────────────────────────────────────────────────────────────┐  │ │  │
│  │  │  │  update_data_automatically()                               │  │ │  │
│  │  │  │  • Fetch from MUSL API                                     │  │ │  │
│  │  │  │  • Fallback to NY State API                                │  │ │  │
│  │  │  │  • Update database with new draws                          │  │ │  │
│  │  │  └────────────────────────────────────────────────────────────┘  │ │  │
│  │  └──────────────────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🔄 FLUJO DE DATOS PRINCIPAL

### 1. Flujo de Predicción de Usuario

```
┌──────────┐
│ Usuario  │
│ Visita   │
│ Website  │
└────┬─────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Frontend carga index.html                │
│ Service Worker activa cache              │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ JavaScript solicita predicciones         │
│ GET /api/v1/public/predictions/latest    │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Middleware valida autenticación          │
│ • Verifica JWT/Cookie                    │
│ • Calcula cuota disponible (día-based)   │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ API consulta base de datos               │
│ • SELECT TOP N predictions               │
│ • JOIN con draw info                     │
│ • Aplica límite según tier usuario       │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Respuesta JSON con predicciones          │
│ • Números rankeados                      │
│ • Scores de confianza                    │
│ • Info próximo sorteo                    │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Frontend renderiza predicciones          │
│ • Muestra Top 10 (o más si premium)      │
│ • Actualiza cuota restante               │
│ • Countdown próximo sorteo               │
└──────────────────────────────────────────┘
```

### 2. Flujo de Registro y Upgrade a Premium

```
┌──────────┐
│ Usuario  │
│ Click    │
│"Register"│
└────┬─────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Modal de registro se abre                │
│ • Formulario: username, email, password  │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ POST /api/v1/auth/register               │
│ • Valida datos                           │
│ • Hash password (bcrypt)                 │
│ • Crea usuario en DB                     │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Auto-login + Set JWT Cookie              │
│ • Genera JWT token                       │
│ • Set HttpOnly cookie                    │
│ • Retorna user data                      │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Usuario ahora es "Free Tier"             │
│ • 7 insights/semana (día-based)          │
│ • Sábado: 5 insights                     │
│ • Martes/Jueves: 1 insight               │
└────┬─────────────────────────────────────┘
     │
     │ (Usuario decide upgrade)
     ▼
┌──────────────────────────────────────────┐
│ Click "Unlock Premium" ($9.99/año)      │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ POST /api/v1/billing/                    │
│      create-checkout-session             │
│ • Backend llama Stripe API               │
│ • Crea Checkout Session                  │
│ • Retorna session URL                    │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Redirect a Stripe Checkout               │
│ • Usuario ingresa tarjeta                │
│ • Stripe procesa pago                    │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Stripe webhook → Backend                 │
│ POST /api/v1/billing/webhook             │
│ Event: checkout.session.completed        │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Backend actualiza usuario                │
│ • is_premium = true                      │
│ • premium_expires_at = +1 año            │
│ • Guarda subscription en DB              │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Redirect a /payment-success.html         │
│ • Usuario ahora es Premium               │
│ • 100 insights por sorteo                │
└──────────────────────────────────────────┘
```

### 3. Flujo de ML Pipeline (Automático)

```
┌──────────────────────────────────────────┐
│ APScheduler trigger (11:30 PM ET)        │
│ • Cada Lun/Mié/Sáb                       │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Step 1: Data Update                      │
│ • Fetch MUSL API /v3/numbers             │
│ • Fallback NY State si falla             │
│ • Parse y transform a DataFrame          │
│ • Bulk insert nuevos draws a DB          │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Step 2: Weight Optimization              │
│ • Retrieve recent performance metrics    │
│ • Calculate model accuracy per classifier│
│ • Adjust weights based on performance    │
│ • Save new weights to adaptive_weights   │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Step 3: Prediction Generation            │
│ • Load all historical draws              │
│ • Feature engineering (15+ features)     │
│ • Train XGBoost ensemble (5 models)      │
│ • Generate 100 predictions               │
│ • Score and rank combinations            │
│ • Save to predictions_log table          │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Step 4: Historical Validation            │
│ • Compare predictions vs actual results  │
│ • Calculate matches (main + PB)          │
│ • Detect winning combinations            │
│ • Calculate prize tiers                  │
│ • Save to performance_tracking           │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Step 5: Performance Analysis             │
│ • Calculate win rate (30/7/1 days)       │
│ • Average accuracy metrics               │
│ • Prize distribution stats               │
│ • Generate insights and trends           │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Pipeline Complete                        │
│ • Log execution summary                  │
│ • Update pipeline_executions table       │
│ • New predictions available for users    │
└──────────────────────────────────────────┘
```

### 4. Flujo de Verificación de Ticket

```
┌──────────┐
│ Usuario  │
│ Upload   │
│ Ticket   │
│ Image    │
└────┬─────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Frontend: Captura imagen (cámara/file)   │
│ • Resize to max 1024x1024                │
│ • Compress to reduce size                │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ POST /api/v1/tickets/verify              │
│ • Multipart form data                    │
│ • Image file + draw date (opcional)      │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Backend: Process image                   │
│ • Validate format (jpg, png)             │
│ • Optimize for Gemini AI                 │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Call Google Gemini AI API                │
│ • Send image with OCR prompt             │
│ • Prompt: "Extract Powerball numbers"    │
│ • Request JSON response                  │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Gemini AI returns extracted numbers      │
│ • 5 main numbers (1-69)                  │
│ • 1 powerball (1-26)                     │
│ • Confidence score                       │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Validate extracted numbers               │
│ • Check range (1-69, 1-26)               │
│ • Check format (5 main + 1 PB)           │
│ • Check for duplicates                   │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Query database for draw results          │
│ • If draw_date provided, query exact     │
│ • Else, check recent draws               │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Compare ticket vs actual draw            │
│ • Count main number matches              │
│ • Check powerball match                  │
│ • Calculate prize tier                   │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Calculate prize amount                   │
│ • 5+PB → Jackpot                         │
│ • 5 → $1M                                │
│ • 4+PB → $50K                            │
│ • [otros tiers]                          │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Save verification to DB                  │
│ • ticket_verifications table             │
│ • Link to user if authenticated          │
│ • Save image path (opcional)             │
└────┬─────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│ Return result to frontend                │
│ • Win/Loss status                        │
│ • Number of matches                      │
│ • Prize amount (if win)                  │
│ • Congratulations message                │
└──────────────────────────────────────────┘
```

## 📊 DIAGRAMA DE ENTIDAD-RELACIÓN (ER)

```
┌─────────────────────┐
│      users          │
├─────────────────────┤
│ id (PK)             │
│ username            │
│ email               │
│ password_hash       │
│ is_premium          │
│ premium_expires_at  │
│ is_admin            │
│ created_at          │
│ last_login          │
│ login_count         │
└──────┬──────────────┘
       │
       │ 1:N (FK: user_id)
       │
       ├─────────────────────────────────┐
       │                                 │
       ▼                                 ▼
┌─────────────────────┐        ┌─────────────────────┐
│ stripe_subscriptions│        │ ticket_verifications│
├─────────────────────┤        ├─────────────────────┤
│ id (PK)             │        │ id (PK)             │
│ user_id (FK)        │        │ user_id (FK)        │
│ stripe_customer_id  │        │ draw_date           │
│ stripe_subscription │        │ ticket_numbers      │
│ status              │        │ actual_numbers      │
│ current_period_end  │        │ matches             │
│ cancel_at_period_end│        │ prize_amount        │
└─────────────────────┘        │ verification_status │
                               │ created_at          │
                               └─────────────────────┘

┌─────────────────────┐
│  powerball_draws    │        ┌─────────────────────┐
├─────────────────────┤        │  predictions_log    │
│ id (PK)             │        ├─────────────────────┤
│ draw_date           │◀───1:N─│ id (PK)             │
│ n1, n2, n3, n4, n5  │        │ n1, n2, n3, n4, n5  │
│ powerball           │        │ powerball           │
│ multiplier          │        │ score_total         │
│ jackpot             │        │ score_frequency     │
│ created_at          │        │ score_gap           │
└─────────────────────┘        │ model_version       │
                               │ dataset_hash        │
                               │ next_draw_date (FK) │
                               │ created_at          │
                               └──────┬──────────────┘
                                      │
                                      │ 1:N (FK: prediction_id)
                                      │
                                      ▼
                               ┌─────────────────────┐
                               │performance_tracking │
                               ├─────────────────────┤
                               │ id (PK)             │
                               │ prediction_id (FK)  │
                               │ actual_draw_id (FK) │
                               │ matches_main        │
                               │ matches_pb          │
                               │ score_accuracy      │
                               │ prize_tier          │
                               │ prize_amount        │
                               │ created_at          │
                               └─────────────────────┘

┌─────────────────────┐
│  premium_passes     │        ┌─────────────────────┐
├─────────────────────┤        │ device_fingerprints │
│ id (PK)             │        ├─────────────────────┤
│ pass_id (unique)    │◀───1:N─│ id (PK)             │
│ email               │        │ premium_pass_id (FK)│
│ is_active           │        │ fingerprint_hash    │
│ devices_allowed     │        │ user_agent          │
│ devices_used        │        │ first_seen          │
│ expires_at          │        │ last_seen           │
│ stripe_payment_id   │        │ is_active           │
└─────────────────────┘        └─────────────────────┘

┌─────────────────────┐
│  reliable_plays     │
├─────────────────────┤
│ id (PK)             │
│ numbers (JSON)      │
│ powerball           │
│ reliability_score   │
│ performance_history │
│ win_rate            │
│ avg_score           │
│ last_validated      │
└─────────────────────┘

┌─────────────────────┐
│  pattern_analysis   │
├─────────────────────┤
│ id (PK)             │
│ pattern_type        │
│ pattern_description │
│ pattern_data (JSON) │
│ success_rate        │
│ frequency           │
│ confidence_score    │
│ date_range_start    │
│ date_range_end      │
│ created_at          │
└─────────────────────┘

┌─────────────────────┐
│  adaptive_weights   │
├─────────────────────┤
│ id (PK)             │
│ weight_name         │
│ weight_value        │
│ weight_category     │
│ performance_score   │
│ last_updated        │
│ is_active           │
└─────────────────────┘

┌─────────────────────┐
│  jti_revocation     │
├─────────────────────┤
│ id (PK)             │
│ jti                 │
│ revoked_at          │
│ reason              │
│ user_id             │
└─────────────────────┘
```

## 🔒 ARQUITECTURA DE SEGURIDAD

```
┌─────────────────────────────────────────────────────────────────┐
│                    CAPAS DE SEGURIDAD                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Capa 1: Network Security                                        │
├─────────────────────────────────────────────────────────────────┤
│ • HTTPS/TLS 1.3 (Certificado SSL)                               │
│ • CORS Policy (Restrictivo en producción)                       │
│ • Rate Limiting (Recomendado - Pendiente)                       │
│ • DDoS Protection (Cloudflare/AWS Shield)                       │
│ • IP Whitelisting (Admin endpoints)                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Capa 2: Application Security                                    │
├─────────────────────────────────────────────────────────────────┤
│ • JWT Authentication (HMAC-SHA256)                              │
│ • HttpOnly Cookies (XSS Protection)                             │
│ • Secure Flag (HTTPS Only)                                      │
│ • SameSite Cookies (CSRF Protection)                            │
│ • JTI Revocation (Token Blacklist)                              │
│ • Premium Pass System (Separate tokens)                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Capa 3: Authentication & Authorization                          │
├─────────────────────────────────────────────────────────────────┤
│ • Password Hashing (bcrypt, cost=12)                            │
│ • JWT Token Expiration (7 days default, 30 days remember_me)   │
│ • Role-Based Access Control (User/Admin)                        │
│ • Quota Management (Tier-based limits)                          │
│ • Device Fingerprinting (3-device limit)                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Capa 4: Payment Security                                        │
├─────────────────────────────────────────────────────────────────┤
│ • Stripe PCI Compliance (Level 1)                               │
│ • Webhook Signature Verification (HMAC-SHA256)                  │
│ • Idempotency Keys (Duplicate prevention)                       │
│ • Secure Customer Portal (Stripe hosted)                        │
│ • No card data stored locally                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Capa 5: Data Security                                           │
├─────────────────────────────────────────────────────────────────┤
│ • SQL Injection Protection (Parameterized queries)              │
│ • Input Validation (Pydantic models)                            │
│ • Output Sanitization (HTML encoding)                           │
│ • Database Encryption at Rest                                   │
│ • Secrets Management (Environment variables)                    │
│ • Regular Backups (Automated)                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Capa 6: Monitoring & Logging                                    │
├─────────────────────────────────────────────────────────────────┤
│ • Structured Logging (Loguru)                                   │
│ • Error Tracking (Recomendado: Sentry)                          │
│ • Security Event Logging                                        │
│ • Anomaly Detection (Recomendado)                               │
│ • Audit Trail (User actions)                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

**Documento generado:** 14 de Octubre, 2025  
**Versión:** 1.0  
**Autor:** AI Architecture Analysis System
