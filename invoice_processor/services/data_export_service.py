"""
Data Export Service

Provides functionality to export invoice and GST cache data to CSV format.
Requirements: 11.1, 11.2, 11.3
"""

import csv
import logging
from datetime import datetime
from django.http import HttpResponse
from io import StringIO

logger = logging.getLogger(__name__)


class DataExportService:
    """Service for exporting data to CSV format"""
    
    @staticmethod
    def export_invoices_to_csv(queryset, fields=None):
        """
        Export invoices to CSV format
        
        Args:
            queryset: Django queryset of Invoice objects
            fields: Optional list of field names to include. If None, exports all standard fields.
        
        Returns:
            HttpResponse with CSV content
        """
        # Default fields if none specified
        if fields is None:
            fields = [
                'id',
                'invoice_id',
                'invoice_date',
                'vendor_name',
                'vendor_gstin',
                'billed_company_gstin',
                'grand_total',
                'status',
                'gst_verification_status',
                'extraction_method',
                'ai_confidence_score',
                'uploaded_at'
            ]
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="invoices_export_{timestamp}.csv"'
        
        writer = csv.writer(response)
        
        # Write header row with formatted field names
        header = []
        for field in fields:
            # Convert field names to readable headers
            readable_name = field.replace('_', ' ').title()
            header.append(readable_name)
        writer.writerow(header)
        
        # Write data rows
        for invoice in queryset:
            row = []
            for field in fields:
                # Get field value with special handling for certain fields
                if field == 'invoice_date':
                    value = invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else ''
                elif field == 'uploaded_at':
                    value = invoice.uploaded_at.strftime('%Y-%m-%d %H:%M:%S') if invoice.uploaded_at else ''
                elif field == 'grand_total':
                    value = f"{invoice.grand_total:.2f}"
                elif field == 'ai_confidence_score':
                    value = f"{invoice.ai_confidence_score:.2f}" if invoice.ai_confidence_score else ''
                elif field == 'status':
                    value = invoice.get_status_display()
                elif field == 'gst_verification_status':
                    value = invoice.get_gst_verification_status_display()
                elif field == 'extraction_method':
                    value = invoice.get_extraction_method_display()
                else:
                    value = getattr(invoice, field, '')
                
                row.append(value)
            
            writer.writerow(row)
        
        logger.info(f"Exported {queryset.count()} invoices to CSV")
        return response
    
    @staticmethod
    def export_gst_cache_to_csv():
        """
        Export GST cache entries to CSV format
        
        Returns:
            HttpResponse with CSV content
        """
        from invoice_processor.models import GSTCacheEntry
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="gst_cache_export_{timestamp}.csv"'
        
        writer = csv.writer(response)
        
        # Write header row
        header = [
            'GSTIN',
            'Legal Name',
            'Trade Name',
            'Status',
            'Registration Date',
            'Business Constitution',
            'Principal Address',
            'E-Invoice Status',
            'Last Verified',
            'Verification Count'
        ]
        writer.writerow(header)
        
        # Get all GST cache entries
        cache_entries = GSTCacheEntry.objects.all().order_by('-last_verified')
        
        # Write data rows
        for entry in cache_entries:
            row = [
                entry.gstin,
                entry.legal_name,
                entry.trade_name or '',
                entry.status,
                entry.registration_date.strftime('%Y-%m-%d') if entry.registration_date else '',
                entry.business_constitution or '',
                entry.principal_address or '',
                entry.einvoice_status or '',
                entry.last_verified.strftime('%Y-%m-%d %H:%M:%S') if entry.last_verified else '',
                entry.verification_count
            ]
            writer.writerow(row)
        
        logger.info(f"Exported {cache_entries.count()} GST cache entries to CSV")
        return response
    
    @staticmethod
    def export_user_data(user):
        """
        Export all user data (invoices, profile, preferences) as CSV
        
        Args:
            user: Django User object
        
        Returns:
            HttpResponse with CSV content containing all user data
        """
        from invoice_processor.models import Invoice, UserProfile
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="my_data_export_{timestamp}.csv"'
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Section 1: User Profile Information
        writer.writerow(['=== USER PROFILE ==='])
        writer.writerow(['Field', 'Value'])
        writer.writerow(['Username', user.username])
        writer.writerow(['Email', user.email])
        writer.writerow(['First Name', user.first_name])
        writer.writerow(['Last Name', user.last_name])
        writer.writerow(['Date Joined', user.date_joined.strftime('%Y-%m-%d %H:%M:%S')])
        
        # Add profile data if exists
        try:
            profile = user.profile
            writer.writerow(['Phone Number', profile.phone_number or ''])
            writer.writerow(['Company Name', profile.company_name or ''])
            writer.writerow(['Facebook Connected', 'Yes' if profile.facebook_connected else 'No'])
            writer.writerow(['Google Connected', 'Yes' if profile.google_connected else 'No'])
            writer.writerow(['Sound Effects Enabled', 'Yes' if profile.enable_sound_effects else 'No'])
            writer.writerow(['Animations Enabled', 'Yes' if profile.enable_animations else 'No'])
            writer.writerow(['Notifications Enabled', 'Yes' if profile.enable_notifications else 'No'])
        except UserProfile.DoesNotExist:
            writer.writerow(['Profile', 'No profile data available'])
        
        writer.writerow([])  # Empty row for separation
        
        # Section 2: Invoice Data
        writer.writerow(['=== INVOICES ==='])
        invoices = Invoice.objects.filter(uploaded_by=user).order_by('-uploaded_at')
        
        if invoices.exists():
            # Invoice headers
            invoice_headers = [
                'Invoice ID',
                'Date',
                'Vendor Name',
                'Vendor GSTIN',
                'Billed Company GSTIN',
                'Grand Total',
                'Status',
                'GST Verification Status',
                'Extraction Method',
                'AI Confidence Score',
                'Uploaded At'
            ]
            writer.writerow(invoice_headers)
            
            # Invoice data
            for invoice in invoices:
                row = [
                    invoice.invoice_id,
                    invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '',
                    invoice.vendor_name,
                    invoice.vendor_gstin,
                    invoice.billed_company_gstin,
                    f"{invoice.grand_total:.2f}",
                    invoice.get_status_display(),
                    invoice.get_gst_verification_status_display(),
                    invoice.get_extraction_method_display(),
                    f"{invoice.ai_confidence_score:.2f}" if invoice.ai_confidence_score else '',
                    invoice.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')
                ]
                writer.writerow(row)
        else:
            writer.writerow(['No invoices found'])
        
        writer.writerow([])  # Empty row for separation
        
        # Section 3: Summary Statistics
        writer.writerow(['=== SUMMARY STATISTICS ==='])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Invoices', invoices.count()])
        writer.writerow(['Verified Invoices', invoices.filter(gst_verification_status='VERIFIED').count()])
        writer.writerow(['Pending Verification', invoices.filter(gst_verification_status='PENDING').count()])
        writer.writerow(['Failed Verification', invoices.filter(gst_verification_status='FAILED').count()])
        
        total_amount = sum(invoice.grand_total for invoice in invoices)
        writer.writerow(['Total Amount Processed', f"{total_amount:.2f}"])
        
        # Write to response
        response.write(output.getvalue())
        
        logger.info(f"Exported all data for user {user.username}")
        return response


# Create a singleton instance
data_export_service = DataExportService()
