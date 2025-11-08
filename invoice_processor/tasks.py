"""
Celery tasks for asynchronous invoice processing.

This module contains all background tasks for the Smart iInvoice system,
including bulk invoice processing, GST verification, and health score calculation.
"""

import logging
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='invoice_processor.process_invoice_async', max_retries=3)
def process_invoice_async(self, invoice_id, batch_id=None):
    """
    Asynchronously process a single invoice through the complete pipeline.
    
    This task handles:
    - AI extraction using Gemini API
    - Compliance checks (HSN/SAC validation, arithmetic verification)
    - GST verification (with cache lookup)
    - Duplicate detection and linking
    - Health score calculation
    
    Args:
        invoice_id (int): Primary key of the Invoice to process
        batch_id (str, optional): UUID of the InvoiceBatch if part of bulk upload
        
    Returns:
        dict: Processing result with status and details
        
    Raises:
        Exception: Re-raises exceptions after logging for Celery retry mechanism
    """
    from invoice_processor.models import Invoice, InvoiceBatch, LineItem, ComplianceFlag, InvoiceHealthScore
    from invoice_processor.services.gemini_service import extract_data_from_image
    from invoice_processor.services.analysis_engine import run_all_checks, normalize_product_key
    from invoice_processor.services.gst_cache_service import gst_cache_service
    from invoice_processor.services.duplicate_linking_service import duplicate_linking_service
    from invoice_processor.services.health_score_engine import InvoiceHealthScoreEngine
    from invoice_processor.services.confidence_score_calculator import calculate_confidence_score
    from decimal import Decimal
    from datetime import datetime
    import decimal
    
    try:
        logger.info(f"Starting async processing for invoice_id={invoice_id}, batch_id={batch_id}")
        
        # Retrieve the invoice
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except ObjectDoesNotExist:
            logger.error(f"Invoice with id={invoice_id} not found")
            _update_batch_failure(batch_id, invoice_id)
            return {
                'status': 'error',
                'invoice_id': invoice_id,
                'error': 'Invoice not found'
            }
        
        # Update invoice status to processing
        invoice.status = 'PENDING_ANALYSIS'
        invoice.save(update_fields=['status'])
        
        # Step 1: AI Extraction
        logger.info(f"Starting AI extraction for invoice {invoice_id}")
        try:
            extracted_data = extract_data_from_image(invoice.file_path)
            
            if not extracted_data.get('is_invoice', False):
                error_msg = extracted_data.get('error', 'File not recognized as invoice')
                logger.warning(f"AI extraction failed for invoice {invoice_id}: {error_msg}")
                
                # Mark for manual entry
                invoice.extraction_method = 'MANUAL'
                invoice.extraction_failure_reason = error_msg
                invoice.status = 'HAS_ANOMALIES'
                invoice.save()
                
                _update_batch_failure(batch_id, invoice_id)
                return {
                    'status': 'failed',
                    'invoice_id': invoice_id,
                    'error': 'AI extraction failed',
                    'requires_manual_entry': True
                }
            
            # Calculate confidence score
            confidence_result = calculate_confidence_score(extracted_data)
            confidence_score = confidence_result['score']
            
            logger.info(f"AI extraction successful for invoice {invoice_id}, confidence: {confidence_score}%")
            
        except Exception as e:
            logger.error(f"AI extraction error for invoice {invoice_id}: {str(e)}")
            invoice.extraction_method = 'MANUAL'
            invoice.extraction_failure_reason = f'Extraction error: {str(e)[:200]}'
            invoice.status = 'HAS_ANOMALIES'
            invoice.save()
            
            _update_batch_failure(batch_id, invoice_id)
            return {
                'status': 'failed',
                'invoice_id': invoice_id,
                'error': 'AI extraction error',
                'requires_manual_entry': True
            }
        
        # Step 2: Update Invoice with extracted data
        try:
            # Parse invoice date
            invoice_date = None
            if extracted_data.get('invoice_date'):
                try:
                    invoice_date = datetime.strptime(extracted_data['invoice_date'], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    logger.warning(f"Invalid date format for invoice {invoice_id}")
            
            # Update invoice fields
            invoice.invoice_id = extracted_data.get('invoice_id', 'UNKNOWN')
            invoice.invoice_date = invoice_date
            invoice.vendor_name = extracted_data.get('vendor_name', 'Unknown Vendor')
            invoice.vendor_gstin = extracted_data.get('vendor_gstin') or ''
            invoice.billed_company_gstin = extracted_data.get('billed_company_gstin') or ''
            invoice.grand_total = Decimal(str(extracted_data.get('grand_total', 0)))
            invoice.ai_confidence_score = Decimal(str(confidence_score))
            invoice.save()
            
            # Create line items
            line_items_data = extracted_data.get('line_items', [])
            for item_data in line_items_data:
                if item_data.get('description'):
                    try:
                        def safe_decimal(value, default=0):
                            if value is None or value == '':
                                return Decimal(str(default))
                            try:
                                return Decimal(str(value))
                            except (ValueError, TypeError, decimal.InvalidOperation):
                                return Decimal(str(default))
                        
                        LineItem.objects.create(
                            invoice=invoice,
                            description=item_data.get('description', ''),
                            normalized_key=normalize_product_key(item_data.get('description', '')),
                            hsn_sac_code=item_data.get('hsn_sac_code') or '',
                            quantity=safe_decimal(item_data.get('quantity'), 0),
                            unit_price=safe_decimal(item_data.get('unit_price'), 0),
                            billed_gst_rate=safe_decimal(item_data.get('billed_gst_rate'), 0),
                            line_total=safe_decimal(item_data.get('line_total'), 0)
                        )
                    except Exception as e:
                        logger.warning(f"Failed to create line item for invoice {invoice_id}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error updating invoice data for {invoice_id}: {str(e)}")
            _update_batch_failure(batch_id, invoice_id)
            raise
        
        # Step 3: Run compliance checks
        logger.info(f"Running compliance checks for invoice {invoice_id}")
        try:
            compliance_flags = run_all_checks(extracted_data, invoice)
            
            for flag in compliance_flags:
                if not flag.invoice_id:
                    flag.invoice = invoice
                flag.save()
            
            # Update invoice status based on flags
            critical_flags = [f for f in compliance_flags if f.severity == 'CRITICAL']
            if critical_flags:
                invoice.status = 'HAS_ANOMALIES'
            else:
                invoice.status = 'CLEARED'
            invoice.save()
            
        except Exception as e:
            logger.error(f"Error during compliance checks for invoice {invoice_id}: {str(e)}")
            invoice.status = 'HAS_ANOMALIES'
            invoice.save()
            
            ComplianceFlag.objects.create(
                invoice=invoice,
                flag_type='SYSTEM_ERROR',
                severity='WARNING',
                description=f'Error during compliance analysis: {str(e)[:200]}'
            )
        
        # Step 4: GST Verification with cache lookup
        logger.info(f"Checking GST cache for invoice {invoice_id}")
        try:
            # Check if this is a duplicate first
            if duplicate_linking_service.is_duplicate(invoice):
                original = duplicate_linking_service.get_original_invoice(invoice)
                if original and original.gst_verification_status == 'VERIFIED':
                    invoice.gst_verification_status = 'VERIFIED'
                    invoice.save()
                    logger.info(f"Invoice {invoice_id} is duplicate, copied GST status from original")
            elif invoice.vendor_gstin:
                # Check cache
                cache_entry = gst_cache_service.lookup_gstin(invoice.vendor_gstin)
                if cache_entry:
                    invoice.gst_verification_status = 'VERIFIED'
                    invoice.save()
                    logger.info(f"GST verified from cache for invoice {invoice_id}")
                else:
                    # Leave as PENDING for manual CAPTCHA verification
                    logger.info(f"GST not in cache for invoice {invoice_id}, requires manual verification")
        except Exception as e:
            logger.error(f"Error during GST verification for invoice {invoice_id}: {str(e)}")
        
        # Step 5: Calculate health score
        logger.info(f"Calculating health score for invoice {invoice_id}")
        try:
            health_engine = InvoiceHealthScoreEngine()
            health_result = health_engine.calculate_health_score(invoice)
            
            # Use update_or_create to handle cases where health score already exists
            InvoiceHealthScore.objects.update_or_create(
                invoice=invoice,
                defaults={
                    'overall_score': Decimal(str(health_result['score'])),
                    'status': health_result['status'],
                    'data_completeness_score': Decimal(str(health_result['breakdown']['data_completeness'])),
                    'verification_score': Decimal(str(health_result['breakdown']['verification'])),
                    'compliance_score': Decimal(str(health_result['breakdown']['compliance'])),
                    'fraud_detection_score': Decimal(str(health_result['breakdown']['fraud_detection'])),
                    'ai_confidence_score_component': Decimal(str(health_result['breakdown']['ai_confidence'])),
                    'key_flags': health_result['key_flags']
                }
            )
            
            logger.info(f"Health score calculated for invoice {invoice_id}: {health_result['score']}")
            
        except Exception as e:
            logger.error(f"Error calculating health score for invoice {invoice_id}: {str(e)}", exc_info=True)
            # Create default health score
            try:
                InvoiceHealthScore.objects.update_or_create(
                    invoice=invoice,
                    defaults={
                        'overall_score': Decimal('0.0'),
                        'status': 'AT_RISK',
                        'data_completeness_score': Decimal('0.0'),
                        'verification_score': Decimal('0.0'),
                        'compliance_score': Decimal('0.0'),
                        'fraud_detection_score': Decimal('0.0'),
                        'ai_confidence_score_component': Decimal('0.0'),
                        'key_flags': [f'Health score calculation error: {str(e)[:100]}']
                    }
                )
            except Exception as inner_e:
                logger.error(f"Failed to create default health score for invoice {invoice_id}: {str(inner_e)}")
        
        # Update batch progress
        _update_batch_success(batch_id, invoice_id)
        
        logger.info(f"Successfully completed processing for invoice {invoice_id}")
        return {
            'status': 'success',
            'invoice_id': invoice_id,
            'batch_id': batch_id
        }
        
    except Exception as e:
        logger.error(f"Error processing invoice {invoice_id}: {str(e)}", exc_info=True)
        
        # Update batch failure count
        _update_batch_failure(batch_id, invoice_id)
        
        # Retry the task with exponential backoff
        try:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for invoice {invoice_id}")
            return {
                'status': 'failed',
                'invoice_id': invoice_id,
                'error': str(e)
            }


def _update_batch_success(batch_id, invoice_id):
    """Helper function to update batch progress on success"""
    if batch_id:
        try:
            from invoice_processor.models import InvoiceBatch
            batch = InvoiceBatch.objects.get(batch_id=batch_id)
            batch.processed_count += 1
            
            # Update batch status
            if batch.processed_count + batch.failed_count >= batch.total_files:
                batch.status = 'COMPLETED' if batch.failed_count == 0 else 'PARTIAL_FAILURE'
            
            batch.save(update_fields=['processed_count', 'status'])
            logger.info(f"Updated batch {batch_id}: {batch.processed_count}/{batch.total_files} processed")
        except ObjectDoesNotExist:
            logger.warning(f"Batch {batch_id} not found for invoice {invoice_id}")


def _update_batch_failure(batch_id, invoice_id):
    """Helper function to update batch progress on failure"""
    if batch_id:
        try:
            from invoice_processor.models import InvoiceBatch
            batch = InvoiceBatch.objects.get(batch_id=batch_id)
            batch.failed_count += 1
            
            # Update batch status
            if batch.processed_count + batch.failed_count >= batch.total_files:
                batch.status = 'COMPLETED' if batch.failed_count == 0 else 'PARTIAL_FAILURE'
            
            batch.save(update_fields=['failed_count', 'status'])
            logger.warning(f"Updated batch {batch_id}: {batch.failed_count} failed")
        except ObjectDoesNotExist:
            logger.warning(f"Batch {batch_id} not found for failed invoice {invoice_id}")


@shared_task(name='invoice_processor.test_celery_connection')
def test_celery_connection():
    """
    Simple test task to verify Celery is working correctly.
    
    Returns:
        str: Success message
    """
    logger.info("Celery test task executed successfully")
    return "Celery is working correctly!"


@shared_task(name='invoice_processor.cleanup_old_results')
def cleanup_old_results():
    """
    Periodic task to clean up old task results and temporary data.
    
    This task can be scheduled to run daily to maintain database hygiene.
    """
    logger.info("Running cleanup task for old results")
    # TODO: Implement cleanup logic in future phases
    return "Cleanup completed"
