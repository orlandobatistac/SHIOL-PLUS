
#!/usr/bin/env python3
"""
Debug script para verificar específicamente los problemas del dashboard
"""

import requests
import time
import json
from datetime import datetime

def debug_dashboard_issues():
    """Debug específico para los problemas encontrados"""
    base_url = "https://ca2ad072-fb07-4d65-b794-85eb3cda7ebc-00-30p6md69d9t1.kirk.replit.dev"
    
    print("🔍 DEBUGGING DASHBOARD ISSUES")
    print("=" * 50)
    
    # Test 1: Basic server connection
    print("\n1. Testing basic server connection...")
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Response size: {len(response.text)} chars")
        print(f"   Content-Type: {response.headers.get('content-type', 'unknown')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: Dashboard page access
    print("\n2. Testing dashboard page access...")
    try:
        response = requests.get(f"{base_url}/dashboard.html", timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Response size: {len(response.text)} chars")
        
        content = response.text.lower()
        dashboard_keywords = ['dashboard', 'shiol', 'pipeline', 'predictions']
        found_keywords = [kw for kw in dashboard_keywords if kw in content]
        
        print(f"   Keywords found: {found_keywords}")
        print(f"   Contains 'dashboard': {'dashboard' in content}")
        print(f"   Contains 'shiol': {'shiol' in content}")
        
        # Show first 200 chars of response
        print(f"   First 200 chars: {response.text[:200]}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Static assets
    print("\n3. Testing static assets...")
    assets = [
        "/css/styles.css",
        "/js/app.js", 
        "/js/auth.js"
    ]
    
    for asset in assets:
        try:
            response = requests.get(f"{base_url}{asset}", timeout=5)
            print(f"   {asset}: {response.status_code} ({len(response.text)} chars)")
        except Exception as e:
            print(f"   {asset}: ❌ {e}")
    
    # Test 4: API endpoints
    print("\n4. Testing API endpoints...")
    api_endpoints = [
        "/api/v1/pipeline/status",
        "/api/v1/public/next-drawing",
        "/api/v1/predict/smart?limit=5"
    ]
    
    for endpoint in api_endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            print(f"   {endpoint}: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"      Keys: {list(data.keys())}")
        except Exception as e:
            print(f"   {endpoint}: ❌ {e}")
    
    # Test 5: Authentication flow
    print("\n5. Testing authentication...")
    session = requests.Session()
    
    try:
        # Test login
        login_data = {"username": "admin", "password": "shiol2024!"}
        response = session.post(f"{base_url}/api/v1/auth/login", json=login_data, timeout=10)
        print(f"   Login: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Login success: {data.get('success', False)}")
            
            # Test dashboard access with auth
            response = session.get(f"{base_url}/dashboard.html", timeout=10)
            print(f"   Dashboard with auth: {response.status_code}")
            
            # Test auth verification
            response = session.get(f"{base_url}/api/v1/auth/verify", timeout=5)
            print(f"   Auth verify: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"      Authenticated: {data.get('authenticated', False)}")
                print(f"      User: {data.get('user', {}).get('username', 'unknown')}")
        
    except Exception as e:
        print(f"   ❌ Auth error: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 DEBUG COMPLETED")

if __name__ == "__main__":
    debug_dashboard_verification()
