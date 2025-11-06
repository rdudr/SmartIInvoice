from django.db import models
from django.contrib.auth.models import User


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
