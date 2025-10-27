#!/usr/bin/env python3
"""
Script to generate secure secret keys for SHIOL-PLUS
Run: python scripts/generate_secrets.py
"""
import secrets
import string

def generate_secret_key(length=64):
    """Generate a secure secret key"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{}|;:,.<>?"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_jwt_secret(length=64):
    """Generate a secure JWT secret (alphanumeric only)"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

if __name__ == "__main__":
    print("=" * 60)
    print("🔐 SECRET KEY GENERATOR - SHIOL-PLUS")
    print("=" * 60)
    print("\nGenerate secure secret keys for your .env file\n")
    
    print("JWT_SECRET_KEY:")
    print(generate_jwt_secret(64))
    print()
    
    print("PREMIUM_PASS_SECRET_KEY:")
    print(generate_secret_key(64))
    print()
    
    print("=" * 60)
    print("📝 INSTRUCTIONS:")
    print("=" * 60)
    print("1. Copy the generated keys above")
    print("2. Paste them into your .env file")
    print("3. Add your Gemini and Stripe API keys")
    print("4. Done!")
    print()
    print("🔗 Get API Keys:")
    print("  • Gemini AI: https://makersuite.google.com/app/apikey")
    print("  • Stripe:    https://dashboard.stripe.com/apikeys")
    print("=" * 60)
