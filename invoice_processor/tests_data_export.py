"""
Unit tests for Data Export Service

Tests CSV generation, field formatting, and filename generation.
Requirements: 11.1, 11.2, 11.3
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from decimal import Decimal
from datetime import date, datetime
from invoice_processor.models import Invoice, GSTCacheEntry, UserProfile
from invoice_processor.services.data_export_service import DataExportService
import csv
from io import StringIO


class DataExportServiceTests(TestCase):
    """Test cases for Data Export Service"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        # Create user profile
        self.profile = UserProfile.objects.create(
            user=self.user,
            phone_number='1234567890',
            company_name='Test Company',
            enable_sound_effects=True,
            enable_animations=False,
            enable_notifications=True
        )
        
        # Create test invoices
        self.invoice1 = Invoice.objects.create(
            invoice_id='INV-001',
            invoice_date=date(2024, 1, 15),
            vendor_name='Vendor A',
            vendor_gstin='29ABCDE1234F1Z5',
            billed_company_gstin='27XYZAB5678G1H9',
            grand_total=Decimal('10000.50'),
            status='CLEARED',
            gst_verification_status='VERIFIED',
            uploaded_by=self.user,
            extraction_method='AI',
            ai_confidence_score=Decimal('95.50')
        )
        
        self.invoice2 = Invoice.objects.create(
            invoice_id='INV-002',
            invoice_date=date(2024, 1, 20),
            vendor_name='Vendor B',
            vendor_gstin='29FGHIJ9876K1L2',
            billed_company_gstin='27XYZAB5678G1H9',
            grand_total=Decimal('25000.00'),
            status='HAS_ANOMALIES',
            gst_verification_status='PENDING',
            uploaded_by=self.user,
            extraction_method='MANUAL',
            ai_confidence_score=None
        )
        
        # Create GST cache entries
        self.gst_entry1 = GSTCacheEntry.objects.create(
            gstin='29ABCDE1234F1Z5',
            legal_name='ABC Company Private Limited',
            trade_name='ABC Corp',
            status='Active',
            registration_date=date(2020, 5, 10),
            business_constitution='Private Limited Company',
            principal_address='123 Main St, City, State - 560001',
            einvoice_status='Yes',
            verification_count=5
        )
        
        self.gst_entry2 = GSTCacheEntry.objects.create(
            gstin='29FGHIJ9876K1L2',
            legal_name='XYZ Enterprises',
            trade_name='',
            status='Inactive',
            registration_date=date(2019, 3, 15),
            business_constitution='Proprietorship',
            principal_address='456 Second St, Town, State - 560002',
            einvoice_status='No',
            verification_count=2
        )
        
        self.service = DataExportService()
    
    def test_export_invoices_to_csv_generates_valid_csv(self):
        """Test that invoice export generates valid CSV with correct headers"""
        queryset = Invoice.objects.filter(uploaded_by=self.user)
        response = self.service.export_invoices_to_csv(queryset)
        
        # Check response type and headers
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('invoices_export_', response['Content-Disposition'])
        self.assertIn('.csv', response['Content-Disposition'])
        
        # Parse CSV content
        content = response.content.decode('utf-8')
        csv_reader = csv.reader(StringIO(content))
        rows = list(csv_reader)
        
        # Check header row
        self.assertEqual(len(rows), 3)  # Header + 2 invoices
        header = rows[0]
        self.assertIn('Invoice Id', header)
        self.assertIn('Vendor Name', header)
        self.assertIn('Grand Total', header)
        self.assertIn('Status', header)
    
    def test_export_invoices_formats_fields_correctly(self):
        """Test that invoice fields are formatted correctly in CSV"""
        queryset = Invoice.objects.filter(uploaded_by=self.user)
        response = self.service.export_invoices_to_csv(queryset)
        
        content = response.content.decode('utf-8')
        csv_reader = csv.reader(StringIO(content))
        rows = list(csv_reader)
        
        # Check first invoice data
        invoice1_row = rows[1]
        self.assertIn('INV-001', invoice1_row)
        self.assertIn('Vendor A', invoice1_row)
        self.assertIn('10000.50', invoice1_row)
        self.assertIn('Cleared', invoice1_row)
        self.assertIn('Verified', invoice1_row)
        self.assertIn('95.50', invoice1_row)
        
        # Check second invoice data
        invoice2_row = rows[2]
        self.assertIn('INV-002', invoice2_row)
        self.assertIn('Vendor B', invoice2_row)
        self.assertIn('25000.00', invoice2_row)
        self.assertIn('Has Anomalies', invoice2_row)
        self.assertIn('Pending', invoice2_row)
    
    def test_export_invoices_handles_empty_queryset(self):
        """Test that export handles empty queryset gracefully"""
        queryset = Invoice.objects.none()
        response = self.service.export_invoices_to_csv(queryset)
        
        content = response.content.decode('utf-8')
        csv_reader = csv.reader(StringIO(content))
        rows = list(csv_reader)
        
        # Should only have header row
        self.assertEqual(len(rows), 1)
    
    def test_export_gst_cache_to_csv_generates_valid_csv(self):
        """Test that GST cache export generates valid CSV"""
        response = self.service.export_gst_cache_to_csv()
        
        # Check response type and headers
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('gst_cache_export_', response['Content-Disposition'])
        self.assertIn('.csv', response['Content-Disposition'])
        
        # Parse CSV content
        content = response.content.decode('utf-8')
        csv_reader = csv.reader(StringIO(content))
        rows = list(csv_reader)
        
        # Check header row
        self.assertEqual(len(rows), 3)  # Header + 2 entries
        header = rows[0]
        self.assertIn('GSTIN', header)
        self.assertIn('Legal Name', header)
        self.assertIn('Status', header)
        self.assertIn('Business Constitution', header)
    
    def test_export_gst_cache_formats_fields_correctly(self):
        """Test that GST cache fields are formatted correctly"""
        response = self.service.export_gst_cache_to_csv()
        
        content = response.content.decode('utf-8')
        csv_reader = csv.reader(StringIO(content))
        rows = list(csv_reader)
        
        # Check first entry
        entry1_row = rows[1]
        self.assertIn('29ABCDE1234F1Z5', entry1_row)
        self.assertIn('ABC Company Private Limited', entry1_row)
        self.assertIn('ABC Corp', entry1_row)
        self.assertIn('Active', entry1_row)
        self.assertIn('Private Limited Company', entry1_row)
        
        # Check second entry
        entry2_row = rows[2]
        self.assertIn('29FGHIJ9876K1L2', entry2_row)
        self.assertIn('XYZ Enterprises', entry2_row)
        self.assertIn('Inactive', entry2_row)
        self.assertIn('Proprietorship', entry2_row)
    
    def test_export_user_data_generates_comprehensive_csv(self):
        """Test that user data export includes all sections"""
        response = self.service.export_user_data(self.user)
        
        # Check response type and headers
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('my_data_export_', response['Content-Disposition'])
        self.assertIn('.csv', response['Content-Disposition'])
        
        # Parse CSV content
        content = response.content.decode('utf-8')
        
        # Check for section headers
        self.assertIn('=== USER PROFILE ===', content)
        self.assertIn('=== INVOICES ===', content)
        self.assertIn('=== SUMMARY STATISTICS ===', content)
        
        # Check for user data
        self.assertIn('testuser', content)
        self.assertIn('test@example.com', content)
        self.assertIn('Test Company', content)
        
        # Check for invoice data
        self.assertIn('INV-001', content)
        self.assertIn('INV-002', content)
    
    def test_export_user_data_includes_preferences(self):
        """Test that user data export includes preference settings"""
        response = self.service.export_user_data(self.user)
        content = response.content.decode('utf-8')
        
        # Check preferences are included
        self.assertIn('Sound Effects Enabled', content)
        self.assertIn('Animations Enabled', content)
        self.assertIn('Notifications Enabled', content)
    
    def test_filename_generation_includes_timestamp(self):
        """Test that generated filenames include timestamps"""
        queryset = Invoice.objects.filter(uploaded_by=self.user)
        response = self.service.export_invoices_to_csv(queryset)
        
        filename = response['Content-Disposition']
        
        # Check filename format
        self.assertIn('invoices_export_', filename)
        self.assertIn('.csv', filename)
        
        # Extract timestamp part (format: YYYYMMDD_HHMMSS)
        # Should be between 'invoices_export_' and '.csv'
        self.assertRegex(filename, r'invoices_export_\d{8}_\d{6}\.csv')


class DataExportViewTests(TestCase):
    """Test cases for data export views"""
    
    def setUp(self):
        """Set up test data and client"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test invoice
        self.invoice = Invoice.objects.create(
            invoice_id='INV-001',
            invoice_date=date(2024, 1, 15),
            vendor_name='Test Vendor',
            vendor_gstin='29ABCDE1234F1Z5',
            billed_company_gstin='27XYZAB5678G1H9',
            grand_total=Decimal('10000.00'),
            status='CLEARED',
            gst_verification_status='VERIFIED',
            uploaded_by=self.user
        )
    
    def test_export_invoices_requires_authentication(self):
        """Test that export invoices endpoint requires login"""
        response = self.client.get(reverse('export_invoices'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_export_invoices_returns_csv(self):
        """Test that export invoices returns CSV file"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('export_invoices'))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
    
    def test_export_invoices_respects_filters(self):
        """Test that export respects filter parameters"""
        self.client.login(username='testuser', password='testpass123')
        
        # Export with status filter
        response = self.client.get(reverse('export_invoices') + '?status=verified')
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        self.assertIn('INV-001', content)
    
    def test_export_gst_cache_requires_authentication(self):
        """Test that export GST cache endpoint requires login"""
        response = self.client.get(reverse('export_gst_cache'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_export_gst_cache_returns_csv(self):
        """Test that export GST cache returns CSV file"""
        # Create GST cache entry
        GSTCacheEntry.objects.create(
            gstin='29ABCDE1234F1Z5',
            legal_name='Test Company',
            status='Active',
            verification_count=1
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('export_gst_cache'))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
    
    def test_export_my_data_requires_authentication(self):
        """Test that export my data endpoint requires login"""
        response = self.client.get(reverse('export_my_data'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_export_my_data_returns_csv(self):
        """Test that export my data returns CSV file"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('export_my_data'))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        
        # Check content includes user data
        content = response.content.decode('utf-8')
        self.assertIn('testuser', content)
        self.assertIn('test@example.com', content)
