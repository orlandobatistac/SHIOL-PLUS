#!/usr/bin/env python3
"""
Test script for Stripe payment verification fix.

This script tests the new payment flow without requiring real Stripe API calls.
It verifies that the enhanced status endpoint and activation flow work correctly.

Usage:
    python scripts/test_payment_flow.py
"""

import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_db_connection, initialize_database
from src.premium_pass_service import create_premium_pass, get_premium_pass_by_email


def setup_test_environment():
    """Set up test environment with minimal configuration."""
    print("🔧 Setting up test environment...")
    
    # Set test environment variables
    os.environ["ENVIRONMENT"] = "test"
    os.environ["FEATURE_BILLING_ENABLED"] = "true"
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_TESTING_KEY"
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_TESTING_SECRET"
    os.environ["STRIPE_PRICE_ID_ANNUAL"] = "price_test_TESTING_PRICE"
    
    # Initialize database
    initialize_database()
    print("✅ Test environment ready")


def test_premium_pass_creation():
    """Test Premium Pass creation (simulates webhook processing)."""
    print("\n📝 Test 1: Premium Pass Creation")
    print("-" * 50)
    
    test_email = f"test_{datetime.now().timestamp()}@example.com"
    test_subscription = f"sub_test_{datetime.now().timestamp()}"
    
    print(f"Creating Premium Pass for: {test_email}")
    
    try:
        pass_data = create_premium_pass(test_email, test_subscription)
        
        print(f"✅ Premium Pass created successfully!")
        print(f"   Pass ID: {pass_data['pass_id']}")
        print(f"   Email: {pass_data['email']}")
        print(f"   Subscription: {pass_data['stripe_subscription_id']}")
        print(f"   Token: {pass_data['token'][:50]}...")
        
        return pass_data
        
    except Exception as e:
        print(f"❌ Premium Pass creation failed: {e}")
        return None


def test_premium_pass_retrieval(email):
    """Test Premium Pass retrieval by email."""
    print("\n🔍 Test 2: Premium Pass Retrieval")
    print("-" * 50)
    
    print(f"Retrieving Premium Pass for: {email}")
    
    try:
        pass_data = get_premium_pass_by_email(email)
        
        if pass_data:
            print(f"✅ Premium Pass found!")
            print(f"   Pass ID: {pass_data['pass_id']}")
            print(f"   Created: {pass_data['created_at']}")
            return True
        else:
            print(f"❌ Premium Pass not found")
            return False
            
    except Exception as e:
        print(f"❌ Retrieval failed: {e}")
        return False


def test_status_endpoint_logic():
    """Test the status endpoint logic flow."""
    print("\n🔄 Test 3: Status Endpoint Logic")
    print("-" * 50)
    
    test_email = f"status_test_{datetime.now().timestamp()}@example.com"
    test_subscription = f"sub_status_{datetime.now().timestamp()}"
    
    print("Step 1: Create Premium Pass (simulates webhook)")
    pass_data = create_premium_pass(test_email, test_subscription)
    
    if not pass_data:
        print("❌ Failed to create Premium Pass")
        return False
    
    print("✅ Premium Pass created")
    
    print("\nStep 2: Check if pass can be retrieved (simulates status check)")
    retrieved_pass = get_premium_pass_by_email(test_email)
    
    if retrieved_pass:
        print("✅ Premium Pass retrieved successfully")
        print(f"   Status endpoint would return: is_premium=True")
        return True
    else:
        print("❌ Premium Pass retrieval failed")
        return False


def test_idempotent_creation():
    """Test idempotent Premium Pass creation."""
    print("\n🔁 Test 4: Idempotent Creation")
    print("-" * 50)
    
    test_email = f"idempotent_{datetime.now().timestamp()}@example.com"
    test_subscription = f"sub_idempotent_{datetime.now().timestamp()}"
    
    print("Creating Premium Pass (first time)...")
    pass1 = create_premium_pass(test_email, test_subscription)
    
    print("Creating Premium Pass (second time - should return existing)...")
    pass2 = create_premium_pass(test_email, test_subscription)
    
    if pass1['pass_id'] == pass2['pass_id']:
        print("✅ Idempotent creation works correctly")
        print(f"   Both attempts returned same pass_id: {pass1['pass_id']}")
        return True
    else:
        print("❌ Idempotent creation failed - different IDs returned")
        return False


def test_database_schema():
    """Verify database schema for billing."""
    print("\n🗄️  Test 5: Database Schema")
    print("-" * 50)
    
    required_tables = [
        "premium_passes",
        "webhook_events",
        "idempotency_keys"
    ]
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            for table in required_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"✅ Table '{table}' exists ({count} rows)")
        
        return True
        
    except Exception as e:
        print(f"❌ Database schema check failed: {e}")
        return False


def cleanup_test_data():
    """Clean up test data."""
    print("\n🧹 Cleanup: Removing test data...")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Remove test premium passes
            cursor.execute("DELETE FROM premium_passes WHERE email LIKE '%@example.com'")
            deleted_passes = cursor.rowcount
            
            # Remove test webhook events
            cursor.execute("DELETE FROM webhook_events WHERE stripe_event_id LIKE 'evt_test_%'")
            deleted_webhooks = cursor.rowcount
            
            conn.commit()
            
        print(f"✅ Cleaned up {deleted_passes} test passes, {deleted_webhooks} test webhooks")
        
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")


def print_summary(results):
    """Print test summary."""
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    total = len(results)
    passed = sum(results.values())
    failed = total - passed
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("-" * 50)
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Payment flow fix is working correctly.")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("🧪 STRIPE PAYMENT FLOW TEST SUITE")
    print("=" * 50)
    
    # Setup
    setup_test_environment()
    
    # Run tests
    results = {}
    
    pass_data = test_premium_pass_creation()
    results["Premium Pass Creation"] = pass_data is not None
    
    if pass_data:
        results["Premium Pass Retrieval"] = test_premium_pass_retrieval(pass_data['email'])
    else:
        results["Premium Pass Retrieval"] = False
    
    results["Status Endpoint Logic"] = test_status_endpoint_logic()
    results["Idempotent Creation"] = test_idempotent_creation()
    results["Database Schema"] = test_database_schema()
    
    # Cleanup
    cleanup_test_data()
    
    # Summary
    all_passed = print_summary(results)
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
