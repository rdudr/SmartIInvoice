"""
Invoice Health Score Engine

This module calculates comprehensive health scores for invoices using a weighted rubric
across five categories: Data Completeness, Verification, Compliance, Fraud Detection,
and AI Confidence.
"""

import logging
from decimal import Decimal
from typing import Dict, List
from django.db.models import Q

from ..models import Invoice, InvoiceHealthScore, ComplianceFlag, InvoiceDuplicateLink

logger = logging.getLogger(__name__)


class InvoiceHealthScoreEngine:
    """
    Calculate invoice health scores using weighted category scoring.
    
    Scoring Rubric:
    - Data Completeness: 25%
    - Vendor & Buyer Verification: 30%
    - Compliance & Legal Checks: 25%
    - Fraud & Anomaly Detection: 15%
    - AI Confidence & Document Quality: 5%
    
    Overall Score: 0.0 to 10.0
    Status: HEALTHY (8.0-10.0), REVIEW (5.0-7.9), AT_RISK (0.0-4.9)
    """
    
    # Category weights (must sum to 1.0)
    WEIGHT_DATA_COMPLETENESS = 0.25
    WEIGHT_VERIFICATION = 0.30
    WEIGHT_COMPLIANCE = 0.25
    WEIGHT_FRAUD_DETECTION = 0.15
    WEIGHT_AI_CONFIDENCE = 0.05
    
    # Status thresholds
    THRESHOLD_HEALTHY = 8.0
    THRESHOLD_REVIEW = 5.0
    
    def calculate_health_score(self, invoice: Invoice) -> Dict:
        """
        Calculate comprehensive health score for an invoice.
        
        Args:
            invoice: Invoice model instance
            
        Returns:
            dict: {
                'score': float (0.0-10.0),
                'status': str ('HEALTHY', 'REVIEW', 'AT_RISK'),
                'breakdown': dict (scores by category),
                'key_flags': list (specific issues)
            }
        """
        try:
            # Calculate individual category scores (0-100 scale)
            data_completeness = self._score_data_completeness(invoice)
            verification = self._score_verification(invoice)
            compliance = self._score_compliance(invoice)
            fraud_detection = self._score_fraud_detection(invoice)
            ai_confidence = self._score_ai_confidence(invoice)
            
            # Calculate weighted overall score (0-10 scale)
            overall_score = (
                (data_completeness * self.WEIGHT_DATA_COMPLETENESS) +
                (verification * self.WEIGHT_VERIFICATION) +
                (compliance * self.WEIGHT_COMPLIANCE) +
                (fraud_detection * self.WEIGHT_FRAUD_DETECTION) +
                (ai_confidence * self.WEIGHT_AI_CONFIDENCE)
            ) / 10.0  # Convert from 0-100 to 0-10
            
            # Determine status
            if overall_score >= self.THRESHOLD_HEALTHY:
                status = 'HEALTHY'
            elif overall_score >= self.THRESHOLD_REVIEW:
                status = 'REVIEW'
            else:
                status = 'AT_RISK'
            
            # Generate key flags
            key_flags = self._generate_key_flags(
                invoice,
                data_completeness,
                verification,
                compliance,
                fraud_detection,
                ai_confidence
            )
            
            result = {
                'score': round(overall_score, 1),
                'status': status,
                'breakdown': {
                    'data_completeness': round(data_completeness, 2),
                    'verification': round(verification, 2),
                    'compliance': round(compliance, 2),
                    'fraud_detection': round(fraud_detection, 2),
                    'ai_confidence': round(ai_confidence, 2),
                },
                'key_flags': key_flags
            }
            
            logger.info(f"Calculated health score for invoice {invoice.invoice_id}: "
                       f"{overall_score:.1f} ({status})")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating health score for invoice {invoice.invoice_id}: {str(e)}")
            # Return minimal safe score on error
            return {
                'score': 0.0,
                'status': 'AT_RISK',
                'breakdown': {
                    'data_completeness': 0.0,
                    'verification': 0.0,
                    'compliance': 0.0,
                    'fraud_detection': 0.0,
                    'ai_confidence': 0.0,
                },
                'key_flags': [f"System error during health score calculation: {str(e)}"]
            }
    
    def _score_data_completeness(self, invoice: Invoice) -> float:
        """
        Score data completeness (0-100).
        Checks for presence of all required fields.
        
        Args:
            invoice: Invoice model instance
            
        Returns:
            float: Score from 0 to 100
        """
        score = 100.0
        required_fields = [
            ('invoice_id', invoice.invoice_id),
            ('invoice_date', invoice.invoice_date),
            ('vendor_name', invoice.vendor_name),
            ('vendor_gstin', invoice.vendor_gstin),
            ('billed_company_gstin', invoice.billed_company_gstin),
            ('grand_total', invoice.grand_total),
        ]
        
        # Deduct points for missing required fields
        for field_name, field_value in required_fields:
            if not field_value or (isinstance(field_value, str) and not field_value.strip()):
                score -= 16.67  # Each field worth ~16.67 points (100/6)
                logger.debug(f"Invoice {invoice.invoice_id}: Missing {field_name}")
        
        # Check for line items
        line_items_count = invoice.line_items.count()
        if line_items_count == 0:
            score -= 20.0  # No line items is a major issue
            logger.debug(f"Invoice {invoice.invoice_id}: No line items")
        
        return max(0.0, score)
    
    def _score_verification(self, invoice: Invoice) -> float:
        """
        Score vendor and buyer verification (0-100).
        Checks GST verification status.
        
        Args:
            invoice: Invoice model instance
            
        Returns:
            float: Score from 0 to 100
        """
        score = 100.0
        
        # Check GST verification status
        if invoice.gst_verification_status == 'VERIFIED':
            # Full points for verified
            pass
        elif invoice.gst_verification_status == 'PENDING':
            score -= 50.0  # Pending verification
            logger.debug(f"Invoice {invoice.invoice_id}: GST verification pending")
        elif invoice.gst_verification_status == 'FAILED':
            score -= 100.0  # Failed verification is critical
            logger.debug(f"Invoice {invoice.invoice_id}: GST verification failed")
        
        return max(0.0, score)
    
    def _score_compliance(self, invoice: Invoice) -> float:
        """
        Score compliance and legal checks (0-100).
        Checks for compliance flags (arithmetic errors, HSN mismatches).
        
        Args:
            invoice: Invoice model instance
            
        Returns:
            float: Score from 0 to 100
        """
        score = 100.0
        
        # Get compliance flags
        flags = invoice.compliance_flags.all()
        
        # Deduct points based on flag severity
        for flag in flags:
            if flag.flag_type in ['ARITHMETIC_ERROR', 'HSN_MISMATCH']:
                if flag.severity == 'CRITICAL':
                    score -= 30.0
                elif flag.severity == 'WARNING':
                    score -= 15.0
                elif flag.severity == 'INFO':
                    score -= 5.0
        
        return max(0.0, score)
    
    def _score_fraud_detection(self, invoice: Invoice) -> float:
        """
        Score fraud and anomaly detection (0-100).
        Checks for duplicates and price anomalies.
        
        Args:
            invoice: Invoice model instance
            
        Returns:
            float: Score from 0 to 100
        """
        score = 100.0
        
        # Check for duplicate flag
        duplicate_flags = invoice.compliance_flags.filter(flag_type='DUPLICATE')
        if duplicate_flags.exists():
            score -= 50.0  # Duplicates are serious
            logger.debug(f"Invoice {invoice.invoice_id}: Duplicate detected")
        
        # Check for duplicate link
        try:
            if hasattr(invoice, 'duplicate_link'):
                score -= 50.0  # Linked as duplicate
                logger.debug(f"Invoice {invoice.invoice_id}: Linked as duplicate")
        except InvoiceDuplicateLink.DoesNotExist:
            pass
        
        # Check for price anomalies
        price_anomaly_flags = invoice.compliance_flags.filter(flag_type='PRICE_ANOMALY')
        anomaly_count = price_anomaly_flags.count()
        if anomaly_count > 0:
            # Deduct 10 points per anomaly, up to 50 points max
            score -= min(anomaly_count * 10.0, 50.0)
            logger.debug(f"Invoice {invoice.invoice_id}: {anomaly_count} price anomalies")
        
        return max(0.0, score)
    
    def _score_ai_confidence(self, invoice: Invoice) -> float:
        """
        Score AI confidence and document quality (0-100).
        Uses the AI confidence score if available.
        
        Args:
            invoice: Invoice model instance
            
        Returns:
            float: Score from 0 to 100
        """
        # If manual entry, give neutral score
        if invoice.extraction_method == 'MANUAL':
            return 75.0  # Neutral score for manual entry
        
        # Use AI confidence score if available
        if invoice.ai_confidence_score is not None:
            # ai_confidence_score is already 0-100
            return float(invoice.ai_confidence_score)
        
        # Default to moderate score if no confidence data
        return 70.0
    
    def _generate_key_flags(
        self,
        invoice: Invoice,
        data_completeness: float,
        verification: float,
        compliance: float,
        fraud_detection: float,
        ai_confidence: float
    ) -> List[str]:
        """
        Generate list of key issues affecting the health score.
        
        Args:
            invoice: Invoice model instance
            data_completeness: Data completeness score
            verification: Verification score
            compliance: Compliance score
            fraud_detection: Fraud detection score
            ai_confidence: AI confidence score
            
        Returns:
            list: List of issue descriptions
        """
        key_flags = []
        
        # Data completeness issues
        if data_completeness < 80.0:
            missing_fields = []
            if not invoice.invoice_id:
                missing_fields.append("invoice number")
            if not invoice.invoice_date:
                missing_fields.append("invoice date")
            if not invoice.vendor_name:
                missing_fields.append("vendor name")
            if not invoice.vendor_gstin:
                missing_fields.append("vendor GSTIN")
            if not invoice.billed_company_gstin:
                missing_fields.append("buyer GSTIN")
            if not invoice.grand_total:
                missing_fields.append("grand total")
            if invoice.line_items.count() == 0:
                missing_fields.append("line items")
            
            if missing_fields:
                key_flags.append(f"Missing required data: {', '.join(missing_fields)}")
        
        # Verification issues
        if verification < 100.0:
            if invoice.gst_verification_status == 'FAILED':
                key_flags.append("GST verification failed")
            elif invoice.gst_verification_status == 'PENDING':
                key_flags.append("GST verification pending")
        
        # Compliance issues
        if compliance < 100.0:
            critical_flags = invoice.compliance_flags.filter(
                flag_type__in=['ARITHMETIC_ERROR', 'HSN_MISMATCH'],
                severity='CRITICAL'
            )
            if critical_flags.exists():
                for flag in critical_flags[:3]:  # Limit to first 3
                    key_flags.append(flag.description[:100])  # Truncate long descriptions
        
        # Fraud detection issues
        if fraud_detection < 100.0:
            duplicate_flags = invoice.compliance_flags.filter(flag_type='DUPLICATE')
            if duplicate_flags.exists():
                key_flags.append("Duplicate invoice detected")
            
            try:
                if hasattr(invoice, 'duplicate_link'):
                    key_flags.append("Invoice is a duplicate of an earlier submission")
            except InvoiceDuplicateLink.DoesNotExist:
                pass
            
            price_anomaly_count = invoice.compliance_flags.filter(flag_type='PRICE_ANOMALY').count()
            if price_anomaly_count > 0:
                key_flags.append(f"{price_anomaly_count} price anomaly(ies) detected")
        
        # AI confidence issues
        if ai_confidence < 60.0:
            if invoice.extraction_method == 'MANUAL':
                key_flags.append("Manual data entry (AI extraction failed)")
            else:
                key_flags.append(f"Low AI confidence score ({ai_confidence:.0f}%)")
        
        return key_flags
