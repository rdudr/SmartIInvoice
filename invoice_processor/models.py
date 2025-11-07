from django.db import models
from django.contrib.auth.models import User
import uuid


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('PENDING_ANALYSIS', 'Pending Analysis'),
        ('CLEARED', 'Cleared'),
        ('HAS_ANOMALIES', 'Has Anomalies'),
    ]
    
    GST_VERIFICATION_CHOICES = [
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('FAILED', 'Failed'),
    ]
    
    EXTRACTION_METHOD_CHOICES = [
        ('AI', 'AI Extracted'),
        ('MANUAL', 'Manual Entry'),
    ]
    
    invoice_id = models.CharField(max_length=100, db_index=True)  # Extracted invoice number
    invoice_date = models.DateField()  # Invoice date
    vendor_name = models.CharField(max_length=255)  # Vendor name
    vendor_gstin = models.CharField(max_length=15, db_index=True)  # Vendor GST number
    billed_company_gstin = models.CharField(max_length=15)  # Buyer GST number
    grand_total = models.DecimalField(max_digits=12, decimal_places=2)  # Total invoice amount
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_ANALYSIS', db_index=True)  # Processing status
    gst_verification_status = models.CharField(max_length=20, choices=GST_VERIFICATION_CHOICES, default='PENDING', db_index=True)  # GST verification status
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)  # User who uploaded
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)  # Upload timestamp
    file_path = models.FileField(upload_to='invoices/')  # Stored invoice file
    
    # Phase 2 fields
    extraction_method = models.CharField(max_length=20, choices=EXTRACTION_METHOD_CHOICES, default='AI')  # How data was extracted
    extraction_failure_reason = models.TextField(null=True, blank=True)  # Why AI extraction failed
    ai_confidence_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # AI confidence (0.00 to 100.00)
    batch = models.ForeignKey('InvoiceBatch', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')  # Batch this invoice belongs to
    
    class Meta:
        indexes = [
            models.Index(fields=['vendor_gstin', 'invoice_id']),  # For duplicate detection
            models.Index(fields=['uploaded_at']),  # For recent activity queries
            models.Index(fields=['status']),  # For dashboard metrics
        ]
        
    def __str__(self):
        return f"Invoice {self.invoice_id} - {self.vendor_name}"


class LineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')  # Parent invoice
    description = models.CharField(max_length=500)  # Item description
    normalized_key = models.CharField(max_length=255, db_index=True)  # Normalized product key for price comparison
    hsn_sac_code = models.CharField(max_length=20, db_index=True)  # HSN/SAC code
    quantity = models.DecimalField(max_digits=10, decimal_places=2)  # Quantity
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)  # Price per unit
    billed_gst_rate = models.DecimalField(max_digits=5, decimal_places=2)  # GST rate on invoice
    line_total = models.DecimalField(max_digits=12, decimal_places=2)  # Total for this line
    created_at = models.DateTimeField(auto_now_add=True)  # When line item was created (for price trend analysis)
    
    class Meta:
        indexes = [
            models.Index(fields=['normalized_key']),  # For price anomaly detection
            models.Index(fields=['hsn_sac_code']),  # For HSN rate validation
        ]
        
    def __str__(self):
        return f"{self.description} - {self.invoice.invoice_id}"


class ComplianceFlag(models.Model):
    FLAG_TYPE_CHOICES = [
        ('DUPLICATE', 'Duplicate'),
        ('ARITHMETIC_ERROR', 'Arithmetic Error'),
        ('HSN_MISMATCH', 'HSN Rate Mismatch'),
        ('UNKNOWN_HSN', 'Unknown HSN/SAC Code'),
        ('PRICE_ANOMALY', 'Price Anomaly'),
        ('SYSTEM_ERROR', 'System Error'),
    ]
    
    SEVERITY_CHOICES = [
        ('CRITICAL', 'Critical'),
        ('WARNING', 'Warning'),
        ('INFO', 'Info'),
    ]
    
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='compliance_flags')  # Parent invoice
    line_item = models.ForeignKey(LineItem, on_delete=models.CASCADE, null=True, blank=True)  # Optional line item reference
    flag_type = models.CharField(max_length=50, choices=FLAG_TYPE_CHOICES, db_index=True)  # Type of compliance issue
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, db_index=True)  # Severity level
    description = models.TextField()  # Human-readable description
    created_at = models.DateTimeField(auto_now_add=True)  # When flag was created
    
    class Meta:
        indexes = [
            models.Index(fields=['flag_type', 'severity']),  # For dashboard analytics
            models.Index(fields=['created_at']),  # For recent flags queries
        ]
        
    def __str__(self):
        return f"{self.flag_type} - {self.invoice.invoice_id}"



# Phase 2 Models

class InvoiceBatch(models.Model):
    """Track bulk upload batches for asynchronous processing"""
    STATUS_CHOICES = [
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('PARTIAL_FAILURE', 'Partial Failure'),
    ]
    
    batch_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoice_batches')
    total_files = models.IntegerField()
    processed_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROCESSING')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['status']),
        ]
        verbose_name_plural = 'Invoice Batches'
    
    def __str__(self):
        return f"Batch {self.batch_id} - {self.status}"


class InvoiceDuplicateLink(models.Model):
    """Link duplicate invoices to their originals"""
    duplicate_invoice = models.OneToOneField(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='duplicate_link',
        primary_key=True
    )
    original_invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='duplicates'
    )
    detected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['original_invoice']),
        ]
    
    def __str__(self):
        return f"Duplicate: {self.duplicate_invoice.invoice_id} -> Original: {self.original_invoice.invoice_id}"


class GSTCacheEntry(models.Model):
    """Cache verified GST numbers to bypass CAPTCHA for known vendors"""
    gstin = models.CharField(max_length=15, unique=True, primary_key=True)
    legal_name = models.CharField(max_length=255)  # lgnm
    trade_name = models.CharField(max_length=255, null=True, blank=True)  # tradeNam
    status = models.CharField(max_length=50)  # sts (Active/Inactive)
    registration_date = models.DateField(null=True, blank=True)  # rgdt
    business_constitution = models.CharField(max_length=100, null=True, blank=True)  # ctb
    principal_address = models.TextField(null=True, blank=True)  # pradr.adr
    einvoice_status = models.CharField(max_length=50, null=True, blank=True)  # einvoiceStatus
    last_verified = models.DateTimeField(auto_now=True)
    verification_count = models.IntegerField(default=1)
    
    class Meta:
        indexes = [
            models.Index(fields=['legal_name']),
            models.Index(fields=['status']),
        ]
        verbose_name = 'GST Cache Entry'
        verbose_name_plural = 'GST Cache Entries'
    
    def __str__(self):
        return f"{self.gstin} - {self.legal_name}"


class InvoiceHealthScore(models.Model):
    """Store calculated health scores for invoices"""
    STATUS_CHOICES = [
        ('HEALTHY', 'Healthy (8.0-10.0)'),
        ('REVIEW', 'Review (5.0-7.9)'),
        ('AT_RISK', 'At Risk (0.0-4.9)'),
    ]
    
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name='health_score', primary_key=True)
    overall_score = models.DecimalField(max_digits=3, decimal_places=1)  # 0.0 to 10.0
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    # Category scores (weighted components)
    data_completeness_score = models.DecimalField(max_digits=4, decimal_places=2)  # 0.00 to 100.00
    verification_score = models.DecimalField(max_digits=4, decimal_places=2)  # 0.00 to 100.00
    compliance_score = models.DecimalField(max_digits=4, decimal_places=2)  # 0.00 to 100.00
    fraud_detection_score = models.DecimalField(max_digits=4, decimal_places=2)  # 0.00 to 100.00
    ai_confidence_score_component = models.DecimalField(max_digits=4, decimal_places=2)  # 0.00 to 100.00
    
    key_flags = models.JSONField(default=list)  # List of issue descriptions
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['overall_score']),
        ]
    
    def __str__(self):
        return f"{self.invoice.invoice_id} - Score: {self.overall_score} ({self.status})"


class UserProfile(models.Model):
    """Extended user information and preferences"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', primary_key=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    
    # Social connections
    facebook_connected = models.BooleanField(default=False)
    google_connected = models.BooleanField(default=False)
    
    # Preferences
    enable_sound_effects = models.BooleanField(default=True)
    enable_animations = models.BooleanField(default=True)
    enable_notifications = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile: {self.user.username}"


class APIKeyUsage(models.Model):
    """Track API key usage and status for automatic failover"""
    key_hash = models.CharField(max_length=64, unique=True)  # SHA256 hash for security
    is_active = models.BooleanField(default=True)
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    exhausted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['is_active']),
        ]
        verbose_name = 'API Key Usage'
        verbose_name_plural = 'API Key Usage Records'
    
    def __str__(self):
        status = "Active" if self.is_active else "Exhausted"
        return f"API Key {self.key_hash[:8]}... - {status}"
