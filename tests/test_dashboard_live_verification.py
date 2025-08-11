
"""
SHIOL+ Live Dashboard Verification
=================================

Script para verificar en tiempo real que todas las funcionalidades 
del dashboard están funcionando correctamente.
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any, List


class DashboardLiveVerifier:
    """Live verification of dashboard functionality"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:3000"):
        """
        Initialize the live verifier
        
        Args:
            base_url: Base URL of the API server
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session_token = None
        self.verification_results = []
    
    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log verification result"""
        status = "✅ PASS" if success else "❌ FAIL"
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        result = {
            "timestamp": timestamp,
            "test": test_name,
            "success": success,
            "details": details
        }
        
        self.verification_results.append(result)
        print(f"[{timestamp}] {status} {test_name}")
        if details and not success:
            print(f"         Details: {details}")
    
    def verify_server_connection(self) -> bool:
        """Verify server is running and accessible"""
        try:
            response = self.session.get(f"{self.base_url}/", timeout=5)
            if response.status_code == 200:
                self.log_result("Server Connection", True, "Server is accessible")
                return True
            else:
                self.log_result("Server Connection", False, f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Server Connection", False, str(e))
            return False
    
    def verify_login_functionality(self) -> bool:
        """Verify login system works"""
        try:
            # Test login endpoint
            login_data = {
                "username": "admin",
                "password": "shiol2024!"
            }
            
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/login",
                json=login_data,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.log_result("Login Functionality", True, "Login successful")
                    
                    # Store session for further tests
                    cookies = response.cookies
                    if 'shiol_session_token' in cookies:
                        self.session.cookies.update(cookies)
                    
                    return True
                else:
                    self.log_result("Login Functionality", False, "Login returned success=false")
                    return False
            else:
                self.log_result("Login Functionality", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Login Functionality", False, str(e))
            return False
    
    def verify_authentication_check(self) -> bool:
        """Verify authentication verification works"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/auth/verify",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("valid") and data.get("authenticated"):
                    user_info = data.get("user", {})
                    username = user_info.get("username", "unknown")
                    self.log_result("Authentication Check", True, f"Authenticated as {username}")
                    return True
                else:
                    self.log_result("Authentication Check", False, "Not authenticated")
                    return False
            else:
                self.log_result("Authentication Check", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Authentication Check", False, str(e))
            return False
    
    def verify_dashboard_access(self) -> bool:
        """Verify dashboard page is accessible"""
        try:
            response = self.session.get(f"{self.base_url}/dashboard", timeout=5)
            
            if response.status_code == 200:
                content = response.text.lower()
                if "dashboard" in content and "shiol" in content:
                    self.log_result("Dashboard Access", True, "Dashboard page loads correctly")
                    return True
                else:
                    self.log_result("Dashboard Access", False, "Dashboard content not found")
                    return False
            else:
                self.log_result("Dashboard Access", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Dashboard Access", False, str(e))
            return False
    
    def verify_pipeline_status(self) -> bool:
        """Verify pipeline status endpoint"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/pipeline/status",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if "pipeline_status" in data:
                    status = data["pipeline_status"].get("current_status", "unknown")
                    self.log_result("Pipeline Status", True, f"Status: {status}")
                    return True
                else:
                    self.log_result("Pipeline Status", False, "Invalid response format")
                    return False
            else:
                self.log_result("Pipeline Status", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Pipeline Status", False, str(e))
            return False
    
    def verify_public_endpoints(self) -> bool:
        """Verify public endpoints work"""
        try:
            # Test next drawing endpoint
            response = self.session.get(
                f"{self.base_url}/api/v1/public/next-drawing",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if "next_drawing" in data and "featured_prediction" in data:
                    drawing_date = data["next_drawing"].get("date", "unknown")
                    self.log_result("Public Endpoints", True, f"Next drawing: {drawing_date}")
                    return True
                else:
                    self.log_result("Public Endpoints", False, "Invalid response format")
                    return False
            else:
                self.log_result("Public Endpoints", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Public Endpoints", False, str(e))
            return False
    
    def verify_smart_predictions(self) -> bool:
        """Verify Smart AI predictions endpoint"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/predict/smart?limit=5",
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if "smart_predictions" in data:
                    count = len(data["smart_predictions"])
                    self.log_result("Smart Predictions", True, f"Retrieved {count} predictions")
                    return True
                else:
                    self.log_result("Smart Predictions", False, "No predictions in response")
                    return False
            else:
                self.log_result("Smart Predictions", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Smart Predictions", False, str(e))
            return False
    
    def verify_static_assets(self) -> bool:
        """Verify static assets load correctly"""
        try:
            assets_to_check = [
                "/js/app.js",
                "/js/auth.js",
                "/css/styles.css",
                "/login.html"
            ]
            
            all_passed = True
            for asset in assets_to_check:
                response = self.session.get(f"{self.base_url}{asset}", timeout=5)
                if response.status_code != 200:
                    all_passed = False
                    break
            
            if all_passed:
                self.log_result("Static Assets", True, f"All {len(assets_to_check)} assets load correctly")
                return True
            else:
                self.log_result("Static Assets", False, "Some assets failed to load")
                return False
                
        except Exception as e:
            self.log_result("Static Assets", False, str(e))
            return False
    
    def run_comprehensive_verification(self) -> Dict[str, Any]:
        """Run all verification tests"""
        print("🔍 STARTING DASHBOARD LIVE VERIFICATION")
        print("=" * 50)
        
        start_time = time.time()
        
        # Run all verification tests
        tests = [
            ("Server Connection", self.verify_server_connection),
            ("Login Functionality", self.verify_login_functionality),
            ("Authentication Check", self.verify_authentication_check),
            ("Dashboard Access", self.verify_dashboard_access),
            ("Pipeline Status", self.verify_pipeline_status),
            ("Public Endpoints", self.verify_public_endpoints),
            ("Smart Predictions", self.verify_smart_predictions),
            ("Static Assets", self.verify_static_assets)
        ]
        
        total_tests = len(tests)
        passed_tests = 0
        
        for test_name, test_func in tests:
            if test_func():
                passed_tests += 1
            time.sleep(0.5)  # Brief pause between tests
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Generate summary
        success_rate = (passed_tests / total_tests) * 100
        
        summary = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "success_rate": success_rate,
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.now().isoformat(),
            "all_passed": passed_tests == total_tests
        }
        
        print("\n" + "=" * 50)
        print("📊 VERIFICATION SUMMARY")
        print("=" * 50)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Duration: {duration:.1f} seconds")
        
        if summary["all_passed"]:
            print("\n🎉 ALL TESTS PASSED!")
            print("   Your dashboard is working perfectly!")
        else:
            print(f"\n⚠️  {total_tests - passed_tests} TESTS FAILED")
            print("   Please check the failed tests above.")
        
        return summary


def main():
    """Main verification function"""
    print("SHIOL+ Dashboard Live Verification Tool")
    print("Verifying dashboard functionality in real-time...\n")
    
    # Initialize verifier
    verifier = DashboardLiveVerifier()
    
    # Run verification
    results = verifier.run_comprehensive_verification()
    
    # Save results to file
    try:
        with open("dashboard_verification_results.json", "w") as f:
            json.dump({
                "summary": results,
                "detailed_results": verifier.verification_results
            }, f, indent=2)
        print(f"\n📄 Results saved to: dashboard_verification_results.json")
    except Exception as e:
        print(f"\n⚠️  Could not save results: {e}")
    
    return results["all_passed"]


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
