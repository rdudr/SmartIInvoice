from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from decimal import Decimal
import decimal
import logging
import json
from datetime import datetime, timedelta
from django.utils import timezone

from .forms import CustomUserCreationForm, CustomAuthenticationForm, InvoiceUploadForm
from .models import Invoice, LineItem, ComplianceFlag
from .services.gemini_service import extract_data_from_image
from .services.analysis_engine import run_all_checks, normalize_product_key
from .services.gst_client import get_captcha, verify_gstin

logger = logging.getLogger(__name__)


def handler404(request, exception):
    """Custom 404 error handler"""
    return render(request, 'errors/404.html', {
        'error_title': 'Page Not Found',
        'error_message': 'The page you are looking for does not exist.',
        'error_code': '404'
    }, status=404)


def handler500(request):
    """Custom 500 error handler"""
    return render(request, 'errors/500.html', {
        'error_title': 'Server Error',
        'error_message': 'An internal server error occurred. Please try again later.',
        'error_code': '500'
    }, status=500)


def handler403(request, exception):
    """Custom 403 error handler"""
    return render(request, 'errors/403.html', {
        'error_title': 'Access Forbidden',
        'error_message': 'You do not have permission to access this resource.',
        'error_code': '403'
    }, status=403)


@login_required
def dashboard(request):
    """Dashboard view with metrics calculation logic"""
    
    # Calculate key metrics
    # 1. Invoices Awaiting Verification
    invoices_awaiting_verification = Invoice.objects.filter(
        uploaded_by=request.user,
        gst_verification_status='PENDING'
    ).count()
    
    # 2. Anomalies Found This Week
    one_week_ago = timezone.now() - timedelta(days=7)
    anomalies_this_week = ComplianceFlag.objects.filter(
        invoice__uploaded_by=request.user,
        created_at__gte=one_week_ago
    ).count()
    
    # 3. Total Amount Processed
    total_amount = Invoice.objects.filter(
        uploaded_by=request.user
    ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0')
    
    # Anomaly breakdown for donut chart
    anomaly_breakdown = ComplianceFlag.objects.filter(
        invoice__uploaded_by=request.user
    ).values('flag_type').annotate(count=Count('id')).order_by('-count')
    
    # Recent activity - 5 most recently processed invoices
    recent_invoices = Invoice.objects.filter(
        uploaded_by=request.user
    ).order_by('-uploaded_at')[:5]
    
    # Suspected invoices - top 5 invoices with Critical compliance flags
    suspected_invoices = Invoice.objects.filter(
        uploaded_by=request.user,
        compliance_flags__severity='CRITICAL'
    ).annotate(
        critical_flags_count=Count('compliance_flags', filter=Q(compliance_flags__severity='CRITICAL'))
    ).order_by('-critical_flags_count', '-uploaded_at')[:5]
    
    context = {
        'metrics': {
            'invoices_awaiting_verification': invoices_awaiting_verification,
            'anomalies_this_week': anomalies_this_week,
            'total_amount_processed': total_amount,
        },
        'anomaly_breakdown': list(anomaly_breakdown),
        'recent_invoices': recent_invoices,
        'suspected_invoices': suspected_invoices,
    }
    
    return render(request, 'dashboard.html', context)


def login_view(request):
    """Custom login view with styled form"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})


def register_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Account created successfully! You can now log in.')
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'registration/register.html', {'form': form})


@login_required
@require_http_methods(["POST"])
def upload_invoice(request):
    """
    Handle invoice file upload, data extraction, and compliance analysis
    
    Returns JSON response with upload status for AJAX handling
    """
    try:
        # Step 1: Validate form and file upload
        form = InvoiceUploadForm(request.POST, request.FILES)
        
        if not form.is_valid():
            # Extract specific validation errors
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    error_messages.append(str(error))
            
            return JsonResponse({
                'success': False,
                'error': 'File validation failed',
                'details': '; '.join(error_messages),
                'error_code': 'VALIDATION_ERROR'
            }, status=400)
        
        invoice_file = form.cleaned_data['invoice_file']
        
        # Step 2: Extract data using Gemini API with comprehensive error handling
        logger.info(f"Starting invoice extraction for file: {invoice_file.name} (size: {invoice_file.size} bytes)")
        
        try:
            extracted_data = extract_data_from_image(invoice_file)
        except Exception as e:
            logger.error(f"Gemini service error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invoice extraction service encountered an error. Please try again.',
                'details': 'The AI service is temporarily unavailable',
                'error_code': 'EXTRACTION_SERVICE_ERROR'
            }, status=503)
        
        # Check if extraction was successful
        if not extracted_data.get('is_invoice', False):
            error_msg = extracted_data.get('error', 'File not recognized as invoice')
            error_code = extracted_data.get('error_code', 'NOT_AN_INVOICE')
            
            logger.warning(f"Invoice extraction failed: {error_msg}")
            return JsonResponse({
                'success': False,
                'error': error_msg,
                'error_code': error_code
            }, status=400)
        
        # Step 3: Validate extracted data has minimum required fields
        required_fields = ['invoice_id', 'vendor_name']
        missing_fields = [field for field in required_fields if not extracted_data.get(field)]
        
        if missing_fields:
            logger.warning(f"Missing required fields in extracted data: {missing_fields}")
            return JsonResponse({
                'success': False,
                'error': 'Unable to extract essential invoice information from the image',
                'details': f'Could not find: {", ".join(missing_fields)}. Please ensure the invoice is clear and complete.',
                'error_code': 'INCOMPLETE_EXTRACTION'
            }, status=400)
        
        # Step 4: Save invoice and line items in a transaction with error handling
        try:
            with transaction.atomic():
                # Parse invoice date if provided
                invoice_date = None
                if extracted_data.get('invoice_date'):
                    try:
                        invoice_date = datetime.strptime(extracted_data['invoice_date'], '%Y-%m-%d').date()
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid date format: {extracted_data.get('invoice_date')} - {str(e)}")
                
                # Validate and convert grand_total
                try:
                    grand_total = Decimal(str(extracted_data.get('grand_total', 0)))
                except (ValueError, TypeError, decimal.InvalidOperation) as e:
                    logger.warning(f"Invalid grand_total value: {extracted_data.get('grand_total')} - {str(e)}")
                    grand_total = Decimal('0')
                
                # Create Invoice record
                invoice = Invoice.objects.create(
                    invoice_id=extracted_data.get('invoice_id', ''),
                    invoice_date=invoice_date,
                    vendor_name=extracted_data.get('vendor_name', ''),
                    vendor_gstin=extracted_data.get('vendor_gstin') or '',
                    billed_company_gstin=extracted_data.get('billed_company_gstin') or '',
                    grand_total=grand_total,
                    status='PENDING_ANALYSIS',
                    uploaded_by=request.user,
                    file_path=invoice_file
                )
                
                # Create LineItem records with error handling
                line_items_data = extracted_data.get('line_items', [])
                created_line_items = 0
                
                for item_data in line_items_data:
                    if item_data.get('description'):  # Only create if description exists
                        try:
                            LineItem.objects.create(
                                invoice=invoice,
                                description=item_data.get('description', ''),
                                normalized_key=normalize_product_key(item_data.get('description', '')),
                                hsn_sac_code=item_data.get('hsn_sac_code') or '',
                                quantity=Decimal(str(item_data.get('quantity', 0))),
                                unit_price=Decimal(str(item_data.get('unit_price', 0))),
                                billed_gst_rate=Decimal(str(item_data.get('billed_gst_rate', 0))),
                                line_total=Decimal(str(item_data.get('line_total', 0)))
                            )
                            created_line_items += 1
                        except (ValueError, TypeError, decimal.InvalidOperation) as e:
                            logger.warning(f"Skipping invalid line item: {item_data} - {str(e)}")
                            continue
                
                # Step 5: Run compliance checks with error handling
                logger.info(f"Running compliance checks for invoice {invoice.invoice_id}")
                
                try:
                    compliance_flags = run_all_checks(extracted_data, invoice)
                    
                    # Save compliance flags
                    for flag in compliance_flags:
                        if not flag.invoice_id:  # Ensure invoice is set
                            flag.invoice = invoice
                        flag.save()
                    
                    # Update invoice status based on flags
                    critical_flags = [f for f in compliance_flags if f.severity == 'CRITICAL']
                    if critical_flags:
                        invoice.status = 'HAS_ANOMALIES'
                    else:
                        invoice.status = 'CLEARED'
                    
                    invoice.save()
                    
                    logger.info(f"Invoice {invoice.invoice_id} processed successfully. "
                               f"Status: {invoice.status}, Flags: {len(compliance_flags)}")
                    
                except Exception as e:
                    logger.error(f"Error during compliance checks: {str(e)}")
                    # Still save the invoice but mark it as having processing issues
                    invoice.status = 'HAS_ANOMALIES'
                    invoice.save()
                    
                    # Create a system error flag
                    ComplianceFlag.objects.create(
                        invoice=invoice,
                        flag_type='SYSTEM_ERROR',
                        severity='WARNING',
                        description=f'Error during compliance analysis: {str(e)[:200]}'
                    )
                    
                    compliance_flags = [ComplianceFlag.objects.filter(invoice=invoice).first()]
                    critical_flags = []
        
        except Exception as e:
            logger.error(f"Database error during invoice save: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to save invoice data to database',
                'details': 'Please try uploading the invoice again',
                'error_code': 'DATABASE_ERROR'
            }, status=500)
        
        # Step 6: Return success response
        return JsonResponse({
            'success': True,
            'message': 'Invoice uploaded and processed successfully',
            'invoice': {
                'id': invoice.id,
                'invoice_id': invoice.invoice_id,
                'vendor_name': invoice.vendor_name,
                'status': invoice.status,
                'grand_total': str(invoice.grand_total),
                'line_items_count': created_line_items,
                'compliance_flags_count': len(compliance_flags) if 'compliance_flags' in locals() else 0,
                'critical_flags_count': len(critical_flags) if 'critical_flags' in locals() else 0
            }
        })
        
    except MemoryError as e:
        logger.error(f"Memory error during invoice processing: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'File is too large to process',
            'details': 'Please upload a smaller file (under 10MB)',
            'error_code': 'MEMORY_ERROR'
        }, status=413)
    
    except Exception as e:
        logger.error(f"Unexpected error processing invoice upload: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred while processing your invoice',
            'details': 'Please try again. If the problem persists, contact support.',
            'error_code': 'UNEXPECTED_ERROR'
        }, status=500)


@login_required
def gst_verification(request):
    """
    GST Verification page with invoice table, pagination, and filtering
    """
    # Get filter parameter
    status_filter = request.GET.get('status', 'all')
    
    # Base queryset for user's invoices
    invoices_qs = Invoice.objects.filter(uploaded_by=request.user).order_by('-uploaded_at')
    
    # Apply status filter
    if status_filter == 'pending':
        invoices_qs = invoices_qs.filter(gst_verification_status='PENDING')
    elif status_filter == 'verified':
        invoices_qs = invoices_qs.filter(gst_verification_status='VERIFIED')
    elif status_filter == 'failed':
        invoices_qs = invoices_qs.filter(gst_verification_status='FAILED')
    # 'all' shows all invoices (no additional filter)
    
    # Pagination - 10 rows per page
    paginator = Paginator(invoices_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'current_filter': status_filter,
        'total_count': invoices_qs.count(),
    }
    
    return render(request, 'gst_verification.html', context)


@login_required
@require_http_methods(["POST"])
def request_captcha(request):
    """
    AJAX endpoint to request CAPTCHA from GST microservice
    """
    try:
        logger.info("Requesting CAPTCHA for GST verification")
        
        # Call GST microservice to get CAPTCHA with comprehensive error handling
        try:
            captcha_response = get_captcha()
        except Exception as e:
            logger.error(f"GST service call failed: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'GST verification service is temporarily unavailable. Please try again later.',
                'error_code': 'GST_SERVICE_UNAVAILABLE'
            }, status=503)
        
        # Check for service-level errors
        if 'error' in captcha_response:
            error_msg = captcha_response['error']
            logger.warning(f"GST service returned error: {error_msg}")
            
            # Provide user-friendly error messages based on error type
            if 'unavailable' in error_msg.lower() or 'connection' in error_msg.lower():
                user_error = 'GST verification service is temporarily unavailable. Please try again in a few minutes.'
                error_code = 'SERVICE_UNAVAILABLE'
            elif 'timeout' in error_msg.lower():
                user_error = 'GST verification service is taking too long to respond. Please try again.'
                error_code = 'SERVICE_TIMEOUT'
            else:
                user_error = 'Unable to connect to GST verification service. Please try again later.'
                error_code = 'SERVICE_ERROR'
            
            return JsonResponse({
                'success': False,
                'error': user_error,
                'error_code': error_code
            }, status=503)
        
        # Validate response structure
        if not captcha_response.get('sessionId') or not captcha_response.get('image'):
            logger.error(f"Invalid CAPTCHA response structure: {captcha_response}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid response from GST verification service. Please try again.',
                'error_code': 'INVALID_RESPONSE'
            }, status=502)
        
        # Return CAPTCHA data to frontend
        logger.info(f"Successfully retrieved CAPTCHA with session ID: {captcha_response['sessionId']}")
        return JsonResponse({
            'success': True,
            'sessionId': captcha_response['sessionId'],
            'captchaImage': captcha_response['image']
        })
        
    except Exception as e:
        logger.error(f"Unexpected error requesting CAPTCHA: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred while requesting CAPTCHA. Please try again.',
            'error_code': 'UNEXPECTED_ERROR'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def verify_gst(request):
    """
    AJAX endpoint to submit GST verification request
    """
    try:
        # Parse JSON request body with error handling
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in GST verification request: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid request format',
                'error_code': 'INVALID_JSON'
            }, status=400)
        
        invoice_id = data.get('invoice_id')
        session_id = data.get('session_id')
        captcha_text = data.get('captcha')
        
        # Validate required parameters
        if not invoice_id:
            return JsonResponse({
                'success': False,
                'error': 'Invoice ID is required',
                'error_code': 'MISSING_INVOICE_ID'
            }, status=400)
        
        if not session_id:
            return JsonResponse({
                'success': False,
                'error': 'Session ID is required. Please request a new CAPTCHA.',
                'error_code': 'MISSING_SESSION_ID'
            }, status=400)
        
        if not captcha_text or not captcha_text.strip():
            return JsonResponse({
                'success': False,
                'error': 'Please enter the CAPTCHA text',
                'error_code': 'MISSING_CAPTCHA'
            }, status=400)
        
        # Get invoice and verify ownership
        try:
            invoice = get_object_or_404(Invoice, id=invoice_id, uploaded_by=request.user)
        except Exception as e:
            logger.error(f"Invoice not found or access denied: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invoice not found or access denied',
                'error_code': 'INVOICE_NOT_FOUND'
            }, status=404)
        
        if not invoice.vendor_gstin:
            logger.warning(f"No GSTIN found for invoice {invoice.id}")
            return JsonResponse({
                'success': False,
                'error': 'No GSTIN found for this invoice. Cannot perform verification.',
                'error_code': 'NO_GSTIN'
            }, status=400)
        
        # Validate GSTIN format
        if len(invoice.vendor_gstin.strip()) != 15:
            logger.warning(f"Invalid GSTIN format: {invoice.vendor_gstin}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid GSTIN format in invoice. Cannot perform verification.',
                'error_code': 'INVALID_GSTIN_FORMAT'
            }, status=400)
        
        logger.info(f"Verifying GSTIN {invoice.vendor_gstin} for invoice {invoice.invoice_id}")
        
        # Call GST microservice for verification with comprehensive error handling
        try:
            verification_response = verify_gstin(session_id, invoice.vendor_gstin, captcha_text.strip())
        except Exception as e:
            logger.error(f"GST verification service call failed: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'GST verification service is temporarily unavailable. Please try again later.',
                'error_code': 'VERIFICATION_SERVICE_ERROR'
            }, status=503)
        
        # Process verification response
        if 'error' in verification_response:
            error_msg = verification_response['error']
            logger.warning(f"GST verification failed for {invoice.vendor_gstin}: {error_msg}")
            
            # Update invoice status
            invoice.gst_verification_status = 'FAILED'
            invoice.save()
            
            # Provide user-friendly error messages
            if 'captcha' in error_msg.lower():
                user_error = 'CAPTCHA verification failed. Please try again with a new CAPTCHA.'
                error_code = 'CAPTCHA_FAILED'
            elif 'invalid' in error_msg.lower() and 'gstin' in error_msg.lower():
                user_error = 'The GSTIN appears to be invalid or not registered.'
                error_code = 'INVALID_GSTIN'
            elif 'session' in error_msg.lower() or 'expired' in error_msg.lower():
                user_error = 'Session expired. Please request a new CAPTCHA and try again.'
                error_code = 'SESSION_EXPIRED'
            elif 'timeout' in error_msg.lower():
                user_error = 'Verification request timed out. Please try again.'
                error_code = 'VERIFICATION_TIMEOUT'
            else:
                user_error = 'GST verification failed. Please try again with a new CAPTCHA.'
                error_code = 'VERIFICATION_FAILED'
            
            return JsonResponse({
                'success': False,
                'error': user_error,
                'error_code': error_code,
                'invoice_id': invoice.id,
                'new_status': 'FAILED'
            })
        else:
            # Verification successful
            logger.info(f"GST verification successful for {invoice.vendor_gstin}")
            
            try:
                invoice.gst_verification_status = 'VERIFIED'
                invoice.save()
            except Exception as e:
                logger.error(f"Failed to update invoice status after successful verification: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': 'Verification completed but failed to update status. Please refresh the page.',
                    'error_code': 'STATUS_UPDATE_ERROR'
                }, status=500)
            
            return JsonResponse({
                'success': True,
                'message': 'GST verification completed successfully',
                'invoice_id': invoice.id,
                'new_status': 'VERIFIED',
                'verification_data': verification_response
            })
        
    except Exception as e:
        logger.error(f"Unexpected error during GST verification: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred during GST verification. Please try again.',
            'error_code': 'UNEXPECTED_ERROR'
        }, status=500)