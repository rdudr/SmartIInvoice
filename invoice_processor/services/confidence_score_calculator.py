"""
Confidence Score Calculator for AI-extracted invoice data

This module calculates confidence scores based on the quality and completeness
of data extracted by the Gemini AI service.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfidenceScoreCalculator:
    """
    Calculate confidence scores for AI-extracted invoice data
    
    The confidence score (0-100%) indicates how certain the AI is about
    the extracted data based on:
    - Field completeness (40%)
    - Data quality indicators (30%)
    - Response certainty (30%)
    """
    
    # Confidence level thresholds
    HIGH_THRESHOLD = 80.0
    MEDIUM_THRESHOLD = 50.0
    
    # Required fields for invoice
    REQUIRED_FIELDS = ['invoice_id', 'vendor_name', 'grand_total']
    
    # Important optional fields
    IMPORTANT_FIELDS = ['invoice_date', 'vendor_gstin', 'billed_company_gstin']
    
    def calculate_confidence(self, extraction_result: Dict[str, Any]) -> float:
        """
        Calculate confidence score for extracted invoice data
        
        Args:
            extraction_result: Dictionary containing extracted invoice data
            
        Returns:
            float: Confidence score from 0.00 to 100.00
        """
        try:
            # Check if this is a valid invoice extraction
            if not extraction_result.get('is_invoice', False):
                logger.warning("Extraction result is not an invoice")
                return 0.0
            
            # Calculate component scores
            completeness_score = self._calculate_completeness_score(extraction_result)
            quality_score = self._calculate_quality_score(extraction_result)
            certainty_score = self._calculate_certainty_score(extraction_result)
            
            # Weighted average
            confidence = (
                completeness_score * 0.40 +
                quality_score * 0.30 +
                certainty_score * 0.30
            )
            
            # Ensure score is within bounds
            confidence = max(0.0, min(100.0, confidence))
            
            logger.info(f"Calculated confidence score: {confidence:.2f}% "
                       f"(completeness: {completeness_score:.1f}, "
                       f"quality: {quality_score:.1f}, "
                       f"certainty: {certainty_score:.1f})")
            
            return round(confidence, 2)
            
        except Exception as e:
            logger.error(f"Error calculating confidence score: {str(e)}")
            return 0.0
    
    def get_confidence_level(self, score: float) -> str:
        """
        Categorize confidence score into HIGH/MEDIUM/LOW
        
        Args:
            score: Confidence score (0-100)
            
        Returns:
            str: 'HIGH', 'MEDIUM', or 'LOW'
        """
        if score >= self.HIGH_THRESHOLD:
            return 'HIGH'
        elif score >= self.MEDIUM_THRESHOLD:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _calculate_completeness_score(self, data: Dict[str, Any]) -> float:
        """
        Calculate score based on field completeness (0-100)
        
        Checks:
        - All required fields present and non-empty (60 points)
        - Important optional fields present (30 points)
        - Line items present and complete (10 points)
        """
        score = 0.0
        
        # Check required fields (60 points total, 20 per field)
        required_present = 0
        for field in self.REQUIRED_FIELDS:
            value = data.get(field)
            if value is not None and str(value).strip():
                required_present += 1
        
        score += (required_present / len(self.REQUIRED_FIELDS)) * 60.0
        
        # Check important optional fields (30 points total, 10 per field)
        important_present = 0
        for field in self.IMPORTANT_FIELDS:
            value = data.get(field)
            if value is not None and str(value).strip():
                important_present += 1
        
        score += (important_present / len(self.IMPORTANT_FIELDS)) * 30.0
        
        # Check line items (10 points)
        line_items = data.get('line_items', [])
        if isinstance(line_items, list) and len(line_items) > 0:
            # Check if line items have key fields
            complete_items = 0
            for item in line_items:
                if isinstance(item, dict):
                    if (item.get('description') and 
                        item.get('quantity') is not None and 
                        item.get('unit_price') is not None):
                        complete_items += 1
            
            if len(line_items) > 0:
                score += (complete_items / len(line_items)) * 10.0
        
        return score
    
    def _calculate_quality_score(self, data: Dict[str, Any]) -> float:
        """
        Calculate score based on data quality indicators (0-100)
        
        Checks:
        - GSTIN format validity (30 points)
        - Date format validity (20 points)
        - Numeric values are valid (30 points)
        - HSN/SAC codes present (20 points)
        """
        score = 0.0
        
        # Check GSTIN format (30 points total, 15 per GSTIN)
        vendor_gstin = data.get('vendor_gstin', '')
        billed_gstin = data.get('billed_company_gstin', '')
        
        if vendor_gstin and len(str(vendor_gstin).strip()) == 15:
            score += 15.0
        if billed_gstin and len(str(billed_gstin).strip()) == 15:
            score += 15.0
        
        # Check date format (20 points)
        invoice_date = data.get('invoice_date', '')
        if invoice_date and self._is_valid_date_format(invoice_date):
            score += 20.0
        
        # Check numeric values (30 points)
        grand_total = data.get('grand_total')
        if grand_total is not None and self._is_valid_number(grand_total):
            score += 15.0
        
        # Check line item numeric values
        line_items = data.get('line_items', [])
        if isinstance(line_items, list) and len(line_items) > 0:
            valid_numeric_items = 0
            for item in line_items:
                if isinstance(item, dict):
                    if (self._is_valid_number(item.get('quantity')) and
                        self._is_valid_number(item.get('unit_price')) and
                        self._is_valid_number(item.get('line_total'))):
                        valid_numeric_items += 1
            
            score += (valid_numeric_items / len(line_items)) * 15.0
        
        # Check HSN/SAC codes (20 points)
        if isinstance(line_items, list) and len(line_items) > 0:
            items_with_hsn = 0
            for item in line_items:
                if isinstance(item, dict) and item.get('hsn_sac_code'):
                    items_with_hsn += 1
            
            score += (items_with_hsn / len(line_items)) * 20.0
        
        return score
    
    def _calculate_certainty_score(self, data: Dict[str, Any]) -> float:
        """
        Calculate score based on response certainty (0-100)
        
        Checks:
        - No null values in critical fields (40 points)
        - Consistent data (e.g., line totals match calculations) (30 points)
        - Complete vendor information (30 points)
        """
        score = 0.0
        
        # Check for null values in critical fields (40 points)
        critical_fields = ['invoice_id', 'vendor_name', 'grand_total', 'invoice_date']
        non_null_critical = 0
        for field in critical_fields:
            if data.get(field) is not None:
                non_null_critical += 1
        
        score += (non_null_critical / len(critical_fields)) * 40.0
        
        # Check data consistency (30 points)
        # Verify line totals are consistent with quantity * unit_price
        line_items = data.get('line_items', [])
        if isinstance(line_items, list) and len(line_items) > 0:
            consistent_items = 0
            for item in line_items:
                if isinstance(item, dict):
                    qty = item.get('quantity')
                    price = item.get('unit_price')
                    total = item.get('line_total')
                    
                    if qty is not None and price is not None and total is not None:
                        try:
                            expected_total = float(qty) * float(price)
                            actual_total = float(total)
                            # Allow 1% tolerance for rounding
                            if abs(expected_total - actual_total) / max(expected_total, 0.01) < 0.01:
                                consistent_items += 1
                            else:
                                # Still count as partially consistent if values exist
                                consistent_items += 0.5
                        except (ValueError, TypeError):
                            pass
            
            if len(line_items) > 0:
                score += (consistent_items / len(line_items)) * 30.0
        else:
            # If no line items, give partial credit
            score += 15.0
        
        # Check complete vendor information (30 points)
        vendor_fields = ['vendor_name', 'vendor_gstin']
        complete_vendor = 0
        for field in vendor_fields:
            value = data.get(field)
            if value is not None and str(value).strip():
                complete_vendor += 1
        
        score += (complete_vendor / len(vendor_fields)) * 30.0
        
        return score
    
    def _is_valid_date_format(self, date_str: str) -> bool:
        """Check if date string is in valid YYYY-MM-DD format"""
        if not isinstance(date_str, str):
            return False
        
        try:
            parts = date_str.split('-')
            if len(parts) != 3:
                return False
            
            year, month, day = parts
            if len(year) == 4 and len(month) == 2 and len(day) == 2:
                # Basic validation
                y, m, d = int(year), int(month), int(day)
                if 1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
                    return True
        except (ValueError, AttributeError):
            pass
        
        return False
    
    def _is_valid_number(self, value: Any) -> bool:
        """Check if value is a valid number"""
        if value is None:
            return False
        
        try:
            num = float(value)
            return num >= 0  # Negative values are suspicious for invoices
        except (ValueError, TypeError):
            return False


# Create a singleton instance for easy import
confidence_calculator = ConfidenceScoreCalculator()


def calculate_confidence_score(extraction_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function for calculating confidence score
    
    Args:
        extraction_result: Dictionary containing extracted invoice data
        
    Returns:
        dict: {
            'score': float (0-100),
            'level': str ('HIGH', 'MEDIUM', 'LOW')
        }
    """
    score = confidence_calculator.calculate_confidence(extraction_result)
    level = confidence_calculator.get_confidence_level(score)
    
    return {
        'score': score,
        'level': level
    }
