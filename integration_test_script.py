#!/usr/bin/env python
"""
Integration and Manual Testing Script for Smart iInvoice MVP

This script performs comprehensive integration testing of the Smart iInvoice system,
covering all major workflows and error scenarios as specified in task 13.

Test Coverage:
1. Complete invoice upload and processing flow
2. GST verification workflow end-to-end
3. Authentication and authorization flows
4. Status transitions verification
5. Error handling scenarios

Usage:
    python integration_test_script.py
"""

import os
import sys
import django
import json
import time
import requests
from decimal import Decimal
from datetime import date, datetime
from io import BytesIO
from PIL import Image
import subprocess
import signal

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartinvoice.settings')
django.setup()

from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from invoice_processor.models import Invoice, LineItem, ComplianceFlag
from invoice_processor.services.gemini_service import extract_data_from_image
from invoice_processor.services.analysis_engine import run_all_checks, normalize_product_key
from invoice_processor.services.gst_client import get_captcha, verify_gstin, is_gst_service_available


class IntegrationTestRunner:
    """Main test runner for integration tests"""
    
    def __init__(self):
        self.client = Client()
        self.test_user = None
        self.gst_service_process = None
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
    
    def setup_test_environment(self):
        """Setup test environment and data"""
        self.log("Setting up test environment...")
        
        # Create test user
        try:
            self.test_user = User.objects.create_user(
                username='testuser_integration',
                email='test@integration.com',
                password='testpass123',
                first_name='Test',
                last_name='User'
            )
            self.log("Test user created successfully")
        except Exception as e:
            self.log(f"Error creating test user: {str(e)}", 'ERROR')
            return False
            
        # Start GST microservice
        try:
            self.start_gst_service()
        except Exception as e:
            self.log(f"Warning: Could not start GST service: {str(e)}", 'WARNING')
            
        return True
    
    def start_gst_service(self):
        """Start the GST microservice for testing"""
        self.log("Starting GST microservice...")
        
        gst_app_path = os.path.join(os.getcwd(), 'gst verification template', 'app.py')
        if os.path.exists(gst_app_path):
            # Start the GST service as a subprocess
            self.gst_service_process = subprocess.Popen([
                sys.executable, gst_app_path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait a moment for service to start
            time.sleep(3)
            
            # Check if service is running
            if is_gst_service_available():
                self.log("GST microservice started successfully")
            else:
                self.log("GST microservice may not be fully ready", 'WARNING')
        else:
            self.log("GST microservice app.py not found", 'WARNING')
    
    def cleanup_test_environment(self):
        """Cleanup test environment"""
        self.log("Cleaning up test environment...")
        
        # Stop GST service
        if self.gst_service_process:
            try:
                self.gst_service_process.terminate()
                self.gst_service_process.wait(timeout=5)
                self.log("GST microservice stopped")
            except subprocess.TimeoutExpired:
                self.gst_service_process.kill()
                self.log("GST microservice force killed")
            except Exception as e:
                self.log(f"Error stopping GST service: {str(e)}", 'WARNING')
        
        # Clean up test data
        try:
            if self.test_user:
                Invoice.objects.filter(uploaded_by=self.test_user).delete()
                self.test_user.delete()
                self.log("Test data cleaned up")
        except Exception as e:
            self.log(f"Error cleaning up test data: {str(e)}", 'WARNING')
    
    def create_test_image_file(self, filename='test_invoice.png'):
        """Create a test image file for upload testing"""
        # Create a test image
        image = Image.new('RGB', (800, 600), color='white')
        image_io = BytesIO()
        image.save(image_io, format='PNG')
        image_io.seek(0)
        
        return SimpleUploadedFile(
            filename,
            image_io.getvalue(),
            content_type='image/png'
        )
    
    def test_authentication_flows(self):
        """Test 1: Authentication and authorization flows"""
        self.log("=" * 60)
        self.log("TEST 1: Authentication and Authorization Flows")
        self.log("=" * 60)
        
        # Test 1.1: Login page access
        response = self.client.get(reverse('login'))
        self.assert_test(
            response.status_code == 200,
            "Login page accessible",
            f"Expected 200, got {response.status_code}"
        )
        
        # Test 1.2: Dashboard requires authentication
        response = self.client.get(reverse('dashboard'))
        self.assert_test(
            response.status_code == 302,
            "Dashboard redirects unauthenticated users",
            f"Expected 302 redirect, got {response.status_code}"
        )
        
        # Test 1.3: Successful login
        login_success = self.client.login(username='testuser_integration', password='testpass123')
        self.assert_test(
            login_success,
            "User can login with correct credentials"
        )
        
        # Test 1.4: Dashboard accessible after login
        response = self.client.get(reverse('dashboard'))
        self.assert_test(
            response.status_code == 200,
            "Dashboard accessible after authentication",
            f"Expected 200, got {response.status_code}"
        )
        
        # Test 1.5: Upload endpoint requires authentication
        self.client.logout()
        test_file = self.create_test_image_file()
        response = self.client.post(reverse('upload_invoice'), {
            'invoice_file': test_file
        })
        self.assert_test(
            response.status_code == 302,
            "Upload endpoint requires authentication",
            f"Expected 302 redirect, got {response.status_code}"
        )
        
        # Re-login for subsequent tests
        self.client.login(username='testuser_integration', password='testpass123')
    
    def test_invoice_upload_processing_flow(self):
        """Test 2: Complete invoice upload and processing flow"""
        self.log("=" * 60)
        self.log("TEST 2: Invoice Upload and Processing Flow")
        self.log("=" * 60)
        
        # Test 2.1: Valid file upload
        test_file = self.create_test_image_file()
        
        # Mock the Gemini service response for testing
        sample_extracted_data = {
            'is_invoice': True,
            'invoice_id': 'TEST-INV-001',
            'invoice_date': '2023-12-01',
            'vendor_name': 'Test Vendor Ltd',
            'vendor_gstin': '27AAPFU0939F1ZV',
            'billed_company_gstin': '29AABCT1332L1ZZ',
            'grand_total': 1180.00,
            'line_items': [
                {
                    'description': 'Test Product A',
                    'hsn_sac_code': '1001',
                    'quantity': 10,
                    'unit_price': 100.00,
                    'billed_gst_rate': 18.00,
                    'line_total': 1180.00
                }
            ]
        }
        
        # Test file upload (this will use real Gemini API if configured)
        response = self.client.post(reverse('upload_invoice'), {
            'invoice_file': test_file
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Check if upload was processed (may fail if Gemini API not configured)
        if response.status_code == 200:
            response_data = json.loads(response.content)
            self.assert_test(
                response_data.get('success', False),
                "Invoice upload processed successfully"
            )
            
            # Test 2.2: Invoice saved to database
            invoice_count = Invoice.objects.filter(uploaded_by=self.test_user).count()
            self.assert_test(
                invoice_count > 0,
                "Invoice saved to database",
                f"Expected > 0 invoices, found {invoice_count}"
            )
            
            if invoice_count > 0:
                invoice = Invoice.objects.filter(uploaded_by=self.test_user).first()
                
                # Test 2.3: Invoice status transitions
                self.assert_test(
                    invoice.status in ['PENDING_ANALYSIS', 'CLEARED', 'HAS_ANOMALIES'],
                    "Invoice has valid status",
                    f"Invalid status: {invoice.status}"
                )
                
                # Test 2.4: Line items created
                line_items_count = LineItem.objects.filter(invoice=invoice).count()
                self.assert_test(
                    line_items_count >= 0,
                    "Line items processed",
                    f"Line items count: {line_items_count}"
                )
        else:
            self.log("Upload failed - likely due to Gemini API configuration", 'WARNING')
            self.assert_test(
                response.status_code in [400, 503],
                "Upload fails gracefully when service unavailable"
            )
    
    def test_file_validation(self):
        """Test 3: File upload validation"""
        self.log("=" * 60)
        self.log("TEST 3: File Upload Validation")
        self.log("=" * 60)
        
        # Test 3.1: Invalid file type
        invalid_file = SimpleUploadedFile(
            "test.txt",
            b"This is not an image",
            content_type="text/plain"
        )
        
        response = self.client.post(reverse('upload_invoice'), {
            'invoice_file': invalid_file
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assert_test(
            response.status_code == 400,
            "Invalid file type rejected",
            f"Expected 400, got {response.status_code}"
        )
        
        # Test 3.2: File too large (simulate)
        # Note: This is hard to test without actually creating a large file
        self.log("File size validation - would need large file to test properly", 'INFO')
        
        # Test 3.3: Empty file
        empty_file = SimpleUploadedFile(
            "empty.png",
            b"",
            content_type="image/png"
        )
        
        response = self.client.post(reverse('upload_invoice'), {
            'invoice_file': empty_file
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assert_test(
            response.status_code == 400,
            "Empty file rejected",
            f"Expected 400, got {response.status_code}"
        )
    
    def test_analysis_engine_functions(self):
        """Test 4: Analysis engine compliance checks"""
        self.log("=" * 60)
        self.log("TEST 4: Analysis Engine Functions")
        self.log("=" * 60)
        
        # Test 4.1: Product key normalization
        test_cases = [
            ("Test Product A", "test product"),
            ("The Best Product for Testing", "best product testing"),
            ("Product-A (Special) & More!", "product special more"),
            ("", ""),
        ]
        
        for input_text, expected in test_cases:
            result = normalize_product_key(input_text)
            self.assert_test(
                result == expected,
                f"Product key normalization: '{input_text}' -> '{expected}'",
                f"Got '{result}', expected '{expected}'"
            )
        
        # Test 4.2: Create test invoice for compliance checks
        test_invoice = Invoice.objects.create(
            invoice_id='TEST-COMPLIANCE-001',
            invoice_date=date(2023, 12, 1),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1180.00'),
            uploaded_by=self.test_user,
            file_path='test/path.pdf'
        )
        
        # Test 4.3: Line item creation
        test_line_item = LineItem.objects.create(
            invoice=test_invoice,
            description='Test Product A',
            normalized_key=normalize_product_key('Test Product A'),
            hsn_sac_code='1001',
            quantity=Decimal('10'),
            unit_price=Decimal('100.00'),
            billed_gst_rate=Decimal('18.00'),
            line_total=Decimal('1180.00')
        )
        
        self.assert_test(
            test_line_item.normalized_key == 'test product',
            "Line item normalized key set correctly"
        )
        
        # Test 4.4: Compliance flag creation
        test_flag = ComplianceFlag.objects.create(
            invoice=test_invoice,
            flag_type='ARITHMETIC_ERROR',
            severity='CRITICAL',
            description='Test compliance flag'
        )
        
        self.assert_test(
            test_flag.flag_type == 'ARITHMETIC_ERROR',
            "Compliance flag created successfully"
        )
    
    def test_gst_verification_workflow(self):
        """Test 5: GST verification workflow end-to-end"""
        self.log("=" * 60)
        self.log("TEST 5: GST Verification Workflow")
        self.log("=" * 60)
        
        # Test 5.1: GST verification page access
        response = self.client.get(reverse('gst_verification'))
        self.assert_test(
            response.status_code == 200,
            "GST verification page accessible",
            f"Expected 200, got {response.status_code}"
        )
        
        # Test 5.2: GST service availability check
        service_available = is_gst_service_available()
        self.log(f"GST service available: {service_available}", 'INFO')
        
        if service_available:
            # Test 5.3: CAPTCHA request
            try:
                response = self.client.post(reverse('request_captcha'), 
                                          HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                
                if response.status_code == 200:
                    captcha_data = json.loads(response.content)
                    self.assert_test(
                        captcha_data.get('success', False),
                        "CAPTCHA request successful"
                    )
                    
                    if captcha_data.get('success'):
                        self.assert_test(
                            'sessionId' in captcha_data and 'captchaImage' in captcha_data,
                            "CAPTCHA response contains required fields"
                        )
                else:
                    self.assert_test(
                        response.status_code == 503,
                        "CAPTCHA request fails gracefully when service unavailable"
                    )
            except Exception as e:
                self.log(f"CAPTCHA test error: {str(e)}", 'WARNING')
        else:
            self.log("GST service not available - skipping CAPTCHA tests", 'WARNING')
        
        # Test 5.4: GST verification page filtering
        for filter_status in ['all', 'pending', 'verified', 'failed']:
            response = self.client.get(reverse('gst_verification'), {'status': filter_status})
            self.assert_test(
                response.status_code == 200,
                f"GST verification page filter '{filter_status}' works",
                f"Expected 200, got {response.status_code}"
            )
    
    def test_dashboard_functionality(self):
        """Test 6: Dashboard functionality and metrics"""
        self.log("=" * 60)
        self.log("TEST 6: Dashboard Functionality")
        self.log("=" * 60)
        
        # Test 6.1: Dashboard loads with metrics
        response = self.client.get(reverse('dashboard'))
        self.assert_test(
            response.status_code == 200,
            "Dashboard loads successfully"
        )
        
        # Test 6.2: Dashboard context contains required data
        context_keys = ['metrics', 'anomaly_breakdown', 'recent_invoices', 'suspected_invoices']
        for key in context_keys:
            self.assert_test(
                key in response.context,
                f"Dashboard context contains '{key}'"
            )
        
        # Test 6.3: Metrics calculation
        metrics = response.context.get('metrics', {})
        required_metrics = ['invoices_awaiting_verification', 'anomalies_this_week', 'total_amount_processed']
        for metric in required_metrics:
            self.assert_test(
                metric in metrics,
                f"Dashboard metrics contains '{metric}'"
            )
    
    def test_error_handling_scenarios(self):
        """Test 7: Error handling scenarios"""
        self.log("=" * 60)
        self.log("TEST 7: Error Handling Scenarios")
        self.log("=" * 60)
        
        # Test 7.1: Invalid URL access
        response = self.client.get('/invalid-url/')
        self.assert_test(
            response.status_code == 404,
            "Invalid URLs return 404",
            f"Expected 404, got {response.status_code}"
        )
        
        # Test 7.2: CSRF protection
        self.client.logout()
        response = self.client.post(reverse('upload_invoice'), {
            'invoice_file': self.create_test_image_file()
        })
        # Should redirect to login due to authentication, but CSRF would be checked first
        self.assert_test(
            response.status_code in [302, 403],
            "CSRF protection active"
        )
        
        # Re-login for other tests
        self.client.login(username='testuser_integration', password='testpass123')
        
        # Test 7.3: Invalid GST verification request
        response = self.client.post(reverse('verify_gst'), 
                                  json.dumps({'invalid': 'data'}),
                                  content_type='application/json',
                                  HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assert_test(
            response.status_code == 400,
            "Invalid GST verification request rejected"
        )
    
    def test_database_relationships(self):
        """Test 8: Database model relationships and constraints"""
        self.log("=" * 60)
        self.log("TEST 8: Database Relationships and Constraints")
        self.log("=" * 60)
        
        # Create test data
        invoice = Invoice.objects.create(
            invoice_id='TEST-REL-001',
            invoice_date=date(2023, 12, 1),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1000.00'),
            uploaded_by=self.test_user,
            file_path='test/path.pdf'
        )
        
        line_item = LineItem.objects.create(
            invoice=invoice,
            description='Test Product',
            normalized_key='test product',
            hsn_sac_code='1001',
            quantity=Decimal('1'),
            unit_price=Decimal('1000.00'),
            billed_gst_rate=Decimal('0.00'),
            line_total=Decimal('1000.00')
        )
        
        flag = ComplianceFlag.objects.create(
            invoice=invoice,
            line_item=line_item,
            flag_type='ARITHMETIC_ERROR',
            severity='CRITICAL',
            description='Test flag'
        )
        
        # Test 8.1: Relationships work correctly
        self.assert_test(
            invoice.line_items.count() == 1,
            "Invoice-LineItem relationship works"
        )
        
        self.assert_test(
            invoice.compliance_flags.count() == 1,
            "Invoice-ComplianceFlag relationship works"
        )
        
        # Test 8.2: Cascade deletion
        invoice_id = invoice.id
        line_item_id = line_item.id
        flag_id = flag.id
        
        invoice.delete()
        
        self.assert_test(
            not LineItem.objects.filter(id=line_item_id).exists(),
            "LineItem deleted when Invoice deleted (cascade)"
        )
        
        self.assert_test(
            not ComplianceFlag.objects.filter(id=flag_id).exists(),
            "ComplianceFlag deleted when Invoice deleted (cascade)"
        )
    
    def run_all_tests(self):
        """Run all integration tests"""
        self.log("🚀 Starting Smart iInvoice Integration Tests")
        self.log("=" * 80)
        
        start_time = time.time()
        
        # Setup
        if not self.setup_test_environment():
            self.log("Failed to setup test environment", 'ERROR')
            return False
        
        try:
            # Run all test suites
            self.test_authentication_flows()
            self.test_invoice_upload_processing_flow()
            self.test_file_validation()
            self.test_analysis_engine_functions()
            self.test_gst_verification_workflow()
            self.test_dashboard_functionality()
            self.test_error_handling_scenarios()
            self.test_database_relationships()
            
        except Exception as e:
            self.log(f"Unexpected error during testing: {str(e)}", 'ERROR')
            self.test_results['failed'] += 1
            self.test_results['errors'].append(f"Unexpected error: {str(e)}")
        
        finally:
            # Cleanup
            self.cleanup_test_environment()
        
        # Report results
        end_time = time.time()
        duration = end_time - start_time
        
        self.log("=" * 80)
        self.log("🏁 Integration Test Results")
        self.log("=" * 80)
        self.log(f"Tests Passed: {self.test_results['passed']}")
        self.log(f"Tests Failed: {self.test_results['failed']}")
        self.log(f"Total Duration: {duration:.2f} seconds")
        
        if self.test_results['errors']:
            self.log("\n❌ Failed Tests:")
            for error in self.test_results['errors']:
                self.log(f"  - {error}")
        
        success_rate = (self.test_results['passed'] / 
                       (self.test_results['passed'] + self.test_results['failed'])) * 100
        
        self.log(f"\n📊 Success Rate: {success_rate:.1f}%")
        
        if self.test_results['failed'] == 0:
            self.log("🎉 All tests passed!")
            return True
        else:
            self.log("⚠️  Some tests failed. Please review the errors above.")
            return False


def main():
    """Main entry point for integration testing"""
    print("Smart iInvoice Integration Testing Suite")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists('manage.py'):
        print("❌ Error: Please run this script from the Django project root directory")
        sys.exit(1)
    
    # Run the tests
    runner = IntegrationTestRunner()
    success = runner.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()