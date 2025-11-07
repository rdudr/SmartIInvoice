"""
Duplicate Linking Service for Smart Invoice Management

This module provides functionality to automatically link duplicate invoices to their
originals, preventing redundant GST verification and maintaining clean audit trails.
"""

import logging
from typing import Optional
from django.db import transaction
from django.utils import timezone

from ..models import Invoice, InvoiceDuplicateLink

logger = logging.getLogger(__name__)


class DuplicateLinkingService:
    """
    Service for managing duplicate invoice relationships
    """
    
    def find_original_invoice(self, vendor_gstin: str, invoice_id: str) -> Optional[Invoice]:
        """
        Find the first occurrence (original) of an invoice with matching identifiers.
        
        Args:
            vendor_gstin: Vendor GST number
            invoice_id: Invoice number/ID
            
        Returns:
            Invoice: The original invoice if found, None otherwise
        """
        try:
            if not vendor_gstin or not invoice_id:
                logger.warning("Missing vendor_gstin or invoice_id for finding original")
                return None
            
            # Find the earliest invoice with matching identifiers
            # Exclude PENDING_ANALYSIS to avoid linking to currently processing invoices
            original_invoice = Invoice.objects.filter(
                vendor_gstin=vendor_gstin,
                invoice_id=invoice_id
            ).exclude(
                status='PENDING_ANALYSIS'
            ).order_by('uploaded_at').first()
            
            if original_invoice:
                logger.info(f"Found original invoice: {original_invoice.id} "
                           f"(Invoice ID: {invoice_id}, Vendor: {vendor_gstin})")
            else:
                logger.debug(f"No original invoice found for Invoice ID: {invoice_id}, "
                            f"Vendor: {vendor_gstin}")
            
            return original_invoice
            
        except Exception as e:
            logger.error(f"Error finding original invoice: {str(e)}")
            return None
    
    def link_duplicate(self, duplicate: Invoice, original: Invoice) -> bool:
        """
        Create a link between duplicate and original invoice, and copy GST verification status.
        
        Args:
            duplicate: The duplicate invoice to link
            original: The original invoice to link to
            
        Returns:
            bool: True if linking was successful, False otherwise
        """
        try:
            if not duplicate or not original:
                logger.error("Cannot link: duplicate or original invoice is None")
                return False
            
            # Prevent self-linking
            if duplicate.id == original.id:
                logger.warning(f"Attempted to link invoice {duplicate.id} to itself")
                return False
            
            # Check if duplicate is already linked
            if hasattr(duplicate, 'duplicate_link'):
                logger.warning(f"Invoice {duplicate.id} is already linked to "
                             f"invoice {duplicate.duplicate_link.original_invoice.id}")
                return False
            
            with transaction.atomic():
                # Create the duplicate link
                InvoiceDuplicateLink.objects.create(
                    duplicate_invoice=duplicate,
                    original_invoice=original
                )
                
                # Copy GST verification status from original to duplicate
                if original.gst_verification_status == 'VERIFIED':
                    duplicate.gst_verification_status = 'VERIFIED'
                    duplicate.save(update_fields=['gst_verification_status'])
                    
                    logger.info(f"Linked duplicate invoice {duplicate.id} to original {original.id} "
                               f"and copied GST verification status: {original.gst_verification_status}")
                else:
                    logger.info(f"Linked duplicate invoice {duplicate.id} to original {original.id} "
                               f"(Original GST status: {original.gst_verification_status})")
                
                return True
                
        except Exception as e:
            logger.error(f"Error linking duplicate invoice {duplicate.id if duplicate else 'None'} "
                        f"to original {original.id if original else 'None'}: {str(e)}")
            return False
    
    def is_duplicate(self, invoice: Invoice) -> bool:
        """
        Check if an invoice is marked as a duplicate.
        
        Args:
            invoice: Invoice to check
            
        Returns:
            bool: True if invoice is a duplicate, False otherwise
        """
        try:
            return hasattr(invoice, 'duplicate_link')
        except Exception as e:
            logger.error(f"Error checking if invoice {invoice.id} is duplicate: {str(e)}")
            return False
    
    def get_original_invoice(self, duplicate: Invoice) -> Optional[Invoice]:
        """
        Get the original invoice for a duplicate.
        
        Args:
            duplicate: The duplicate invoice
            
        Returns:
            Invoice: The original invoice if found, None otherwise
        """
        try:
            if hasattr(duplicate, 'duplicate_link'):
                return duplicate.duplicate_link.original_invoice
            return None
        except Exception as e:
            logger.error(f"Error getting original invoice for duplicate {duplicate.id}: {str(e)}")
            return None
    
    def get_all_duplicates(self, original: Invoice) -> list:
        """
        Get all duplicate invoices linked to an original.
        
        Args:
            original: The original invoice
            
        Returns:
            list: List of duplicate Invoice objects
        """
        try:
            duplicate_links = InvoiceDuplicateLink.objects.filter(
                original_invoice=original
            ).select_related('duplicate_invoice').order_by('detected_at')
            
            return [link.duplicate_invoice for link in duplicate_links]
            
        except Exception as e:
            logger.error(f"Error getting duplicates for original invoice {original.id}: {str(e)}")
            return []


# Create a singleton instance for easy import
duplicate_linking_service = DuplicateLinkingService()
