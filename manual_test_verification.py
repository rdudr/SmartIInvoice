#!/usr/bin/env python
"""
Manual Test Verification Script for Smart iInvoice MVP

This script performs manual verification of the key workflows by making HTTP requests
to the running Django application and GST microservice.

Prerequisites:
- Django server running on http://127.0.0.1:8000
- GST microservice running on http://127.0.0.1:5001

Usage:
    python manual_test_verification.py
"""

import requests
import json
import time
from datetime import datetime
import base64
from io import BytesIO
from PIL import Image


class ManualTestVerifier:
    """Manual test verifier for Smart iInvoice workflows"""
    
    def __init__(self):
        self.django_base_url = "http://127.0.0.1:8000"
        self.gst_base_url = "http://127.0.0.1:5001"
        self.session = requests.Session()
        self.csrf_token = None
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }
        
    def log(self, message, level='INFO'):
        """Log test messages with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {level}: {message}")
        
    def assert_test(self, condition, test_name, error_message=""):
        """Assert test condition and track results"""
        if condition:
            self.test_results['passed'] += 1
            self.log(f"✅ PASS: {test_name}")
            return True
        else:
            self.test_results['failed'] += 1
            self.test_results['errors'].append(f"{test_name}: {error_message}")
            self.log(f"❌ FAIL: {test_name} - {error_message}", 'ERROR')
            return False
    
    def get_csrf_token(self):
        """Get CSRF token from Django"""
        try:
            response = self.session.get(f"{self.django_base_url}/login/")
            if response.status_code == 200:
                # Extract CSRF token from response
                csrf_start = response.text.find('name="csrfmiddlewaretoken" value="')
                if csrf_start != -1:
                    csrf_start += len('name="csrfmiddlewaretoken" value="')
                    csrf_end = response.text.find('"', csrf_start)
                    self.csrf_token = response.text[csrf_start:csrf_end]
                    return True
            return False
        except Exception as e:
            self.log(f"Error getting CSRF token: {str(e)}", 'ERROR')
            return False
    
    def test_service_availability(self):
        """Test 1: Service availability"""
        self.log("=" * 60)
        self.log("TEST 1: Service Availability")
        self.log("=" * 60)
        
        # Test Django server
        try:
            response = self.session.get(f"{self.django_base_url}/login/")
            self.assert_test(
                response.status_code == 200,
                "Django server accessible",
                f"Status code: {response.status_code}"
            )
        except Exception as e:
            self.assert_test(False, "Django server accessible", str(e))
        
        # Test GST microservice
        try:
            response = requests.get(f"{self.gst_base_url}/api/v1/getCaptcha", timeout=5)
            self.assert_test(
                response.status_code == 200,
                "GST microservice accessible",
                f"Status code: {response.status_code}"
            )
        except Exception as e:
            self.assert_test(False, "GST microservice accessible", str(e))
    
    def test_authentication_workflow(self):
        """Test 2: Authentication workflow"""
        self.log("=" * 60)
        self.log("TEST 2: Authentication Workflow")
        self.log("=" * 60)
        
        # Get CSRF token
        csrf_success = self.get_csrf_token()
        self.assert_test(csrf_success, "CSRF token retrieved")
        
        # Test login page access
        try:
            response = self.session.get(f"{self.django_base_url}/login/")
            self.assert_test(
                response.status_code == 200 and "login" in response.text.lower(),
                "Login page loads correctly"
            )
        except Exception as e:
            self.assert_test(False, "Login page loads correctly", str(e))
        
        # Test dashboard redirect for unauthenticated user
        try:
            response = self.session.get(f"{self.django_base_url}/", allow_redirects=False)
            self.assert_test(
                response.status_code == 302,
                "Dashboard redirects unauthenticated users",
                f"Status code: {response.status_code}"
            )
        except Exception as e:
            self.assert_test(False, "Dashboard redirects unauthenticated users", str(e))
    
    def test_gst_microservice_workflow(self):
        """Test 3: GST microservice workflow"""
        self.log("=" * 60)
        self.log("TEST 3: GST Microservice Workflow")
        self.log("=" * 60)
        
        # Test CAPTCHA request
        try:
            response = requests.get(f"{self.gst_base_url}/api/v1/getCaptcha", timeout=10)
            
            if response.status_code == 200:
                captcha_data = response.json()
                
                self.assert_test(
                    'sessionId' in captcha_data and 'image' in captcha_data,
                    "CAPTCHA request returns required fields"
                )
                
                # Verify image data format
                image_data = captcha_data.get('image', '')
                self.assert_test(
                    image_data.startswith('data:image/png;base64,'),
                    "CAPTCHA image in correct format"
                )
                
                # Test GST verification with invalid data (should fail gracefully)
                session_id = captcha_data.get('sessionId')
                if session_id:
                    verify_data = {
                        "sessionId": session_id,
                        "GSTIN": "INVALID_GSTIN",
                        "captcha": "INVALID"
                    }
                    
                    verify_response = requests.post(
                        f"{self.gst_base_url}/api/v1/getGSTDetails",
                        json=verify_data,
                        timeout=10
                    )
                    
                    self.assert_test(
                        verify_response.status_code == 200,
                        "GST verification endpoint responds",
                        f"Status code: {verify_response.status_code}"
                    )
                    
                    # Should return error for invalid data
                    verify_result = verify_response.json()
                    self.assert_test(
                        'error' in verify_result or verify_result.get('success') == False,
                        "GST verification fails gracefully for invalid data"
                    )
            else:
                self.assert_test(False, "CAPTCHA request successful", f"Status: {response.status_code}")
                
        except Exception as e:
            self.assert_test(False, "GST microservice workflow", str(e))
    
    def test_static_files_and_templates(self):
        """Test 4: Static files and templates"""
        self.log("=" * 60)
        self.log("TEST 4: Static Files and Templates")
        self.log("=" * 60)
        
        # Test login page template
        try:
            response = self.session.get(f"{self.django_base_url}/login/")
            
            # Check for key template elements
            template_checks = [
                ("Smart iInvoice" in response.text, "Page title present"),
                ("login" in response.text.lower(), "Login form present"),
                ("csrfmiddlewaretoken" in response.text, "CSRF protection active"),
                ("tailwind" in response.text.lower() or "css" in response.text.lower(), "CSS styling present")
            ]
            
            for check, description in template_checks:
                self.assert_test(check, description)
                
        except Exception as e:
            self.assert_test(False, "Template rendering", str(e))
    
    def test_error_handling(self):
        """Test 5: Error handling"""
        self.log("=" * 60)
        self.log("TEST 5: Error Handling")
        self.log("=" * 60)
        
        # Test 404 error
        try:
            response = self.session.get(f"{self.django_base_url}/nonexistent-page/")
            self.assert_test(
                response.status_code == 404,
                "404 error for nonexistent pages",
                f"Status code: {response.status_code}"
            )
        except Exception as e:
            self.assert_test(False, "404 error handling", str(e))
        
        # Test invalid API endpoint
        try:
            response = self.session.post(f"{self.django_base_url}/api/invalid/")
            self.assert_test(
                response.status_code in [404, 405],
                "Invalid API endpoints handled correctly",
                f"Status code: {response.status_code}"
            )
        except Exception as e:
            self.assert_test(False, "Invalid API endpoint handling", str(e))
    
    def test_database_connectivity(self):
        """Test 6: Database connectivity (indirect)"""
        self.log("=" * 60)
        self.log("TEST 6: Database Connectivity")
        self.log("=" * 60)
        
        # Test that pages requiring database access work
        try:
            response = self.session.get(f"{self.django_base_url}/login/")
            
            # If login page loads, database is accessible (Django checks this)
            self.assert_test(
                response.status_code == 200,
                "Database connectivity (via Django)",
                f"Status code: {response.status_code}"
            )
            
        except Exception as e:
            self.assert_test(False, "Database connectivity", str(e))
    
    def test_security_headers(self):
        """Test 7: Security headers and configurations"""
        self.log("=" * 60)
        self.log("TEST 7: Security Headers")
        self.log("=" * 60)
        
        try:
            response = self.session.get(f"{self.django_base_url}/login/")
            headers = response.headers
            
            # Check for security headers
            security_checks = [
                ('X-Frame-Options' in headers, "X-Frame-Options header present"),
                ('X-Content-Type-Options' in headers, "X-Content-Type-Options header present"),
                (response.status_code == 200, "HTTPS redirect not blocking local testing")
            ]
            
            for check, description in security_checks:
                self.assert_test(check, description)
                
        except Exception as e:
            self.assert_test(False, "Security headers check", str(e))
    
    def test_api_endpoints_authentication(self):
        """Test 8: API endpoints require authentication"""
        self.log("=" * 60)
        self.log("TEST 8: API Authentication")
        self.log("=" * 60)
        
        # Test upload endpoint without authentication
        try:
            # Create a simple test file
            test_image = Image.new('RGB', (100, 100), color='white')
            img_buffer = BytesIO()
            test_image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            files = {'invoice_file': ('test.png', img_buffer, 'image/png')}
            
            response = requests.post(
                f"{self.django_base_url}/upload/",
                files=files,
                allow_redirects=False
            )
            
            self.assert_test(
                response.status_code in [302, 401, 403],
                "Upload endpoint requires authentication",
                f"Status code: {response.status_code}"
            )
            
        except Exception as e:
            self.assert_test(False, "API authentication check", str(e))
        
        # Test GST verification endpoints without authentication
        try:
            response = requests.post(
                f"{self.django_base_url}/api/request-captcha/",
                allow_redirects=False
            )
            
            self.assert_test(
                response.status_code in [302, 401, 403],
                "GST CAPTCHA endpoint requires authentication",
                f"Status code: {response.status_code}"
            )
            
        except Exception as e:
            self.assert_test(False, "GST API authentication check", str(e))
    
    def run_all_tests(self):
        """Run all manual verification tests"""
        self.log("🚀 Starting Smart iInvoice Manual Verification Tests")
        self.log("=" * 80)
        
        start_time = time.time()
        
        try:
            # Run all test suites
            self.test_service_availability()
            self.test_authentication_workflow()
            self.test_gst_microservice_workflow()
            self.test_static_files_and_templates()
            self.test_error_handling()
            self.test_database_connectivity()
            self.test_security_headers()
            self.test_api_endpoints_authentication()
            
        except Exception as e:
            self.log(f"Unexpected error during testing: {str(e)}", 'ERROR')
            self.test_results['failed'] += 1
            self.test_results['errors'].append(f"Unexpected error: {str(e)}")
        
        # Report results
        end_time = time.time()
        duration = end_time - start_time
        
        self.log("=" * 80)
        self.log("🏁 Manual Verification Results")
        self.log("=" * 80)
        self.log(f"Tests Passed: {self.test_results['passed']}")
        self.log(f"Tests Failed: {self.test_results['failed']}")
        self.log(f"Total Duration: {duration:.2f} seconds")
        
        if self.test_results['errors']:
            self.log("\n❌ Failed Tests:")
            for error in self.test_results['errors']:
                self.log(f"  - {error}")
        
        if self.test_results['passed'] + self.test_results['failed'] > 0:
            success_rate = (self.test_results['passed'] / 
                           (self.test_results['passed'] + self.test_results['failed'])) * 100
            self.log(f"\n📊 Success Rate: {success_rate:.1f}%")
        
        if self.test_results['failed'] == 0:
            self.log("🎉 All manual verification tests passed!")
            return True
        else:
            self.log("⚠️  Some tests failed. Please review the errors above.")
            return False


def main():
    """Main entry point for manual verification"""
    print("Smart iInvoice Manual Verification Suite")
    print("=" * 50)
    
    # Check if services are running
    print("Checking if services are running...")
    
    try:
        django_response = requests.get("http://127.0.0.1:8000/login/", timeout=5)
        print("✅ Django server is running")
    except:
        print("❌ Django server is not running. Please start with: python manage.py runserver 8000")
        return False
    
    try:
        gst_response = requests.get("http://127.0.0.1:5001/api/v1/getCaptcha", timeout=5)
        print("✅ GST microservice is running")
    except:
        print("⚠️  GST microservice is not running. Some tests may fail.")
    
    print("\nStarting manual verification tests...\n")
    
    # Run the tests
    verifier = ManualTestVerifier()
    success = verifier.run_all_tests()
    
    return success


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)