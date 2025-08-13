
# SHIOL+ v6.1: Optimized AI-Powered Lottery Analysis System

An intelligent, streamlined system designed to analyze historical Powerball lottery data and generate predictions using advanced Machine Learning techniques with an optimized pipeline and modern web interface.

**🌐 Live Demo**: [https://shiolplus.replit.app](https://shiolplus.replit.app)

## 🚀 Project Overview

**SHIOL+ (System for Hybrid Intelligence Optimization and Learning)** is an optimized AI platform that analyzes historical Powerball lottery data to identify statistical patterns and generate intelligent predictions. The system combines machine learning models with adaptive algorithms, providing a complete 6-step pipeline for data processing, prediction generation, validation, and performance analysis.

Version 6.1 introduces **pipeline optimization** with a streamlined codebase, enhanced performance, and a focus on the core prediction workflow that powers the frontend interface.

> **Important**: This tool is created for educational, research, and entertainment purposes. The lottery is a game of chance, and SHIOL+ **does not guarantee prizes or winnings**. Always play responsibly.

## ✨ Key Features

### 🤖 Optimized AI Pipeline System
- **6-Step Automated Pipeline**: Data update, adaptive analysis, weight optimization, prediction generation, validation, and performance analysis
- **Smart AI Predictions**: 100 optimized predictions per execution using ensemble machine learning
- **Automatic Scheduling**: Executes 30 minutes after each Powerball drawing (Mon/Wed/Sat at 11:29 PM ET)
- **Adaptive Learning**: Continuous improvement based on historical performance data
- **Multi-Criteria Scoring**: Probability, diversity, historical patterns, and risk assessment

### 🌐 Modern Web Interface
- **Real-time Dashboard**: Live pipeline status, prediction displays, and system monitoring
- **Public Interface**: Clean, mobile-responsive design for viewing latest predictions
- **Countdown Timer**: Real-time countdown to next Powerball drawing
- **Performance Analytics**: Historical win rates, accuracy metrics, and trend analysis
- **RESTful API**: Complete API suite for integration and automation

### 📊 Intelligent Prediction Engine
- **Ensemble Model**: Multiple ML algorithms working together for optimal accuracy
- **Feature Engineering**: 15+ engineered features from historical lottery data
- **Dynamic Weighting**: Adaptive weight optimization based on recent performance
- **Quality Validation**: Automatic model validation and retraining when needed
- **Target Dating**: Predictions automatically generated for next scheduled drawing

### 🔧 System Architecture
- **Streamlined Codebase**: Optimized for performance and maintainability
- **SQLite Database**: Efficient data storage with automatic cleanup and optimization
- **FastAPI Backend**: High-performance API with automatic documentation
- **Automated Scheduling**: APScheduler for reliable, timezone-aware execution
- **Comprehensive Logging**: Detailed execution tracking and error handling

## 🏃‍♂️ Quick Start

### Simple Setup & Execution

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

The SHIOL+ system follows an optimized 6-step pipeline:

### Step 1: Data Update
- Downloads latest Powerball drawing results
- Validates and stores new data in SQLite database
- Loads historical data for analysis (currently 36+ drawings)

### Step 2: Adaptive Analysis
- Analyzes recent prediction performance
- Identifies patterns in winning combinations
- Updates adaptive learning parameters

### Step 3: Weight Optimization
- Optimizes scoring weights based on performance data
- Uses differential evolution algorithm for optimization
- Balances probability, diversity, historical, and risk factors

### Step 4: Historical Validation
- Validates recent predictions against actual results
- Tracks win rates and accuracy metrics
- Feeds results back into adaptive learning system

### Step 5: Prediction Generation ⭐
- **Primary Function**: Generates 100 Smart AI predictions
- **Target Dating**: Automatically calculates next drawing date
- **Ensemble Scoring**: Multi-criteria evaluation of each combination
- **Quality Assurance**: Model validation and automatic retraining if needed

### Step 6: Performance Analysis
- Generates comprehensive performance metrics
- Analyzes trends over 1, 7, and 30-day periods
- Provides insights for system optimization

## 🌐 Web Interface Features

### Public Dashboard
- **Next Drawing Countdown**: Real-time countdown with timezone handling
- **Latest Predictions**: Top-scored predictions with confidence ratings
- **System Status**: Pipeline health and last execution time
- **Mobile Responsive**: Optimized for all device sizes

### API Endpoints
- `GET /api/v1/public/featured-predictions` - Latest AI predictions
- `GET /api/v1/public/next-drawing` - Next drawing information
- `GET /api/v1/pipeline/status` - Pipeline execution status
- `GET /api/v1/system/stats` - System health metrics

## 📈 Performance & Analytics

### Current System Status
- **Database**: 36+ historical Powerball drawings
- **Model**: Trained ensemble with multiple ML algorithms
- **Predictions**: Smart AI generates 100 predictions per execution
- **Execution**: Automatic runs 30 minutes after each drawing
- **Accuracy**: Continuous tracking and improvement

### Prediction Quality
- **Scoring Algorithm**: Multi-criteria evaluation system
- **Quality Thresholds**: Automatic filtering of low-quality predictions
- **Diversity Optimization**: Ensures varied number combinations
- **Risk Assessment**: Balanced approach between safety and potential

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
-- Core tables (optimized)
powerball_numbers     -- Historical drawing results
predictions_log       -- Generated predictions with scores
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

# Run full pipeline
python main.py

# Start web server
python main.py --server --host 0.0.0.0 --port 3000
```

### Replit Deployment (Recommended)
The system is optimized for Replit deployment with automatic:
- Dependency management
- Port forwarding (port 3000)
- Public URL generation
- Automatic scheduling
- Database persistence

**Live Demo**: [https://shiolplus.replit.app](https://shiolplus.replit.app)

## 📋 Command Line Interface

### Pipeline Operations
```bash
# Full pipeline execution
python main.py

# Specific steps
python main.py --step data          # Data update only
python main.py --step prediction    # Prediction generation only
python main.py --step validation    # Validation only

# System status
python main.py --status

# Web server
python main.py --server --host 0.0.0.0 --port 3000
```

### CLI Tool (Advanced)
```bash
# Generate predictions
python src/cli.py predict --count 100

# Validate against results
python src/cli.py validate

# Analyze performance
python src/cli.py analyze-feedback --days 30

# Optimize weights
python src/cli.py optimize-weights
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
```

## 🧠 Machine Learning Details

### Model Architecture
- **Ensemble Approach**: Multiple algorithms with weighted voting
- **Feature Engineering**: 15+ calculated features from historical data
- **Training Data**: All available Powerball drawing history
- **Validation**: Cross-validation with historical splits
- **Optimization**: Continuous parameter tuning based on performance

### Prediction Process
1. **Data Preparation**: Feature engineering from historical draws
2. **Model Prediction**: Ensemble generates probability scores
3. **Candidate Generation**: Creates thousands of potential combinations
4. **Multi-Criteria Scoring**: Evaluates each combination across multiple dimensions
5. **Selection Algorithm**: Chooses top 100 diverse, high-quality predictions
6. **Quality Validation**: Final verification before serving

## 🔄 Automation & Scheduling

### Automatic Execution
- **Schedule**: 30 minutes after each Powerball drawing
- **Drawing Days**: Monday, Wednesday, Saturday at 10:59 PM ET
- **Pipeline Runs**: Monday 11:29 PM, Wednesday 11:29 PM, Saturday 11:29 PM ET
- **Timezone**: America/New_York (handles DST automatically)
- **Overlap Protection**: Prevents multiple simultaneous executions

### Manual Execution
- **CLI**: `python main.py` for full pipeline
- **API**: `POST /api/v1/pipeline/trigger` for programmatic execution
- **Web Interface**: Direct pipeline triggering (when authentication is enabled)

## 📈 Performance Monitoring

### Real-time Metrics
- **Pipeline Status**: Current execution state and progress
- **Prediction Quality**: Scoring distributions and confidence levels
- **System Health**: Database status, model validity, execution history
- **Performance Trends**: Win rates, accuracy metrics over time

### Analytics Dashboard
- **Execution History**: Success rates, timing, error tracking
- **Prediction Performance**: Hit rates, prize categories, ROI analysis
- **System Resources**: Database size, model performance, API response times

## 🔒 Security & Reliability

### Data Security
- **Local Storage**: All data stored locally in SQLite database
- **No External Dependencies**: Predictions generated entirely locally
- **Secure API**: CORS configuration for controlled access
- **Input Validation**: Comprehensive validation of all inputs

### System Reliability
- **Error Handling**: Comprehensive exception handling with recovery
- **Logging**: Detailed execution logs for debugging and monitoring
- **Backup System**: Automatic database backups before major operations
- **Health Checks**: Continuous monitoring of system components

## 🚀 Future Enhancements

### Planned Features
- **Advanced Analytics**: Enhanced performance tracking and visualization
- **Model Improvements**: New ML algorithms and feature engineering
- **API Expansion**: Additional endpoints for detailed analytics
- **Mobile App**: Native mobile application for iOS/Android
- **Multi-Lottery Support**: Support for additional lottery games

### Performance Optimizations
- **Database Optimization**: Query performance and storage efficiency
- **Prediction Speed**: Faster generation with maintained quality
- **API Performance**: Response time optimization and caching
- **Resource Usage**: Memory and CPU optimization

## 📝 Contributing

We welcome contributions to SHIOL+ v6.1! Please follow these guidelines:

### Development Process
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

### Code Standards
- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add comprehensive docstrings
- Include tests for new features
- Update documentation for changes

## 📄 License

Private use – All rights reserved.

## 🏆 Credits

- **Creator**: Orlando Batista
- **Version**: 6.1 (Optimized Pipeline)
- **Last Updated**: August 2025
- **Live Demo**: [https://shiolplus.replit.app](https://shiolplus.replit.app)

---

**SHIOL+ v6.1** - Optimized AI-powered lottery analysis with streamlined performance and intelligent predictions.

**🌐 Experience SHIOL+ Live**: [https://shiolplus.replit.app](https://shiolplus.replit.app)

For support, documentation, and updates, visit the project repository.

**⚡ Optimized for Performance • 🤖 Powered by AI • 🎯 Built for Accuracy**
