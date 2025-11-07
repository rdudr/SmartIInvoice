"""
Bulk Upload Handler Service

This service manages multi-file invoice uploads and coordinates asynchronous processing.
It creates batch records for tracking and queues individual invoice processing tasks.
"""

import logging
from typing import List, Dict, Any
from django.core.files.uploadedfile import UploadedFile
from django.contrib.auth.models import User
from django.db import transaction

from invoice_processor.models import Invoice, InvoiceBatch
from invoice_processor.tasks import process_invoice_async

logger = logging.getLogger(__name__)


class BulkUploadHandler:
    """
    Handles bulk invoice uploads with asynchronous processing.
    
    This class manages the creation of invoice batches, saves uploaded files,
    and queues individual invoice processing tasks for background execution.
    """
    
    def handle_bulk_upload(self, user: User, files: List[UploadedFile]) -> Dict[str, Any]:
        """
        Process multiple invoice files and queue them for asynchronous processing.
        
        This method:
        1. Creates an InvoiceBatch record for tracking
        2. Creates Invoice records for each file
        3. Queues Celery tasks for asynchronous processing
        4. Returns batch_id for status tracking
        
        Args:
            user: The User uploading the invoices
            files: List of uploaded file objects
            
        Returns:
            dict: {
                'success': bool,
                'batch_id': str (UUID),
                'total_files': int,
                'message': str
            }
            
        Raises:
            Exception: If batch creation or task queuing fails
        """
        if not files:
            logger.warning("handle_bulk_upload called with empty file list")
            return {
                'success': False,
                'error': 'No files provided',
                'error_code': 'NO_FILES'
            }
        
        try:
            with transaction.atomic():
                # Create InvoiceBatch record
                batch = InvoiceBatch.objects.create(
                    user=user,
                    total_files=len(files),
                    processed_count=0,
                    failed_count=0,
                    status='PROCESSING'
                )
                
                logger.info(f"Created batch {batch.batch_id} for user {user.username} with {len(files)} files")
                
                # Create Invoice records and queue processing tasks
                queued_count = 0
                from datetime import date
                
                for file in files:
                    try:
                        # Create Invoice record with minimal data
                        # Use today's date as placeholder since invoice_date is required
                        invoice = Invoice.objects.create(
                            invoice_id='PENDING',  # Will be updated during processing
                            invoice_date=date.today(),  # Placeholder - will be extracted during processing
                            vendor_name='Processing...',  # Will be extracted during processing
                            vendor_gstin='',
                            billed_company_gstin='',
                            grand_total=0,
                            status='PENDING_ANALYSIS',
                            uploaded_by=user,
                            file_path=file,
                            batch=batch,
                            extraction_method='AI'
                        )
                        
                        # Queue asynchronous processing task
                        process_invoice_async.delay(invoice.id, str(batch.batch_id))
                        queued_count += 1
                        
                        logger.info(f"Queued invoice {invoice.id} for processing in batch {batch.batch_id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to create invoice for file {file.name}: {str(e)}")
                        # Increment failed count for this file
                        batch.failed_count += 1
                        batch.save(update_fields=['failed_count'])
                
                # Update batch status if all files failed
                if queued_count == 0:
                    batch.status = 'PARTIAL_FAILURE'
                    batch.save(update_fields=['status'])
                    
                    return {
                        'success': False,
                        'error': 'Failed to queue any files for processing',
                        'error_code': 'ALL_FILES_FAILED',
                        'batch_id': str(batch.batch_id)
                    }
                
                logger.info(f"Successfully queued {queued_count}/{len(files)} files for batch {batch.batch_id}")
                
                return {
                    'success': True,
                    'batch_id': str(batch.batch_id),
                    'total_files': len(files),
                    'queued_files': queued_count,
                    'message': f'Successfully queued {queued_count} invoice(s) for processing'
                }
                
        except Exception as e:
            logger.error(f"Error in handle_bulk_upload: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': 'Failed to create batch upload',
                'details': str(e),
                'error_code': 'BATCH_CREATION_ERROR'
            }
    
    def get_batch_status(self, batch_id: str, user: User) -> Dict[str, Any]:
        """
        Retrieve the current status of a batch upload.
        
        Args:
            batch_id: UUID of the batch to check
            user: User who owns the batch (for authorization)
            
        Returns:
            dict: {
                'success': bool,
                'batch_id': str,
                'status': str,
                'total_files': int,
                'processed_count': int,
                'failed_count': int,
                'in_progress_count': int,
                'progress_percentage': float,
                'created_at': str (ISO format)
            }
        """
        try:
            batch = InvoiceBatch.objects.get(batch_id=batch_id, user=user)
            
            in_progress_count = batch.total_files - batch.processed_count - batch.failed_count
            progress_percentage = ((batch.processed_count + batch.failed_count) / batch.total_files * 100) if batch.total_files > 0 else 0
            
            return {
                'success': True,
                'batch_id': str(batch.batch_id),
                'status': batch.status,
                'total_files': batch.total_files,
                'processed_count': batch.processed_count,
                'failed_count': batch.failed_count,
                'in_progress_count': in_progress_count,
                'progress_percentage': round(progress_percentage, 1),
                'created_at': batch.created_at.isoformat()
            }
            
        except InvoiceBatch.DoesNotExist:
            logger.warning(f"Batch {batch_id} not found for user {user.username}")
            return {
                'success': False,
                'error': 'Batch not found',
                'error_code': 'BATCH_NOT_FOUND'
            }
        except Exception as e:
            logger.error(f"Error getting batch status: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': 'Failed to retrieve batch status',
                'error_code': 'STATUS_RETRIEVAL_ERROR'
            }


# Singleton instance
bulk_upload_handler = BulkUploadHandler()
