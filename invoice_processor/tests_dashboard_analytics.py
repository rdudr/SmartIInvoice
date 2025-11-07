"""
Unit tests for Dashboard Analytics Service

Tests data aggregation methods, date range filtering, sorting, and limiting
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from invoice_processor.models import Invoice, LineItem, InvoiceHealthScore
from invoice_processor.services.dashboard_analytics_service import DashboardAnalyticsService


class DashboardAnalyticsServiceTest(TestCase):
    """Test suite for DashboardAnalyticsService"""
    
    def setUp(self):
        """Set up test data"""
        self.service = DashboardAnalyticsService()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test invoices with different dates and health scores
        self.invoices = []
        
        # Create invoices for the last 7 days
        for i in range(7):
            date = timezone.now() - timedelta(days=i)
            
            # Create 2 invoices per day - one healthy, one at-risk
            healthy_invoice = Invoice.objects.create(
                invoice_id=f'INV-HEALTHY-{i}',
                invoice_date=date.date(),
                vendor_name=f'Vendor {i}',
                vendor_gstin=f'29ABCDE{i:04d}FGH',
                billed_company_gstin='29XYZAB1234C1Z5',
                grand_total=Decimal('10000.00') + Decimal(i * 1000),
                uploaded_by=self.user,
                uploaded_at=date
            )
            
            InvoiceHealthScore.objects.create(
                invoice=healthy_invoice,
                overall_score=Decimal('8.5'),
                status='HEALTHY',
                data_completeness_score=Decimal('90.00'),
                verification_score=Decimal('95.00'),
                compliance_score=Decimal('85.00'),
                fraud_detection_score=Decimal('90.00'),
                ai_confidence_score_component=Decimal('88.00')
            )
            
            at_risk_invoice = Invoice.objects.create(
                invoice_id=f'INV-RISK-{i}',
                invoice_date=date.date(),
                vendor_name=f'Risky Vendor {i}',
                vendor_gstin=f'29ZYXWV{i:04d}UTS',
                billed_company_gstin='29XYZAB1234C1Z5',
                grand_total=Decimal('5000.00') + Decimal(i * 500),
                uploaded_by=self.user,
                uploaded_at=date
            )
            
            InvoiceHealthScore.objects.create(
                invoice=at_risk_invoice,
                overall_score=Decimal('3.5'),
                status='AT_RISK',
                data_completeness_score=Decimal('60.00'),
                verification_score=Decimal('40.00'),
                compliance_score=Decimal('50.00'),
                fraud_detection_score=Decimal('30.00'),
                ai_confidence_score_component=Decimal('45.00')
            )
            
            self.invoices.extend([healthy_invoice, at_risk_invoice])
        
        # Create line items with different HSN codes
        hsn_codes = ['8517', '8471', '9403', '8528', '8443']
        for i, invoice in enumerate(self.invoices[:5]):
            LineItem.objects.create(
                invoice=invoice,
                description=f'Product {i}',
                normalized_key=f'product_{i}',
                hsn_sac_code=hsn_codes[i % len(hsn_codes)],
                quantity=Decimal('10.00'),
                unit_price=Decimal('1000.00'),
                billed_gst_rate=Decimal('18.00'),
                line_total=Decimal('11800.00')
            )
    
    def test_get_invoice_per_day_data_default_days(self):
        """Test invoice per day data with default 5 days"""
        result = self.service.get_invoice_per_day_data(self.user, days=5)
        
        # Verify structure
        self.assertIn('dates', result)
        self.assertIn('genuine_counts', result)
        self.assertIn('at_risk_counts', result)
        self.assertIn('total_days', result)
        
        # Verify data length
        self.assertEqual(len(result['dates']), 5)
        self.assertEqual(len(result['genuine_counts']), 5)
        self.assertEqual(len(result['at_risk_counts']), 5)
        self.assertEqual(result['total_days'], 5)
        
        # Verify we have data (we created 7 days of invoices, so 5 days should have some)
        # Each day in our test data has 1 healthy and 1 at-risk invoice
        total_genuine = sum(result['genuine_counts'])
        total_at_risk = sum(result['at_risk_counts'])
        # We should have at least some invoices in the 5-day window
        self.assertGreater(total_genuine, 0)
        self.assertGreater(total_at_risk, 0)
    
    def test_get_invoice_per_day_data_custom_days(self):
        """Test invoice per day data with custom day range"""
        result = self.service.get_invoice_per_day_data(self.user, days=7)
        
        # Verify data length matches requested days
        self.assertEqual(len(result['dates']), 7)
        self.assertEqual(len(result['genuine_counts']), 7)
        self.assertEqual(len(result['at_risk_counts']), 7)
        self.assertEqual(result['total_days'], 7)
    
    def test_get_invoice_per_day_data_clamping(self):
        """Test that days parameter is clamped between 5 and 14"""
        # Test below minimum
        result = self.service.get_invoice_per_day_data(self.user, days=3)
        self.assertEqual(result['total_days'], 5)
        
        # Test above maximum
        result = self.service.get_invoice_per_day_data(self.user, days=20)
        self.assertEqual(result['total_days'], 14)
    
    def test_get_invoice_per_day_data_date_format(self):
        """Test that dates are formatted correctly"""
        result = self.service.get_invoice_per_day_data(self.user, days=5)
        
        # Check date format (e.g., "07 Nov")
        for date_str in result['dates']:
            self.assertRegex(date_str, r'\d{2} \w{3}')
    
    def test_get_money_flow_by_hsn_default_limit(self):
        """Test money flow by HSN with default limit"""
        result = self.service.get_money_flow_by_hsn(self.user, limit=5)
        
        # Verify result is a list
        self.assertIsInstance(result, list)
        
        # Verify we have results (up to 5)
        self.assertLessEqual(len(result), 5)
        
        # Verify structure of each item
        if len(result) > 0:
            item = result[0]
            self.assertIn('hsn_code', item)
            self.assertIn('amount', item)
            self.assertIn('percentage', item)
            self.assertIn('count', item)
    
    def test_get_money_flow_by_hsn_sorting(self):
        """Test that money flow results are sorted by amount descending"""
        result = self.service.get_money_flow_by_hsn(self.user, limit=5)
        
        if len(result) > 1:
            # Verify descending order
            for i in range(len(result) - 1):
                self.assertGreaterEqual(result[i]['amount'], result[i + 1]['amount'])
    
    def test_get_money_flow_by_hsn_percentage_calculation(self):
        """Test that percentages sum to approximately 100%"""
        result = self.service.get_money_flow_by_hsn(self.user, limit=5)
        
        if len(result) > 0:
            total_percentage = sum(item['percentage'] for item in result)
            # Allow for rounding differences
            self.assertAlmostEqual(total_percentage, 100.0, delta=1.0)
    
    def test_get_money_flow_by_hsn_limit(self):
        """Test that limit parameter is respected"""
        result = self.service.get_money_flow_by_hsn(self.user, limit=3)
        self.assertLessEqual(len(result), 3)
    
    def test_get_company_leaderboard_default_limit(self):
        """Test company leaderboard with default limit"""
        result = self.service.get_company_leaderboard(self.user, limit=5)
        
        # Verify result is a list
        self.assertIsInstance(result, list)
        
        # Verify we have results (up to 5)
        self.assertLessEqual(len(result), 5)
        
        # Verify structure of each item
        if len(result) > 0:
            vendor = result[0]
            self.assertIn('vendor_name', vendor)
            self.assertIn('vendor_gstin', vendor)
            self.assertIn('total_amount', vendor)
            self.assertIn('invoice_count', vendor)
    
    def test_get_company_leaderboard_sorting(self):
        """Test that leaderboard is sorted by total amount descending"""
        result = self.service.get_company_leaderboard(self.user, limit=5)
        
        if len(result) > 1:
            # Verify descending order by total_amount
            for i in range(len(result) - 1):
                self.assertGreaterEqual(result[i]['total_amount'], result[i + 1]['total_amount'])
    
    def test_get_company_leaderboard_aggregation(self):
        """Test that vendor data is properly aggregated"""
        # Create multiple invoices for the same vendor
        vendor_gstin = '29TESTVENDOR123'
        for i in range(3):
            Invoice.objects.create(
                invoice_id=f'INV-SAME-VENDOR-{i}',
                invoice_date=timezone.now().date(),
                vendor_name='Same Vendor',
                vendor_gstin=vendor_gstin,
                billed_company_gstin='29XYZAB1234C1Z5',
                grand_total=Decimal('1000.00'),
                uploaded_by=self.user
            )
        
        result = self.service.get_company_leaderboard(self.user, limit=20)
        
        # Find the aggregated vendor
        same_vendor = next((v for v in result if v['vendor_gstin'] == vendor_gstin), None)
        self.assertIsNotNone(same_vendor)
        self.assertEqual(same_vendor['invoice_count'], 3)
        self.assertEqual(same_vendor['total_amount'], 3000.00)
    
    def test_get_company_leaderboard_limit(self):
        """Test that limit parameter is respected"""
        result = self.service.get_company_leaderboard(self.user, limit=3)
        self.assertLessEqual(len(result), 3)
    
    def test_get_red_flag_list_default_limit(self):
        """Test red flag list with default limit"""
        result = self.service.get_red_flag_list(self.user, limit=5)
        
        # Verify result is a list
        self.assertIsInstance(result, list)
        
        # Verify we have results (up to 5)
        self.assertLessEqual(len(result), 5)
        
        # Verify structure of each item
        if len(result) > 0:
            invoice = result[0]
            self.assertIn('invoice_id', invoice)
            self.assertIn('invoice_number', invoice)
            self.assertIn('vendor_name', invoice)
            self.assertIn('date', invoice)
            self.assertIn('health_score', invoice)
            self.assertIn('health_status', invoice)
            self.assertIn('grand_total', invoice)
    
    def test_get_red_flag_list_sorting(self):
        """Test that red flag list is sorted by health score ascending"""
        result = self.service.get_red_flag_list(self.user, limit=5)
        
        if len(result) > 1:
            # Verify ascending order (lowest scores first)
            for i in range(len(result) - 1):
                self.assertLessEqual(result[i]['health_score'], result[i + 1]['health_score'])
    
    def test_get_red_flag_list_only_includes_scored_invoices(self):
        """Test that only invoices with health scores are included"""
        # Create invoice without health score
        Invoice.objects.create(
            invoice_id='INV-NO-SCORE',
            invoice_date=timezone.now().date(),
            vendor_name='No Score Vendor',
            vendor_gstin='29NOSCORE1234FG',
            billed_company_gstin='29XYZAB1234C1Z5',
            grand_total=Decimal('5000.00'),
            uploaded_by=self.user
        )
        
        result = self.service.get_red_flag_list(self.user, limit=20)
        
        # Verify all results have health scores
        for invoice in result:
            self.assertIsNotNone(invoice['health_score'])
    
    def test_get_red_flag_list_limit(self):
        """Test that limit parameter is respected"""
        result = self.service.get_red_flag_list(self.user, limit=3)
        self.assertLessEqual(len(result), 3)
    
    def test_get_red_flag_list_date_format(self):
        """Test that dates are formatted correctly"""
        result = self.service.get_red_flag_list(self.user, limit=5)
        
        if len(result) > 0:
            # Check date format (MM/DD/YYYY)
            date_str = result[0]['date']
            self.assertRegex(date_str, r'\d{2}/\d{2}/\d{4}')
    
    def test_empty_data_handling(self):
        """Test that methods handle empty data gracefully"""
        # Create a new user with no invoices
        empty_user = User.objects.create_user(
            username='emptyuser',
            email='empty@example.com',
            password='testpass123'
        )
        
        # Test all methods return empty/default results
        invoice_per_day = self.service.get_invoice_per_day_data(empty_user, days=5)
        self.assertEqual(len(invoice_per_day['dates']), 5)
        self.assertEqual(sum(invoice_per_day['genuine_counts']), 0)
        self.assertEqual(sum(invoice_per_day['at_risk_counts']), 0)
        
        money_flow = self.service.get_money_flow_by_hsn(empty_user, limit=5)
        self.assertEqual(len(money_flow), 0)
        
        leaderboard = self.service.get_company_leaderboard(empty_user, limit=5)
        self.assertEqual(len(leaderboard), 0)
        
        red_flags = self.service.get_red_flag_list(empty_user, limit=5)
        self.assertEqual(len(red_flags), 0)