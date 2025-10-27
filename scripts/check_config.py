#!/usr/bin/env python3
"""
Script to verify SHIOL-PLUS API keys configuration
Run: python scripts/check_config.py
"""
import os
from pathlib import Path

# Try to load dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
    dotenv_available = True
except ImportError:
    dotenv_available = False
    print("⚠️  python-dotenv is not installed. Install with: pip install python-dotenv")

def check_env_var(var_name, required=False, min_length=10):
    """Check if an environment variable is configured"""
    value = os.getenv(var_name)
    
    if not value or len(value) < min_length:
        status = "❌ Not configured" if required else "⚠️  Optional (not configured)"
        configured = False
    else:
        status = "✅ Configured"
        configured = True
    
    # Show a short preview for verification
    preview = ""
    if configured and value:
        if len(value) > 20:
            preview = f"  [{value[:8]}...{value[-4:]}]"
        else:
            preview = f"  [{value[:4]}...]"
    
    return status, configured, preview

if __name__ == "__main__":
    print("=" * 70)
    print("🔐 CONFIGURATION VERIFICATION - SHIOL-PLUS")
    print("=" * 70)
    print()
    
    # Check .env file
    env_file = Path(".env")
    if env_file.exists():
        print(f"✅ .env file found ({env_file.stat().st_size} bytes)")
    else:
        print("❌ .env file NOT found")
        print("   Create with: cp .env.example .env")
    print()
    
    # Required variables
    print("🔑 REQUIRED API KEYS:")
    print("-" * 70)
    
    required_vars = {
        "JWT_SECRET_KEY": (True, 32, "User authentication"),
        "PREMIUM_PASS_SECRET_KEY": (True, 32, "Premium subscriptions"),
    }
    
    for var, (req, min_len, desc) in required_vars.items():
        status, configured, preview = check_env_var(var, req, min_len)
        print(f"{status:<25} {var:<30} {desc}")
        if preview:
            print(f"{'':25} {preview}")
    
    print()
    print("🤖 OPTIONAL API KEYS:")
    print("-" * 70)
    
    optional_vars = {
        "GEMINI_API_KEY": "AI for ticket processing",
        "MUSL_API_KEY": "Official Powerball data",
        "STRIPE_SECRET_KEY": "Stripe payments",
        "STRIPE_WEBHOOK_SECRET": "Stripe webhooks",
        "STRIPE_PRICE_ID_ANNUAL": "Annual plan (Stripe)",
    }
    
    for var, desc in optional_vars.items():
        status, configured, preview = check_env_var(var, False, 10)
        print(f"{status:<25} {var:<30} {desc}")
        if preview:
            print(f"{'':25} {preview}")
    
    print()
    print("⚙️  GENERAL CONFIGURATION:")
    print("-" * 70)
    
    config_vars = {
        "ENVIRONMENT": os.getenv("ENVIRONMENT", "development"),
        "DATABASE_PATH": os.getenv("DATABASE_PATH", "./data/shiolplus.db"),
        "PORT": os.getenv("PORT", "8000"),
        "HOST": os.getenv("HOST", "0.0.0.0"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
    }
    
    for var, value in config_vars.items():
        print(f"  {var:<30} {value}")
    
    print()
    print("=" * 70)
    print("📝 NEXT STEPS:")
    print("=" * 70)
    
    # Check how many are configured
    jwt_status = check_env_var("JWT_SECRET_KEY", True, 32)[1]
    gemini_status = check_env_var("GEMINI_API_KEY", False, 10)[1]
    stripe_status = check_env_var("STRIPE_SECRET_KEY", False, 10)[1]
    
    if not jwt_status:
        print("1. ⚠️  Generate secret keys: python scripts/generate_secrets.py")
    else:
        print("1. ✅ Secret keys configured")
    
    if not gemini_status:
        print("2. ⚠️  Add Gemini API key for AI functionality")
        print("   Get at: https://makersuite.google.com/app/apikey")
    else:
        print("2. ✅ Gemini AI configured")
    
    if not stripe_status:
        print("3. ℹ️  Stripe optional (only if you use payments)")
    else:
        print("3. ✅ Stripe configured")
    
    print()
    print("🚀 Restart server after changes:")
    print("   python main.py")
    print("=" * 70)
