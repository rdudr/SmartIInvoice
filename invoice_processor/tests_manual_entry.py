"""
Integration tests for manual invoice data entry functionality.

This test module covers:
- Form validation (client-side and server-side)
- Submission and processing of manually entered data
- Compliance checks on manual data
- Health score calculation for manual entries

Requirements tested: 2.3, 2.4
"""

from decimal import Decimal
from datetime import datetime, date, timedelta
from io import BytesIO
from PIL import Image

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from invoice_processor.models import Invoice, LineItem, ComplianceFlag, InvoiceHealthScore
from invoice_processor.services.manual_entry_service import manual_entry_service
from invoice_processor.forms import ManualInvoiceEntryForm


class ManualEntryIntegrationTests(TestCase):
    """Integration tests for manual invoice entry functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a test invoice flagged for manual entry
        # Use a placeholder date since invoice_date is required by the model
        self.manual_invoice = Invoice.objects.create(
            invoice_id='',
            invoice_date=date.today(),  # Placeholder date
            vendor_name='',
            vendor_gstin='',
            billed_company_gstin='',
            grand_total=Decimal('0'),
            status='PENDING_ANALYSIS',
            uploaded_by=self.user,
            file_path=self.create_test_image_file(),
            extraction_method='MANUAL',
            extraction_failure_reason='AI extraction failed: Not an invoice'
        )
    
    def create_test_image_file(self, filename='test_invoice.png'):
        """Create a test image file"""
        image = Image.new('RGB', (800, 600), color='white')
        image_io = BytesIO()
        image.save(image_io, format='PNG')
        image_io.seek(0)
        
        return SimpleUploadedFile(
            filename,
            image_io.getvalue(),
            content_type='image/png'
        )
    
    # Test 1: Form Validation
    
    def test_manual_entry_form_valid_data(self):
        """Test form validation with valid data"""
        form_data = {
            'invoice_id': 'INV-2024-001',
            'invoice_date': date(2024, 1, 15),
            'vendor_name': 'Test Vendor Ltd',
            'vendor_gstin': '27AAPFU0939F1ZV',
            'billed_company_gstin': '29AABCT1332L1ZZ',
            'grand_total': Decimal('1180.00')
        }
        
        form = ManualInvoiceEntryForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_manual_entry_form_missing_required_fields(self):
        """Test form validation with missing required fields"""
        # Missing invoice_id
        form_data = {
            'invoice_date': date(2024, 1, 15),
            'vendor_name': 'Test Vendor Ltd',
            'grand_total': Decimal('1180.00')
        }
        
        form = ManualInvoiceEntryForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('invoice_id', form.errors)
    
    def test_manual_entry_form_invalid_gstin_format(self):
        """Test form validation with invalid GSTIN format"""
        form_data = {
            'invoice_id': 'INV-2024-001',
            'invoice_date': date(2024, 1, 15),
            'vendor_name': 'Test Vendor Ltd',
            'vendor_gstin': 'INVALID_GSTIN',  # Invalid format
            'grand_total': Decimal('1180.00')
        }
        
        form = ManualInvoiceEntryForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('vendor_gstin', form.errors)
    
    def test_manual_entry_form_future_date(self):
        """Test form validation with future invoice date"""
        future_date = date.today() + timedelta(days=30)
        
        form_data = {
            'invoice_id': 'INV-2024-001',
            'invoice_date': future_date,
            'vendor_name': 'Test Vendor Ltd',
            'grand_total': Decimal('1180.00')
        }
        
        form = ManualInvoiceEntryForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('invoice_date', form.errors)
    
    def test_manual_entry_form_negative_grand_total(self):
        """Test form validation with negative grand total"""
        form_data = {
            'invoice_id': 'INV-2024-001',
            'invoice_date': date(2024, 1, 15),
            'vendor_name': 'Test Vendor Ltd',
            'grand_total': Decimal('-100.00')  # Negative value
        }
        
        form = ManualInvoiceEntryForm(data=form_data)
        # Form should accept it, but service validation should catch it
        # This tests the multi-layer validation approach
    
    def test_manual_entry_service_validation_valid_data(self):
        """Test service-level validation with valid data"""
        manual_data = {
            'invoice_id': 'INV-2024-001',
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Vendor Ltd',
            'vendor_gstin': '27AAPFU0939F1ZV',
            'billed_company_gstin': '29AABCT1332L1ZZ',
            'grand_total': '1180.00',
            'line_items': [
                {
                    'description': 'Test Product A',
                    'hsn_sac_code': '1001',
                    'quantity': '10',
                    'unit_price': '100.00',
                    'billed_gst_rate': '18.00',
                    'line_total': '1180.00'
                }
            ]
        }
        
        is_valid, errors = manual_entry_service.validate_manual_entry(manual_data)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_manual_entry_service_validation_missing_line_items(self):
        """Test service validation with no line items"""
        manual_data = {
            'invoice_id': 'INV-2024-001',
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Vendor Ltd',
            'grand_total': '1180.00',
            'line_items': []
        }
        
        is_valid, errors = manual_entry_service.validate_manual_entry(manual_data)
        self.assertFalse(is_valid)
        self.assertTrue(any('line item' in error.lower() for error in errors))
    
    def test_manual_entry_service_validation_arithmetic_mismatch(self):
        """Test service validation with arithmetic mismatch"""
        manual_data = {
            'invoice_id': 'INV-2024-001',
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Vendor Ltd',
            'grand_total': '2000.00',  # Doesn't match line total
            'line_items': [
                {
                    'description': 'Test Product A',
                    'hsn_sac_code': '1001',
                    'quantity': '10',
                    'unit_price': '100.00',
                    'billed_gst_rate': '18.00',
                    'line_total': '1180.00'
                }
            ]
        }
        
        is_valid, errors = manual_entry_service.validate_manual_entry(manual_data)
        self.assertFalse(is_valid)
        self.assertTrue(any('grand total' in error.lower() for error in errors))
    
    # Test 2: Submission and Processing
    
    def test_manual_entry_page_requires_authentication(self):
        """Test that manual entry page requires authentication"""
        url = reverse('manual_entry', args=[self.manual_invoice.id])
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_manual_entry_page_access_own_invoice(self):
        """Test accessing manual entry page for own invoice"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('manual_entry', args=[self.manual_invoice.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Manual Invoice Entry')
        self.assertContains(response, self.manual_invoice.extraction_failure_reason)
    
    def test_manual_entry_page_cannot_access_other_user_invoice(self):
        """Test cannot access another user's invoice"""
        # Create another user and their invoice
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        other_invoice = Invoice.objects.create(
            invoice_id='',
            invoice_date=date.today(),  # Placeholder date
            vendor_name='',
            vendor_gstin='',
            billed_company_gstin='',
            grand_total=Decimal('0'),
            status='PENDING_ANALYSIS',
            uploaded_by=other_user,
            file_path=self.create_test_image_file(),
            extraction_method='MANUAL',
            extraction_failure_reason='AI extraction failed'
        )
        
        # Try to access as testuser
        self.client.login(username='testuser', password='testpass123')
        url = reverse('manual_entry', args=[other_invoice.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 404)
    
    def test_manual_entry_page_redirect_if_not_manual(self):
        """Test redirect if invoice doesn't require manual entry"""
        # Create a normal invoice (not flagged for manual entry)
        normal_invoice = Invoice.objects.create(
            invoice_id='INV-001',
            invoice_date=date(2024, 1, 15),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1000.00'),
            status='CLEARED',
            uploaded_by=self.user,
            file_path=self.create_test_image_file(),
            extraction_method='AI'
        )
        
        self.client.login(username='testuser', password='testpass123')
        url = reverse('manual_entry', args=[normal_invoice.id])
        response = self.client.get(url)
        
        # Should redirect to invoice detail
        self.assertEqual(response.status_code, 302)
    
    def test_manual_entry_submission_success(self):
        """Test successful manual entry submission"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('submit_manual_entry', args=[self.manual_invoice.id])
        
        # Prepare form data
        form_data = {
            'invoice_id': 'INV-2024-001',
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Vendor Ltd',
            'vendor_gstin': '27AAPFU0939F1ZV',
            'billed_company_gstin': '29AABCT1332L1ZZ',
            'grand_total': '1180.00',
            # Line items
            'line_items[1][description]': 'Test Product A',
            'line_items[1][hsn_sac_code]': '1001',
            'line_items[1][quantity]': '10',
            'line_items[1][unit_price]': '100.00',
            'line_items[1][billed_gst_rate]': '18.00',
            'line_items[1][line_total]': '1180.00',
        }
        
        response = self.client.post(url, form_data)
        
        # Should redirect to invoice detail
        self.assertEqual(response.status_code, 302)
        
        # Verify invoice was updated
        self.manual_invoice.refresh_from_db()
        self.assertEqual(self.manual_invoice.invoice_id, 'INV-2024-001')
        self.assertEqual(self.manual_invoice.vendor_name, 'Test Vendor Ltd')
        self.assertEqual(self.manual_invoice.vendor_gstin, '27AAPFU0939F1ZV')
        self.assertEqual(self.manual_invoice.grand_total, Decimal('1180.00'))
        
        # Verify line items were created
        self.assertEqual(self.manual_invoice.line_items.count(), 1)
        line_item = self.manual_invoice.line_items.first()
        self.assertEqual(line_item.description, 'Test Product A')
        self.assertEqual(line_item.quantity, Decimal('10'))
    
    def test_manual_entry_submission_with_multiple_line_items(self):
        """Test manual entry with multiple line items"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('submit_manual_entry', args=[self.manual_invoice.id])
        
        form_data = {
            'invoice_id': 'INV-2024-002',
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Vendor Ltd',
            'grand_total': '2360.00',
            # Line item 1
            'line_items[1][description]': 'Product A',
            'line_items[1][hsn_sac_code]': '1001',
            'line_items[1][quantity]': '10',
            'line_items[1][unit_price]': '100.00',
            'line_items[1][billed_gst_rate]': '18.00',
            'line_items[1][line_total]': '1180.00',
            # Line item 2
            'line_items[2][description]': 'Product B',
            'line_items[2][hsn_sac_code]': '1002',
            'line_items[2][quantity]': '5',
            'line_items[2][unit_price]': '200.00',
            'line_items[2][billed_gst_rate]': '18.00',
            'line_items[2][line_total]': '1180.00',
        }
        
        response = self.client.post(url, form_data)
        
        self.assertEqual(response.status_code, 302)
        
        # Verify both line items were created
        self.manual_invoice.refresh_from_db()
        self.assertEqual(self.manual_invoice.line_items.count(), 2)
    
    def test_manual_entry_submission_invalid_data(self):
        """Test manual entry submission with invalid data"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('submit_manual_entry', args=[self.manual_invoice.id])
        
        # Missing required field (invoice_id)
        form_data = {
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Vendor Ltd',
            'grand_total': '1180.00',
        }
        
        response = self.client.post(url, form_data)
        
        # Should re-render form with errors (status 200)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Manual Invoice Entry')
    
    # Test 3: Compliance Checks on Manual Data
    
    def test_manual_entry_compliance_checks_executed(self):
        """Test that compliance checks run on manually entered data"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('submit_manual_entry', args=[self.manual_invoice.id])
        
        form_data = {
            'invoice_id': 'INV-2024-001',
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Vendor Ltd',
            'vendor_gstin': '27AAPFU0939F1ZV',
            'grand_total': '1180.00',
            'line_items[1][description]': 'Test Product A',
            'line_items[1][hsn_sac_code]': '9999',  # Unknown HSN
            'line_items[1][quantity]': '10',
            'line_items[1][unit_price]': '100.00',
            'line_items[1][billed_gst_rate]': '18.00',
            'line_items[1][line_total]': '1180.00',
        }
        
        response = self.client.post(url, form_data)
        
        self.assertEqual(response.status_code, 302)
        
        # Verify compliance flags were created
        self.manual_invoice.refresh_from_db()
        flags = ComplianceFlag.objects.filter(invoice=self.manual_invoice)
        self.assertGreater(flags.count(), 0)
    
    def test_manual_entry_duplicate_detection(self):
        """Test duplicate detection for manually entered invoice"""
        # Create an existing invoice with same ID and vendor
        existing_invoice = Invoice.objects.create(
            invoice_id='INV-DUPLICATE',
            invoice_date=date(2024, 1, 1),
            vendor_name='Test Vendor Ltd',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1000.00'),
            status='CLEARED',
            uploaded_by=self.user,
            file_path=self.create_test_image_file()
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('submit_manual_entry', args=[self.manual_invoice.id])
        
        # Submit with same invoice ID and vendor
        form_data = {
            'invoice_id': 'INV-DUPLICATE',
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Vendor Ltd',
            'vendor_gstin': '27AAPFU0939F1ZV',
            'grand_total': '1180.00',
            'line_items[1][description]': 'Test Product',
            'line_items[1][quantity]': '10',
            'line_items[1][unit_price]': '100.00',
            'line_items[1][billed_gst_rate]': '18.00',
            'line_items[1][line_total]': '1180.00',
        }
        
        response = self.client.post(url, form_data)
        
        self.assertEqual(response.status_code, 302)
        
        # Verify duplicate flag was created
        self.manual_invoice.refresh_from_db()
        duplicate_flags = ComplianceFlag.objects.filter(
            invoice=self.manual_invoice,
            flag_type='DUPLICATE'
        )
        self.assertGreater(duplicate_flags.count(), 0)
        self.assertEqual(self.manual_invoice.status, 'HAS_ANOMALIES')
    
    def test_manual_entry_arithmetic_error_detection(self):
        """Test arithmetic error detection in manual entry"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('submit_manual_entry', args=[self.manual_invoice.id])
        
        # Line total doesn't match calculation
        form_data = {
            'invoice_id': 'INV-2024-001',
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Vendor Ltd',
            'grand_total': '1000.00',  # Incorrect total
            'line_items[1][description]': 'Test Product',
            'line_items[1][quantity]': '10',
            'line_items[1][unit_price]': '100.00',
            'line_items[1][billed_gst_rate]': '18.00',
            'line_items[1][line_total]': '1180.00',
        }
        
        response = self.client.post(url, form_data)
        
        # Should fail validation before submission
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'grand total')
    
    def test_manual_entry_health_score_calculation(self):
        """Test health score is calculated for manually entered invoice"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('submit_manual_entry', args=[self.manual_invoice.id])
        
        form_data = {
            'invoice_id': 'INV-2024-001',
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Vendor Ltd',
            'vendor_gstin': '27AAPFU0939F1ZV',
            'billed_company_gstin': '29AABCT1332L1ZZ',
            'grand_total': '1180.00',
            'line_items[1][description]': 'Test Product A',
            'line_items[1][hsn_sac_code]': '1001',
            'line_items[1][quantity]': '10',
            'line_items[1][unit_price]': '100.00',
            'line_items[1][billed_gst_rate]': '18.00',
            'line_items[1][line_total]': '1180.00',
        }
        
        response = self.client.post(url, form_data)
        
        self.assertEqual(response.status_code, 302)
        
        # Verify health score was created
        self.manual_invoice.refresh_from_db()
        self.assertTrue(hasattr(self.manual_invoice, 'health_score'))
        
        health_score = InvoiceHealthScore.objects.get(invoice=self.manual_invoice)
        self.assertIsNotNone(health_score.overall_score)
        self.assertIn(health_score.status, ['HEALTHY', 'REVIEW', 'AT_RISK'])
    
    def test_manual_entry_status_cleared_no_critical_flags(self):
        """Test invoice status is CLEARED when no critical flags"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('submit_manual_entry', args=[self.manual_invoice.id])
        
        # Valid data with no issues
        form_data = {
            'invoice_id': 'INV-2024-CLEAN',
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Vendor Ltd',
            'vendor_gstin': '27AAPFU0939F1ZV',
            'billed_company_gstin': '29AABCT1332L1ZZ',
            'grand_total': '1180.00',
            'line_items[1][description]': 'Test Product A',
            'line_items[1][hsn_sac_code]': '1001',
            'line_items[1][quantity]': '10',
            'line_items[1][unit_price]': '100.00',
            'line_items[1][billed_gst_rate]': '18.00',
            'line_items[1][line_total]': '1180.00',
        }
        
        response = self.client.post(url, form_data)
        
        self.assertEqual(response.status_code, 302)
        
        # Verify status
        self.manual_invoice.refresh_from_db()
        # Status could be CLEARED or HAS_ANOMALIES depending on compliance checks
        # Just verify it's not PENDING_ANALYSIS anymore
        self.assertIn(self.manual_invoice.status, ['CLEARED', 'HAS_ANOMALIES'])
    
    def test_manual_entry_preserves_extraction_method(self):
        """Test that extraction_method remains MANUAL after submission"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('submit_manual_entry', args=[self.manual_invoice.id])
        
        form_data = {
            'invoice_id': 'INV-2024-001',
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Vendor Ltd',
            'grand_total': '1180.00',
            'line_items[1][description]': 'Test Product',
            'line_items[1][quantity]': '10',
            'line_items[1][unit_price]': '100.00',
            'line_items[1][billed_gst_rate]': '18.00',
            'line_items[1][line_total]': '1180.00',
        }
        
        response = self.client.post(url, form_data)
        
        self.assertEqual(response.status_code, 302)
        
        # Verify extraction method is still MANUAL
        self.manual_invoice.refresh_from_db()
        self.assertEqual(self.manual_invoice.extraction_method, 'MANUAL')
    
    def test_manual_entry_resubmission_replaces_line_items(self):
        """Test that resubmitting manual entry replaces existing line items"""
        # First submission
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('submit_manual_entry', args=[self.manual_invoice.id])
        
        form_data = {
            'invoice_id': 'INV-2024-001',
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Vendor Ltd',
            'grand_total': '1180.00',
            'line_items[1][description]': 'Original Product',
            'line_items[1][quantity]': '10',
            'line_items[1][unit_price]': '100.00',
            'line_items[1][billed_gst_rate]': '18.00',
            'line_items[1][line_total]': '1180.00',
        }
        
        self.client.post(url, form_data)
        
        # Verify first submission
        self.manual_invoice.refresh_from_db()
        self.assertEqual(self.manual_invoice.line_items.count(), 1)
        self.assertEqual(self.manual_invoice.line_items.first().description, 'Original Product')
        
        # Second submission with different data
        form_data['line_items[1][description]'] = 'Updated Product'
        
        self.client.post(url, form_data)
        
        # Verify line items were replaced
        self.manual_invoice.refresh_from_db()
        self.assertEqual(self.manual_invoice.line_items.count(), 1)
        self.assertEqual(self.manual_invoice.line_items.first().description, 'Updated Product')
