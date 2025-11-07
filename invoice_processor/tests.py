from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from PIL import Image
import json
import requests

from invoice_processor.services.gemini_service import GeminiService, extract_data_from_image
from invoice_processor.services.gst_client import GSTClient, get_captcha, verify_gstin, is_gst_service_available


class GeminiServiceTests(TestCase):
    """Test cases for Gemini API integration service"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_api_key = "test_api_key_12345"
    
    @patch('invoice_processor.services.gemini_service.config')
    def test_gemini_service_initialization_success(self, mock_config):
        """Test successful initialization of GeminiService"""
        mock_config.return_value = self.mock_api_key
        
        # Test with key manager disabled for backward compatibility
        service = GeminiService(use_key_manager=False)
        
        self.assertEqual(service.api_key, self.mock_api_key)
        self.assertEqual(service.max_retries, 1)
        self.assertEqual(service.timeout_seconds, 30)
        self.assertFalse(service.use_key_manager)
    
    @patch('invoice_processor.services.gemini_service.config')
    def test_gemini_service_initialization_no_api_key(self, mock_config):
        """Test GeminiService initialization fails without API key"""
        mock_config.return_value = None
        
        with self.assertRaises(ValueError) as context:
            GeminiService(use_key_manager=False)
        
        self.assertIn("GEMINI_API_KEY environment variable is required", str(context.exception))
    
    def test_clean_string_methods(self):
        """Test data cleaning methods"""
        service = GeminiService.__new__(GeminiService)  # Create instance without __init__
        
        # Test _clean_string
        self.assertEqual(service._clean_string("  test  "), "test")
        self.assertIsNone(service._clean_string(""))
        self.assertIsNone(service._clean_string(None))
        self.assertEqual(service._clean_string(123), "123")
        
        # Test _clean_decimal
        self.assertEqual(service._clean_decimal("123.45"), 123.45)
        self.assertEqual(service._clean_decimal("1,234.56"), 1234.56)
        self.assertEqual(service._clean_decimal(100), 100.0)
        self.assertIsNone(service._clean_decimal("invalid"))
        self.assertIsNone(service._clean_decimal(None))
        
        # Test _clean_gstin
        self.assertEqual(service._clean_gstin("27AAPFU0939F1ZV"), "27AAPFU0939F1ZV")
        self.assertEqual(service._clean_gstin("27aapfu0939f1zv"), "27AAPFU0939F1ZV")
        self.assertIsNone(service._clean_gstin("invalid_gstin"))
        self.assertIsNone(service._clean_gstin(None))
        
        # Test _clean_date
        self.assertEqual(service._clean_date("2023-12-01"), "2023-12-01")
        self.assertIsNone(service._clean_date("invalid_date"))
        self.assertIsNone(service._clean_date(None))
    
    def test_extract_data_from_image_invalid_file(self):
        """Test extract_data_from_image with invalid file"""
        # Create a mock file that will cause an error
        mock_file = Mock()
        mock_file.seek.side_effect = Exception("File error")
        
        result = extract_data_from_image(mock_file)
        
        self.assertFalse(result.get('is_invoice'))
        self.assertIn('error', result)


from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date

from invoice_processor.models import Invoice, LineItem, ComplianceFlag
from invoice_processor.services.analysis_engine import (
    normalize_product_key, check_duplicates, check_arithmetics, 
    check_hsn_rates, check_price_outliers, run_all_checks
)


class ModelValidationTests(TestCase):
    """Test cases for model validations and relationships"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_invoice_model_creation(self):
        """Test Invoice model creation with valid data"""
        invoice = Invoice.objects.create(
            invoice_id='TEST-001',
            invoice_date=date(2023, 12, 1),
            vendor_name='Test Vendor Ltd',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1180.00'),
            uploaded_by=self.user,
            file_path='test/invoice.pdf'
        )
        
        self.assertEqual(invoice.invoice_id, 'TEST-001')
        self.assertEqual(invoice.vendor_name, 'Test Vendor Ltd')
        self.assertEqual(invoice.status, 'PENDING_ANALYSIS')  # Default status
        self.assertEqual(invoice.gst_verification_status, 'PENDING')  # Default status
        self.assertEqual(str(invoice), 'Invoice TEST-001 - Test Vendor Ltd')
    
    def test_invoice_model_relationships(self):
        """Test Invoice model relationships with User"""
        invoice = Invoice.objects.create(
            invoice_id='TEST-002',
            invoice_date=date(2023, 12, 1),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1000.00'),
            uploaded_by=self.user,
            file_path='test/invoice2.pdf'
        )
        
        # Test foreign key relationship
        self.assertEqual(invoice.uploaded_by, self.user)
        self.assertIn(invoice, self.user.invoice_set.all())
    
    def test_invoice_status_choices(self):
        """Test Invoice status field choices"""
        invoice = Invoice.objects.create(
            invoice_id='TEST-003',
            invoice_date=date(2023, 12, 1),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1000.00'),
            uploaded_by=self.user,
            file_path='test/invoice3.pdf'
        )
        
        # Test valid status changes
        invoice.status = 'CLEARED'
        invoice.save()
        self.assertEqual(invoice.status, 'CLEARED')
        
        invoice.status = 'HAS_ANOMALIES'
        invoice.save()
        self.assertEqual(invoice.status, 'HAS_ANOMALIES')
        
        # Test GST verification status
        invoice.gst_verification_status = 'VERIFIED'
        invoice.save()
        self.assertEqual(invoice.gst_verification_status, 'VERIFIED')
    
    def test_line_item_model_creation(self):
        """Test LineItem model creation and relationships"""
        invoice = Invoice.objects.create(
            invoice_id='TEST-004',
            invoice_date=date(2023, 12, 1),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1180.00'),
            uploaded_by=self.user,
            file_path='test/invoice4.pdf'
        )
        
        line_item = LineItem.objects.create(
            invoice=invoice,
            description='Test Product A',
            normalized_key='test product',
            hsn_sac_code='1001',
            quantity=Decimal('10'),
            unit_price=Decimal('100.00'),
            billed_gst_rate=Decimal('18.00'),
            line_total=Decimal('1180.00')
        )
        
        self.assertEqual(line_item.invoice, invoice)
        self.assertEqual(line_item.description, 'Test Product A')
        self.assertEqual(line_item.normalized_key, 'test product')
        self.assertEqual(str(line_item), 'Test Product A - TEST-004')
        
        # Test relationship from invoice side
        self.assertIn(line_item, invoice.line_items.all())
        self.assertEqual(invoice.line_items.count(), 1)
    
    def test_compliance_flag_model_creation(self):
        """Test ComplianceFlag model creation and relationships"""
        invoice = Invoice.objects.create(
            invoice_id='TEST-005',
            invoice_date=date(2023, 12, 1),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1000.00'),
            uploaded_by=self.user,
            file_path='test/invoice5.pdf'
        )
        
        line_item = LineItem.objects.create(
            invoice=invoice,
            description='Test Product',
            normalized_key='test product',
            hsn_sac_code='1001',
            quantity=Decimal('5'),
            unit_price=Decimal('200.00'),
            billed_gst_rate=Decimal('18.00'),
            line_total=Decimal('1180.00')
        )
        
        # Test flag without line item reference
        flag1 = ComplianceFlag.objects.create(
            invoice=invoice,
            flag_type='DUPLICATE',
            severity='CRITICAL',
            description='Duplicate invoice detected'
        )
        
        # Test flag with line item reference
        flag2 = ComplianceFlag.objects.create(
            invoice=invoice,
            line_item=line_item,
            flag_type='PRICE_ANOMALY',
            severity='WARNING',
            description='Price anomaly detected for this item'
        )
        
        self.assertEqual(flag1.invoice, invoice)
        self.assertIsNone(flag1.line_item)
        self.assertEqual(flag1.flag_type, 'DUPLICATE')
        self.assertEqual(flag1.severity, 'CRITICAL')
        self.assertEqual(str(flag1), 'DUPLICATE - TEST-005')
        
        self.assertEqual(flag2.invoice, invoice)
        self.assertEqual(flag2.line_item, line_item)
        self.assertEqual(flag2.flag_type, 'PRICE_ANOMALY')
        self.assertEqual(flag2.severity, 'WARNING')
        
        # Test relationships
        self.assertEqual(invoice.compliance_flags.count(), 2)
        self.assertIn(flag1, invoice.compliance_flags.all())
        self.assertIn(flag2, invoice.compliance_flags.all())
    
    def test_compliance_flag_choices(self):
        """Test ComplianceFlag field choices"""
        invoice = Invoice.objects.create(
            invoice_id='TEST-006',
            invoice_date=date(2023, 12, 1),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1000.00'),
            uploaded_by=self.user,
            file_path='test/invoice6.pdf'
        )
        
        # Test all flag types
        flag_types = ['DUPLICATE', 'ARITHMETIC_ERROR', 'HSN_MISMATCH', 'UNKNOWN_HSN', 'PRICE_ANOMALY', 'SYSTEM_ERROR']
        severities = ['CRITICAL', 'WARNING', 'INFO']
        
        for flag_type in flag_types:
            for severity in severities:
                flag = ComplianceFlag.objects.create(
                    invoice=invoice,
                    flag_type=flag_type,
                    severity=severity,
                    description=f'Test {flag_type} with {severity} severity'
                )
                self.assertEqual(flag.flag_type, flag_type)
                self.assertEqual(flag.severity, severity)
    
    def test_model_cascade_deletion(self):
        """Test cascade deletion behavior"""
        invoice = Invoice.objects.create(
            invoice_id='TEST-007',
            invoice_date=date(2023, 12, 1),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1000.00'),
            uploaded_by=self.user,
            file_path='test/invoice7.pdf'
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
        
        # Verify objects exist
        self.assertTrue(Invoice.objects.filter(id=invoice.id).exists())
        self.assertTrue(LineItem.objects.filter(id=line_item.id).exists())
        self.assertTrue(ComplianceFlag.objects.filter(id=flag.id).exists())
        
        # Delete invoice - should cascade to line items and flags
        invoice.delete()
        
        # Verify cascade deletion
        self.assertFalse(Invoice.objects.filter(id=invoice.id).exists())
        self.assertFalse(LineItem.objects.filter(id=line_item.id).exists())
        self.assertFalse(ComplianceFlag.objects.filter(id=flag.id).exists())
    
    def test_model_indexes(self):
        """Test that model indexes are properly configured"""
        # This test verifies that the models can be created and queried efficiently
        # The actual index testing would require database introspection
        
        invoice = Invoice.objects.create(
            invoice_id='TEST-008',
            invoice_date=date(2023, 12, 1),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1000.00'),
            uploaded_by=self.user,
            file_path='test/invoice8.pdf'
        )
        
        # Test queries that should use indexes
        # These should execute efficiently due to db_index=True fields
        result1 = Invoice.objects.filter(vendor_gstin='27AAPFU0939F1ZV')
        result2 = Invoice.objects.filter(status='PENDING_ANALYSIS')
        result3 = Invoice.objects.filter(gst_verification_status='PENDING')
        
        self.assertIn(invoice, result1)
        self.assertIn(invoice, result2)
        self.assertIn(invoice, result3)


class AnalysisEngineTests(TestCase):
    """Test cases for Analysis Engine compliance checks"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Sample invoice data for testing
        self.sample_invoice_data = {
            'invoice_id': 'INV-001',
            'invoice_date': '2023-12-01',
            'vendor_name': 'Test Vendor',
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
        
        # Create test invoice
        self.test_invoice = Invoice.objects.create(
            invoice_id='INV-001',
            invoice_date=date(2023, 12, 1),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1180.00'),
            uploaded_by=self.user,
            file_path='test/path.pdf'
        )
    
    def test_normalize_product_key(self):
        """Test product key normalization function"""
        # Test basic normalization
        self.assertEqual(normalize_product_key("Test Product A"), "test product")
        
        # Test removal of common words
        self.assertEqual(normalize_product_key("The Best Product for Testing"), "best product testing")
        
        # Test special character removal
        self.assertEqual(normalize_product_key("Product-A (Special) & More!"), "product special more")
        
        # Test empty/None input
        self.assertEqual(normalize_product_key(""), "")
        self.assertEqual(normalize_product_key(None), "")
        
        # Test quantity words removal
        self.assertEqual(normalize_product_key("10 pieces of Product A"), "10 product")
    
    def test_check_duplicates_no_duplicate(self):
        """Test duplicate check when no duplicate exists"""
        result = check_duplicates(self.sample_invoice_data)
        self.assertIsNone(result)
    
    def test_check_duplicates_found(self):
        """Test duplicate check when duplicate exists"""
        # Create existing invoice with same ID and vendor
        Invoice.objects.create(
            invoice_id='INV-001',
            invoice_date=date(2023, 11, 1),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1000.00'),
            status='CLEARED',
            uploaded_by=self.user,
            file_path='test/existing.pdf'
        )
        
        result = check_duplicates(self.sample_invoice_data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.flag_type, 'DUPLICATE')
        self.assertEqual(result.severity, 'CRITICAL')
        self.assertIn('INV-001', result.description)
    
    def test_check_arithmetics_correct(self):
        """Test arithmetic check with correct calculations"""
        result = check_arithmetics(self.sample_invoice_data)
        self.assertEqual(len(result), 0)  # No flags should be generated
    
    def test_check_arithmetics_line_error(self):
        """Test arithmetic check with line item calculation error"""
        incorrect_data = self.sample_invoice_data.copy()
        incorrect_data['line_items'][0]['line_total'] = 1000.00  # Should be 1180.00
        
        result = check_arithmetics(incorrect_data)
        
        self.assertEqual(len(result), 2)  # Line error + grand total error
        self.assertTrue(any(flag.flag_type == 'ARITHMETIC_ERROR' for flag in result))
        self.assertTrue(any('Line item 1 calculation error' in flag.description for flag in result))
    
    def test_check_arithmetics_grand_total_error(self):
        """Test arithmetic check with grand total error"""
        incorrect_data = self.sample_invoice_data.copy()
        incorrect_data['grand_total'] = 1000.00  # Should be 1180.00
        
        result = check_arithmetics(incorrect_data)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].flag_type, 'ARITHMETIC_ERROR')
        self.assertIn('Grand total mismatch', result[0].description)
    
    @patch('invoice_processor.services.analysis_engine.load_hsn_master_data')
    def test_check_hsn_rates_unknown_code(self, mock_load_data):
        """Test HSN rate check with unknown HSN code"""
        mock_load_data.return_value = {"goods": {}, "services": {}}
        
        result = check_hsn_rates(self.sample_invoice_data)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].flag_type, 'UNKNOWN_HSN')
        self.assertIn('1001', result[0].description)
    
    @patch('invoice_processor.services.analysis_engine.load_hsn_master_data')
    def test_check_hsn_rates_mismatch(self, mock_load_data):
        """Test HSN rate check with rate mismatch"""
        mock_load_data.return_value = {
            "goods": {
                "1001": {"rate": 12.0, "description": "Test goods"}
            },
            "services": {}
        }
        
        result = check_hsn_rates(self.sample_invoice_data)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].flag_type, 'HSN_MISMATCH')
        self.assertIn('Billed 18.0%, Official rate 12.0%', result[0].description)
    
    def test_check_price_outliers_insufficient_data(self):
        """Test price outlier check with insufficient historical data"""
        result = check_price_outliers(self.sample_invoice_data, '27AAPFU0939F1ZV')
        
        # Should return empty list since no historical data exists
        self.assertEqual(len(result), 0)
    
    def test_check_price_outliers_with_anomaly(self):
        """Test price outlier check with price anomaly"""
        # Create historical line items for same product
        for i in range(5):
            historical_invoice = Invoice.objects.create(
                invoice_id=f'HIST-{i}',
                invoice_date=date(2023, 10, i+1),
                vendor_name='Test Vendor',
                vendor_gstin='27AAPFU0939F1ZV',
                billed_company_gstin='29AABCT1332L1ZZ',
                grand_total=Decimal('1000.00'),
                status='CLEARED',
                uploaded_by=self.user,
                file_path=f'test/hist{i}.pdf'
            )
            
            LineItem.objects.create(
                invoice=historical_invoice,
                description='Test Product A',
                normalized_key='test product',
                hsn_sac_code='1001',
                quantity=Decimal('10'),
                unit_price=Decimal('50.00'),  # Much lower than current 100.00
                billed_gst_rate=Decimal('18.00'),
                line_total=Decimal('590.00')
            )
        
        result = check_price_outliers(self.sample_invoice_data, '27AAPFU0939F1ZV')
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].flag_type, 'PRICE_ANOMALY')
        self.assertIn('price anomaly detected', result[0].description)
    
    @patch('invoice_processor.services.analysis_engine.load_hsn_master_data')
    def test_run_all_checks_integration(self, mock_load_data):
        """Test complete analysis engine workflow"""
        mock_load_data.return_value = {"goods": {}, "services": {}}
        
        result = run_all_checks(self.sample_invoice_data, self.test_invoice)
        
        # Should have at least one flag (unknown HSN)
        self.assertGreater(len(result), 0)
        
        # All flags should have invoice reference
        for flag in result:
            self.assertEqual(flag.invoice, self.test_invoice)
            self.assertIn(flag.flag_type, [choice[0] for choice in ComplianceFlag.FLAG_TYPE_CHOICES])
            self.assertIn(flag.severity, [choice[0] for choice in ComplianceFlag.SEVERITY_CHOICES])


class InvoiceUploadTests(TestCase):
    """Test cases for invoice upload functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.upload_url = reverse('upload_invoice')
        
        # Sample extracted data that Gemini would return
        self.sample_extracted_data = {
            'is_invoice': True,
            'invoice_id': 'TEST-001',
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
    
    def create_test_image_file(self):
        """Create a test image file for upload"""
        # Create a larger test image with proper PNG signature (at least 1KB)
        image = Image.new('RGB', (500, 500), color='white')
        image_io = BytesIO()
        image.save(image_io, format='PNG')
        
        # Ensure file is large enough by adding some content if needed
        current_size = image_io.tell()
        if current_size < 1024:  # Less than 1KB
            # Add some dummy data to make it larger
            padding = b'0' * (1024 - current_size)
            image_io.write(padding)
        
        image_io.seek(0)
        image_io.name = 'test_invoice.png'
        image_io.content_type = 'image/png'
        
        # Set size attribute for Django file validation
        image_io.size = len(image_io.getvalue())
        
        return image_io
    
    def create_test_pdf_file(self):
        """Create a test PDF file for upload"""
        # Create a minimal PDF file with proper PDF signature
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000074 00000 n \n0000000120 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n179\n%%EOF'
        pdf_io = BytesIO(pdf_content)
        pdf_io.name = 'test_invoice.pdf'
        pdf_io.content_type = 'application/pdf'
        return pdf_io
    
    def test_upload_requires_authentication(self):
        """Test that upload endpoint requires authentication"""
        test_file = self.create_test_image_file()
        
        response = self.client.post(self.upload_url, {
            'invoice_file': test_file
        })
        
        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    @patch('invoice_processor.views.extract_data_from_image')
    @patch('invoice_processor.views.run_all_checks')
    def test_successful_upload(self, mock_run_checks, mock_extract):
        """Test successful invoice upload and processing"""
        # Login user
        self.client.login(username='testuser', password='testpass123')
        
        # Mock Gemini extraction
        mock_extract.return_value = self.sample_extracted_data
        
        # Mock analysis engine (no flags)
        mock_run_checks.return_value = []
        
        # Create test file
        test_file = self.create_test_image_file()
        
        # Upload file
        response = self.client.post(self.upload_url, {
            'invoice_file': test_file
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Check response
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('invoice', response_data)
        
        # Check database
        self.assertEqual(Invoice.objects.count(), 1)
        invoice = Invoice.objects.first()
        self.assertEqual(invoice.invoice_id, 'TEST-001')
        self.assertEqual(invoice.vendor_name, 'Test Vendor Ltd')
        self.assertEqual(invoice.status, 'CLEARED')  # No flags = CLEARED
        
        # Check line items
        self.assertEqual(LineItem.objects.count(), 1)
        line_item = LineItem.objects.first()
        self.assertEqual(line_item.description, 'Test Product A')
        self.assertEqual(line_item.normalized_key, 'test product')
    
    @patch('invoice_processor.views.extract_data_from_image')
    def test_upload_invalid_file_type(self, mock_extract):
        """Test upload with invalid file type"""
        # Login user
        self.client.login(username='testuser', password='testpass123')
        
        # Create invalid file (text file)
        invalid_file = BytesIO(b'This is not an image')
        invalid_file.name = 'test.txt'
        invalid_file.content_type = 'text/plain'
        
        response = self.client.post(self.upload_url, {
            'invoice_file': invalid_file
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertEqual(response_data['error'], 'File validation failed')
    
    @patch('invoice_processor.views.extract_data_from_image')
    def test_upload_not_invoice(self, mock_extract):
        """Test upload when file is not recognized as invoice"""
        # Login user
        self.client.login(username='testuser', password='testpass123')
        
        # Mock Gemini to return not an invoice
        mock_extract.return_value = {'is_invoice': False, 'error': 'Not an invoice'}
        
        test_file = self.create_test_image_file()
        
        response = self.client.post(self.upload_url, {
            'invoice_file': test_file
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertEqual(response_data['error'], 'Not an invoice')
    
    @patch('invoice_processor.views.extract_data_from_image')
    @patch('invoice_processor.views.run_all_checks')
    def test_upload_with_compliance_flags(self, mock_run_checks, mock_extract):
        """Test upload that generates compliance flags"""
        # Login user
        self.client.login(username='testuser', password='testpass123')
        
        # Mock Gemini extraction
        mock_extract.return_value = self.sample_extracted_data
        
        # Mock analysis engine with critical flag
        mock_flag = ComplianceFlag(
            flag_type='DUPLICATE',
            severity='CRITICAL',
            description='Test duplicate flag'
        )
        mock_run_checks.return_value = [mock_flag]
        
        test_file = self.create_test_image_file()
        
        response = self.client.post(self.upload_url, {
            'invoice_file': test_file
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Check invoice status is HAS_ANOMALIES due to critical flag
        invoice = Invoice.objects.first()
        self.assertEqual(invoice.status, 'HAS_ANOMALIES')
        
        # Check response includes flag counts
        self.assertEqual(response_data['invoice']['compliance_flags_count'], 1)
        self.assertEqual(response_data['invoice']['critical_flags_count'], 1)


class GSTClientTests(TestCase):
    """Test cases for GST Client microservice communication"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_service_url = "http://127.0.0.1:5001"
        self.sample_captcha_response = {
            "sessionId": "test-session-123",
            "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        }
        self.sample_verification_response = {
            "gstin": "27AAPFU0939F1ZV",
            "lgnm": "Test Company Ltd",
            "stj": "Active",
            "dty": "Regular"
        }
    
    @patch('invoice_processor.services.gst_client.config')
    def test_gst_client_initialization_default_url(self, mock_config):
        """Test GST client initialization with default URL"""
        mock_config.return_value = None  # No URL configured
        
        client = GSTClient()
        
        self.assertEqual(client.service_url, "http://127.0.0.1:5001")
        self.assertEqual(client.timeout_seconds, 30)
        self.assertEqual(client.max_retries, 1)
    
    @patch('invoice_processor.services.gst_client.config')
    def test_gst_client_initialization_custom_url(self, mock_config):
        """Test GST client initialization with custom URL"""
        mock_config.return_value = "http://custom-gst-service:8080/"
        
        client = GSTClient()
        
        # Should strip trailing slash
        self.assertEqual(client.service_url, "http://custom-gst-service:8080")
    
    @patch('invoice_processor.services.gst_client.requests.get')
    @patch('invoice_processor.services.gst_client.config')
    def test_get_captcha_success(self, mock_config, mock_get):
        """Test successful CAPTCHA request"""
        mock_config.return_value = self.mock_service_url
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_captcha_response
        mock_get.return_value = mock_response
        
        client = GSTClient()
        result = client.get_captcha()
        
        # Verify request was made correctly
        mock_get.assert_called_once_with(
            f"{self.mock_service_url}/api/v1/getCaptcha",
            timeout=30
        )
        
        # Verify response
        self.assertEqual(result, self.sample_captcha_response)
        self.assertIn('sessionId', result)
        self.assertIn('image', result)
    
    @patch('invoice_processor.services.gst_client.requests.get')
    @patch('invoice_processor.services.gst_client.config')
    def test_get_captcha_connection_error(self, mock_config, mock_get):
        """Test CAPTCHA request with connection error"""
        mock_config.return_value = self.mock_service_url
        
        # Mock connection error
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        client = GSTClient()
        result = client.get_captcha()
        
        # Should return error response
        self.assertIn('error', result)
        self.assertIn('temporarily unavailable', result['error'])
    
    @patch('invoice_processor.services.gst_client.requests.get')
    @patch('invoice_processor.services.gst_client.config')
    def test_get_captcha_timeout(self, mock_config, mock_get):
        """Test CAPTCHA request with timeout"""
        mock_config.return_value = self.mock_service_url
        
        # Mock timeout error
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        
        client = GSTClient()
        result = client.get_captcha()
        
        # Should return error response
        self.assertIn('error', result)
        self.assertIn('taking too long', result['error'])
    
    @patch('invoice_processor.services.gst_client.requests.get')
    @patch('invoice_processor.services.gst_client.config')
    def test_get_captcha_invalid_response(self, mock_config, mock_get):
        """Test CAPTCHA request with invalid response structure"""
        mock_config.return_value = self.mock_service_url
        
        # Mock response with missing fields
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid": "response"}
        mock_get.return_value = mock_response
        
        client = GSTClient()
        result = client.get_captcha()
        
        # Should return error response
        self.assertIn('error', result)
        self.assertIn('Invalid response', result['error'])
    
    @patch('invoice_processor.services.gst_client.requests.post')
    @patch('invoice_processor.services.gst_client.config')
    def test_verify_gstin_success(self, mock_config, mock_post):
        """Test successful GST verification"""
        mock_config.return_value = self.mock_service_url
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_verification_response
        mock_post.return_value = mock_response
        
        client = GSTClient()
        result = client.verify_gstin("test-session-123", "27AAPFU0939F1ZV", "ABC123")
        
        # Verify request was made correctly
        expected_payload = {
            "sessionId": "test-session-123",
            "GSTIN": "27AAPFU0939F1ZV",
            "captcha": "ABC123"
        }
        mock_post.assert_called_once_with(
            f"{self.mock_service_url}/api/v1/getGSTDetails",
            json=expected_payload,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        
        # Verify response
        self.assertEqual(result, self.sample_verification_response)
    
    @patch('invoice_processor.services.gst_client.requests.post')
    @patch('invoice_processor.services.gst_client.config')
    def test_verify_gstin_missing_parameters(self, mock_config, mock_post):
        """Test GST verification with missing parameters"""
        mock_config.return_value = self.mock_service_url
        
        client = GSTClient()
        
        # Test missing session_id
        result = client.verify_gstin("", "27AAPFU0939F1ZV", "ABC123")
        self.assertIn('error', result)
        self.assertIn('Missing required parameters', result['error'])
        
        # Test missing gstin
        result = client.verify_gstin("test-session", "", "ABC123")
        self.assertIn('error', result)
        self.assertIn('Missing required parameters', result['error'])
        
        # Test missing captcha
        result = client.verify_gstin("test-session", "27AAPFU0939F1ZV", "")
        self.assertIn('error', result)
        self.assertIn('Missing required parameters', result['error'])
        
        # Verify no API calls were made
        mock_post.assert_not_called()
    
    @patch('invoice_processor.services.gst_client.requests.post')
    @patch('invoice_processor.services.gst_client.config')
    def test_verify_gstin_invalid_format(self, mock_config, mock_post):
        """Test GST verification with invalid GSTIN format"""
        mock_config.return_value = self.mock_service_url
        
        client = GSTClient()
        result = client.verify_gstin("test-session", "INVALID", "ABC123")
        
        # Should return error for invalid format
        self.assertIn('error', result)
        self.assertIn('Invalid GSTIN format', result['error'])
        
        # Verify no API call was made
        mock_post.assert_not_called()
    
    @patch('invoice_processor.services.gst_client.requests.post')
    @patch('invoice_processor.services.gst_client.config')
    def test_verify_gstin_connection_error(self, mock_config, mock_post):
        """Test GST verification with connection error"""
        mock_config.return_value = self.mock_service_url
        
        # Mock connection error
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        client = GSTClient()
        result = client.verify_gstin("test-session-123", "27AAPFU0939F1ZV", "ABC123")
        
        # Should return error response
        self.assertIn('error', result)
        self.assertIn('temporarily unavailable', result['error'])
    
    @patch('invoice_processor.services.gst_client.requests.get')
    @patch('invoice_processor.services.gst_client.config')
    def test_is_service_available_true(self, mock_config, mock_get):
        """Test service availability check when service is available"""
        mock_config.return_value = self.mock_service_url
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        client = GSTClient()
        result = client.is_service_available()
        
        self.assertTrue(result)
        mock_get.assert_called_once_with(
            f"{self.mock_service_url}/api/v1/getCaptcha",
            timeout=5
        )
    
    @patch('invoice_processor.services.gst_client.requests.get')
    @patch('invoice_processor.services.gst_client.config')
    def test_is_service_available_false(self, mock_config, mock_get):
        """Test service availability check when service is unavailable"""
        mock_config.return_value = self.mock_service_url
        
        # Mock connection error
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        client = GSTClient()
        result = client.is_service_available()
        
        self.assertFalse(result)
    
    @patch('invoice_processor.services.gst_client.gst_client')
    def test_convenience_functions(self, mock_client):
        """Test convenience functions delegate to client instance"""
        # Mock client methods
        mock_client.get_captcha.return_value = self.sample_captcha_response
        mock_client.verify_gstin.return_value = self.sample_verification_response
        mock_client.is_service_available.return_value = True
        
        # Test get_captcha convenience function
        result = get_captcha()
        self.assertEqual(result, self.sample_captcha_response)
        mock_client.get_captcha.assert_called_once()
        
        # Test verify_gstin convenience function
        result = verify_gstin("session", "gstin", "captcha")
        self.assertEqual(result, self.sample_verification_response)
        mock_client.verify_gstin.assert_called_once_with("session", "gstin", "captcha")
        
        # Test is_gst_service_available convenience function
        result = is_gst_service_available()
        self.assertTrue(result)
        mock_client.is_service_available.assert_called_once()



class InvoiceHealthScoreEngineTests(TestCase):
    """Test cases for Invoice Health Score Engine"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a base invoice for testing
        self.invoice = Invoice.objects.create(
            invoice_id='TEST-001',
            invoice_date=date(2023, 12, 1),
            vendor_name='Test Vendor Ltd',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1180.00'),
            uploaded_by=self.user,
            file_path='test/invoice.pdf',
            gst_verification_status='VERIFIED',
            ai_confidence_score=Decimal('85.00')
        )
        
        # Add line items
        LineItem.objects.create(
            invoice=self.invoice,
            description='Test Product A',
            normalized_key='test product',
            hsn_sac_code='1001',
            quantity=Decimal('10'),
            unit_price=Decimal('100.00'),
            billed_gst_rate=Decimal('18.00'),
            line_total=Decimal('1180.00')
        )
    
    def test_score_data_completeness_perfect(self):
        """Test data completeness scoring with all fields present"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_data_completeness(self.invoice)
        
        self.assertEqual(score, 100.0)
    
    def test_score_data_completeness_missing_fields(self):
        """Test data completeness scoring with missing fields"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        # Create invoice with missing fields
        incomplete_invoice = Invoice.objects.create(
            invoice_id='',  # Missing
            invoice_date=date(2023, 12, 1),
            vendor_name='',  # Missing
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='',  # Missing
            grand_total=Decimal('1000.00'),
            uploaded_by=self.user,
            file_path='test/incomplete.pdf'
        )
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_data_completeness(incomplete_invoice)
        
        # Should lose points for missing fields
        self.assertLess(score, 100.0)
        self.assertGreaterEqual(score, 0.0)
    
    def test_score_data_completeness_no_line_items(self):
        """Test data completeness scoring with no line items"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        # Create invoice without line items
        no_items_invoice = Invoice.objects.create(
            invoice_id='TEST-002',
            invoice_date=date(2023, 12, 1),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1000.00'),
            uploaded_by=self.user,
            file_path='test/no_items.pdf'
        )
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_data_completeness(no_items_invoice)
        
        # Should lose 20 points for no line items
        self.assertLess(score, 100.0)
    
    def test_score_verification_verified(self):
        """Test verification scoring with verified GST"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_verification(self.invoice)
        
        self.assertEqual(score, 100.0)
    
    def test_score_verification_pending(self):
        """Test verification scoring with pending GST verification"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        self.invoice.gst_verification_status = 'PENDING'
        self.invoice.save()
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_verification(self.invoice)
        
        self.assertEqual(score, 50.0)
    
    def test_score_verification_failed(self):
        """Test verification scoring with failed GST verification"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        self.invoice.gst_verification_status = 'FAILED'
        self.invoice.save()
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_verification(self.invoice)
        
        self.assertEqual(score, 0.0)
    
    def test_score_compliance_no_flags(self):
        """Test compliance scoring with no flags"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_compliance(self.invoice)
        
        self.assertEqual(score, 100.0)
    
    def test_score_compliance_with_critical_flags(self):
        """Test compliance scoring with critical flags"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        # Add critical arithmetic error
        ComplianceFlag.objects.create(
            invoice=self.invoice,
            flag_type='ARITHMETIC_ERROR',
            severity='CRITICAL',
            description='Arithmetic error detected'
        )
        
        # Add critical HSN mismatch
        ComplianceFlag.objects.create(
            invoice=self.invoice,
            flag_type='HSN_MISMATCH',
            severity='CRITICAL',
            description='HSN rate mismatch'
        )
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_compliance(self.invoice)
        
        # Should lose 30 points per critical flag
        self.assertEqual(score, 40.0)
    
    def test_score_compliance_with_warning_flags(self):
        """Test compliance scoring with warning flags"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        # Add warning flag
        ComplianceFlag.objects.create(
            invoice=self.invoice,
            flag_type='ARITHMETIC_ERROR',
            severity='WARNING',
            description='Minor arithmetic issue'
        )
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_compliance(self.invoice)
        
        # Should lose 15 points for warning
        self.assertEqual(score, 85.0)
    
    def test_score_fraud_detection_no_issues(self):
        """Test fraud detection scoring with no issues"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_fraud_detection(self.invoice)
        
        self.assertEqual(score, 100.0)
    
    def test_score_fraud_detection_duplicate_flag(self):
        """Test fraud detection scoring with duplicate flag"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        # Add duplicate flag
        ComplianceFlag.objects.create(
            invoice=self.invoice,
            flag_type='DUPLICATE',
            severity='CRITICAL',
            description='Duplicate invoice detected'
        )
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_fraud_detection(self.invoice)
        
        # Should lose 50 points for duplicate
        self.assertEqual(score, 50.0)
    
    def test_score_fraud_detection_price_anomalies(self):
        """Test fraud detection scoring with price anomalies"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        # Add multiple price anomaly flags
        for i in range(3):
            ComplianceFlag.objects.create(
                invoice=self.invoice,
                flag_type='PRICE_ANOMALY',
                severity='WARNING',
                description=f'Price anomaly {i+1}'
            )
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_fraud_detection(self.invoice)
        
        # Should lose 10 points per anomaly (3 * 10 = 30)
        self.assertEqual(score, 70.0)
    
    def test_score_ai_confidence_with_score(self):
        """Test AI confidence scoring with confidence score"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_ai_confidence(self.invoice)
        
        # Should return the AI confidence score
        self.assertEqual(score, 85.0)
    
    def test_score_ai_confidence_manual_entry(self):
        """Test AI confidence scoring for manual entry"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        self.invoice.extraction_method = 'MANUAL'
        self.invoice.ai_confidence_score = None
        self.invoice.save()
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_ai_confidence(self.invoice)
        
        # Should return neutral score for manual entry
        self.assertEqual(score, 75.0)
    
    def test_score_ai_confidence_no_score(self):
        """Test AI confidence scoring with no score available"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        self.invoice.ai_confidence_score = None
        self.invoice.save()
        
        engine = InvoiceHealthScoreEngine()
        score = engine._score_ai_confidence(self.invoice)
        
        # Should return default moderate score
        self.assertEqual(score, 70.0)
    
    def test_calculate_health_score_healthy(self):
        """Test overall health score calculation for healthy invoice"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        engine = InvoiceHealthScoreEngine()
        result = engine.calculate_health_score(self.invoice)
        
        self.assertIn('score', result)
        self.assertIn('status', result)
        self.assertIn('breakdown', result)
        self.assertIn('key_flags', result)
        
        # Perfect invoice should have high score
        self.assertGreaterEqual(result['score'], 8.0)
        self.assertEqual(result['status'], 'HEALTHY')
        self.assertEqual(len(result['key_flags']), 0)
    
    def test_calculate_health_score_review(self):
        """Test overall health score calculation for review status"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        # Add some issues to bring score to review range
        self.invoice.gst_verification_status = 'PENDING'
        self.invoice.ai_confidence_score = Decimal('60.00')
        self.invoice.save()
        
        ComplianceFlag.objects.create(
            invoice=self.invoice,
            flag_type='ARITHMETIC_ERROR',
            severity='WARNING',
            description='Minor arithmetic issue'
        )
        
        ComplianceFlag.objects.create(
            invoice=self.invoice,
            flag_type='PRICE_ANOMALY',
            severity='WARNING',
            description='Price anomaly detected'
        )
        
        engine = InvoiceHealthScoreEngine()
        result = engine.calculate_health_score(self.invoice)
        
        # Should be in review range (5.0-7.9)
        self.assertGreaterEqual(result['score'], 5.0)
        self.assertLess(result['score'], 8.0)
        self.assertEqual(result['status'], 'REVIEW')
        self.assertGreater(len(result['key_flags']), 0)
    
    def test_calculate_health_score_at_risk(self):
        """Test overall health score calculation for at-risk status"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        # Add multiple critical issues
        self.invoice.gst_verification_status = 'FAILED'
        self.invoice.ai_confidence_score = Decimal('30.00')
        self.invoice.save()
        
        ComplianceFlag.objects.create(
            invoice=self.invoice,
            flag_type='DUPLICATE',
            severity='CRITICAL',
            description='Duplicate invoice'
        )
        
        ComplianceFlag.objects.create(
            invoice=self.invoice,
            flag_type='ARITHMETIC_ERROR',
            severity='CRITICAL',
            description='Arithmetic error'
        )
        
        ComplianceFlag.objects.create(
            invoice=self.invoice,
            flag_type='HSN_MISMATCH',
            severity='CRITICAL',
            description='HSN rate mismatch'
        )
        
        engine = InvoiceHealthScoreEngine()
        result = engine.calculate_health_score(self.invoice)
        
        # Should be at risk (< 5.0)
        self.assertLess(result['score'], 5.0)
        self.assertEqual(result['status'], 'AT_RISK')
        self.assertGreater(len(result['key_flags']), 0)
    
    def test_generate_key_flags_comprehensive(self):
        """Test key flags generation with various issues"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        # Add various issues
        self.invoice.gst_verification_status = 'FAILED'
        self.invoice.ai_confidence_score = Decimal('45.00')
        self.invoice.save()
        
        ComplianceFlag.objects.create(
            invoice=self.invoice,
            flag_type='DUPLICATE',
            severity='CRITICAL',
            description='Duplicate invoice detected'
        )
        
        ComplianceFlag.objects.create(
            invoice=self.invoice,
            flag_type='ARITHMETIC_ERROR',
            severity='CRITICAL',
            description='Grand total mismatch'
        )
        
        ComplianceFlag.objects.create(
            invoice=self.invoice,
            flag_type='PRICE_ANOMALY',
            severity='WARNING',
            description='Price anomaly detected'
        )
        
        engine = InvoiceHealthScoreEngine()
        result = engine.calculate_health_score(self.invoice)
        
        key_flags = result['key_flags']
        
        # Should have multiple flags
        self.assertGreater(len(key_flags), 0)
        
        # Check for specific flag types
        flag_text = ' '.join(key_flags)
        self.assertIn('GST verification failed', flag_text)
        self.assertIn('Duplicate', flag_text)
        self.assertIn('Low AI confidence', flag_text)
    
    def test_calculate_health_score_breakdown(self):
        """Test that breakdown contains all category scores"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        engine = InvoiceHealthScoreEngine()
        result = engine.calculate_health_score(self.invoice)
        
        breakdown = result['breakdown']
        
        # Check all categories are present
        self.assertIn('data_completeness', breakdown)
        self.assertIn('verification', breakdown)
        self.assertIn('compliance', breakdown)
        self.assertIn('fraud_detection', breakdown)
        self.assertIn('ai_confidence', breakdown)
        
        # All scores should be 0-100
        for category, score in breakdown.items():
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 100.0)
    
    def test_calculate_health_score_weighted_correctly(self):
        """Test that overall score is weighted correctly"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        engine = InvoiceHealthScoreEngine()
        result = engine.calculate_health_score(self.invoice)
        
        # Manually calculate expected score
        breakdown = result['breakdown']
        expected_score = (
            (breakdown['data_completeness'] * 0.25) +
            (breakdown['verification'] * 0.30) +
            (breakdown['compliance'] * 0.25) +
            (breakdown['fraud_detection'] * 0.15) +
            (breakdown['ai_confidence'] * 0.05)
        ) / 10.0
        
        # Should match calculated score (within rounding)
        self.assertAlmostEqual(result['score'], expected_score, places=1)
    
    def test_calculate_health_score_status_thresholds(self):
        """Test status determination thresholds"""
        from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
        
        engine = InvoiceHealthScoreEngine()
        
        # Test HEALTHY threshold (>= 8.0)
        self.assertEqual(engine.THRESHOLD_HEALTHY, 8.0)
        
        # Test REVIEW threshold (>= 5.0)
        self.assertEqual(engine.THRESHOLD_REVIEW, 5.0)


# GST Cache Integration Tests

from invoice_processor.models import GSTCacheEntry
from invoice_processor.services.gst_cache_service import GSTCacheService, gst_cache_service
from datetime import datetime


class GSTCacheServiceTests(TestCase):
    """Test cases for GST Cache Service"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = GSTCacheService()
        self.test_gstin = '27AAPFU0939F1ZV'
        self.test_verification_data = {
            'lgnm': 'Test Company Private Limited',
            'tradeNam': 'Test Company',
            'sts': 'Active',
            'rgdt': '01/01/2020',
            'ctb': 'Private Limited Company',
            'pradr': {
                'adr': '123 Test Street, Test City, Test State - 123456'
            },
            'einvoiceStatus': 'Yes'
        }
    
    def tearDown(self):
        """Clean up test data"""
        GSTCacheEntry.objects.all().delete()
    
    def test_lookup_gstin_cache_miss(self):
        """Test cache lookup when GSTIN is not in cache"""
        result = self.service.lookup_gstin(self.test_gstin)
        self.assertIsNone(result)
    
    def test_lookup_gstin_cache_hit(self):
        """Test cache lookup when GSTIN exists in cache"""
        # Create cache entry
        cache_entry = GSTCacheEntry.objects.create(
            gstin=self.test_gstin,
            legal_name='Test Company Private Limited',
            trade_name='Test Company',
            status='Active',
            registration_date=datetime(2020, 1, 1).date(),
            business_constitution='Private Limited Company',
            principal_address='123 Test Street',
            einvoice_status='Yes',
            verification_count=1
        )
        
        # Lookup should return the entry
        result = self.service.lookup_gstin(self.test_gstin)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.gstin, self.test_gstin)
        self.assertEqual(result.legal_name, 'Test Company Private Limited')
        self.assertEqual(result.verification_count, 2)  # Should increment
    
    def test_lookup_gstin_invalid_format(self):
        """Test cache lookup with invalid GSTIN format"""
        result = self.service.lookup_gstin('INVALID')
        self.assertIsNone(result)
        
        result = self.service.lookup_gstin('')
        self.assertIsNone(result)
        
        result = self.service.lookup_gstin(None)
        self.assertIsNone(result)
    
    def test_lookup_gstin_case_insensitive(self):
        """Test cache lookup is case-insensitive"""
        # Create cache entry with uppercase
        GSTCacheEntry.objects.create(
            gstin=self.test_gstin.upper(),
            legal_name='Test Company',
            status='Active',
            verification_count=1
        )
        
        # Lookup with lowercase should work
        result = self.service.lookup_gstin(self.test_gstin.lower())
        self.assertIsNotNone(result)
        self.assertEqual(result.gstin, self.test_gstin.upper())
    
    def test_add_to_cache_success(self):
        """Test adding a new GSTIN to cache"""
        result = self.service.add_to_cache(self.test_gstin, self.test_verification_data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.gstin, self.test_gstin.upper())
        self.assertEqual(result.legal_name, 'Test Company Private Limited')
        self.assertEqual(result.trade_name, 'Test Company')
        self.assertEqual(result.status, 'Active')
        self.assertEqual(result.business_constitution, 'Private Limited Company')
        self.assertEqual(result.einvoice_status, 'Yes')
        self.assertEqual(result.verification_count, 1)
        
        # Verify it's in database
        self.assertTrue(GSTCacheEntry.objects.filter(gstin=self.test_gstin.upper()).exists())
    
    def test_add_to_cache_update_existing(self):
        """Test updating an existing cache entry"""
        # Create initial entry
        initial_entry = GSTCacheEntry.objects.create(
            gstin=self.test_gstin,
            legal_name='Old Company Name',
            status='Active',
            verification_count=5
        )
        
        # Update with new data
        result = self.service.add_to_cache(self.test_gstin, self.test_verification_data)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.gstin, self.test_gstin.upper())
        self.assertEqual(result.legal_name, 'Test Company Private Limited')  # Updated
        self.assertEqual(result.verification_count, 1)  # Reset to 1
        
        # Verify only one entry exists
        self.assertEqual(GSTCacheEntry.objects.filter(gstin=self.test_gstin.upper()).count(), 1)
    
    def test_add_to_cache_invalid_gstin(self):
        """Test adding invalid GSTIN to cache"""
        result = self.service.add_to_cache('INVALID', self.test_verification_data)
        self.assertIsNone(result)
        
        result = self.service.add_to_cache('', self.test_verification_data)
        self.assertIsNone(result)
        
        result = self.service.add_to_cache(None, self.test_verification_data)
        self.assertIsNone(result)
    
    def test_add_to_cache_invalid_data(self):
        """Test adding GSTIN with invalid verification data"""
        # Test with error in data
        result = self.service.add_to_cache(self.test_gstin, {'error': 'Verification failed'})
        self.assertIsNone(result)
        
        # Test with None data
        result = self.service.add_to_cache(self.test_gstin, None)
        self.assertIsNone(result)
    
    def test_add_to_cache_date_parsing(self):
        """Test date parsing in add_to_cache"""
        # Test with valid date
        result = self.service.add_to_cache(self.test_gstin, self.test_verification_data)
        self.assertIsNotNone(result)
        self.assertEqual(result.registration_date, datetime(2020, 1, 1).date())
        
        # Test with invalid date format
        invalid_data = self.test_verification_data.copy()
        invalid_data['rgdt'] = 'invalid-date'
        result = self.service.add_to_cache('29AABCT1332L1ZZ', invalid_data)
        self.assertIsNotNone(result)
        self.assertIsNone(result.registration_date)
    
    def test_add_to_cache_address_extraction(self):
        """Test address extraction from nested structure"""
        result = self.service.add_to_cache(self.test_gstin, self.test_verification_data)
        self.assertIsNotNone(result)
        self.assertEqual(result.principal_address, '123 Test Street, Test City, Test State - 123456')
        
        # Test with missing address
        data_no_address = self.test_verification_data.copy()
        data_no_address['pradr'] = {}
        result = self.service.add_to_cache('29AABCT1332L1ZZ', data_no_address)
        self.assertIsNotNone(result)
        self.assertEqual(result.principal_address, '')
    
    @patch('invoice_processor.services.gst_cache_service.verify_gstin')
    def test_refresh_cache_entry_success(self, mock_verify):
        """Test refreshing a cache entry with successful verification"""
        # Create existing cache entry
        GSTCacheEntry.objects.create(
            gstin=self.test_gstin,
            legal_name='Old Company Name',
            status='Active',
            verification_count=5
        )
        
        # Mock successful verification
        mock_verify.return_value = self.test_verification_data
        
        # Refresh entry
        result = self.service.refresh_cache_entry(self.test_gstin, 'test-session-id', 'ABC123')
        
        self.assertTrue(result['success'])
        self.assertIn('data', result)
        self.assertEqual(result['data']['gstin'], self.test_gstin.upper())
        self.assertEqual(result['data']['legal_name'], 'Test Company Private Limited')
        
        # Verify mock was called
        mock_verify.assert_called_once_with('test-session-id', self.test_gstin.upper(), 'ABC123')
        
        # Verify cache was updated
        updated_entry = GSTCacheEntry.objects.get(gstin=self.test_gstin.upper())
        self.assertEqual(updated_entry.legal_name, 'Test Company Private Limited')
    
    @patch('invoice_processor.services.gst_cache_service.verify_gstin')
    def test_refresh_cache_entry_verification_failed(self, mock_verify):
        """Test refreshing cache entry when verification fails"""
        # Mock failed verification
        mock_verify.return_value = {'error': 'CAPTCHA verification failed'}
        
        # Refresh entry
        result = self.service.refresh_cache_entry(self.test_gstin, 'test-session-id', 'ABC123')
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'CAPTCHA verification failed')
    
    def test_refresh_cache_entry_invalid_params(self):
        """Test refresh with invalid parameters"""
        # Invalid GSTIN
        result = self.service.refresh_cache_entry('INVALID', 'session-id', 'captcha')
        self.assertFalse(result['success'])
        self.assertIn('Invalid GSTIN', result['error'])
        
        # Missing session ID
        result = self.service.refresh_cache_entry(self.test_gstin, '', 'captcha')
        self.assertFalse(result['success'])
        self.assertIn('Session ID and CAPTCHA are required', result['error'])
        
        # Missing CAPTCHA
        result = self.service.refresh_cache_entry(self.test_gstin, 'session-id', '')
        self.assertFalse(result['success'])
        self.assertIn('Session ID and CAPTCHA are required', result['error'])
    
    def test_get_all_entries_no_filter(self):
        """Test getting all cache entries without filters"""
        # Create multiple entries
        GSTCacheEntry.objects.create(
            gstin='27AAPFU0939F1ZV',
            legal_name='Company A',
            status='Active',
            verification_count=1
        )
        GSTCacheEntry.objects.create(
            gstin='29AABCT1332L1ZZ',
            legal_name='Company B',
            status='Inactive',
            verification_count=2
        )
        
        result = self.service.get_all_entries()
        self.assertEqual(result.count(), 2)
    
    def test_get_all_entries_search_by_gstin(self):
        """Test searching cache entries by GSTIN"""
        GSTCacheEntry.objects.create(
            gstin='27AAPFU0939F1ZV',
            legal_name='Company A',
            status='Active',
            verification_count=1
        )
        GSTCacheEntry.objects.create(
            gstin='29AABCT1332L1ZZ',
            legal_name='Company B',
            status='Active',
            verification_count=1
        )
        
        result = self.service.get_all_entries(search_query='27AAPFU')
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().gstin, '27AAPFU0939F1ZV')
    
    def test_get_all_entries_search_by_name(self):
        """Test searching cache entries by legal name"""
        GSTCacheEntry.objects.create(
            gstin='27AAPFU0939F1ZV',
            legal_name='Test Company Private Limited',
            status='Active',
            verification_count=1
        )
        GSTCacheEntry.objects.create(
            gstin='29AABCT1332L1ZZ',
            legal_name='Another Company Ltd',
            status='Active',
            verification_count=1
        )
        
        result = self.service.get_all_entries(search_query='Test Company')
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().legal_name, 'Test Company Private Limited')
    
    def test_get_all_entries_search_by_trade_name(self):
        """Test searching cache entries by trade name"""
        GSTCacheEntry.objects.create(
            gstin='27AAPFU0939F1ZV',
            legal_name='Company A',
            trade_name='Brand X',
            status='Active',
            verification_count=1
        )
        GSTCacheEntry.objects.create(
            gstin='29AABCT1332L1ZZ',
            legal_name='Company B',
            trade_name='Brand Y',
            status='Active',
            verification_count=1
        )
        
        result = self.service.get_all_entries(search_query='Brand X')
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().trade_name, 'Brand X')
    
    def test_get_all_entries_filter_by_status(self):
        """Test filtering cache entries by status"""
        GSTCacheEntry.objects.create(
            gstin='27AAPFU0939F1ZV',
            legal_name='Company A',
            status='Active',
            verification_count=1
        )
        GSTCacheEntry.objects.create(
            gstin='29AABCT1332L1ZZ',
            legal_name='Company B',
            status='Inactive',
            verification_count=1
        )
        GSTCacheEntry.objects.create(
            gstin='24AABCT1332L1ZZ',
            legal_name='Company C',
            status='Active',
            verification_count=1
        )
        
        result = self.service.get_all_entries(status_filter='Active')
        self.assertEqual(result.count(), 2)
        
        result = self.service.get_all_entries(status_filter='Inactive')
        self.assertEqual(result.count(), 1)
    
    def test_get_all_entries_combined_filters(self):
        """Test combining search and status filters"""
        GSTCacheEntry.objects.create(
            gstin='27AAPFU0939F1ZV',
            legal_name='Test Company A',
            status='Active',
            verification_count=1
        )
        GSTCacheEntry.objects.create(
            gstin='29AABCT1332L1ZZ',
            legal_name='Test Company B',
            status='Inactive',
            verification_count=1
        )
        GSTCacheEntry.objects.create(
            gstin='24AABCT1332L1ZZ',
            legal_name='Other Company',
            status='Active',
            verification_count=1
        )
        
        result = self.service.get_all_entries(search_query='Test', status_filter='Active')
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().legal_name, 'Test Company A')
    
    def test_get_all_entries_ordering(self):
        """Test that entries are ordered by last_verified descending"""
        from django.utils import timezone
        from datetime import timedelta
        import time
        
        # Create entries with slight delays to ensure different timestamps
        entry1 = GSTCacheEntry.objects.create(
            gstin='27AAPFU0939F1ZV',
            legal_name='Company A',
            status='Active',
            verification_count=1
        )
        time.sleep(0.01)  # Small delay
        
        entry2 = GSTCacheEntry.objects.create(
            gstin='29AABCT1332L1ZZ',
            legal_name='Company B',
            status='Active',
            verification_count=1
        )
        time.sleep(0.01)  # Small delay
        
        entry3 = GSTCacheEntry.objects.create(
            gstin='24AABCT1332L1ZZ',
            legal_name='Company C',
            status='Active',
            verification_count=1
        )
        
        result = list(self.service.get_all_entries())
        
        # Should be ordered by most recent first (entry3, entry2, entry1)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].gstin, '24AABCT1332L1ZZ')  # Most recent
        self.assertEqual(result[1].gstin, '29AABCT1332L1ZZ')
        self.assertEqual(result[2].gstin, '27AAPFU0939F1ZV')  # Oldest


class GSTCacheViewTests(TestCase):
    """Test cases for GST Cache views and endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        from django.utils import timezone
        self.timezone = timezone
        
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.cache_url = reverse('gst_cache')
        self.check_cache_url = reverse('check_gst_cache')
        self.refresh_cache_url = reverse('refresh_gst_cache_entry')
    
    def tearDown(self):
        """Clean up test data"""
        GSTCacheEntry.objects.all().delete()
    
    def test_gst_cache_page_requires_authentication(self):
        """Test that GST cache page requires authentication"""
        response = self.client.get(self.cache_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_gst_cache_page_loads(self):
        """Test that GST cache page loads successfully"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(self.cache_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gst_cache.html')
    
    def test_gst_cache_page_displays_entries(self):
        """Test that cache entries are displayed on the page"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create cache entries
        GSTCacheEntry.objects.create(
            gstin='27AAPFU0939F1ZV',
            legal_name='Test Company A',
            status='Active',
            verification_count=5
        )
        GSTCacheEntry.objects.create(
            gstin='29AABCT1332L1ZZ',
            legal_name='Test Company B',
            status='Inactive',
            verification_count=3
        )
        
        response = self.client.get(self.cache_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 2)
        self.assertEqual(response.context['total_count'], 2)
    
    def test_gst_cache_page_search(self):
        """Test search functionality on cache page"""
        self.client.login(username='testuser', password='testpass123')
        
        GSTCacheEntry.objects.create(
            gstin='27AAPFU0939F1ZV',
            legal_name='Test Company A',
            status='Active',
            verification_count=1
        )
        GSTCacheEntry.objects.create(
            gstin='29AABCT1332L1ZZ',
            legal_name='Another Company',
            status='Active',
            verification_count=1
        )
        
        response = self.client.get(self.cache_url, {'search': 'Test Company'})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 1)
        self.assertEqual(response.context['page_obj'][0].legal_name, 'Test Company A')
    
    def test_gst_cache_page_status_filter(self):
        """Test status filtering on cache page"""
        self.client.login(username='testuser', password='testpass123')
        
        GSTCacheEntry.objects.create(
            gstin='27AAPFU0939F1ZV',
            legal_name='Company A',
            status='Active',
            verification_count=1
        )
        GSTCacheEntry.objects.create(
            gstin='29AABCT1332L1ZZ',
            legal_name='Company B',
            status='Inactive',
            verification_count=1
        )
        
        response = self.client.get(self.cache_url, {'status': 'Active'})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 1)
        self.assertEqual(response.context['page_obj'][0].status, 'Active')
    
    @patch('invoice_processor.views.gst_cache_service.lookup_gstin')
    def test_check_gst_cache_hit(self, mock_lookup):
        """Test check_gst_cache endpoint with cache hit"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create test invoice
        invoice = Invoice.objects.create(
            invoice_id='TEST-001',
            invoice_date=datetime(2023, 12, 1).date(),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1000.00'),
            uploaded_by=self.user,
            file_path='test/invoice.pdf'
        )
        
        # Mock cache hit
        mock_cache_entry = Mock()
        mock_cache_entry.legal_name = 'Test Company'
        mock_cache_entry.trade_name = 'Test Brand'
        mock_cache_entry.status = 'Active'
        mock_cache_entry.registration_date = datetime(2020, 1, 1).date()
        mock_cache_entry.business_constitution = 'Private Limited'
        mock_cache_entry.principal_address = '123 Test Street'
        mock_cache_entry.einvoice_status = 'Yes'
        mock_cache_entry.last_verified = self.timezone.now()
        mock_lookup.return_value = mock_cache_entry
        
        response = self.client.post(
            self.check_cache_url,
            json.dumps({'invoice_id': invoice.id}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertTrue(data['success'])
        self.assertTrue(data['cached'])
        self.assertEqual(data['new_status'], 'VERIFIED')
        self.assertIn('cache_data', data)
        
        # Verify invoice was updated
        invoice.refresh_from_db()
        self.assertEqual(invoice.gst_verification_status, 'VERIFIED')
    
    @patch('invoice_processor.views.gst_cache_service.lookup_gstin')
    def test_check_gst_cache_miss(self, mock_lookup):
        """Test check_gst_cache endpoint with cache miss"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create test invoice
        invoice = Invoice.objects.create(
            invoice_id='TEST-001',
            invoice_date=datetime(2023, 12, 1).date(),
            vendor_name='Test Vendor',
            vendor_gstin='27AAPFU0939F1ZV',
            billed_company_gstin='29AABCT1332L1ZZ',
            grand_total=Decimal('1000.00'),
            uploaded_by=self.user,
            file_path='test/invoice.pdf'
        )
        
        # Mock cache miss
        mock_lookup.return_value = None
        
        response = self.client.post(
            self.check_cache_url,
            json.dumps({'invoice_id': invoice.id}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertTrue(data['success'])
        self.assertFalse(data['cached'])
        self.assertIn('CAPTCHA verification required', data['message'])
    
    @patch('invoice_processor.views.gst_cache_service.refresh_cache_entry')
    def test_refresh_gst_cache_entry_success(self, mock_refresh):
        """Test refresh cache entry endpoint with success"""
        self.client.login(username='testuser', password='testpass123')
        
        # Mock successful refresh
        mock_refresh.return_value = {
            'success': True,
            'data': {
                'gstin': '27AAPFU0939F1ZV',
                'legal_name': 'Updated Company Name',
                'status': 'Active',
                'last_verified': self.timezone.now().isoformat()
            }
        }
        
        response = self.client.post(
            self.refresh_cache_url,
            json.dumps({
                'gstin': '27AAPFU0939F1ZV',
                'session_id': 'test-session-id',
                'captcha': 'ABC123'
            }),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertEqual(data['data']['legal_name'], 'Updated Company Name')
    
    @patch('invoice_processor.views.gst_cache_service.refresh_cache_entry')
    def test_refresh_gst_cache_entry_failure(self, mock_refresh):
        """Test refresh cache entry endpoint with failure"""
        self.client.login(username='testuser', password='testpass123')
        
        # Mock failed refresh
        mock_refresh.return_value = {
            'success': False,
            'error': 'CAPTCHA verification failed'
        }
        
        response = self.client.post(
            self.refresh_cache_url,
            json.dumps({
                'gstin': '27AAPFU0939F1ZV',
                'session_id': 'test-session-id',
                'captcha': 'WRONG'
            }),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        
        self.assertFalse(data['success'])
        self.assertIn('error', data)
