#!/usr/bin/env python3
"""
Create demo user for public demonstrations
Usage: python scripts/create_demo_user.py
"""

import sys
import os
import hashlib
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import get_db_connection
import bcrypt

def create_demo_user():
    """Create or update demo user account"""
    
    # Demo user credentials
    email = "demo@shiolplus.com"
    username = "demo"
    password = "Demo2025!"  # Public demo password
    
    # Hash password with SHA-256 pre-hash (matching auth system)
    prehash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(prehash.encode('utf-8'), salt).decode('utf-8')
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if demo user already exists
            cursor.execute("SELECT id, username FROM users WHERE email = ?", (email,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing demo user
                user_id = existing[0]
                cursor.execute("""
                    UPDATE users 
                    SET password_hash = ?,
                        username = ?,
                        is_admin = 1,
                        premium_expires_at = ?,
                        is_premium = 1
                    WHERE id = ?
                """, (password_hash, username, 
                      (datetime.now() + timedelta(days=365)).isoformat(), 
                      user_id))
                print(f"✅ Demo user updated (ID: {user_id})")
            else:
                # Create new demo user
                cursor.execute("""
                    INSERT INTO users (email, username, password_hash, is_admin, premium_expires_at, is_premium)
                    VALUES (?, ?, ?, 1, ?, 1)
                """, (email, username, password_hash, 
                      (datetime.now() + timedelta(days=365)).isoformat()))
                user_id = cursor.lastrowid
                print(f"✅ Demo user created (ID: {user_id})")
            
            conn.commit()
            
            # Display credentials
            print("\n" + "="*50)
            print("DEMO USER CREDENTIALS")
            print("="*50)
            print(f"Email:    {email}")
            print(f"Username: {username}")
            print(f"Password: {password}")
            print(f"Role:     Admin (with Premium)")
            print("="*50)
            print("\n⚠️  NOTE: This user is protected by demo-mode.js")
            print("   - Cannot be deleted")
            print("   - Cannot be modified by admin actions")
            print("   - GitHub links and sensitive data hidden")
            print("   - Pipeline execution disabled")
            
    except Exception as e:
        print(f"❌ Error creating demo user: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Creating demo user for SHIOL+...\n")
    success = create_demo_user()
    sys.exit(0 if success else 1)
