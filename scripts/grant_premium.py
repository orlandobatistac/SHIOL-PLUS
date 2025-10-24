#!/usr/bin/env python3
"""
Grant premium access to a user (e.g., admin) and create a Premium Pass.

Usage:
  python scripts/grant_premium.py --email admin@shiolplus.com

This will:
  - Find the user by email
  - Upgrade them to premium for 1 year
  - Create a Premium Pass token with a manual subscription id
  - Print a short summary
"""
import argparse
from datetime import datetime, timedelta
from loguru import logger

import sys
import os

# Ensure imports work when run from project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.database import get_db_connection, upgrade_user_to_premium
from src.premium_pass_service import create_premium_pass, get_premium_pass_by_email


def get_user_by_email(email: str):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, email, username, is_premium, premium_expires_at
            FROM users WHERE email = ? AND is_active = TRUE
            """,
            (email,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "email": row[1],
            "username": row[2],
            "is_premium": bool(row[3]),
            "premium_expires_at": row[4],
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True, help="User email to upgrade")
    args = parser.parse_args()

    email = args.email.strip().lower()

    user = get_user_by_email(email)
    if not user:
        logger.error(f"User with email {email} not found. Please create the user first.")
        sys.exit(1)

    # Upgrade user to premium (1 year)
    expiry = datetime.utcnow() + timedelta(days=365)
    if upgrade_user_to_premium(user["id"], expiry):
        logger.info(f"Upgraded user {email} to premium until {expiry.isoformat()}")
    else:
        logger.warning("Failed to update user premium flag (may already be premium)")

    # Create or reuse Premium Pass
    existing = get_premium_pass_by_email(email)
    if existing:
        logger.info(f"Existing Premium Pass found (id={existing['pass_id']}). Reusing.")
        token = existing["token"]
        sub_id = existing["stripe_subscription_id"]
    else:
        manual_subscription_id = f"admin_manual_grant_{datetime.utcnow().strftime('%Y%m%d')}"
        created = create_premium_pass(email=email, stripe_subscription_id=manual_subscription_id, user_id=user["id"])
        token = created["token"]
        sub_id = manual_subscription_id
        logger.info(f"Created Premium Pass for {email} (subscription={sub_id}, pass_id={created['pass_id']})")

    print("\n==== Premium Grant Summary ====")
    print(f"Email: {email}")
    print(f"User ID: {user['id']}")
    print(f"Premium until: {expiry.isoformat()}")
    print(f"Subscription ID: {sub_id}")
    print("Token (keep secret):")
    print(token)
    print("\nNote: Premium access works via user.is_premium or Premium Pass cookie. After login, the premium flag will be honored.\n")


if __name__ == "__main__":
    main()
