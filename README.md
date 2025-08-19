
# SHIOL+ v6.1: Optimized AI-Powered Lottery Analysis System

An intelligent and optimized system designed to analyze historical Powerball data and generate predictions using advanced Machine Learning techniques with an optimized pipeline and modern web interface.

**🌐 Live Demo**: [https://shiolplus.replit.app](https://shiolplus.replit.app)

## 🚀 Project Description

**SHIOL+ (System for Hybrid Intelligence Optimization and Learning)** is an optimized AI platform that analyzes historical Powerball lottery data to identify statistical patterns and generate intelligent predictions. The system combines machine learning models with adaptive algorithms, providing a complete 7-step pipeline for data processing, prediction generation, evaluation, and performance analysis.

Version 6.1 introduces **optimized pipeline architecture** with streamlined code, improved performance, and focus on the main prediction flow that powers the frontend interface.

> **Important**: This tool is created for educational, research, and entertainment purposes. The lottery is a game of chance, and SHIOL+ **does not guarantee prizes or winnings**. Always play responsibly.

## ✨ Key Features

### 🤖 Optimized AI Pipeline System
- **Automated 7-Step Pipeline**: Data update, adaptive analysis, weight optimization, prediction generation, evaluation, validation, and performance analysis
- **Intelligent Predictions**: 100 optimized predictions per execution using ensemble machine learning
- **Automatic Scheduling**: Runs 30 minutes after each Powerball drawing (Mon/Wed/Sat at 11:29 PM ET)
- **Adaptive Learning**: Continuous improvement based on historical performance data
- **Real Results Evaluation**: Compares predictions against official drawings and calculates prizes won

### 🌐 Modern Web Interface
- **Real-Time Dashboard**: Live pipeline status, prediction visualization, and system monitoring
- **Public Interface**: Clean and responsive design for viewing latest predictions
- **Live Countdown**: Real-time countdown to next Powerball drawing
- **Evaluation Analytics**: Prediction evaluation metrics, hit rates, and prizes won
- **RESTful API**: Complete API suite for integration and automation

### 📊 Intelligent Prediction Engine
- **Ensemble Model**: Multiple ML algorithms working together for maximum accuracy
- **Feature Engineering**: 15+ engineered features from historical lottery data
- **Dynamic Weights**: Adaptive weight optimization based on recent performance
- **Quality Validation**: Automatic model validation and retraining when needed
- **Automatic Evaluation**: System that evaluates predictions against official results

### 🔧 System Architecture
- **Optimized Code**: Streamlined for performance and maintainability
- **SQLite Database**: Efficient storage with automatic cleanup and optimization
- **FastAPI Backend**: High-performance API with automatic documentation
- **Automated Scheduling**: APScheduler for reliable, timezone-aware execution
- **Comprehensive Logging**: Detailed execution tracking and error handling

## 🏃‍♂️ Quick Start

### Simple Setup and Execution

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize the system
python src/database.py

# Run the complete pipeline
python main.py

# Start the web server
python main.py --server --host 0.0.0.0 --port 3000
```

### Access the System

After starting the server:

- **Public Interface**: `http://localhost:3000/` - View latest predictions and countdown
- **Live Demo**: [https://shiolplus.replit.app](https://shiolplus.replit.app) - Public demonstration

## 🔄 Pipeline Workflow

The SHIOL+ system follows an optimized 7-step pipeline:

### Step 1: Data Update
- Downloads latest Powerball drawing results
- Validates and stores new data in SQLite database
- Loads historical data for analysis

### Step 2: Adaptive Analysis
- Analyzes recent prediction performance
- Identifies patterns in winning combinations
- Updates adaptive learning parameters

### Step 3: Weight Optimization
- Optimizes scoring weights based on performance data
- Uses differential evolution algorithm for optimization
- Balances probability, diversity, historical, and risk factors

### Step 4: Prediction Generation ⭐
- **Main Function**: Generates 100 Smart AI predictions
- **Target Dating**: Automatically calculates next drawing date
- **Ensemble Scoring**: Multi-criteria evaluation of each combination
- **Quality Assurance**: Model validation and automatic retraining if needed

### Step 5: Prediction Evaluation 🎯
- **Automatic Evaluation**: Compares predictions against official drawing results
- **Prize Calculation**: Determines prizes won according to Powerball rules
- **Database Update**: Marks predictions as evaluated with results
- **Performance Analysis**: Tracks hit rates and accuracy metrics

### Step 6: Historical Validation
- Validates recent predictions against actual results
- Feeds results back to adaptive learning system
- Provides metrics for system optimization

### Step 7: Performance Analysis
- Generates comprehensive performance metrics
- Analyzes trends over 1, 7, and 30-day periods
- Provides insights for system optimization

## 🌐 Web Interface Features

### Public Dashboard
- **Next Drawing Countdown**: Real-time countdown with timezone handling
- **Latest Predictions**: Top-scored predictions with confidence ratings
- **Evaluation Results**: Shows prizes won on evaluated predictions
- **System Status**: Pipeline health and last execution time
- **Mobile Responsive**: Optimized for all device sizes

### API Endpoints
- `GET /api/v1/public/featured-predictions` - Latest AI predictions
- `GET /api/v1/public/next-drawing` - Next drawing information
- `GET /api/v1/pipeline/status` - Pipeline execution status
- `GET /api/v1/system/stats` - System health metrics

## 📈 Evaluation and Performance Analysis

### Current System Status
- **Database**: 36+ historical Powerball drawings
- **Model**: Ensemble trained with multiple ML algorithms
- **Predictions**: Smart AI generates 100 predictions per execution
- **Execution**: Automatic 30 minutes after each drawing
- **Evaluation**: Continuous tracking of predictions vs actual results

### Prediction Quality and Evaluation
- **Scoring Algorithm**: Multi-criteria evaluation system
- **Quality Thresholds**: Automatic filtering of low-quality predictions
- **Diversity Optimization**: Ensures varied number combinations
- **Prize Evaluation**: Calculates actual prizes won according to Powerball rules
- **ROI Analysis**: Tracks return on investment for predictions

## 🛠️ Technical Specifications

### Core Technologies
- **Backend**: Python 3.8+, FastAPI, SQLite
- **Machine Learning**: Scikit-learn, XGBoost, Pandas, NumPy
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Scheduling**: APScheduler with timezone awareness
- **API**: RESTful design with automatic documentation

### System Requirements
- **Minimum**: Python 3.8+, 2GB RAM, 1GB disk space
- **Recommended**: Python 3.10+, 4GB RAM, SSD storage
- **Network**: Internet connection for data updates
- **Browser**: Modern browser for web interface

### Database Schema
```sql
-- Main tables (optimized)
powerball_draws       -- Historical drawing results
predictions_log       -- Generated predictions with scores and evaluations
pipeline_executions   -- Execution history and status
adaptive_weights      -- Dynamic scoring parameters
```

## 🚀 Deployment Options

### Local Development
```bash
# Clone repository
git clone <repository-url>
cd shiol-plus

# Install dependencies
pip install -r requirements.txt

# Initialize database
python src/database.py

# Run complete pipeline
python main.py

# Start web server
python main.py --server --host 0.0.0.0 --port 3000
```

### Replit Deployment (Recommended)
The system is optimized for Replit deployment with:
- Automatic dependency management
- Port forwarding (port 3000)
- Automatic public URL generation
- Automatic scheduling
- Database persistence

**Live Demo**: [https://shiolplus.replit.app](https://shiolplus.replit.app)

## 📋 Command Line Interface

### Pipeline Operations
```bash
# Complete pipeline execution
python main.py

# Specific steps
python main.py --step data          # Data update only
python main.py --step prediction    # Prediction generation only
python main.py --step evaluation    # Prediction evaluation only

# System status
python main.py --status

# Web server
python main.py --server --host 0.0.0.0 --port 3000
```

## 🔧 Configuration

### System Configuration (`config/config.ini`)
```ini
[pipeline]
execution_days = 0,2,5  # Monday, Wednesday, Saturday
execution_time = 23:29   # 11:29 PM ET (30 min after drawing)
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
prize_thresholds = 4,7,100,50000  # Powerball prize thresholds
auto_evaluation_enabled = true
```

## 📊 API Documentation

### Public Endpoints
- `GET /` - Main web interface
- `GET /api/v1/public/featured-predictions` - Latest predictions
- `GET /api/v1/public/next-drawing` - Drawing countdown
- `GET /api/v1/system/info` - System information

### Pipeline Endpoints
- `GET /api/v1/pipeline/status` - Current pipeline status
- `POST /api/v1/pipeline/trigger` - Manual pipeline execution
- `GET /api/v1/pipeline/health` - System health check

### Integration Example
```python
import requests

# Get latest predictions
response = requests.get('https://shiolplus.replit.app/api/v1/public/featured-predictions')
predictions = response.json()

# Check next drawing
response = requests.get('https://shiolplus.replit.app/api/v1/public/next-drawing')
next_drawing = response.json()

# View prediction evaluations
for pred in predictions['predictions']:
    if 'prize_won' in pred:
        print(f"Prediction {pred['prediction_id']}: Prize won ${pred['prize_won']}")
```

## 🧠 Machine Learning Details

### Model Architecture
- **Ensemble Approach**: Multiple algorithms with weighted voting
- **Feature Engineering**: 15+ features calculated from historical data
- **Training Data**: All available Powerball drawing history
- **Validation**: Cross-validation with historical splits
- **Optimization**: Continuous parameter tuning based on performance

### Evaluation Process
1. **Automatic Comparison**: Predictions vs official drawing results
2. **Prize Calculation**: Prize determination according to Powerball rules
3. **Data Update**: Marking predictions as evaluated
4. **Performance Analysis**: Accuracy metrics and ROI calculation
5. **System Feedback**: Feeding results for continuous improvement

## 🔄 Automation and Scheduling

### Automatic Execution
- **Schedule**: 30 minutes after each Powerball drawing
- **Drawing Days**: Monday, Wednesday, Saturday at 10:59 PM ET
- **Pipeline Runs**: Monday 11:29 PM, Wednesday 11:29 PM, Saturday 11:29 PM ET
- **Timezone**: America/New_York (handles DST automatically)
- **Overlap Protection**: Prevents multiple simultaneous executions

### Manual Execution
- **CLI**: `python main.py` for complete pipeline
- **API**: `POST /api/v1/pipeline/trigger` for programmatic execution

## 📈 Performance Monitoring

### Real-Time Metrics
- **Pipeline Status**: Current execution status and progress
- **Prediction Quality**: Scoring distributions and confidence levels
- **Evaluation Results**: Prizes won, hit rates, ROI analysis
- **System Health**: Database status, model validity, execution history

### Analytics Dashboard
- **Execution History**: Success rates, timing, error tracking
- **Prediction Performance**: Hit rates, prize categories, ROI analysis
- **System Resources**: Database size, model performance, API response times

## 🔒 Security and Reliability

### Data Security
- **Local Storage**: All data stored locally in SQLite database
- **No External Dependencies**: Predictions generated completely locally
- **Secure API**: CORS configuration for controlled access
- **Input Validation**: Comprehensive validation of all inputs

### System Reliability
- **Error Handling**: Comprehensive exception handling with recovery
- **Logging**: Detailed execution logs for debugging and monitoring
- **Backup System**: Automatic database backups before major operations
- **Health Checks**: Continuous monitoring of system components

## 📝 Contributing

We welcome contributions to SHIOL+ v6.1! Please follow these guidelines:

### Development Process
1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

### Code Standards
- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add comprehensive docstrings
- Include tests for new features
- Update documentation for changes

## 📄 License

Private Use – All Rights Reserved.

## 🏆 Credits

- **Creator**: Orlando Batista
- **Version**: 6.1 (Optimized Pipeline with Evaluation)
- **Last Update**: August 2025
- **Live Demo**: [https://shiolplus.replit.app](https://shiolplus.replit.app)

---

**SHIOL+ v6.1** - Optimized AI-powered lottery analysis with enhanced performance, intelligent predictions, and automatic result evaluation.

**🌐 Experience SHIOL+ Live**: [https://shiolplus.replit.app](https://shiolplus.replit.app)

For support, documentation, and updates, visit the project repository.

**⚡ Optimized for Performance • 🤖 Powered by AI • 🎯 Built for Accuracy • 🏆 Automatic Evaluation**
