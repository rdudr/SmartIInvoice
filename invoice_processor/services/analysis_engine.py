"""
Analysis Engine for Invoice Compliance Checks

This module provides comprehensive compliance checking functionality for invoices,
including duplicate detection, arithmetic verification, HSN/SAC rate validation,
and price anomaly detection.
"""

import json
import re
import logging
import decimal
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Tuple
from django.db.models import Avg, Count
from django.conf import settings
import os

from ..models import Invoice, LineItem, ComplianceFlag

logger = logging.getLogger(__name__)

# Global variable to store HSN/SAC master data
_hsn_master_data = None


def load_hsn_master_data() -> Dict:
    """
    Load HSN/SAC master data from cached JSON file.
    
    Returns:
        dict: Dictionary containing goods and services GST rates
    """
    global _hsn_master_data
    
    if _hsn_master_data is not None:
        return _hsn_master_data
    
    try:
        data_file_path = os.path.join(settings.BASE_DIR, 'data', 'hsn_gst_rates.json')
        
        if not os.path.exists(data_file_path):
            logger.error(f"HSN master data file not found at {data_file_path}")
            return {"goods": {}, "services": {}}
        
        with open(data_file_path, 'r', encoding='utf-8') as f:
            _hsn_master_data = json.load(f)
        
        logger.info(f"Loaded HSN master data: {len(_hsn_master_data.get('goods', {}))} goods, "
                   f"{len(_hsn_master_data.get('services', {}))} services")
        
        return _hsn_master_data
        
    except Exception as e:
        logger.error(f"Error loading HSN master data: {str(e)}")
        return {"goods": {}, "services": {}}


def normalize_product_key(description: str) -> str:
    """
    Normalize item description for consistent matching.
    
    Args:
        description: Raw item description from invoice
        
    Returns:
        str: Normalized product key for comparison
    """
    if not description:
        return ""
    
    # Convert to lowercase
    normalized = description.lower().strip()
    
    # Remove common words that don't affect product identity
    common_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
        'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'between', 'among', 'under', 'over',
        'piece', 'pieces', 'unit', 'units', 'item', 'items', 'nos', 'no', 'qty'
    }
    
    # Split into words and filter
    words = re.findall(r'\b\w+\b', normalized)
    filtered_words = [word for word in words if word not in common_words and len(word) > 1]
    
    # Join back and remove extra spaces
    normalized = ' '.join(filtered_words)
    
    # Remove special characters except spaces and alphanumeric
    normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
    
    # Remove extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def run_all_checks(invoice_data: Dict, invoice_obj: Invoice) -> List[ComplianceFlag]:
    """
    Orchestrate all compliance checks for an invoice.
    
    Args:
        invoice_data: Extracted invoice data from Gemini API
        invoice_obj: Saved Invoice model instance
        
    Returns:
        list: List of ComplianceFlag objects to be saved
    """
    compliance_flags = []
    
    try:
        # 1. Check for duplicates
        duplicate_flag = check_duplicates(invoice_data)
        if duplicate_flag:
            duplicate_flag.invoice = invoice_obj
            compliance_flags.append(duplicate_flag)
        
        # 2. Check arithmetic calculations
        arithmetic_flags = check_arithmetics(invoice_data)
        for flag in arithmetic_flags:
            flag.invoice = invoice_obj
            compliance_flags.append(flag)
        
        # 3. Check HSN/SAC rates
        hsn_flags = check_hsn_rates(invoice_data)
        for flag in hsn_flags:
            flag.invoice = invoice_obj
            compliance_flags.append(flag)
        
        # 4. Check price outliers (only if no duplicates found)
        if not duplicate_flag:
            price_flags = check_price_outliers(invoice_data, invoice_data.get('vendor_gstin'))
            for flag in price_flags:
                flag.invoice = invoice_obj
                compliance_flags.append(flag)
        
        logger.info(f"Completed compliance checks for invoice {invoice_obj.invoice_id}: "
                   f"{len(compliance_flags)} flags generated")
        
    except Exception as e:
        logger.error(f"Error during compliance checks for invoice {invoice_obj.invoice_id}: {str(e)}")
        # Create a generic error flag
        error_flag = ComplianceFlag(
            invoice=invoice_obj,
            flag_type='SYSTEM_ERROR',
            severity='CRITICAL',
            description=f"System error during compliance analysis: {str(e)}"
        )
        compliance_flags.append(error_flag)
    
    return compliance_flags


def check_duplicates(invoice_data: Dict) -> Optional[ComplianceFlag]:
    """
    Check for duplicate invoices by invoice_id and vendor_gstin.
    
    Args:
        invoice_data: Extracted invoice data
        
    Returns:
        ComplianceFlag or None: Duplicate flag if found, None otherwise
    """
    try:
        invoice_id = invoice_data.get('invoice_id')
        vendor_gstin = invoice_data.get('vendor_gstin')
        
        if not invoice_id or not vendor_gstin:
            logger.warning("Missing invoice_id or vendor_gstin for duplicate check")
            return None
        
        # Query for existing invoices with same invoice_id and vendor_gstin
        existing_invoices = Invoice.objects.filter(
            invoice_id=invoice_id,
            vendor_gstin=vendor_gstin
        ).exclude(
            status='PENDING_ANALYSIS'  # Exclude the current invoice being processed
        )
        
        if existing_invoices.exists():
            existing_invoice = existing_invoices.first()
            return ComplianceFlag(
                flag_type='DUPLICATE',
                severity='CRITICAL',
                description=f"Duplicate invoice detected. Same invoice ID '{invoice_id}' "
                           f"from vendor GSTIN '{vendor_gstin}' already exists "
                           f"(uploaded on {existing_invoice.uploaded_at.strftime('%Y-%m-%d %H:%M')})"
            )
        
        return None
        
    except Exception as e:
        logger.error(f"Error in duplicate check: {str(e)}")
        return ComplianceFlag(
            flag_type='SYSTEM_ERROR',
            severity='CRITICAL',
            description=f"Error during duplicate check: {str(e)}"
        )


def check_arithmetics(invoice_data: Dict) -> List[ComplianceFlag]:
    """
    Verify arithmetic calculations on invoice line items and grand total.
    
    Args:
        invoice_data: Extracted invoice data
        
    Returns:
        list: List of ComplianceFlag objects for arithmetic errors
    """
    flags = []
    
    try:
        line_items = invoice_data.get('line_items', [])
        grand_total = invoice_data.get('grand_total')
        
        if not line_items:
            logger.warning("No line items found for arithmetic check")
            return flags
        
        calculated_grand_total = Decimal('0')
        
        # Check each line item calculation
        for i, item in enumerate(line_items):
            try:
                # Helper function to safely convert to Decimal
                def safe_decimal(value, default=0):
                    if value is None or value == '':
                        return Decimal(str(default))
                    try:
                        return Decimal(str(value))
                    except (ValueError, TypeError, decimal.InvalidOperation):
                        return Decimal(str(default))
                
                quantity = safe_decimal(item.get('quantity'), 0)
                unit_price = safe_decimal(item.get('unit_price'), 0)
                billed_gst_rate = safe_decimal(item.get('billed_gst_rate'), 0)
                line_total_raw = item.get('line_total')
                
                line_total = None
                if line_total_raw is not None:
                    line_total = safe_decimal(line_total_raw, 0)
                
                # Calculate expected line total
                # Line total = (quantity * unit_price) + GST
                base_amount = quantity * unit_price
                gst_amount = base_amount * (billed_gst_rate / Decimal('100'))
                expected_total = (base_amount + gst_amount).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                
                # Check if line total matches calculation
                if line_total is not None and abs(expected_total - line_total) > Decimal('0.01'):
                    flags.append(ComplianceFlag(
                        flag_type='ARITHMETIC_ERROR',
                        severity='CRITICAL',
                        description=f"Line item {i+1} calculation error: "
                                   f"Expected {expected_total}, but invoice shows {line_total}. "
                                   f"(Qty: {quantity}, Unit Price: {unit_price}, GST: {billed_gst_rate}%)"
                    ))
                
                # Add to grand total calculation
                if line_total is not None:
                    calculated_grand_total += line_total
                else:
                    calculated_grand_total += expected_total
                    
            except (ValueError, TypeError, AttributeError) as e:
                flags.append(ComplianceFlag(
                    flag_type='ARITHMETIC_ERROR',
                    severity='WARNING',
                    description=f"Line item {i+1} has invalid numeric values: {str(e)}"
                ))
        
        # Check grand total
        if grand_total is not None:
            try:
                grand_total_decimal = Decimal(str(grand_total))
                if abs(calculated_grand_total - grand_total_decimal) > Decimal('0.01'):
                    flags.append(ComplianceFlag(
                        flag_type='ARITHMETIC_ERROR',
                        severity='CRITICAL',
                        description=f"Grand total mismatch: Expected {calculated_grand_total}, "
                                   f"but invoice shows {grand_total_decimal}"
                    ))
            except (ValueError, TypeError) as e:
                flags.append(ComplianceFlag(
                    flag_type='ARITHMETIC_ERROR',
                    severity='WARNING',
                    description=f"Invalid grand total value: {str(e)}"
                ))
        
    except Exception as e:
        logger.error(f"Error in arithmetic check: {str(e)}")
        flags.append(ComplianceFlag(
            flag_type='SYSTEM_ERROR',
            severity='CRITICAL',
            description=f"Error during arithmetic verification: {str(e)}"
        ))
    
    return flags


def check_hsn_rates(invoice_data: Dict) -> List[ComplianceFlag]:
    """
    Validate HSN/SAC codes against master data and check GST rates.
    
    Args:
        invoice_data: Extracted invoice data
        
    Returns:
        list: List of ComplianceFlag objects for HSN/SAC issues
    """
    flags = []
    
    try:
        line_items = invoice_data.get('line_items', [])
        master_data = load_hsn_master_data()
        
        if not line_items:
            logger.warning("No line items found for HSN rate check")
            return flags
        
        goods_data = master_data.get('goods', {})
        services_data = master_data.get('services', {})
        
        for i, item in enumerate(line_items):
            hsn_sac_code = item.get('hsn_sac_code', '').strip()
            billed_gst_rate = item.get('billed_gst_rate')
            description = item.get('description', '')
            
            if not hsn_sac_code:
                flags.append(ComplianceFlag(
                    flag_type='UNKNOWN_HSN',
                    severity='WARNING',
                    description=f"Line item {i+1} '{description}' has no HSN/SAC code"
                ))
                continue
            
            # Clean HSN code (remove spaces, special characters)
            clean_hsn = re.sub(r'[^\w]', '', hsn_sac_code)
            
            # Look up in goods first, then services
            official_rate = None
            found_in = None
            
            if clean_hsn in goods_data:
                official_rate = goods_data[clean_hsn].get('rate', 0)
                found_in = 'goods'
            elif clean_hsn in services_data:
                official_rate = services_data[clean_hsn].get('rate', 0)
                found_in = 'services'
            
            if official_rate is None:
                flags.append(ComplianceFlag(
                    flag_type='UNKNOWN_HSN',
                    severity='INFO',
                    description=f"Line item {i+1} HSN/SAC code '{hsn_sac_code}' not found in master data"
                ))
                continue
            
            # Compare rates if both are available
            if billed_gst_rate is not None:
                try:
                    billed_rate_decimal = Decimal(str(billed_gst_rate))
                    official_rate_decimal = Decimal(str(official_rate))
                    
                    if abs(billed_rate_decimal - official_rate_decimal) > Decimal('0.01'):
                        flags.append(ComplianceFlag(
                            flag_type='HSN_MISMATCH',
                            severity='CRITICAL',
                            description=f"Line item {i+1} GST rate mismatch for HSN/SAC '{hsn_sac_code}': "
                                       f"Billed {billed_gst_rate}%, Official rate {official_rate}% "
                                       f"(found in {found_in} master data)"
                        ))
                        
                except (ValueError, TypeError) as e:
                    flags.append(ComplianceFlag(
                        flag_type='SYSTEM_ERROR',
                        severity='WARNING',
                        description=f"Line item {i+1} has invalid GST rate value: {str(e)}"
                    ))
        
    except Exception as e:
        logger.error(f"Error in HSN rate check: {str(e)}")
        flags.append(ComplianceFlag(
            flag_type='SYSTEM_ERROR',
            severity='CRITICAL',
            description=f"Error during HSN/SAC rate validation: {str(e)}"
        ))
    
    return flags


def check_price_outliers(invoice_data: Dict, vendor_gstin: str) -> List[ComplianceFlag]:
    """
    Detect price anomalies by comparing against historical data.
    
    Args:
        invoice_data: Extracted invoice data
        vendor_gstin: Vendor GST number for historical lookup
        
    Returns:
        list: List of ComplianceFlag objects for price anomalies
    """
    flags = []
    
    try:
        line_items = invoice_data.get('line_items', [])
        
        if not line_items or not vendor_gstin:
            logger.warning("No line items or vendor GSTIN for price outlier check")
            return flags
        
        for i, item in enumerate(line_items):
            try:
                description = item.get('description', '')
                unit_price = item.get('unit_price')
                
                if not description or unit_price is None:
                    continue
                
                # Normalize product description for consistent matching
                normalized_key = normalize_product_key(description)
                
                if not normalized_key:
                    continue
                
                unit_price_decimal = Decimal(str(unit_price))
                
                # Query historical prices for same product from same vendor
                historical_items = LineItem.objects.filter(
                    normalized_key=normalized_key,
                    invoice__vendor_gstin=vendor_gstin,
                    invoice__status__in=['CLEARED', 'HAS_ANOMALIES']  # Only processed invoices
                ).exclude(
                    invoice__status='PENDING_ANALYSIS'  # Exclude current processing
                )
                
                # Need at least 3 historical records for meaningful comparison
                if historical_items.count() < 3:
                    logger.debug(f"Insufficient historical data for product '{normalized_key}' "
                               f"from vendor {vendor_gstin}: {historical_items.count()} records")
                    continue
                
                # Calculate average historical price
                avg_data = historical_items.aggregate(
                    avg_price=Avg('unit_price'),
                    count=Count('id')
                )
                
                avg_price = avg_data['avg_price']
                if avg_price is None or avg_price <= 0:
                    continue
                
                avg_price_decimal = Decimal(str(avg_price))
                
                # Calculate deviation percentage
                deviation = abs(unit_price_decimal - avg_price_decimal) / avg_price_decimal * 100
                
                # Flag if deviation > 25%
                if deviation > 25:
                    flags.append(ComplianceFlag(
                        flag_type='PRICE_ANOMALY',
                        severity='WARNING',
                        description=f"Line item {i+1} '{description}' price anomaly detected: "
                                   f"Current price ₹{unit_price_decimal}, "
                                   f"Historical average ₹{avg_price_decimal:.2f} "
                                   f"({deviation:.1f}% deviation, based on {avg_data['count']} records)"
                    ))
                
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Error processing line item {i+1} for price outlier: {str(e)}")
                continue
        
    except Exception as e:
        logger.error(f"Error in price outlier check: {str(e)}")
        flags.append(ComplianceFlag(
            flag_type='SYSTEM_ERROR',
            severity='CRITICAL',
            description=f"Error during price anomaly detection: {str(e)}"
        ))
    
    return flags