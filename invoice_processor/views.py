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
from .models import Invoice, LineItem, ComplianceFlag, InvoiceHealthScore
from .services.gemini_service import extract_data_from_image
from .services.analysis_engine import run_all_checks, normalize_product_key
from .services.gst_client import get_captcha, verify_gstin
from .services.health_score_engine import InvoiceHealthScoreEngine
from .services.gst_cache_service import gst_cache_service
from .services.confidence_score_calculator import calculate_confidence_score
from .services.manual_entry_service import manual_entry_service
from .services.dashboard_analytics_service import dashboard_analytics_service

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
    
    # Get date range filter parameter (default: 7 days)
    days_filter = int(request.GET.get('days', 7))
    days_filter = max(5, min(14, days_filter))  # Clamp between 5 and 14
    
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
    # Optimized with select_related for health_score
    recent_invoices = Invoice.objects.filter(
        uploaded_by=request.user
    ).select_related('health_score').order_by('-uploaded_at')[:5]
    
    # Suspected invoices - top 5 invoices with Critical compliance flags
    # Optimized with select_related and prefetch_related
    suspected_invoices = Invoice.objects.filter(
        uploaded_by=request.user,
        compliance_flags__severity='CRITICAL'
    ).select_related('health_score').prefetch_related('compliance_flags').annotate(
        critical_flags_count=Count('compliance_flags', filter=Q(compliance_flags__severity='CRITICAL'))
    ).order_by('-critical_flags_count', '-uploaded_at')[:5]
    
    # Phase 2 Analytics
    # Invoice Per Day data for bar chart
    invoice_per_day_data = dashboard_analytics_service.get_invoice_per_day_data(
        request.user, 
        days=days_filter
    )
    
    # Money Flow by HSN/SAC for donut chart
    money_flow_data = dashboard_analytics_service.get_money_flow_by_hsn(request.user)
    
    # Company Leaderboard
    company_leaderboard = dashboard_analytics_service.get_company_leaderboard(request.user)
    
    # Red Flag List (high-risk invoices)
    red_flag_list = dashboard_analytics_service.get_red_flag_list(request.user)
    
    context = {
        'metrics': {
            'invoices_awaiting_verification': invoices_awaiting_verification,
            'anomalies_this_week': anomalies_this_week,
            'total_amount_processed': total_amount,
        },
        'anomaly_breakdown': list(anomaly_breakdown),
        'recent_invoices': recent_invoices,
        'suspected_invoices': suspected_invoices,
        # Phase 2 Analytics
        'invoice_per_day_data': invoice_per_day_data,
        'money_flow_data': money_flow_data,
        'company_leaderboard': company_leaderboard,
        'red_flag_list': red_flag_list,
        'days_filter': days_filter,
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
            
            # Create invoice record flagged for manual entry
            try:
                with transaction.atomic():
                    invoice = Invoice.objects.create(
                        invoice_id='',  # Will be filled manually
                        invoice_date=None,
                        vendor_name='',
                        vendor_gstin='',
                        billed_company_gstin='',
                        grand_total=Decimal('0'),
                        status='PENDING_ANALYSIS',
                        uploaded_by=request.user,
                        file_path=invoice_file,
                        extraction_method='MANUAL',
                        extraction_failure_reason=error_msg
                    )
                    
                    logger.info(f"Invoice {invoice.id} created and flagged for manual entry")
                    
                    return JsonResponse({
                        'success': False,
                        'error': error_msg,
                        'error_code': error_code,
                        'requires_manual_entry': True,
                        'invoice_id': invoice.id
                    }, status=400)
            except Exception as e:
                logger.error(f"Failed to create invoice for manual entry: {str(e)}")
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
            error_msg = f'Could not extract essential information: {", ".join(missing_fields)}. Please enter data manually.'
            
            # Create invoice record flagged for manual entry
            try:
                with transaction.atomic():
                    invoice = Invoice.objects.create(
                        invoice_id='',  # Will be filled manually
                        invoice_date=None,
                        vendor_name='',
                        vendor_gstin='',
                        billed_company_gstin='',
                        grand_total=Decimal('0'),
                        status='PENDING_ANALYSIS',
                        uploaded_by=request.user,
                        file_path=invoice_file,
                        extraction_method='MANUAL',
                        extraction_failure_reason=error_msg
                    )
                    
                    logger.info(f"Invoice {invoice.id} created and flagged for manual entry due to incomplete extraction")
                    
                    return JsonResponse({
                        'success': False,
                        'error': 'Unable to extract essential invoice information from the image',
                        'details': error_msg,
                        'error_code': 'INCOMPLETE_EXTRACTION',
                        'requires_manual_entry': True,
                        'invoice_id': invoice.id
                    }, status=400)
            except Exception as e:
                logger.error(f"Failed to create invoice for manual entry: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': 'Unable to extract essential invoice information from the image',
                    'details': error_msg,
                    'error_code': 'INCOMPLETE_EXTRACTION'
                }, status=400)
        
        # Step 4: Calculate confidence score for the extraction
        logger.info("Calculating confidence score for extracted data")
        confidence_result = calculate_confidence_score(extracted_data)
        confidence_score = confidence_result['score']
        confidence_level = confidence_result['level']
        
        logger.info(f"Confidence score: {confidence_score}% ({confidence_level})")
        
        # Step 5: Save invoice and line items in a transaction with error handling
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
                
                # Create Invoice record with confidence score
                invoice = Invoice.objects.create(
                    invoice_id=extracted_data.get('invoice_id', ''),
                    invoice_date=invoice_date,
                    vendor_name=extracted_data.get('vendor_name', ''),
                    vendor_gstin=extracted_data.get('vendor_gstin') or '',
                    billed_company_gstin=extracted_data.get('billed_company_gstin') or '',
                    grand_total=grand_total,
                    status='PENDING_ANALYSIS',
                    uploaded_by=request.user,
                    file_path=invoice_file,
                    ai_confidence_score=Decimal(str(confidence_score))
                )
                
                # Create LineItem records with error handling
                line_items_data = extracted_data.get('line_items', [])
                created_line_items = 0
                
                for item_data in line_items_data:
                    if item_data.get('description'):  # Only create if description exists
                        try:
                            # Helper function to safely convert to Decimal
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
                            created_line_items += 1
                        except (ValueError, TypeError, decimal.InvalidOperation) as e:
                            logger.warning(f"Skipping invalid line item: {item_data} - {str(e)}")
                            continue
                
                # Step 6: Run compliance checks with error handling
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
                
                # Step 7: Calculate and store health score
                logger.info(f"Calculating health score for invoice {invoice.invoice_id}")
                
                try:
                    health_engine = InvoiceHealthScoreEngine()
                    health_result = health_engine.calculate_health_score(invoice)
                    
                    # Store health score in database
                    InvoiceHealthScore.objects.create(
                        invoice=invoice,
                        overall_score=Decimal(str(health_result['score'])),
                        status=health_result['status'],
                        data_completeness_score=Decimal(str(health_result['breakdown']['data_completeness'])),
                        verification_score=Decimal(str(health_result['breakdown']['verification'])),
                        compliance_score=Decimal(str(health_result['breakdown']['compliance'])),
                        fraud_detection_score=Decimal(str(health_result['breakdown']['fraud_detection'])),
                        ai_confidence_score_component=Decimal(str(health_result['breakdown']['ai_confidence'])),
                        key_flags=health_result['key_flags']
                    )
                    
                    logger.info(f"Health score calculated for invoice {invoice.invoice_id}: "
                               f"{health_result['score']} ({health_result['status']})")
                    
                except Exception as e:
                    logger.error(f"Error calculating health score: {str(e)}")
                    # Health score calculation failure shouldn't block invoice processing
                    # Create a default health score entry
                    try:
                        InvoiceHealthScore.objects.create(
                            invoice=invoice,
                            overall_score=Decimal('0.0'),
                            status='AT_RISK',
                            data_completeness_score=Decimal('0.0'),
                            verification_score=Decimal('0.0'),
                            compliance_score=Decimal('0.0'),
                            fraud_detection_score=Decimal('0.0'),
                            ai_confidence_score_component=Decimal('0.0'),
                            key_flags=[f'Health score calculation error: {str(e)[:100]}']
                        )
                    except Exception as inner_e:
                        logger.error(f"Failed to create default health score: {str(inner_e)}")
        
        except Exception as e:
            logger.error(f"Database error during invoice save: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to save invoice data to database',
                'details': 'Please try uploading the invoice again',
                'error_code': 'DATABASE_ERROR'
            }, status=500)
        
        # Step 8: Return success response with confidence score
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
                'critical_flags_count': len(critical_flags) if 'critical_flags' in locals() else 0,
                'confidence_score': float(confidence_score),
                'confidence_level': confidence_level
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
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    health_filter = request.GET.get('health', 'all')
    confidence_filter = request.GET.get('confidence', 'all')
    sort_by = request.GET.get('sort', 'date')
    
    # Base queryset for user's invoices with health score and duplicate link
    invoices_qs = Invoice.objects.filter(uploaded_by=request.user).select_related('health_score').prefetch_related('duplicate_link')
    
    # Apply GST verification status filter
    if status_filter == 'pending':
        invoices_qs = invoices_qs.filter(gst_verification_status='PENDING')
    elif status_filter == 'verified':
        invoices_qs = invoices_qs.filter(gst_verification_status='VERIFIED')
    elif status_filter == 'failed':
        invoices_qs = invoices_qs.filter(gst_verification_status='FAILED')
    # 'all' shows all invoices (no additional filter)
    
    # Apply health score filter
    if health_filter == 'healthy':
        invoices_qs = invoices_qs.filter(health_score__status='HEALTHY')
    elif health_filter == 'review':
        invoices_qs = invoices_qs.filter(health_score__status='REVIEW')
    elif health_filter == 'at_risk':
        invoices_qs = invoices_qs.filter(health_score__status='AT_RISK')
    # 'all' shows all invoices (no additional filter)
    
    # Apply confidence score filter
    if confidence_filter == 'high':
        invoices_qs = invoices_qs.filter(ai_confidence_score__gte=80)
    elif confidence_filter == 'medium':
        invoices_qs = invoices_qs.filter(ai_confidence_score__gte=50, ai_confidence_score__lt=80)
    elif confidence_filter == 'low':
        invoices_qs = invoices_qs.filter(ai_confidence_score__lt=50)
    # 'all' shows all invoices (no additional filter)
    
    # Apply sorting
    if sort_by == 'health_asc':
        invoices_qs = invoices_qs.order_by('health_score__overall_score', '-uploaded_at')
    elif sort_by == 'health_desc':
        invoices_qs = invoices_qs.order_by('-health_score__overall_score', '-uploaded_at')
    elif sort_by == 'confidence_asc':
        invoices_qs = invoices_qs.order_by('ai_confidence_score', '-uploaded_at')
    elif sort_by == 'confidence_desc':
        invoices_qs = invoices_qs.order_by('-ai_confidence_score', '-uploaded_at')
    else:  # default: sort by date
        invoices_qs = invoices_qs.order_by('-uploaded_at')
    
    # Pagination - 10 rows per page
    paginator = Paginator(invoices_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'current_filter': status_filter,
        'health_filter': health_filter,
        'confidence_filter': confidence_filter,
        'sort_by': sort_by,
        'total_count': invoices_qs.count(),
    }
    
    return render(request, 'gst_verification.html', context)


@login_required
@require_http_methods(["POST"])
def check_gst_cache(request):
    """
    AJAX endpoint to check if GSTIN exists in cache or if invoice is a duplicate
    """
    try:
        from .services.duplicate_linking_service import duplicate_linking_service
        
        # Parse JSON request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in cache check request: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid request format',
                'error_code': 'INVALID_JSON'
            }, status=400)
        
        invoice_id = data.get('invoice_id')
        
        # Validate required parameters
        if not invoice_id:
            return JsonResponse({
                'success': False,
                'error': 'Invoice ID is required',
                'error_code': 'MISSING_INVOICE_ID'
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
        
        # Check if this invoice is a linked duplicate
        if duplicate_linking_service.is_duplicate(invoice):
            original = duplicate_linking_service.get_original_invoice(invoice)
            if original:
                logger.info(f"Invoice {invoice.id} is a duplicate of {original.id}, "
                           f"skipping GST verification")
                
                return JsonResponse({
                    'success': True,
                    'is_duplicate': True,
                    'message': f'This is a duplicate of invoice #{original.id}. '
                              f'GST verification not required.',
                    'invoice_id': invoice.id,
                    'original_invoice_id': original.id,
                    'new_status': invoice.gst_verification_status
                })
        
        if not invoice.vendor_gstin:
            return JsonResponse({
                'success': False,
                'cached': False,
                'error': 'No GSTIN found for this invoice'
            })
        
        # Check cache
        cache_entry = gst_cache_service.lookup_gstin(invoice.vendor_gstin)
        
        if cache_entry:
            # Cache hit - automatically verify using cached data
            logger.info(f"Cache hit for GSTIN {invoice.vendor_gstin}, auto-verifying invoice {invoice.invoice_id}")
            
            try:
                invoice.gst_verification_status = 'VERIFIED'
                invoice.save()
                
                return JsonResponse({
                    'success': True,
                    'cached': True,
                    'message': 'GST verification completed using cached data',
                    'invoice_id': invoice.id,
                    'new_status': 'VERIFIED',
                    'cache_data': {
                        'legal_name': cache_entry.legal_name,
                        'trade_name': cache_entry.trade_name,
                        'status': cache_entry.status,
                        'registration_date': cache_entry.registration_date.isoformat() if cache_entry.registration_date else None,
                        'business_constitution': cache_entry.business_constitution,
                        'principal_address': cache_entry.principal_address,
                        'einvoice_status': cache_entry.einvoice_status,
                        'last_verified': cache_entry.last_verified.isoformat(),
                    }
                })
            except Exception as e:
                logger.error(f"Failed to update invoice status from cache: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to update invoice status',
                    'error_code': 'STATUS_UPDATE_ERROR'
                }, status=500)
        else:
            # Cache miss - need CAPTCHA verification
            return JsonResponse({
                'success': True,
                'cached': False,
                'message': 'GSTIN not in cache, CAPTCHA verification required'
            })
        
    except Exception as e:
        logger.error(f"Unexpected error checking GST cache: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred',
            'error_code': 'UNEXPECTED_ERROR'
        }, status=500)


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
            
            # Add to cache for future use
            try:
                cache_entry = gst_cache_service.add_to_cache(invoice.vendor_gstin, verification_response)
                if cache_entry:
                    logger.info(f"Added GSTIN {invoice.vendor_gstin} to cache")
                else:
                    logger.warning(f"Failed to add GSTIN {invoice.vendor_gstin} to cache")
            except Exception as e:
                logger.error(f"Error adding GSTIN to cache: {str(e)}")
                # Don't fail the verification if caching fails
            
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


@login_required
def invoice_detail(request, invoice_id):
    """
    Invoice detail page showing comprehensive information including health score and duplicate relationships
    """
    from .services.duplicate_linking_service import duplicate_linking_service
    
    # Get invoice with related data
    invoice = get_object_or_404(
        Invoice.objects.select_related('health_score').prefetch_related('line_items', 'compliance_flags'),
        id=invoice_id,
        uploaded_by=request.user
    )
    
    # Get health score breakdown if available
    health_score_data = None
    if hasattr(invoice, 'health_score'):
        health_score_data = {
            'overall_score': invoice.health_score.overall_score,
            'status': invoice.health_score.status,
            'breakdown': {
                'data_completeness': invoice.health_score.data_completeness_score,
                'verification': invoice.health_score.verification_score,
                'compliance': invoice.health_score.compliance_score,
                'fraud_detection': invoice.health_score.fraud_detection_score,
                'ai_confidence': invoice.health_score.ai_confidence_score_component,
            },
            'key_flags': invoice.health_score.key_flags,
            'calculated_at': invoice.health_score.calculated_at,
        }
    
    # Check duplicate relationships
    is_duplicate = duplicate_linking_service.is_duplicate(invoice)
    original_invoice = None
    duplicate_invoices = []
    
    if is_duplicate:
        # This invoice is a duplicate - get the original
        original_invoice = duplicate_linking_service.get_original_invoice(invoice)
    else:
        # This might be an original - get all duplicates
        duplicate_invoices = duplicate_linking_service.get_all_duplicates(invoice)
    
    context = {
        'invoice': invoice,
        'health_score_data': health_score_data,
        'is_duplicate': is_duplicate,
        'original_invoice': original_invoice,
        'duplicate_invoices': duplicate_invoices,
    }
    
    return render(request, 'invoice_detail.html', context)


@login_required
def gst_cache_management(request):
    """
    GST Cache management page with search, filter, and refresh functionality
    """
    # Get filter parameters
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    sort_by = request.GET.get('sort', 'recent')
    
    # Get cache entries using the service
    cache_entries = gst_cache_service.get_all_entries(
        search_query=search_query if search_query else None,
        status_filter=status_filter if status_filter else None
    )
    
    # Apply sorting
    if sort_by == 'gstin':
        cache_entries = cache_entries.order_by('gstin')
    elif sort_by == 'name':
        cache_entries = cache_entries.order_by('legal_name')
    elif sort_by == 'oldest':
        cache_entries = cache_entries.order_by('last_verified')
    else:  # default: recent
        cache_entries = cache_entries.order_by('-last_verified')
    
    # Pagination - 25 rows per page
    paginator = Paginator(cache_entries, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'total_count': cache_entries.count(),
    }
    
    return render(request, 'gst_cache.html', context)


@login_required
@require_http_methods(["POST"])
def refresh_gst_cache_entry(request):
    """
    AJAX endpoint to refresh a specific GST cache entry
    """
    try:
        # Parse JSON request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in refresh cache request: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid request format',
                'error_code': 'INVALID_JSON'
            }, status=400)
        
        gstin = data.get('gstin')
        session_id = data.get('session_id')
        captcha = data.get('captcha')
        
        # Validate required parameters
        if not gstin:
            return JsonResponse({
                'success': False,
                'error': 'GSTIN is required',
                'error_code': 'MISSING_GSTIN'
            }, status=400)
        
        if not session_id or not captcha:
            return JsonResponse({
                'success': False,
                'error': 'Session ID and CAPTCHA are required',
                'error_code': 'MISSING_CAPTCHA_DATA'
            }, status=400)
        
        # Refresh cache entry
        result = gst_cache_service.refresh_cache_entry(gstin, session_id, captcha)
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'message': 'Cache entry refreshed successfully',
                'data': result['data']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Failed to refresh cache entry')
            }, status=400)
        
    except Exception as e:
        logger.error(f"Unexpected error refreshing cache entry: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred',
            'error_code': 'UNEXPECTED_ERROR'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def bulk_upload_invoices(request):
    """
    Handle bulk invoice upload with multiple files
    """
    from .services.bulk_upload_handler import bulk_upload_handler
    
    try:
        # Get uploaded files
        files = request.FILES.getlist('invoice_files')
        
        if not files:
            return JsonResponse({
                'success': False,
                'error': 'No files uploaded',
                'error_code': 'NO_FILES'
            }, status=400)
        
        # Validate file count (max 50 files per batch)
        if len(files) > 50:
            return JsonResponse({
                'success': False,
                'error': 'Maximum 50 files allowed per batch',
                'error_code': 'TOO_MANY_FILES'
            }, status=400)
        
        # Validate each file
        for file in files:
            # Check file size (max 10MB per file)
            if file.size > 10 * 1024 * 1024:
                return JsonResponse({
                    'success': False,
                    'error': f'File {file.name} exceeds 10MB limit',
                    'error_code': 'FILE_TOO_LARGE'
                }, status=400)
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf']
            if file.content_type not in allowed_types:
                return JsonResponse({
                    'success': False,
                    'error': f'File {file.name} has invalid type. Only JPG, PNG, and PDF allowed.',
                    'error_code': 'INVALID_FILE_TYPE'
                }, status=400)
        
        logger.info(f"Processing bulk upload of {len(files)} files for user {request.user.username}")
        
        # Handle bulk upload
        result = bulk_upload_handler.handle_bulk_upload(request.user, files)
        
        if result['success']:
            return JsonResponse(result)
        else:
            return JsonResponse(result, status=400)
        
    except Exception as e:
        logger.error(f"Unexpected error in bulk upload: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred during bulk upload',
            'error_code': 'UNEXPECTED_ERROR'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_batch_status(request, batch_id):
    """
    AJAX endpoint to get batch processing status
    """
    from .services.bulk_upload_handler import bulk_upload_handler
    
    try:
        result = bulk_upload_handler.get_batch_status(batch_id, request.user)
        
        if result['success']:
            return JsonResponse(result)
        else:
            return JsonResponse(result, status=404 if result.get('error_code') == 'BATCH_NOT_FOUND' else 400)
        
    except Exception as e:
        logger.error(f"Unexpected error getting batch status: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred',
            'error_code': 'UNEXPECTED_ERROR'
        }, status=500)


@login_required
def manual_entry(request, invoice_id):
    """
    Manual entry page for invoices where AI extraction failed
    """
    from .forms import ManualInvoiceEntryForm
    
    # Get invoice and verify ownership
    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        uploaded_by=request.user
    )
    
    # Check if this invoice requires manual entry
    if invoice.extraction_method != 'MANUAL':
        messages.warning(request, 'This invoice does not require manual entry.')
        return redirect('invoice_detail', invoice_id=invoice.id)
    
    # If GET request, show the form
    if request.method == 'GET':
        # Pre-populate form with any existing data
        initial_data = {}
        if invoice.invoice_id:
            initial_data['invoice_id'] = invoice.invoice_id
        if invoice.invoice_date:
            initial_data['invoice_date'] = invoice.invoice_date
        if invoice.vendor_name:
            initial_data['vendor_name'] = invoice.vendor_name
        if invoice.vendor_gstin:
            initial_data['vendor_gstin'] = invoice.vendor_gstin
        if invoice.billed_company_gstin:
            initial_data['billed_company_gstin'] = invoice.billed_company_gstin
        if invoice.grand_total:
            initial_data['grand_total'] = invoice.grand_total
        
        form = ManualInvoiceEntryForm(initial=initial_data)
        
        context = {
            'invoice': invoice,
            'form': form,
            'failure_reason': invoice.extraction_failure_reason or 'AI extraction failed',
        }
        
        return render(request, 'manual_entry.html', context)
    
    # POST request handled in separate view
    return redirect('manual_entry', invoice_id=invoice.id)


@login_required
@require_http_methods(["POST"])
def submit_manual_entry(request, invoice_id):
    """
    Handle manual entry form submission
    """
    from .forms import ManualInvoiceEntryForm
    
    # Get invoice and verify ownership
    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        uploaded_by=request.user
    )
    
    # Check if this invoice requires manual entry
    if invoice.extraction_method != 'MANUAL':
        messages.error(request, 'This invoice does not require manual entry.')
        return redirect('invoice_detail', invoice_id=invoice.id)
    
    # Parse form data
    form = ManualInvoiceEntryForm(request.POST)
    
    if not form.is_valid():
        # Re-render form with errors
        context = {
            'invoice': invoice,
            'form': form,
            'failure_reason': invoice.extraction_failure_reason or 'AI extraction failed',
        }
        return render(request, 'manual_entry.html', context)
    
    # Extract line items from POST data
    line_items = []
    line_item_index = 1
    
    while True:
        description = request.POST.get(f'line_items[{line_item_index}][description]')
        if not description:
            break
        
        try:
            line_item = {
                'description': description.strip(),
                'hsn_sac_code': request.POST.get(f'line_items[{line_item_index}][hsn_sac_code]', '').strip(),
                'quantity': request.POST.get(f'line_items[{line_item_index}][quantity]'),
                'unit_price': request.POST.get(f'line_items[{line_item_index}][unit_price]'),
                'billed_gst_rate': request.POST.get(f'line_items[{line_item_index}][billed_gst_rate]'),
                'line_total': request.POST.get(f'line_items[{line_item_index}][line_total]'),
            }
            line_items.append(line_item)
        except Exception as e:
            logger.error(f"Error parsing line item {line_item_index}: {str(e)}")
        
        line_item_index += 1
    
    # Prepare data for validation
    manual_data = {
        'invoice_id': form.cleaned_data['invoice_id'],
        'invoice_date': form.cleaned_data['invoice_date'].isoformat() if form.cleaned_data['invoice_date'] else None,
        'vendor_name': form.cleaned_data['vendor_name'],
        'vendor_gstin': form.cleaned_data.get('vendor_gstin', ''),
        'billed_company_gstin': form.cleaned_data.get('billed_company_gstin', ''),
        'grand_total': str(form.cleaned_data['grand_total']),
        'line_items': line_items
    }
    
    # Validate using ManualEntryService
    is_valid, validation_errors = manual_entry_service.validate_manual_entry(manual_data)
    
    if not is_valid:
        # Add validation errors to messages
        for error in validation_errors:
            messages.error(request, error)
        
        # Re-render form
        context = {
            'invoice': invoice,
            'form': form,
            'failure_reason': invoice.extraction_failure_reason or 'AI extraction failed',
        }
        return render(request, 'manual_entry.html', context)
    
    # Save invoice and line items in a transaction
    try:
        with transaction.atomic():
            # Update invoice with manual data
            invoice.invoice_id = manual_data['invoice_id']
            invoice.invoice_date = form.cleaned_data['invoice_date']
            invoice.vendor_name = manual_data['vendor_name']
            invoice.vendor_gstin = manual_data['vendor_gstin']
            invoice.billed_company_gstin = manual_data['billed_company_gstin']
            invoice.grand_total = Decimal(manual_data['grand_total'])
            invoice.status = 'PENDING_ANALYSIS'
            invoice.save()
            
            # Delete any existing line items (in case of re-submission)
            invoice.line_items.all().delete()
            
            # Create line items
            for item_data in line_items:
                LineItem.objects.create(
                    invoice=invoice,
                    description=item_data['description'],
                    normalized_key=normalize_product_key(item_data['description']),
                    hsn_sac_code=item_data['hsn_sac_code'],
                    quantity=Decimal(str(item_data['quantity'])),
                    unit_price=Decimal(str(item_data['unit_price'])),
                    billed_gst_rate=Decimal(str(item_data['billed_gst_rate'])),
                    line_total=Decimal(str(item_data['line_total']))
                )
            
            logger.info(f"Manual entry completed for invoice {invoice.id}")
            
            # Run compliance checks
            try:
                # Prepare extracted_data format for compliance checks
                extracted_data = {
                    'invoice_id': manual_data['invoice_id'],
                    'invoice_date': manual_data['invoice_date'],
                    'vendor_name': manual_data['vendor_name'],
                    'vendor_gstin': manual_data['vendor_gstin'],
                    'billed_company_gstin': manual_data['billed_company_gstin'],
                    'grand_total': manual_data['grand_total'],
                    'line_items': line_items
                }
                
                compliance_flags = run_all_checks(extracted_data, invoice)
                
                # Save compliance flags
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
                
                logger.info(f"Compliance checks completed for manually entered invoice {invoice.id}")
                
            except Exception as e:
                logger.error(f"Error during compliance checks for manual entry: {str(e)}")
                # Create a system error flag
                ComplianceFlag.objects.create(
                    invoice=invoice,
                    flag_type='SYSTEM_ERROR',
                    severity='WARNING',
                    description=f'Error during compliance analysis: {str(e)[:200]}'
                )
                invoice.status = 'HAS_ANOMALIES'
                invoice.save()
            
            # Calculate health score
            try:
                health_engine = InvoiceHealthScoreEngine()
                health_result = health_engine.calculate_health_score(invoice)
                
                # Store health score in database
                InvoiceHealthScore.objects.create(
                    invoice=invoice,
                    overall_score=Decimal(str(health_result['score'])),
                    status=health_result['status'],
                    data_completeness_score=Decimal(str(health_result['breakdown']['data_completeness'])),
                    verification_score=Decimal(str(health_result['breakdown']['verification'])),
                    compliance_score=Decimal(str(health_result['breakdown']['compliance'])),
                    fraud_detection_score=Decimal(str(health_result['breakdown']['fraud_detection'])),
                    ai_confidence_score_component=Decimal(str(health_result['breakdown']['ai_confidence'])),
                    key_flags=health_result['key_flags']
                )
                
                logger.info(f"Health score calculated for manually entered invoice {invoice.id}")
                
            except Exception as e:
                logger.error(f"Error calculating health score for manual entry: {str(e)}")
                # Create default health score
                try:
                    InvoiceHealthScore.objects.create(
                        invoice=invoice,
                        overall_score=Decimal('0.0'),
                        status='AT_RISK',
                        data_completeness_score=Decimal('0.0'),
                        verification_score=Decimal('0.0'),
                        compliance_score=Decimal('0.0'),
                        fraud_detection_score=Decimal('0.0'),
                        ai_confidence_score_component=Decimal('0.0'),
                        key_flags=[f'Health score calculation error: {str(e)[:100]}']
                    )
                except Exception as inner_e:
                    logger.error(f"Failed to create default health score: {str(inner_e)}")
            
            messages.success(request, 'Invoice data submitted successfully! The invoice has been processed.')
            return redirect('invoice_detail', invoice_id=invoice.id)
            
    except Exception as e:
        logger.error(f"Error saving manual entry data: {str(e)}", exc_info=True)
        messages.error(request, f'Failed to save invoice data: {str(e)}')
        
        # Re-render form
        context = {
            'invoice': invoice,
            'form': form,
            'failure_reason': invoice.extraction_failure_reason or 'AI extraction failed',
        }
        return render(request, 'manual_entry.html', context)


@login_required
@require_http_methods(["GET"])
def dashboard_analytics_api(request):
    """
    AJAX endpoint to get real-time dashboard analytics data
    
    Returns JSON with updated metrics and chart data
    Requirements: 7.5
    """
    try:
        # Get date range filter parameter
        days_filter = int(request.GET.get('days', 7))
        days_filter = max(5, min(14, days_filter))
        
        # Get analytics data
        invoice_per_day_data = dashboard_analytics_service.get_invoice_per_day_data(
            request.user, 
            days=days_filter
        )
        
        money_flow_data = dashboard_analytics_service.get_money_flow_by_hsn(request.user)
        company_leaderboard = dashboard_analytics_service.get_company_leaderboard(request.user)
        red_flag_list = dashboard_analytics_service.get_red_flag_list(request.user)
        
        # Calculate key metrics
        invoices_awaiting_verification = Invoice.objects.filter(
            uploaded_by=request.user,
            gst_verification_status='PENDING'
        ).count()
        
        one_week_ago = timezone.now() - timedelta(days=7)
        anomalies_this_week = ComplianceFlag.objects.filter(
            invoice__uploaded_by=request.user,
            created_at__gte=one_week_ago
        ).count()
        
        total_amount = Invoice.objects.filter(
            uploaded_by=request.user
        ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0')
        
        return JsonResponse({
            'success': True,
            'metrics': {
                'invoices_awaiting_verification': invoices_awaiting_verification,
                'anomalies_this_week': anomalies_this_week,
                'total_amount_processed': float(total_amount),
            },
            'invoice_per_day_data': invoice_per_day_data,
            'money_flow_data': money_flow_data,
            'company_leaderboard': company_leaderboard,
            'red_flag_list': red_flag_list,
        })
        
    except Exception as e:
        logger.error(f"Error fetching dashboard analytics: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to fetch analytics data'
        }, status=500)


@login_required
def user_profile(request):
    """
    User profile page for viewing and editing profile information
    Requirements: 9.1, 9.2, 9.3, 9.4
    """
    from .forms import UserProfileForm
    from .services.user_profile_service import user_profile_service
    
    # Get or create user profile
    profile = user_profile_service.get_or_create_profile(request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES)
        
        if form.is_valid():
            # Update user basic info
            success, error = user_profile_service.update_user_info(
                request.user,
                first_name=form.cleaned_data.get('first_name'),
                last_name=form.cleaned_data.get('last_name'),
                email=form.cleaned_data.get('email')
            )
            
            if not success:
                messages.error(request, error)
                return render(request, 'profile.html', {'form': form})
            
            # Update profile fields
            success, error = user_profile_service.update_profile(
                request.user,
                phone_number=form.cleaned_data.get('phone_number'),
                company_name=form.cleaned_data.get('company_name')
            )
            
            if not success:
                messages.error(request, error)
                return render(request, 'profile.html', {'form': form})
            
            # Handle profile picture upload if provided
            if 'profile_picture' in request.FILES:
                profile_picture = request.FILES['profile_picture']
                success, error = user_profile_service.upload_profile_picture(
                    request.user,
                    profile_picture
                )
                
                if not success:
                    messages.error(request, error)
                    return render(request, 'profile.html', {'form': form})
            
            messages.success(request, 'Profile updated successfully!')
            return redirect('user_profile')
        else:
            # Form has validation errors
            messages.error(request, 'Please correct the errors below.')
    else:
        # GET request - populate form with current data
        initial_data = {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'username': request.user.username,
            'phone_number': profile.phone_number,
            'company_name': profile.company_name,
        }
        form = UserProfileForm(initial=initial_data)
    
    context = {
        'form': form,
    }
    
    return render(request, 'profile.html', context)


@login_required
@require_http_methods(["POST"])
def delete_profile_picture(request):
    """
    AJAX endpoint to delete user's profile picture
    Requirements: 9.4
    """
    from .services.user_profile_service import user_profile_service
    
    try:
        success, error = user_profile_service.delete_profile_picture(request.user)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Profile picture deleted successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': error or 'Failed to delete profile picture'
            }, status=400)
            
    except Exception as e:
        logger.error(f"Unexpected error deleting profile picture: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred'
        }, status=500)


@login_required
def settings(request):
    """
    Comprehensive settings page for managing account, preferences, and connected services
    Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
    """
    from .services.user_profile_service import user_profile_service
    
    # Get or create user profile
    profile = user_profile_service.get_or_create_profile(request.user)
    
    if request.method == 'POST':
        try:
            # Update user basic info
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            
            # Validate username uniqueness (if changed)
            if username != request.user.username:
                from django.contrib.auth.models import User
                if User.objects.filter(username=username).exclude(id=request.user.id).exists():
                    messages.error(request, 'Username already taken. Please choose a different username.')
                    return redirect('settings')
            
            # Validate email uniqueness (if changed)
            if email != request.user.email:
                from django.contrib.auth.models import User
                if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                    messages.error(request, 'Email already in use. Please use a different email.')
                    return redirect('settings')
            
            # Update user info
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.username = username
            request.user.email = email
            request.user.save()
            
            # Handle profile picture upload if provided
            if 'profile_picture' in request.FILES:
                profile_picture = request.FILES['profile_picture']
                
                # Validate file size (1MB max)
                if profile_picture.size > 1048576:  # 1MB in bytes
                    messages.error(request, 'Profile picture must be less than 1 MB.')
                    return redirect('settings')
                
                success, error = user_profile_service.upload_profile_picture(
                    request.user,
                    profile_picture
                )
                
                if not success:
                    messages.error(request, error)
                    return redirect('settings')
            
            # Update connected services (placeholder for future OAuth integration)
            profile.facebook_connected = 'facebook_connected' in request.POST
            profile.google_connected = 'google_connected' in request.POST
            
            # Update preferences
            profile.enable_sound_effects = 'enable_sound_effects' in request.POST
            profile.enable_animations = 'enable_animations' in request.POST
            profile.enable_notifications = 'enable_notifications' in request.POST
            
            profile.save()
            
            messages.success(request, 'Settings updated successfully!')
            return redirect('settings')
            
        except Exception as e:
            logger.error(f"Error updating settings: {str(e)}")
            messages.error(request, 'An error occurred while updating settings. Please try again.')
            return redirect('settings')
    
    # GET request - render settings page
    return render(request, 'settings.html')


@login_required
@require_http_methods(["GET"])
def export_invoices(request):
    """
    Export invoices to CSV with applied filters
    Requirements: 11.1, 11.3, 11.4, 11.5
    """
    from .services.data_export_service import data_export_service
    
    try:
        # Get filter parameters (same as gst_verification view)
        status_filter = request.GET.get('status', 'all')
        health_filter = request.GET.get('health', 'all')
        confidence_filter = request.GET.get('confidence', 'all')
        sort_by = request.GET.get('sort', 'date')
        
        # Base queryset for user's invoices
        invoices_qs = Invoice.objects.filter(uploaded_by=request.user).select_related('health_score')
        
        # Apply GST verification status filter
        if status_filter == 'pending':
            invoices_qs = invoices_qs.filter(gst_verification_status='PENDING')
        elif status_filter == 'verified':
            invoices_qs = invoices_qs.filter(gst_verification_status='VERIFIED')
        elif status_filter == 'failed':
            invoices_qs = invoices_qs.filter(gst_verification_status='FAILED')
        
        # Apply health score filter
        if health_filter == 'healthy':
            invoices_qs = invoices_qs.filter(health_score__status='HEALTHY')
        elif health_filter == 'review':
            invoices_qs = invoices_qs.filter(health_score__status='REVIEW')
        elif health_filter == 'at_risk':
            invoices_qs = invoices_qs.filter(health_score__status='AT_RISK')
        
        # Apply confidence score filter
        if confidence_filter == 'high':
            invoices_qs = invoices_qs.filter(ai_confidence_score__gte=80)
        elif confidence_filter == 'medium':
            invoices_qs = invoices_qs.filter(ai_confidence_score__gte=50, ai_confidence_score__lt=80)
        elif confidence_filter == 'low':
            invoices_qs = invoices_qs.filter(ai_confidence_score__lt=50)
        
        # Apply sorting
        if sort_by == 'health_asc':
            invoices_qs = invoices_qs.order_by('health_score__overall_score', '-uploaded_at')
        elif sort_by == 'health_desc':
            invoices_qs = invoices_qs.order_by('-health_score__overall_score', '-uploaded_at')
        elif sort_by == 'confidence_asc':
            invoices_qs = invoices_qs.order_by('ai_confidence_score', '-uploaded_at')
        elif sort_by == 'confidence_desc':
            invoices_qs = invoices_qs.order_by('-ai_confidence_score', '-uploaded_at')
        else:  # default: sort by date
            invoices_qs = invoices_qs.order_by('-uploaded_at')
        
        logger.info(f"Exporting {invoices_qs.count()} invoices for user {request.user.username}")
        
        # Export to CSV
        return data_export_service.export_invoices_to_csv(invoices_qs)
        
    except Exception as e:
        logger.error(f"Error exporting invoices: {str(e)}", exc_info=True)
        messages.error(request, 'Failed to export invoices. Please try again.')
        return redirect('gst_verification')


@login_required
@require_http_methods(["GET"])
def export_gst_cache(request):
    """
    Export GST cache entries to CSV
    Requirements: 11.2, 11.3, 11.4, 11.5
    """
    from .services.data_export_service import data_export_service
    
    try:
        logger.info(f"Exporting GST cache for user {request.user.username}")
        
        # Export to CSV
        return data_export_service.export_gst_cache_to_csv()
        
    except Exception as e:
        logger.error(f"Error exporting GST cache: {str(e)}", exc_info=True)
        messages.error(request, 'Failed to export GST cache. Please try again.')
        return redirect('gst_cache')


@login_required
@require_http_methods(["GET"])
def export_my_data(request):
    """
    Export all user data (invoices, profile, preferences) to CSV
    Requirements: 10.5
    """
    from .services.data_export_service import data_export_service
    
    try:
        logger.info(f"Exporting all data for user {request.user.username}")
        
        # Export to CSV
        return data_export_service.export_user_data(request.user)
        
    except Exception as e:
        logger.error(f"Error exporting user data: {str(e)}", exc_info=True)
        messages.error(request, 'Failed to export your data. Please try again.')
        return redirect('settings')


@login_required
@require_http_methods(["POST"])
def delete_account(request):
    """
    Handle account deletion with confirmation
    Requirements: 10.6
    
    Implements soft delete by deactivating the account and clearing sensitive data.
    User data is retained for audit purposes but the account becomes inaccessible.
    """
    from django.contrib.auth import logout
    
    try:
        # Get confirmation parameter
        confirmation = request.POST.get('confirmation', '').strip().lower()
        
        # Validate confirmation text
        if confirmation != 'delete my account':
            messages.error(request, 'Please type "delete my account" to confirm account deletion.')
            return redirect('settings')
        
        user = request.user
        username = user.username
        
        logger.info(f"Processing account deletion request for user: {username}")
        
        # Perform account deletion in a transaction
        with transaction.atomic():
            # Soft delete: Deactivate the account
            user.is_active = False
            
            # Clear sensitive personal information
            user.email = f"deleted_{user.id}@deleted.local"
            user.first_name = ""
            user.last_name = ""
            
            # Generate a random unusable username to prevent reuse
            import uuid
            user.username = f"deleted_{uuid.uuid4().hex[:20]}"
            
            # Set an unusable password
            user.set_unusable_password()
            
            user.save()
            
            # Clear profile data if exists
            if hasattr(user, 'profile'):
                profile = user.profile
                
                # Delete profile picture file if exists
                if profile.profile_picture:
                    try:
                        profile.profile_picture.delete(save=False)
                    except Exception as e:
                        logger.warning(f"Failed to delete profile picture file: {str(e)}")
                
                # Clear profile fields
                profile.profile_picture = None
                profile.phone_number = None
                profile.company_name = None
                profile.facebook_connected = False
                profile.google_connected = False
                profile.save()
            
            # Note: Invoice data is retained for audit and compliance purposes
            # but is no longer accessible since the user account is deactivated
            
            logger.info(f"Account successfully deleted for user: {username} (ID: {user.id})")
        
        # Log out the user
        logout(request)
        
        # Redirect to a confirmation page or login with a message
        messages.success(request, 'Your account has been successfully deleted. We\'re sorry to see you go.')
        return redirect('login')
        
    except Exception as e:
        logger.error(f"Error deleting account for user {request.user.username}: {str(e)}", exc_info=True)
        messages.error(request, 'An error occurred while deleting your account. Please try again or contact support.')
        return redirect('settings')


@login_required
def coming_soon(request):
    """
    Coming Soon page for features under development
    Requirements: 13.1, 13.2, 13.3, 13.5
    """
    from .models import FeatureNotificationSignup
    
    # Get feature name from query parameter (optional)
    feature_name = request.GET.get('feature', 'This feature')
    
    # Define feature descriptions
    feature_descriptions = {
        'reports': 'Advanced reporting and analytics with custom date ranges, filters, and export options. Generate comprehensive reports on invoice trends, vendor analysis, and compliance metrics.',
        'default': 'We\'re working hard to bring you this exciting new feature. Stay tuned for updates!'
    }
    
    # Get description based on feature name
    feature_key = feature_name.lower() if feature_name.lower() in feature_descriptions else 'default'
    description = feature_descriptions.get(feature_key, feature_descriptions['default'])
    
    # Handle email signup for notifications
    signup_success = False
    signup_error = None
    
    if request.method == 'POST':
        email = request.POST.get('notification_email', '').strip()
        
        if email:
            try:
                # Validate email format
                from django.core.validators import validate_email
                from django.core.exceptions import ValidationError
                
                try:
                    validate_email(email)
                except ValidationError:
                    signup_error = 'Please enter a valid email address.'
                else:
                    # Check if already signed up
                    existing_signup = FeatureNotificationSignup.objects.filter(
                        email=email,
                        feature_name=feature_name
                    ).first()
                    
                    if existing_signup:
                        signup_error = 'You\'re already signed up for notifications about this feature!'
                    else:
                        # Create signup record
                        FeatureNotificationSignup.objects.create(
                            email=email,
                            feature_name=feature_name,
                            user=request.user
                        )
                        signup_success = True
                        logger.info(f"User {request.user.username} signed up for {feature_name} notifications")
                        
            except Exception as e:
                logger.error(f"Error processing feature notification signup: {str(e)}")
                signup_error = 'An error occurred. Please try again.'
        else:
            signup_error = 'Please enter your email address.'
    
    context = {
        'feature_name': feature_name,
        'description': description,
        'signup_success': signup_success,
        'signup_error': signup_error,
    }
    
    return render(request, 'coming_soon.html', context)
