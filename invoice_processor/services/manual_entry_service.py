"""
Manual Entry Service for handling AI extraction failures

This service provides functionality to flag invoices for manual entry
when AI extraction fails and validate manually entered invoice data.
"""

import logging
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class ManualEntryService:
    """Service for managing manual invoice data entry when AI extraction fails"""
    
    def flag_for_manual_entry(self, invoice, reason: str) -> bool:
        """
        Mark an invoice as requiring manual entry due to AI extraction failure
        
        Args:
            invoice: Invoice model instance
            reason: Human-readable explanation of why AI extraction failed
            
        Returns:
            bool: True if successfully flagged, False otherwise
        """
        try:
            invoice.extraction_method = 'MANUAL'
            invoice.extraction_failure_reason = reason
            invoice.status = 'PENDING_ANALYSIS'
            invoice.save()
            
            logger.info(f"Invoice {invoice.id} flagged for manual entry. Reason: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to flag invoice {invoice.id} for manual entry: {str(e)}")
            return False
    
    def validate_manual_entry(self, data: Dict) -> Tuple[bool, List[str]]:
        """
        Validate manually entered invoice data against business rules
        
        Args:
            data: Dictionary containing invoice and line item data
            
        Returns:
            Tuple of (is_valid: bool, error_messages: List[str])
        """
        errors = []
        
        # Validate invoice-level fields
        errors.extend(self._validate_invoice_fields(data))
        
        # Validate line items
        errors.extend(self._validate_line_items(data.get('line_items', [])))
        
        # Validate arithmetic consistency
        errors.extend(self._validate_arithmetic(data))
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info("Manual entry data validation passed")
        else:
            logger.warning(f"Manual entry data validation failed with {len(errors)} errors")
        
        return is_valid, errors
    
    def _validate_invoice_fields(self, data: Dict) -> List[str]:
        """Validate required invoice-level fields"""
        errors = []
        
        # Invoice ID
        invoice_id = data.get('invoice_id', '').strip()
        if not invoice_id:
            errors.append("Invoice number is required")
        elif len(invoice_id) > 100:
            errors.append("Invoice number must be 100 characters or less")
        
        # Invoice Date
        invoice_date = data.get('invoice_date')
        if not invoice_date:
            errors.append("Invoice date is required")
        else:
            try:
                if isinstance(invoice_date, str):
                    parsed_date = datetime.strptime(invoice_date, '%Y-%m-%d').date()
                    # Check if date is not in the future
                    if parsed_date > datetime.now().date():
                        errors.append("Invoice date cannot be in the future")
            except (ValueError, TypeError):
                errors.append("Invoice date must be in YYYY-MM-DD format")
        
        # Vendor Name
        vendor_name = data.get('vendor_name', '').strip()
        if not vendor_name:
            errors.append("Vendor name is required")
        elif len(vendor_name) > 255:
            errors.append("Vendor name must be 255 characters or less")
        
        # Vendor GSTIN
        vendor_gstin = data.get('vendor_gstin', '').strip()
        if vendor_gstin:  # Optional but must be valid if provided
            if not self._validate_gstin_format(vendor_gstin):
                errors.append("Vendor GSTIN must be 15 characters (format: 22AAAAA0000A1Z5)")
        
        # Billed Company GSTIN
        billed_gstin = data.get('billed_company_gstin', '').strip()
        if billed_gstin:  # Optional but must be valid if provided
            if not self._validate_gstin_format(billed_gstin):
                errors.append("Billed company GSTIN must be 15 characters (format: 22AAAAA0000A1Z5)")
        
        # Grand Total
        grand_total = data.get('grand_total')
        if grand_total is None or grand_total == '':
            errors.append("Grand total is required")
        else:
            try:
                total = Decimal(str(grand_total))
                if total < 0:
                    errors.append("Grand total cannot be negative")
                if total > Decimal('999999999.99'):
                    errors.append("Grand total is too large")
            except (ValueError, InvalidOperation):
                errors.append("Grand total must be a valid number")
        
        return errors
    
    def _validate_line_items(self, line_items: List[Dict]) -> List[str]:
        """Validate line item data"""
        errors = []
        
        if not line_items or len(line_items) == 0:
            errors.append("At least one line item is required")
            return errors
        
        if len(line_items) > 100:
            errors.append("Maximum 100 line items allowed")
        
        for idx, item in enumerate(line_items, start=1):
            item_errors = []
            
            # Description
            description = item.get('description', '').strip()
            if not description:
                item_errors.append(f"Line {idx}: Description is required")
            elif len(description) > 500:
                item_errors.append(f"Line {idx}: Description must be 500 characters or less")
            
            # HSN/SAC Code
            hsn_sac = item.get('hsn_sac_code', '').strip()
            if hsn_sac and len(hsn_sac) > 20:
                item_errors.append(f"Line {idx}: HSN/SAC code must be 20 characters or less")
            
            # Quantity
            quantity = item.get('quantity')
            if quantity is None or quantity == '':
                item_errors.append(f"Line {idx}: Quantity is required")
            else:
                try:
                    qty = Decimal(str(quantity))
                    if qty <= 0:
                        item_errors.append(f"Line {idx}: Quantity must be greater than zero")
                    if qty > Decimal('999999.99'):
                        item_errors.append(f"Line {idx}: Quantity is too large")
                except (ValueError, InvalidOperation):
                    item_errors.append(f"Line {idx}: Quantity must be a valid number")
            
            # Unit Price
            unit_price = item.get('unit_price')
            if unit_price is None or unit_price == '':
                item_errors.append(f"Line {idx}: Unit price is required")
            else:
                try:
                    price = Decimal(str(unit_price))
                    if price < 0:
                        item_errors.append(f"Line {idx}: Unit price cannot be negative")
                    if price > Decimal('999999999.99'):
                        item_errors.append(f"Line {idx}: Unit price is too large")
                except (ValueError, InvalidOperation):
                    item_errors.append(f"Line {idx}: Unit price must be a valid number")
            
            # GST Rate
            gst_rate = item.get('billed_gst_rate')
            if gst_rate is None or gst_rate == '':
                item_errors.append(f"Line {idx}: GST rate is required")
            else:
                try:
                    rate = Decimal(str(gst_rate))
                    if rate < 0 or rate > 100:
                        item_errors.append(f"Line {idx}: GST rate must be between 0 and 100")
                except (ValueError, InvalidOperation):
                    item_errors.append(f"Line {idx}: GST rate must be a valid number")
            
            # Line Total
            line_total = item.get('line_total')
            if line_total is None or line_total == '':
                item_errors.append(f"Line {idx}: Line total is required")
            else:
                try:
                    total = Decimal(str(line_total))
                    if total < 0:
                        item_errors.append(f"Line {idx}: Line total cannot be negative")
                    if total > Decimal('999999999.99'):
                        item_errors.append(f"Line {idx}: Line total is too large")
                except (ValueError, InvalidOperation):
                    item_errors.append(f"Line {idx}: Line total must be a valid number")
            
            errors.extend(item_errors)
        
        return errors
    
    def _validate_arithmetic(self, data: Dict) -> List[str]:
        """Validate arithmetic consistency between line items and grand total"""
        errors = []
        
        try:
            grand_total = Decimal(str(data.get('grand_total', 0)))
            line_items = data.get('line_items', [])
            
            # Calculate sum of line totals
            calculated_total = Decimal('0')
            for item in line_items:
                line_total = item.get('line_total')
                if line_total is not None and line_total != '':
                    try:
                        calculated_total += Decimal(str(line_total))
                    except (ValueError, InvalidOperation):
                        # Skip invalid line totals (already caught in line item validation)
                        pass
            
            # Allow small rounding differences (up to 1 rupee)
            difference = abs(grand_total - calculated_total)
            if difference > Decimal('1.00'):
                errors.append(
                    f"Grand total (₹{grand_total}) does not match sum of line items (₹{calculated_total}). "
                    f"Difference: ₹{difference}"
                )
        
        except (ValueError, InvalidOperation, TypeError):
            # If we can't validate arithmetic, skip this check
            # (individual field errors will be caught elsewhere)
            pass
        
        return errors
    
    def _validate_gstin_format(self, gstin: str) -> bool:
        """
        Validate GSTIN format
        Format: 22AAAAA0000A1Z5 (15 characters)
        - First 2 digits: State code
        - Next 10 characters: PAN
        - 13th character: Entity number
        - 14th character: Z (default)
        - 15th character: Checksum
        """
        if not gstin or len(gstin) != 15:
            return False
        
        # Basic pattern check
        pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
        return bool(re.match(pattern, gstin.upper()))


# Singleton instance
manual_entry_service = ManualEntryService()
