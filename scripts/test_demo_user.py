#!/usr/bin/env python3
"""
Test script to verify demo user exists and credentials work.
"""
import sys
import os
import hashlib
import bcrypt

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_db_connection

def test_demo_user():
    """Test that demo user exists and password is correct."""
    print("Testing demo user authentication...\n")
    
    demo_email = "demo@shiolplus.com"
    demo_password = "Demo2025!"
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Fetch demo user
            cursor.execute("""
                SELECT id, email, username, password_hash, is_admin, is_premium, premium_expires_at
                FROM users
                WHERE email = ?
            """, (demo_email,))
            
            user = cursor.fetchone()
            
            if not user:
                print(f"❌ Demo user not found with email: {demo_email}")
                return False
            
            user_id, email, username, password_hash, is_admin, is_premium, premium_expires = user
            
            # Verify password with SHA-256 pre-hash (matching auth system)
            prehash = hashlib.sha256(demo_password.encode('utf-8')).hexdigest()
            password_matches = bcrypt.checkpw(
                prehash.encode('utf-8'),
                password_hash.encode('utf-8')
            )
            
            print("="*50)
            print("DEMO USER VERIFICATION")
            print("="*50)
            print(f"✅ User found in database")
            print(f"   ID: {user_id}")
            print(f"   Email: {email}")
            print(f"   Username: {username}")
            print(f"   Is Admin: {bool(is_admin)}")
            print(f"   Is Premium: {bool(is_premium)}")
            print(f"   Premium Expires: {premium_expires}")
            print(f"   Password Match: {'✅ YES' if password_matches else '❌ NO'}")
            print("="*50)
            
            if password_matches:
                print("\n✅ Demo user authentication successful!")
                print(f"\nYou can login with:")
                print(f"  Email: {demo_email}")
                print(f"  Password: {demo_password}")
                return True
            else:
                print("\n❌ Password does not match!")
                return False
                
    except Exception as e:
        print(f"❌ Error testing demo user: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_demo_user()
    sys.exit(0 if success else 1)
