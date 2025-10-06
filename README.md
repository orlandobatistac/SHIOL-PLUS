# SHIOL+ v4.0 - AI-Powered Powerball Analysis Platform 🎯

**Live Demo**: [https://shiolplus.com/](https://shiolplus.com/)

**SHIOL+ (System for Hybrid Intelligence Optimization and Learning)** is a production-ready AI-powered Powerball analysis platform featuring a conversion-optimized freemium business model, day-based quota system, and advanced machine learning insights. Built with FastAPI, SQLite, and modern web technologies, SHIOL+ v4.0 delivers a polished dark minimalist interface (cyan #00e0ff → pink #ff6b9d gradient) with PWA support and real-time AI insights.

## 🌟 What's New in v4.0

### **🎁 Day-Based Quota System (Conversion Optimized)**
- **Saturday Premium Day**: Free users get 5 AI insights (creates VIP experience on highest jackpot days)
- **Regular Days (Tue/Thu)**: Free users get 1 insight (maintains weekly engagement)
- **Premium Users**: Always 100 insights per draw regardless of day
- **Strategic Design**: Drives premium conversions during peak interest moments
- **Dynamic Backend**: Automatic quota calculation based on draw day with fail-closed security

### **💎 Enhanced Freemium Business Model**
- **Guest Tier**: 1 insight per draw (no registration required)
- **Free Tier**: Day-based quota system (7 insights per week: 1+1+5)
- **Premium Tier**: $9.99/year for 100 insights per draw
- **Stripe Integration**: Full checkout flow with webhook processing
- **Device Fingerprinting**: 3-device limit enforcement for guest premium
- **Anti-Fraud System**: JTI revocation, idempotency, signature verification

### **🔐 Dual Authentication System**
- **Traditional JWT**: For registered users with secure cookies
- **Premium Pass JWT**: Separate token system for guest premium access
- **Remember Me**: Optional 30-day persistent sessions vs default 7-day
- **Secure Cookies**: HttpOnly, Secure, SameSite flags
- **Session Management**: Clean logout and token invalidation

### **📡 MUSL API Integration (Primary Data Source)**
- **Official MUSL Numbers API**: Real-time historical drawing data
- **Grand Prize API**: Live jackpot display with annuity and cash values
- **Fallback System**: NY State Open Data API as secondary source
- **Secure Authentication**: MUSL_API_KEY environment variable
- **Timeout Configuration**: 15-second timeouts for reliability

### **📱 Progressive Web App (PWA)**
- **Installable**: Full PWA support with S+ gradient icon (cyan to pink)
- **Service Worker v2.2.4**: Offline functionality and asset caching
- **Mobile Optimized**: Touch-friendly responsive design
- **Dark Theme**: Ultra-minimalist dark UI with gradient accents
- **Real-time Updates**: Live countdown and jackpot display

### **🎨 Modern Dark UI**
- **Color Palette**: Cyan (#00e0ff) → Gray → Pink (#ff6b9d) gradient
- **Minimalist Header**: Text "Login" link + gradient "Unlock Premium" button
- **Hero Section**: Tier-based CTAs (Guest/Free/Premium dynamic buttons)
- **Clean Modals**: Login, Register, Upgrade modals without marketing fluff
- **Tailwind CSS**: Utility-first styling with custom components

### **🚀 Production-Ready Deployment**
- **Database Reset Script**: Clean SQL script for production setup
- **Automated Deployment**: Bash script for VPS deployment
- **Admin Setup**: Pre-configured admin user (credentials: admin / Abcd1234.)
- **Backup System**: Automatic database backups before deployment
- **Service Management**: Systemd and Supervisor support
- **Environment Variables**: Comprehensive .env configuration guide

## 🏗️ Architecture Overview

### **Backend Stack**
- **FastAPI**: High-performance Python web framework
- **SQLite**: Embedded database with automatic optimization
- **XGBoost**: Gradient boosting ML framework for predictions
- **scikit-learn**: Machine learning algorithms and preprocessing
- **APScheduler**: Timezone-aware task scheduling (30 min after draws)
- **Stripe SDK**: Payment processing and subscription management
- **Passlib (bcrypt)**: Secure password hashing

### **Frontend Stack**
- **Static HTML/CSS/JavaScript**: No framework overhead, fast loading
- **Tailwind CSS**: Utility-first CSS via CDN
- **Font Awesome**: Professional icon library
- **Google Fonts**: Inter and Poppins typography
- **Service Worker**: Offline-first PWA functionality

### **Machine Learning Pipeline**
- **Ensemble XGBoost Models**: Multiple classifiers for number prediction
- **Feature Engineering**: 15+ engineered features from historical data
- **Adaptive Weight Optimization**: Dynamic model selection based on performance
- **Real-time Evaluation**: Automatic comparison against actual results
- **Prize Calculation**: Accurate win detection and prize tracking

### **Data Sources**
- **MUSL API (Primary)**: Official Multi-State Lottery Association API
  - `/v3/numbers` - Historical drawing results
  - `/v3/grandprize` - Real-time jackpot information
- **NY State Open Data (Fallback)**: Secondary data source
- **Local SQLite**: 2,235+ draws stored for ML training

## 💰 Freemium Business Model

### **Tier Comparison**

| Feature | Guest | Free (Registered) | Premium ($9.99/year) |
|---------|-------|-------------------|----------------------|
| AI Insights | 1 per draw | Day-based (1-5) | 100 per draw |
| Saturday Premium Day | ❌ No | ✅ 5 insights | ✅ 100 insights |
| Regular Days (Tue/Thu) | 1 insight | 1 insight | 100 insights |
| Historical Performance | ❌ No | ✅ Yes | ✅ Yes |
| Stats Dashboard | ❌ No | ✅ Yes | ✅ Yes |
| PWA Installation | ✅ Yes | ✅ Yes | ✅ Yes |
| Prize Tracking | ❌ No | ✅ Yes | ✅ Yes |

### **Conversion Strategy**
- **Premium Day Experience**: Free users get "VIP treatment" on Saturdays (highest jackpots)
- **Weekly Engagement**: 3 touchpoints per week (Tuesday: 1, Thursday: 1, Saturday: 5)
- **Scarcity & Urgency**: Limited insights on regular days drive upgrade consideration
- **Low Price Point**: $9.99/year (~$0.83/month) removes price objection
- **Stripe Integration**: Seamless checkout with automatic subscription renewal

## 🔧 Installation & Setup

### **Prerequisites**
- **Python**: 3.8 or higher
- **Memory**: Minimum 512MB RAM (1GB recommended for ML pipeline)
- **Storage**: 100MB for application + data growth
- **API Keys**: MUSL_API_KEY, STRIPE_SECRET_KEY (for billing)

### **Quick Start (Replit)**
```bash
# 1. Clone or fork this repository to Replit

# 2. Add Secrets in Replit:
#    - MUSL_API_KEY: Your MUSL API key
#    - STRIPE_SECRET_KEY: Your Stripe secret key (optional for billing)
#    - STRIPE_WEBHOOK_SECRET: Stripe webhook secret (optional for billing)

# 3. Click "Run" button - dependencies auto-install

# 4. Database auto-creates on first run

# 5. Access via web preview
```

### **Production Deployment (VPS Linux)**

#### **Step 1: Prepare Local Database**
```bash
# Database is already cleaned with admin user
# Credentials: admin / Abcd1234.
# See scripts/INSTRUCCIONES_DEPLOYMENT.txt for details
```

#### **Step 2: Configure Deployment Script**
```bash
# Edit scripts/deploy_to_production.sh
nano scripts/deploy_to_production.sh

# Update these values:
SERVER_USER="your_username"              # e.g., root, ubuntu
SERVER_HOST="your-server.com"            # IP or domain
PROJECT_PATH="/home/user/shiolplus"      # Project path on server
SERVICE_NAME="shiolplus"                 # Systemd service name
```

#### **Step 3: Run Automated Deployment**
```bash
# Execute deployment script
bash scripts/deploy_to_production.sh

# The script will:
# - Create backup of production database
# - Upload cleaned database with admin user
# - Upload updated code (src, frontend, main.py)
# - Configure file permissions
# - Restart systemd service
```

#### **Step 4: Configure Environment Variables (On Server)**
```bash
# SSH into your server
ssh your_user@your-server.com

# Navigate to project directory
cd /path/to/shiolplus

# Create .env file
nano .env

# Add required environment variables:
MUSL_API_KEY=your_musl_api_key_here
STRIPE_SECRET_KEY=your_stripe_secret_key  # Optional
STRIPE_WEBHOOK_SECRET=your_webhook_secret  # Optional

# Or configure in systemd service:
sudo nano /etc/systemd/system/shiolplus.service

# Add under [Service] section:
Environment="MUSL_API_KEY=your_key"
Environment="STRIPE_SECRET_KEY=your_key"

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart shiolplus
```

#### **Step 5: Verify Deployment**
```bash
# Check service status
sudo systemctl status shiolplus

# View logs in real-time
sudo journalctl -u shiolplus -f

# Test the application
curl http://localhost:5000/health

# Access web interface
# https://your-domain.com
```

### **Manual Deployment (Alternative)**
See `scripts/INSTRUCCIONES_DEPLOYMENT.txt` for detailed step-by-step manual deployment instructions.

## 📊 API Endpoints

### **Authentication**
```
POST /api/v1/auth/register          # Register new user
POST /api/v1/auth/login             # Login (returns JWT + sets cookie)
POST /api/v1/auth/logout            # Logout (clears session cookie)
GET  /api/v1/auth/status            # Check auth status + quota info
GET  /api/v1/auth/stats             # User stats (wins, prizes)
GET  /api/v1/auth/me                # Current user profile
```

### **Billing & Premium**
```
POST /api/v1/billing/create-checkout-session  # Start Stripe checkout
POST /api/v1/billing/webhook                  # Stripe webhook handler
GET  /api/v1/billing/subscription-status      # Check subscription status
POST /api/v1/billing/cancel-subscription      # Cancel subscription
```

### **Public Endpoints**
```
GET /api/v1/public/predictions/latest         # Latest AI predictions
GET /api/v1/public/predictions/by-draw        # Predictions for specific draw
GET /api/v1/public/draws/recent               # Recent drawing results
GET /api/v1/public/jackpot                    # Current jackpot (MUSL API)
GET /api/v1/public/stats                      # System statistics
GET /api/v1/public/winners-stats              # Winning predictions stats
POST /api/v1/public/register-visit            # Anonymous visitor tracking
```

### **System Monitoring**
```
GET /health                         # Simple health check
GET /api/v1/health                  # Detailed health status
```

### **Response Examples**

#### Auth Status (Free User - Saturday)
```json
{
  "authenticated": true,
  "plan_tier": "free",
  "insights_remaining": 5,
  "insights_total": 5,
  "is_premium_day": true,
  "next_draw_day": "Saturday"
}
```

#### Jackpot Info (MUSL API)
```json
{
  "jackpot": "$150,000,000",
  "cash_value": "$75,000,000",
  "next_draw_date": "2025-10-08",
  "source": "musl_api"
}
```

## 🎮 Usage Guide

### **For Guests**
1. Visit shiolplus.com
2. View 1 AI insight without registration
3. Click "Try Free" to register for day-based quota
4. Click "Unlock Premium" for full 100 insights ($9.99/year)

### **For Free Users**
1. Register an account (username, email, password)
2. **Saturday**: Get 5 AI insights (Premium Day experience)
3. **Tuesday/Thursday**: Get 1 AI insight (Regular Day)
4. Total: 7 insights per week across 3 drawing days
5. Track your wins and prizes in stats dashboard
6. Upgrade anytime for 100 insights per draw

### **For Premium Users**
1. Subscribe via Stripe Checkout ($9.99/year)
2. Get 100 ranked AI insights for every draw
3. Full access regardless of day
4. Priority features and historical performance tracking
5. Cancel anytime through account settings

### **Mobile Experience**
1. Install SHIOL+ as PWA (Add to Home Screen)
2. Works offline with cached predictions
3. Touch-optimized interface for mobile
4. Real-time countdown timer
5. Live jackpot updates

## 🧠 Machine Learning Details

### **Pipeline Architecture**
1. **Data Update**: Fetch latest draws from MUSL API
2. **Adaptive Analysis**: Analyze recent performance patterns
3. **Weight Optimization**: Adjust model weights based on accuracy
4. **Prediction Generation**: Create 100 ranked predictions
5. **Evaluation**: Compare predictions against actual results
6. **Validation**: Verify prediction quality and consistency
7. **Performance Analysis**: Track metrics and optimize

### **Scheduling**
- **Automated Execution**: APScheduler runs 30 minutes after each drawing
- **Timezone Aware**: Synchronized to America/New_York (Eastern Time)
- **Drawing Days**: Monday, Wednesday, Saturday at 10:59 PM ET
- **Pipeline Runs**: 11:29 PM ET (30 minutes after drawing)

### **Feature Engineering**
- Historical frequency analysis
- Gap patterns and intervals
- Statistical distribution measures
- Temporal trends and seasonality
- Cross-number correlations
- Recent draw weighting
- Hot/cold number tracking

### **Model Validation**
- Time-series cross-validation
- Real-time performance tracking
- Automatic model retraining
- Continuous accuracy monitoring

## 🔒 Security Features

### **Authentication Security**
- **bcrypt Password Hashing**: Industry-standard password security
- **JWT Tokens**: Secure session management with expiration
- **HttpOnly Cookies**: Protection against XSS attacks
- **Secure Flags**: HTTPS-only cookies in production
- **SameSite Protection**: CSRF attack prevention

### **Payment Security**
- **Stripe Integration**: PCI-compliant payment processing
- **Webhook Verification**: Cryptographic signature validation
- **Idempotency**: Prevents duplicate charge processing
- **Event Deduplication**: Protects against replay attacks

### **Anti-Fraud Measures**
- **Device Fingerprinting**: Browser fingerprint tracking
- **3-Device Limit**: Prevents premium pass abuse
- **JTI Revocation**: Token invalidation system
- **Rate Limiting**: API abuse prevention

### **Data Privacy**
- **No Personal Data Sale**: User data never sold or shared
- **Minimal Data Collection**: Only essential information stored
- **Secure Storage**: Encrypted passwords and sensitive data
- **GDPR Compliance**: User data rights respected

## 📁 Project Structure

```
shiol-plus-v4/
├── src/                          # Backend source code
│   ├── api_auth_endpoints.py    # Authentication API
│   ├── api_billing_endpoints.py # Stripe billing integration
│   ├── api_public_endpoints.py  # Public API endpoints
│   ├── auth_middleware.py       # Auth middleware + quota logic
│   ├── database.py              # Database operations
│   ├── date_utils.py            # Timezone and date utilities
│   ├── musl_api.py              # MUSL API integration
│   └── premium_pass_auth.py     # Premium Pass JWT system
│
├── frontend/                     # Frontend static files
│   ├── index.html               # Main landing page
│   ├── css/
│   │   ├── styles.css           # Main stylesheet
│   │   └── dark-theme.css       # Dark theme overrides
│   ├── js/
│   │   ├── auth-manager.js      # Authentication manager
│   │   ├── text-constants.js    # Centralized UI text
│   │   ├── device-fingerprint.js # Device fingerprinting
│   │   ├── countdown.js         # Countdown timer
│   │   └── public.js            # Public page logic
│   ├── static/                  # PWA assets
│   │   ├── icon-*.png           # PWA icons (various sizes)
│   │   └── apple-touch-icon.png # iOS icon
│   ├── manifest.json            # PWA manifest
│   └── service-worker.js        # Service worker v2.2.4
│
├── scripts/                      # Deployment scripts
│   ├── deploy_to_production.sh  # Automated deployment
│   ├── reset_db_for_production.sql # Database reset SQL
│   └── INSTRUCCIONES_DEPLOYMENT.txt # Deployment guide
│
├── data/                         # Database and data storage
│   └── shiolplus.db             # SQLite database (cleaned)
│
├── main.py                       # Application entry point
├── requirements.txt              # Python dependencies
├── replit.md                     # Project documentation
└── README.md                     # This file
```

## 🚀 Performance Optimizations

### **Backend Optimizations**
- **SQLite Optimizations**: WAL mode, automatic vacuuming, index optimization
- **Efficient Queries**: Indexed lookups, query result caching
- **Async Operations**: FastAPI async endpoints for I/O operations
- **Database Pooling**: Connection pooling for concurrent requests
- **Scheduled Cleanup**: Automatic cleanup of old data and logs

### **Frontend Optimizations**
- **Service Worker Caching**: Assets cached for offline access
- **CDN Delivery**: Tailwind CSS and Font Awesome via CDN
- **Lazy Loading**: Images and content loaded on demand
- **Minified Assets**: Production CSS/JS minification
- **HTTP/2**: Server supports multiplexing and header compression

### **ML Pipeline Optimizations**
- **Incremental Training**: Only retrain when new data available
- **Feature Caching**: Pre-computed features for faster predictions
- **Batch Processing**: Efficient batch prediction generation
- **Memory Management**: Garbage collection and resource cleanup

## ⚖️ Legal & Disclaimers

### **Educational Purpose**
This system is designed for **educational and research purposes only**. It demonstrates AI integration, machine learning applications, and modern web development practices in lottery analysis.

### **No Guarantees**
- **Predictions are for entertainment only** and do not guarantee results
- **Lottery outcomes are random** - past results do not predict future drawings
- **No financial advice** is provided or implied by this system
- **Use responsibly** and only with money you can afford to lose
- **Gambling can be addictive** - seek help if needed

### **Privacy & Security**
- **User data is protected** with industry-standard security measures
- **Passwords are hashed** using bcrypt (never stored in plain text)
- **Payment processing** handled securely by Stripe (PCI compliant)
- **No data selling** - user information is never sold or shared with third parties

### **Data Sources**
- Historical Powerball data from official MUSL and NY State sources
- All data used is publicly available information
- Real-time jackpot information from MUSL Grand Prize API
- No proprietary or confidential data is utilized

### **Subscription Terms**
- **Billing**: $9.99/year charged annually via Stripe
- **Cancellation**: Cancel anytime through account settings
- **Refunds**: Contact support for refund inquiries
- **Auto-Renewal**: Subscription automatically renews unless cancelled
- **Access**: Premium access valid until subscription expires

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the Repository**: Create your own copy
2. **Create Feature Branch**: `git checkout -b feature/your-feature`
3. **Follow Code Style**: Match existing conventions
4. **Test Thoroughly**: Ensure all functionality works
5. **Submit Pull Request**: Describe changes and benefits

### **Development Guidelines**
- Use descriptive variable and function names
- Add comments for complex logic
- Test across different devices and browsers
- Maintain security best practices
- Document API changes

## 📞 Support

For questions, issues, or support:

- **Email**: support@shiolplus.com
- **GitHub Issues**: Report bugs and request features
- **Documentation**: Refer to this README and inline code comments

## 📜 Version History

### **v4.0.0 (Current) - October 2025**
- ✨ Day-based quota system (Saturday Premium Day)
- ✨ Enhanced freemium model with conversion optimization
- ✨ MUSL API integration as primary data source
- ✨ Production-ready deployment scripts
- ✨ Database reset and admin setup automation
- ✨ PWA support with service worker v2.2.4
- ✨ Dark minimalist UI redesign
- ✨ Remember me functionality (30-day sessions)
- ✨ Comprehensive security hardening
- ✨ Fail-closed quota logic for security

### **v3.0.0 - September 2025**
- Ticket verification system with Google Gemini AI
- Automatic number extraction from ticket images
- Prize calculation engine
- Mobile camera integration
- Enhanced frontend layout

### **v2.0.0 - August 2025**
- Freemium business model implementation
- Stripe payment integration
- Premium subscription system
- User authentication and authorization

### **v1.0.0 - July 2025**
- Initial release with ML predictions
- XGBoost ensemble models
- Basic web interface
- Historical data analysis

---

**SHIOL+ v4.0** - AI-Powered Powerball Analysis Platform with Day-Based Freemium Model

*© 2025 SHIOL+ AI Prediction System. Educational use only. Predictions do not guarantee results. Lottery outcomes are random. Use responsibly.*

**Admin Credentials** (Change on first login):
- Username: `admin`
- Password: `Abcd1234.`

**Ready for Production Deployment** ✅
