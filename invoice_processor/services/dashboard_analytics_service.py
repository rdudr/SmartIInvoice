"""
Dashboard Analytics Service

Provides data aggregation and analytics methods for the enhanced dashboard.
Generates data for charts, tables, and visualizations.
"""

from django.db.models import Count, Sum, Q, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Any
import logging

from invoice_processor.models import Invoice, LineItem, InvoiceHealthScore

logger = logging.getLogger(__name__)


class DashboardAnalyticsService:
    """Service for generating dashboard analytics data"""
    
    def get_invoice_per_day_data(self, user, days: int = 5) -> Dict[str, Any]:
        """
        Get invoice processing data per day for bar chart visualization.
        
        Args:
            user: The user to filter invoices for
            days: Number of days to include (default: 5, can be 5-14)
            
        Returns:
            Dictionary with dates, genuine_counts, and at_risk_counts lists
            
        Requirements: 7.1, 7.6
        """
        try:
            # Validate days parameter
            days = max(5, min(14, days))  # Clamp between 5 and 14
            
            # Calculate date range
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days - 1)
            
            # Initialize result structure
            dates = []
            genuine_counts = []
            at_risk_counts = []
            
            # Query invoices for each day
            for i in range(days):
                current_date = start_date + timedelta(days=i)
                dates.append(current_date.strftime('%d %b'))
                
                # Get invoices for this day
                day_invoices = Invoice.objects.filter(
                    uploaded_by=user,
                    uploaded_at__date=current_date
                ).select_related('health_score')
                
                # Count genuine (HEALTHY) invoices
                genuine_count = day_invoices.filter(
                    health_score__status='HEALTHY'
                ).count()
                
                # Count at-risk (REVIEW + AT_RISK) invoices
                at_risk_count = day_invoices.filter(
                    health_score__status__in=['REVIEW', 'AT_RISK']
                ).count()
                
                genuine_counts.append(genuine_count)
                at_risk_counts.append(at_risk_count)
            
            logger.info(f"Generated invoice per day data for {days} days")
            
            return {
                'dates': dates,
                'genuine_counts': genuine_counts,
                'at_risk_counts': at_risk_counts,
                'total_days': days
            }
            
        except Exception as e:
            logger.error(f"Error generating invoice per day data: {str(e)}")
            return {
                'dates': [],
                'genuine_counts': [],
                'at_risk_counts': [],
                'total_days': days
            }
    
    def get_money_flow_by_hsn(self, user, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get spending distribution by HSN/SAC code for donut chart.
        
        Args:
            user: The user to filter invoices for
            limit: Number of top categories to return (default: 5)
            
        Returns:
            List of dictionaries with hsn_code, description, amount, and percentage
            
        Requirements: 7.2
        """
        try:
            # Get all line items for user's invoices
            line_items = LineItem.objects.filter(
                invoice__uploaded_by=user
            ).values('hsn_sac_code').annotate(
                total_amount=Sum('line_total'),
                count=Count('id')
            ).order_by('-total_amount')[:limit]
            
            # Calculate total for percentage calculation
            total_amount = sum(item['total_amount'] for item in line_items)
            
            if total_amount == 0:
                logger.warning("No line items found for money flow calculation")
                return []
            
            # Format results with percentages
            results = []
            for item in line_items:
                amount = item['total_amount']
                percentage = (float(amount) / float(total_amount)) * 100
                
                results.append({
                    'hsn_code': item['hsn_sac_code'] or 'Unknown',
                    'amount': float(amount),
                    'percentage': round(percentage, 1),
                    'count': item['count']
                })
            
            logger.info(f"Generated money flow data for {len(results)} HSN/SAC codes")
            
            return results
            
        except Exception as e:
            logger.error(f"Error generating money flow data: {str(e)}")
            return []
    
    def get_company_leaderboard(self, user, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get top vendors by total spend and invoice count.
        
        Args:
            user: The user to filter invoices for
            limit: Number of top vendors to return (default: 5)
            
        Returns:
            List of dictionaries with vendor_name, total_amount, and invoice_count
            
        Requirements: 7.3
        """
        try:
            # Aggregate by vendor
            vendors = Invoice.objects.filter(
                uploaded_by=user
            ).values('vendor_name', 'vendor_gstin').annotate(
                total_amount=Sum('grand_total'),
                invoice_count=Count('id')
            ).order_by('-total_amount')[:limit]
            
            # Format results
            results = []
            for vendor in vendors:
                results.append({
                    'vendor_name': vendor['vendor_name'],
                    'vendor_gstin': vendor['vendor_gstin'],
                    'total_amount': float(vendor['total_amount']),
                    'invoice_count': vendor['invoice_count']
                })
            
            logger.info(f"Generated company leaderboard with {len(results)} vendors")
            
            return results
            
        except Exception as e:
            logger.error(f"Error generating company leaderboard: {str(e)}")
            return []
    
    def get_red_flag_list(self, user, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get invoices with lowest health scores (high-risk invoices).
        
        Args:
            user: The user to filter invoices for
            limit: Number of invoices to return (default: 5)
            
        Returns:
            List of dictionaries with invoice details and health scores
            
        Requirements: 7.4
        """
        try:
            # Get invoices with health scores, ordered by score (ascending)
            invoices = Invoice.objects.filter(
                uploaded_by=user
            ).select_related('health_score').filter(
                health_score__isnull=False
            ).order_by('health_score__overall_score')[:limit]
            
            # Format results
            results = []
            for invoice in invoices:
                results.append({
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_id,
                    'vendor_name': invoice.vendor_name,
                    'date': invoice.invoice_date.strftime('%m/%d/%Y') if invoice.invoice_date else 'N/A',
                    'health_score': float(invoice.health_score.overall_score),
                    'health_status': invoice.health_score.status,
                    'grand_total': float(invoice.grand_total)
                })
            
            logger.info(f"Generated red flag list with {len(results)} invoices")
            
            return results
            
        except Exception as e:
            logger.error(f"Error generating red flag list: {str(e)}")
            return []


# Singleton instance
dashboard_analytics_service = DashboardAnalyticsService()
