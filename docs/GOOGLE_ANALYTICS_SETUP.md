# Google Analytics 4 Setup Guide

## 📊 Overview

This guide explains how to integrate Google Analytics 4 (GA4) with SHIOL+ to track visitors, sessions, and engagement metrics, and display them in your admin dashboard.

---

## 🎯 What You'll Get

✅ **Real-time tracking**: Active users, sessions, pageviews  
✅ **Historical analytics**: 7/30/90-day traffic stats  
✅ **Device breakdown**: Mobile vs Desktop vs Tablet  
✅ **Session metrics**: Avg duration, pages per session  
✅ **API access**: Display stats in your custom dashboard  
✅ **100% FREE**: No costs, works forever

---

## 🚀 Setup Instructions (15 minutes)

### **STEP 1: Create Google Analytics Property**

1. **Go to**: [analytics.google.com](https://analytics.google.com)
2. **Click**: "Admin" (gear icon bottom-left)
3. **Create Account** (if you don't have one):
   - Account name: `SHIOL Plus`
   - Click "Next"
4. **Create Property**:
   - Property name: `SHIOL+ Production`
   - Timezone: `(GMT-05:00) Eastern Time`
   - Currency: `USD`
   - Click "Next"
5. **Business Information** (fill as appropriate)
6. **Click**: "Create" → Accept Terms

### **STEP 2: Get Property ID**

1. In GA4 Admin → **Property Settings**
2. Copy your **Property ID** (format: `123456789`)
3. Save it for later (you'll add it to `.env`)

### **STEP 3: Add Tracking Code to Website**

**Edit these files** (replace `G-XXXXXXXXXX` with your actual Measurement ID):

#### Find Measurement ID:
1. GA4 Admin → **Data Streams**
2. Click your web stream
3. Copy **Measurement ID** (format: `G-XXXXXXXXXX`)

#### Update HTML files:

**frontend/index.html** (line 5):
```html
<!-- Google Analytics 4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

**frontend/status.html** (line 4):
```html
<!-- Google Analytics 4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

**Repeat for**: `payment-success.html`, `privacy.html`, `terms.html`

---

### **STEP 4: Create Service Account (for API Access)**

This allows your backend to fetch analytics data.

#### 4.1 Enable Google Analytics Data API

1. **Go to**: [console.cloud.google.com](https://console.cloud.google.com)
2. **Select/Create Project**: Use same project as GA4 or create new one
3. **Enable API**:
   - Click "APIs & Services" → "Enable APIs and Services"
   - Search: `Google Analytics Data API`
   - Click "Enable"

#### 4.2 Create Service Account

1. **Go to**: "IAM & Admin" → "Service Accounts"
2. **Click**: "Create Service Account"
3. **Fill**:
   - Name: `shiolplus-ga4-reader`
   - Description: `Read-only access to GA4 data for SHIOL+ dashboard`
4. **Click**: "Create and Continue"
5. **Grant Role**: Select `Viewer` (or skip, we'll add in GA4)
6. **Click**: "Done"

#### 4.3 Create JSON Key

1. **Click** on newly created service account
2. **Go to**: "Keys" tab
3. **Click**: "Add Key" → "Create new key"
4. **Select**: JSON format
5. **Click**: "Create" → File downloads automatically

#### 4.4 Save Credentials

1. **Rename file** to `ga4-credentials.json`
2. **Move to**: `/workspaces/SHIOL-PLUS/config/ga4-credentials.json`

```bash
# Example:
mkdir -p config
mv ~/Downloads/shiolplus-ga4-xxxxxx.json config/ga4-credentials.json
```

---

### **STEP 5: Grant Service Account Access to GA4**

1. **Back to**: [analytics.google.com](https://analytics.google.com)
2. **Go to**: Admin → Property Access Management
3. **Click**: "+" (Add users)
4. **Email**: Copy service account email from JSON file (format: `xxx@project-id.iam.gserviceaccount.com`)
5. **Role**: Select `Viewer`
6. **Uncheck**: "Notify new users by email"
7. **Click**: "Add"

---

### **STEP 6: Configure Environment Variables**

Edit `/workspaces/SHIOL-PLUS/.env`:

```bash
# Google Analytics 4
GA4_PROPERTY_ID=123456789  # Your Property ID (NOT Measurement ID)
GA4_CREDENTIALS_PATH=config/ga4-credentials.json
```

**Important**: Use **Property ID** (numbers only), NOT Measurement ID (G-XXXXXXXXXX)

---

### **STEP 7: Install Python Dependencies**

```bash
pip install google-analytics-data==0.18.0
```

Or if using requirements.txt (already updated):

```bash
pip install -r requirements.txt
```

---

### **STEP 8: Test Integration**

#### 8.1 Restart Server

```bash
# Stop server (Ctrl+C)
# Start again
python main.py
```

Check logs for:
```
INFO: Google Analytics 4 client initialized successfully
```

If you see error:
```
WARNING: GA4_PROPERTY_ID or credentials file not found. Analytics disabled.
```
→ Check your `.env` file and credentials path.

#### 8.2 Test API Endpoint

```bash
# Test GA4 endpoint (wait 24h after adding tracking code for first data)
curl http://localhost:8000/api/v1/analytics/ga4?days_back=7
```

Expected response:
```json
{
  "enabled": true,
  "period_days": 7,
  "traffic": {
    "unique_visitors": 23,
    "total_sessions": 27,
    "total_pageviews": 145,
    "new_visitors": 10,
    "returning_visitors": 13,
    "avg_session_duration_sec": 182,
    "avg_session_duration_min": 3.0,
    "pages_per_session": 5.4
  },
  "realtime": {
    "active_users_now": 2,
    "pageviews_last_30min": 5
  },
  "devices": {
    "mobile": 15,
    "desktop": 10,
    "tablet": 2
  }
}
```

---

## 📊 Using the Dashboard

### Admin Dashboard (`/status.html`)

After setup, your admin dashboard shows:

- **🟢 Active Now**: Users currently on site (real-time)
- **Sessions (7d)**: Total visits in last 7 days
- **Pageviews (7d)**: Total pages viewed
- **Avg Duration**: How long users stay

### Manual API Queries

```bash
# Get 30-day stats
curl http://localhost:8000/api/v1/analytics/ga4?days_back=30

# Get full system stats (includes GA4 if enabled)
curl http://localhost:8000/api/v1/system/stats
```

---

## 🔧 Troubleshooting

### ❌ "Analytics disabled" in logs
- Check `GA4_PROPERTY_ID` is set in `.env`
- Check `config/ga4-credentials.json` exists
- Verify file path is correct (relative to project root)

### ❌ "Permission denied" errors
- Service account email must be added to GA4 Property Access Management
- Role must be at least "Viewer"
- Wait 5-10 minutes after adding permissions

### ❌ "No data" in API response
- GA4 takes **24-48 hours** to start showing data after setup
- Verify tracking code is present in HTML (`view-source:` in browser)
- Check Real-time report in GA4 dashboard to confirm tracking works

### ❌ Property ID vs Measurement ID confusion
- **Property ID**: Numbers only (e.g., `123456789`) → Use in `.env`
- **Measurement ID**: Starts with `G-` (e.g., `G-XXXXXXXXXX`) → Use in HTML

---

## 🎯 Next Steps

### Track Custom Events

Add event tracking for key actions:

```javascript
// When user verifies ticket
gtag('event', 'ticket_verified', {
  'event_category': 'engagement',
  'prize_tier': 'Match 3',
  'value': 7
});

// When user generates predictions
gtag('event', 'predictions_generated', {
  'event_category': 'conversion',
  'prediction_count': 200
});

// When user upgrades to premium
gtag('event', 'purchase', {
  'transaction_id': 'premium_pass_123',
  'value': 49.99,
  'currency': 'USD'
});
```

### View in GA4 Dashboard

1. **Real-time**: Reports → Realtime → See live users
2. **Traffic**: Reports → Acquisition → Traffic acquisition
3. **Engagement**: Reports → Engagement → Pages and screens
4. **Custom Events**: Reports → Engagement → Events

---

## 📚 Resources

- **GA4 Documentation**: [developers.google.com/analytics](https://developers.google.com/analytics)
- **Data API Reference**: [developers.google.com/analytics/devguides/reporting/data/v1](https://developers.google.com/analytics/devguides/reporting/data/v1)
- **Property Setup**: [support.google.com/analytics](https://support.google.com/analytics/answer/9304153)

---

## ✅ Checklist

- [ ] Created GA4 property and got Property ID
- [ ] Added tracking code to all HTML files (with correct Measurement ID)
- [ ] Enabled Google Analytics Data API in Cloud Console
- [ ] Created service account and downloaded JSON credentials
- [ ] Saved credentials to `config/ga4-credentials.json`
- [ ] Granted service account "Viewer" access in GA4
- [ ] Updated `.env` with `GA4_PROPERTY_ID` and `GA4_CREDENTIALS_PATH`
- [ ] Installed `google-analytics-data` Python package
- [ ] Restarted server and verified "initialized successfully" in logs
- [ ] Waited 24h and verified data appears in API responses
- [ ] Checked admin dashboard shows GA4 stats

---

**Estimated Setup Time**: 15-20 minutes  
**Cost**: $0 (free forever)  
**Data Retention**: 14 months (standard GA4)

Need help? Check logs in `logs/shiolplus.log` or GA4 dashboard at [analytics.google.com](https://analytics.google.com).
