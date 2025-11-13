# 🔐 API Keys Setup - SHIOL-PLUS

## 📋 Quick Instructions

### 1️⃣ `.env` File Already Created

The `.env` file already exists with automatically generated secret keys:
- ✅ JWT_SECRET_KEY (generated)
- ✅ PREMIUM_PASS_SECRET_KEY (generated)

### 2️⃣ Add Your API Keys

Edit the `.env` file and add your own API keys:

```bash
# Open in VS Code
code .env
```

## 🔑 Required API Keys

### **Gemini AI** (Recommended for AI)
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

📍 **How to get it:**
1. Visit: https://makersuite.google.com/app/apikey
2. Sign in with your Google account
3. Create a new API key
4. Copy it and paste into `.env`

**Current status:** ⚠️ Not configured (AI functionality disabled)

---

### **Stripe** (Optional - Only if you use payments)
```env
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_stripe_webhook_secret_here
STRIPE_PRICE_ID_ANNUAL=price_your_stripe_price_id_here
```

📍 **How to get it:**
1. Visit: https://dashboard.stripe.com/apikeys
2. Create a Stripe account (or sign in)
3. Get your keys in TEST mode
4. Copy them and paste into `.env`

**Current status:** ✅ Development mode (payments disabled)

---

### **MUSL API** (Optional - Official data)
```env
MUSL_API_KEY=your_musl_api_key_here
```

📍 **How to get it:**
- Official Multi-State Lottery API
- Contact: https://www.powerball.com/

**Current status:** ⚠️ System works with local data

---

## 🚀 After Configuring

### Restart the server:

```bash
# Stop current server
ps aux | grep "python main.py" | grep -v grep | awk '{print $2}' | xargs kill

# Start new server
python main.py
```

### Verify configuration:

```bash
# Show loaded variables (without printing sensitive values)
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('✅ GEMINI_API_KEY:', 'Configured' if os.getenv('GEMINI_API_KEY') and len(os.getenv('GEMINI_API_KEY')) > 10 else '❌ Not configured')"
```

---

## 📁 Configuration Files

- `.env` - Your local configuration (DO NOT commit) ✅ Protected
- `.env.example` - Template without real keys ✅ Share safely
- `scripts/generate_secrets.py` - Generate secure keys ✅ Useful

---

## ⚠️ Security

### ✅ Best Practices:
- ✅ `.env` is in `.gitignore` (won't be pushed to GitHub)
- ✅ JWT and Premium keys are randomly generated
- ✅ Use TEST mode keys in development
- ✅ Never share your `.env` file

### ❌ Never:
- ❌ Commit `.env` to Git
- ❌ Share keys in messages/emails
- ❌ Use production keys in development

---

## 🆘 Common Issues

### "GEMINI_API_KEY environment variable is required"
**Solution:** Add your Gemini API key to `.env`

### "Stripe configuration loaded for development environment (enabled: False)"
**Solution:** Normal in development. To enable, add Stripe keys

### Regenerate secret keys:
```bash
python scripts/generate_secrets.py
```

---

## 📞 Support

If you need help:
1. Ensure `.env` has the correct format
2. Verify API keys are valid
3. Restart the server after changes

---

**Last update:** October 21, 2025
