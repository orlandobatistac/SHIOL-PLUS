#!/usr/bin/env python3
# Test script for Stripe integration in test mode
"""
Manual testing script for Stripe billing integration.
Run this to test the integration with Stripe test keys.
"""

import os
import sys
import requests
import json
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_billing_status():
    """Test billing status endpoint."""
    print("🔍 Testing billing status endpoint...")
    
    try:
        response = requests.get("http://localhost:5000/api/v1/billing/status")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("enabled"):
                print("✅ Billing is enabled")
            else:
                print("❌ Billing is disabled")
                print(f"Message: {data.get('message', 'No message')}")
        
        return response.status_code == 200
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - make sure the server is running on localhost:5000")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_create_checkout_session():
    """Test creating a checkout session."""
    print("\n💳 Testing checkout session creation...")
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": f"test-{datetime.now().timestamp()}"
        }
        
        data = {
            "success_url": "http://localhost:5000/payment-success",
            "cancel_url": "http://localhost:5000/"
        }
        
        response = requests.post(
            "http://localhost:5000/api/v1/billing/create-checkout-session",
            headers=headers,
            json=data
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            result = response.json()
            checkout_url = result.get("checkout_url")
            session_id = result.get("session_id")
            
            print("✅ Checkout session created successfully")
            print(f"Session ID: {session_id}")
            print(f"Checkout URL: {checkout_url}")
            
            if checkout_url:
                print("\n📝 You can test the payment flow by visiting:")
                print(f"   {checkout_url}")
                print("\n💡 Use Stripe test card numbers:")
                print("   Success: 4242 4242 4242 4242")
                print("   Decline: 4000 0000 0000 0002")
                print("   Any future date, any 3-digit CVC")
            
            return True
        else:
            print(f"❌ Failed to create checkout session")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_webhook_endpoint():
    """Test webhook endpoint (without valid signature)."""
    print("\n🔗 Testing webhook endpoint...")
    
    try:
        # This will fail signature verification but tests the endpoint
        headers = {
            "Content-Type": "application/json",
            "stripe-signature": "invalid_signature_for_testing"
        }
        
        test_event = {
            "id": "evt_test_webhook",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "customer_email": "test@example.com",
                    "subscription": "sub_test_123"
                }
            }
        }
        
        response = requests.post(
            "http://localhost:5000/api/v1/billing/webhook",
            headers=headers,
            data=json.dumps(test_event)
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 400:
            print("✅ Webhook endpoint is working (signature verification failed as expected)")
            return True
        else:
            print(f"⚠️ Unexpected response: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_environment_variables():
    """Check required environment variables."""
    print("🔧 Checking environment variables...")
    
    required_vars = [
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET", 
        "STRIPE_PRICE_ID_ANNUAL",
        "PREMIUM_PASS_SECRET_KEY"
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask the value for security
            masked_value = value[:8] + "..." if len(value) > 8 else "***"
            print(f"✅ {var}: {masked_value}")
        else:
            print(f"❌ {var}: Not set")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️ Missing environment variables: {', '.join(missing_vars)}")
        print("\n💡 For testing, you can set test values:")
        print("export STRIPE_SECRET_KEY='sk_test_your_key_here'")
        print("export STRIPE_WEBHOOK_SECRET='whsec_your_webhook_secret'")
        print("export STRIPE_PRICE_ID_ANNUAL='price_your_price_id'")
        print("export PREMIUM_PASS_SECRET_KEY='your_premium_pass_secret'")
        return False
    
    return True

def run_integration_tests():
    """Run all integration tests."""
    print("🚀 Starting Stripe integration tests...")
    print("=" * 50)
    
    # Check environment
    if not check_environment_variables():
        print("\n❌ Environment check failed")
        return False
    
    # Test endpoints
    tests = [
        ("Billing Status", test_billing_status),
        ("Checkout Session", test_create_checkout_session),
        ("Webhook Endpoint", test_webhook_endpoint)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'=' * 20} {test_name} {'=' * 20}")
        success = test_func()
        results.append((test_name, success))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    all_passed = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {test_name}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All tests passed! Stripe integration is working correctly.")
        print("\n📋 Next steps:")
        print("1. Test the complete payment flow in your browser")
        print("2. Check the payment-success page")
        print("3. Verify Premium Pass tokens are working")
    else:
        print("\n⚠️ Some tests failed. Check the logs above for details.")
    
    return all_passed

if __name__ == "__main__":
    print("SHIOL+ Stripe Integration Test Suite")
    print("===================================\n")
    
    success = run_integration_tests()
    
    exit_code = 0 if success else 1
    sys.exit(exit_code)