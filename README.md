# SHIOL+ v3.0 - AI-Powered Powerball System with Ticket Verification 🎯🎟️

**Live Demo**: [https://shiolplus.com/](https://shiolplus.com/)

**SHIOL+ (System for Hybrid Intelligence Optimization and Learning)** is an advanced AI-powered lottery analysis system that combines machine learning predictions with intelligent ticket verification. Using Google Gemini AI, the system can extract numbers and dates from lottery tickets, verify wins against official results, and calculate prize amounts. Built for educational and research purposes, this system demonstrates sophisticated AI integration in lottery data analysis.

## 🌟 Key Features

### 🎟️ **Intelligent Ticket Verification (NEW in v3.0)**
- **Google Gemini AI Integration**: Advanced image analysis for ticket processing
- **Automatic Number Extraction**: Identifies all 5 plays (A, B, C, D, E) from ticket images
- **Smart Date Detection**: Extracts draw dates from various ticket formats
- **North Carolina Format Support**: Specialized for NC lottery ticket layout
- **Prize Calculation**: Automatic win/lose determination with prize amounts
- **No Data Storage**: Secure, temporary processing with no permanent data retention

### 🤖 **Advanced AI Prediction Engine**
- **Ensemble Machine Learning**: Multiple XGBoost classifiers with feature engineering
- **Adaptive Weight Optimization**: Dynamic model selection based on recent performance
- **Real-time Evaluation**: Automatic comparison against actual drawing results
- **15+ Engineered Features**: Advanced statistical analysis of historical patterns

### 📱 **Mobile-Optimized Interface**
- **Responsive Design**: Perfect viewing experience on smartphones and tablets
- **Reorganized Layout**: Predictions → Recent Draws → Ticket Verification
- **Touch-Friendly Controls**: Optimized for mobile interaction
- **Real-time Updates**: Live countdown and prediction updates

### ⏰ **Live Countdown Timer**
- **Dynamic Color System**: Blue → Yellow → Orange → Red based on proximity
- **Accurate Scheduling**: Monday, Wednesday, Saturday at 10:59 PM ET
- **Real-time Updates**: Second-by-second countdown display
- **Timezone Aware**: Eastern Time (ET) synchronized

### 🎱 **Authentic Ball Design**
- **White Balls**: Authentic Powerball-style main numbers (1-69)
- **Red Powerball**: Official red Powerball design (1-26)
- **Elegant Halo Effects**: Premium shadow and ring styling
- **Consistent Design**: Unified appearance across all interfaces

### 📊 **Comprehensive Analytics**
- **Match Highlighting**: Green highlights for winning number matches
- **Prize Calculations**: Automatic prize amount computation
- **Performance Tracking**: Historical accuracy and evaluation metrics
- **Interactive Modals**: Detailed prediction vs. draw result comparisons

### 🔄 **Automated Pipeline**
- **Scheduled Execution**: Runs 30 minutes after each Powerball drawing
- **Data Integration**: Fetches real historical data from official sources
- **Model Retraining**: Continuous learning with each new drawing
- **Performance Optimization**: Automatic database cleanup and optimization

## 🚀 Technology Stack

### **Backend Architecture**
- **FastAPI**: High-performance Python web framework
- **SQLite**: Lightweight, embedded database for data persistence
- **Google Gemini AI**: Advanced image analysis and text extraction
- **XGBoost**: Gradient boosting machine learning framework
- **scikit-learn**: Machine learning algorithms and preprocessing
- **APScheduler**: Timezone-aware task scheduling
- **Pandas/NumPy**: Data manipulation and numerical computing

### **Frontend Technology**
- **Modern HTML5/CSS3/JavaScript**: Clean, semantic markup
- **Tailwind CSS**: Utility-first CSS framework for responsive design
- **Font Awesome**: Professional icon library
- **Google Fonts**: Inter and Poppins typography
- **Progressive Enhancement**: Works on all devices and browsers

### **AI & Machine Learning Pipeline**
- **Google Gemini Pro Vision**: Intelligent ticket image processing
- **Feature Engineering**: 15+ statistical features from historical data
- **Ensemble Methods**: Multiple model combination for improved accuracy
- **Cross-validation**: Robust model evaluation and selection
- **Hyperparameter Optimization**: Automated parameter tuning
- **Performance Monitoring**: Continuous accuracy tracking

## 📋 System Requirements

### **Server Requirements**
- **Python**: 3.8 or higher
- **Memory**: Minimum 512MB RAM (1GB recommended for ML pipeline)
- **Storage**: 100MB for application + data growth
- **Network**: Internet connection for data fetching and Gemini API

### **API Keys Required**
- **GEMINI_API_KEY**: Google Gemini AI for ticket processing
- **GOOGLE_CLOUD_VISION_API_KEY**: Legacy support (optional)

### **Supported Browsers**
- **Desktop**: Chrome 80+, Firefox 75+, Safari 13+, Edge 80+
- **Mobile**: iOS Safari 13+, Chrome Mobile 80+, Samsung Internet 12+
- **Features**: ES6 JavaScript support, CSS Grid, Flexbox, File Upload API

## 🔧 Installation & Setup

### **Quick Start (Replit)**
1. **Clone Repository**: Fork or import this project to Replit
2. **Configure Secrets**: Add GEMINI_API_KEY to Replit Secrets
3. **Install Dependencies**: Dependencies auto-install on first run
4. **Configure Environment**: Database auto-creates on startup
5. **Run Application**: Click "Run" button to start the web server
6. **Access Interface**: Open the web preview to view the application

### **Production Deployment (VPS)**
```bash
# Clone the repository
git clone <repository-url>
cd shiol-plus-v3

# Install production dependencies (optimized - no OpenCV, 180MB lighter)
pip install -r requirements-prod.txt

# Set environment variables
export GEMINI_API_KEY="your_gemini_api_key_here"

# Initialize database and generate first predictions
python main.py --verbose

# Run the web application
python main.py --server --host 0.0.0.0 --port 5000
```

### **Pipeline Management (VPS)**
```bash
# Check pipeline status
python main.py --status

# Run full pipeline in background (recommended for VPS)
nohup python main.py --verbose > pipeline.log 2>&1 &

# Update only data from official sources
python main.py --step data --verbose

# Generate new predictions with existing data
python main.py --step prediction --verbose

# Monitor pipeline execution
tail -f pipeline.log

# Set up automatic daily updates (optional)
# Add to crontab: 0 2 * * * cd /path/to/project && python main.py --step data >> cron.log 2>&1
```

### **Development Setup**
```bash
# Install all dependencies (including dev tools)
pip install -r requirements.txt

# Run with development features
python main.py --server --host 0.0.0.0 --port 5000
```

### **Environment Configuration**
```bash
# Required: Gemini API key for ticket verification
export GEMINI_API_KEY="your_gemini_api_key"

# Optional: Set custom database path
export DATABASE_PATH="data/custom.db"

# Optional: Configure timezone (default: America/New_York)
export TIMEZONE="America/New_York"
```

## 🎮 Usage Guide

### **Viewing Predictions**
1. **Main Dashboard**: View 50 AI-generated predictions for next drawing
2. **Countdown Timer**: See time remaining until next Powerball drawing
3. **Number Display**: White balls (1-69) + Red Powerball (1-26)
4. **Ranking System**: Predictions ranked #1-#50 by confidence score

### **Verifying Lottery Tickets (NEW)**
1. **Upload Ticket**: Take photo or select image of your North Carolina Powerball ticket
2. **AI Processing**: Gemini AI extracts numbers and draw date automatically
3. **Number Verification**: System validates all 5 plays (A, B, C, D, E)
4. **Results Display**: Shows wins/losses with prize amounts for each play
5. **Secure Processing**: No ticket data is stored permanently

### **Analyzing Results**
1. **Recent Draws**: Browse historical Powerball drawing results
2. **Match Analysis**: Click any draw to see prediction matches
3. **Prize Calculation**: Automatic computation of winnings
4. **Performance Metrics**: View system accuracy and statistics

### **Mobile Experience**
1. **Camera Integration**: Direct camera access for ticket photos
2. **Responsive Layout**: Optimized for smartphones and tablets
3. **Touch Navigation**: Easy scrolling and interaction
4. **Fast Processing**: Optimized AI processing for mobile networks

## 🧠 Machine Learning Details

### **Model Architecture**
- **Base Models**: Multiple XGBoost classifiers for each number position
- **Feature Set**: Historical frequency, gaps, patterns, statistical measures
- **Training Data**: Complete Powerball history with feature engineering
- **Validation**: Time-series cross-validation for temporal data

### **Prediction Process**
1. **Data Preprocessing**: Clean and normalize historical drawing data
2. **Feature Engineering**: Generate 15+ statistical features per drawing
3. **Model Training**: Train ensemble of XGBoost classifiers
4. **Weight Optimization**: Adaptive weighting based on recent performance
5. **Prediction Generation**: Create 50 ranked predictions for next drawing

### **Ticket Verification Process**
1. **Image Upload**: User uploads ticket photo via web interface
2. **AI Analysis**: Gemini AI processes image to extract text and numbers
3. **Data Extraction**: System identifies draw date and all play numbers
4. **Validation**: Checks number ranges and format compliance
5. **Result Comparison**: Compares against official drawing results
6. **Prize Calculation**: Determines win/lose status and prize amounts

## 📊 API Endpoints

### **Public API**
```
GET /api/v1/public/predictions/latest     # Latest predictions
GET /api/v1/public/draws/recent          # Recent drawing results  
GET /api/v1/public/predictions/by-draw   # Predictions for specific draw
GET /api/v1/public/next-drawing          # Next drawing information
```

### **Ticket Verification API (NEW)**
```
POST /api/v1/tickets/verify              # Upload and verify ticket
POST /api/v1/tickets/process             # Process ticket image with Gemini
GET  /api/v1/tickets/results/{id}        # Get verification results
```

### **System Monitoring API (NEW)**
```
GET /health                              # Simple health check
GET /api/v1/health                       # Detailed health status with timestamp
GET /api/v1/system/info                  # System information and model status
```

### **Response Format**
```json
{
  "ticket_verification": {
    "draw_date": "2025-07-28",
    "plays": [
      {
        "play": "A",
        "numbers": [2, 3, 15, 20, 22],
        "powerball": 7,
        "matches": 1,
        "powerball_match": false,
        "prize": 4,
        "status": "winner"
      }
    ],
    "total_winnings": 16,
    "processing_time": 2.3
  }
}
```

## 🎯 Version 3.0 Highlights

### **🆕 Major New Features**
- **Ticket Verification System**: Complete Google Gemini AI integration
- **Automatic Number Extraction**: Intelligent image processing
- **Prize Calculation Engine**: Accurate win/lose determination
- **North Carolina Support**: Specialized for NC lottery format
- **Secure Processing**: No permanent data storage for privacy

### **🔧 Technical Improvements**
- **Gemini AI Integration**: Replaced Google Vision with more intelligent AI
- **OpenCV Elimination**: Removed OpenCV dependency for 180MB lighter deployment
- **Enhanced Date Detection**: Robust parsing of various date formats
- **Optimized Dependencies**: Created requirements-prod.txt for efficient deployment
- **Frontend Reorganization**: Improved user flow and interface layout
- **API Expansion**: New endpoints for ticket processing and verification
- **Health Monitoring**: Added `/health` endpoint for production monitoring
- **Pipeline Management**: Enhanced VPS deployment with background execution

### **🎨 Design Enhancements**
- **Reorganized Layout**: Logical flow from predictions to verification
- **Mobile Camera Support**: Direct camera access for ticket photos
- **Enhanced Visual Feedback**: Clear win/lose indicators and prize displays
- **Improved Responsiveness**: Better mobile experience across all features
- **Professional Polish**: Refined interface with consistent styling

### **⚡ Performance Optimizations**
- **180MB Lighter Deployment**: Eliminated OpenCV dependency completely
- **Reduced Dependencies**: 60% smaller production footprint with optimized requirements
- **Faster AI Processing**: Pure Gemini AI integration without computer vision overhead
- **Efficient Image Handling**: Streamlined photo processing pipeline using only Gemini
- **Database Optimization**: Improved query performance and storage
- **Background Pipeline**: VPS-optimized background execution with monitoring
- **Health Monitoring**: Real-time system status via `/health` endpoint

## ⚖️ Legal & Disclaimers

### **Educational Purpose**
This system is designed for **educational and research purposes only**. It demonstrates AI integration, machine learning applications, and image processing in lottery analysis.

### **No Guarantees**
- **Predictions are for entertainment only** and do not guarantee results
- **Lottery outcomes are random** and past results do not predict future drawings
- **Ticket verification is for informational purposes** - always check official sources
- **No financial advice** is provided or implied
- **Use responsibly** and within your means

### **Privacy & Security**
- **No ticket data is stored permanently** on our servers
- **Images are processed temporarily** and deleted after verification
- **Personal information is not collected** or retained
- **Secure API communication** with encrypted data transmission

### **Data Sources**
- Historical Powerball data from official lottery sources
- All data used is publicly available information
- Google Gemini AI for intelligent image processing
- No proprietary or confidential data is utilized

## 🤝 Contributing

We welcome contributions to improve SHIOL+ v3.0:

1. **Fork the Repository**: Create your own copy for development
2. **Create Feature Branch**: `git checkout -b feature/your-feature`
3. **Make Changes**: Implement your improvements
4. **Test Thoroughly**: Ensure all functionality works correctly
5. **Submit Pull Request**: Describe your changes and benefits

### **Development Guidelines**
- Follow existing code style and conventions
- Add appropriate documentation and comments
- Test AI integration thoroughly with various ticket formats
- Ensure mobile compatibility for all changes
- Maintain security best practices for file uploads

## 📞 Support & Contact

For questions, issues, or contributions:

- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Documentation**: Refer to inline code comments and this README
- **Community**: Join discussions in repository discussions section

---

**SHIOL+ v3.0** - Advancing AI-powered lottery analysis through intelligent ticket verification and machine learning innovation.

*© 2025 SHIOL+ AI Prediction System. Educational use only. Predictions do not guarantee results. Ticket verification for informational purposes only - always verify with official sources.*