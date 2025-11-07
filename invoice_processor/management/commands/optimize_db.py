"""
Management command to optimize database queries and verify indexes
"""
from django.core.management.base import BaseCommand
from django.db import connection
from invoice_processor.models import (
    Invoice, LineItem, ComplianceFlag, InvoiceBatch,
    InvoiceDuplicateLink, GSTCacheEntry, InvoiceHealthScore,
    UserProfile, APIKeyUsage, FeatureNotificationSignup
)


class Command(BaseCommand):
    help = 'Optimize database and verify indexes are in place'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting database optimization...'))
        
        # Check if indexes exist
        self.check_indexes()
        
        # Analyze tables for query optimization
        self.analyze_tables()
        
        # Show query statistics
        self.show_query_stats()
        
        self.stdout.write(self.style.SUCCESS('Database optimization complete!'))

    def check_indexes(self):
        """Check if all required indexes are in place"""
        self.stdout.write('\nChecking indexes...')
        
        with connection.cursor() as cursor:
            # Get all indexes
            cursor.execute("""
                SELECT 
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                ORDER BY tablename, indexname;
            """)
            
            indexes = cursor.fetchall()
            
            # Group by table
            table_indexes = {}
            for table, index_name, index_def in indexes:
                if table not in table_indexes:
                    table_indexes[table] = []
                table_indexes[table].append((index_name, index_def))
            
            # Display indexes
            for table, indexes in sorted(table_indexes.items()):
                if table.startswith('invoice_processor_'):
                    self.stdout.write(f'\n  {table}:')
                    for index_name, index_def in indexes:
                        self.stdout.write(f'    ✓ {index_name}')

    def analyze_tables(self):
        """Run ANALYZE on all tables to update statistics"""
        self.stdout.write('\nAnalyzing tables for query optimization...')
        
        tables = [
            'invoice_processor_invoice',
            'invoice_processor_lineitem',
            'invoice_processor_complianceflag',
            'invoice_processor_invoicebatch',
            'invoice_processor_invoiceduplicatelink',
            'invoice_processor_gstcacheentry',
            'invoice_processor_invoicehealthscore',
            'invoice_processor_userprofile',
            'invoice_processor_apikeyusage',
            'invoice_processor_featurenotificationsignup',
        ]
        
        with connection.cursor() as cursor:
            for table in tables:
                try:
                    cursor.execute(f'ANALYZE {table};')
                    self.stdout.write(f'  ✓ Analyzed {table}')
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠ Could not analyze {table}: {str(e)}')
                    )

    def show_query_stats(self):
        """Show query statistics"""
        self.stdout.write('\nQuery Statistics:')
        
        # Count records in each table
        models = [
            ('Invoices', Invoice),
            ('Line Items', LineItem),
            ('Compliance Flags', ComplianceFlag),
            ('Invoice Batches', InvoiceBatch),
            ('Duplicate Links', InvoiceDuplicateLink),
            ('GST Cache Entries', GSTCacheEntry),
            ('Health Scores', InvoiceHealthScore),
            ('User Profiles', UserProfile),
            ('API Key Usage', APIKeyUsage),
            ('Feature Signups', FeatureNotificationSignup),
        ]
        
        for name, model in models:
            count = model.objects.count()
            self.stdout.write(f'  {name}: {count:,}')
        
        # Show cache hit rate for GST cache
        total_invoices = Invoice.objects.count()
        cached_gst_count = GSTCacheEntry.objects.count()
        if total_invoices > 0:
            cache_coverage = (cached_gst_count / total_invoices) * 100
            self.stdout.write(f'\n  GST Cache Coverage: {cache_coverage:.1f}%')
