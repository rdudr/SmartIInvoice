# Design Document: Smart iInvoice Phase 2 Enhancements

## Overview

Phase 2 transforms Smart iInvoice from a functional invoice processor into an intelligent business analytics platform. This design builds upon the MVP foundation by introducing asynchronous processing, advanced automation, sophisticated risk scoring, and a comprehensive user experience. The enhancements focus on efficiency (bulk processing), intelligence (automated caching and scoring), insights (analytical dashboard), and user empowerment (profile management, data export).

### Key Design Principles

1. **Non-Breaking Evolution**: All Phase 2 features extend the MVP without modifying core functionality
2. **Asynchronous First**: Long-running operations execute in the background to maintain UI responsiveness
3. **Progressive Enhancement**: Features degrade gracefully when dependencies are unavailable
4. **Data-Driven Intelligence**: Leverage historical data to improve automation and insights
5. **User Transparency**: Provide clear visibility into system decisions and confidence levels

## Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface Layer                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Dashboard   │  │   Settings   │  │  GST Cache   │          │
│  │  (Enhanced)  │  │    Page      │  │     Page     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      Django Application Layer                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Views      │  │   Forms      │  │     APIs     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      Business Logic Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Scoring    │  │  API Key     │  │   Export     │          │
│  │   Engine     │  │   Manager    │  │   Service    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    Asynchronous Task Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Celery     │  │    Redis     │  │   Task       │          │
│  │   Workers    │  │    Broker    │  │   Queue      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘

                              │
┌─────────────────────────────────────────────────────────────────┐
│                         Data Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Invoice    │  │  GST Cache   │  │   User       │          │
│  │   Models     │  │    Model     │  │   Profile    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack Additions

**Phase 2 introduces:**
- **Celery**: Distributed task queue for asynchronous processing
- **Redis**: Message broker and result backend for Celery
- **Chart.js or D3.js**: Client-side charting library for dashboard visualizations
- **Django REST Framework** (optional): For AJAX endpoints supporting real-time updates

## Components and Interfaces

### 1. Bulk Upload System

#### Component: BulkUploadHandler

**Purpose**: Manage multi-file upload and coordinate asynchronous processing

**Key Methods**:
```python
class BulkUploadHandler:
    def handle_bulk_upload(request, files: List[UploadedFile]) -> str:
        """
        Accepts multiple files, creates a batch record, and queues processing tasks
        Returns: batch_id for tracking
        """
        
    def get_batch_status(batch_id: str) -> dict:
        """
        Returns processing status: total, processed, failed, in_progress
        """
```

**Celery Task**:
```python
@shared_task
def process_invoice_async(invoice_id: int, batch_id: str = None):
    """
    Asynchronously processes a single invoice through the full pipeline:
    - AI extraction
    - Compliance checks
    - GST verification (with cache lookup)
    - Health score calculation
    """
```

**Database Model**:
```python
class InvoiceBatch(models.Model):
    batch_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total_files = models.IntegerField()
    processed_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20)  # PROCESSING, COMPLETED, PARTIAL_FAILURE
    created_at = models.DateTimeField(auto_now_add=True)
```

#### UI Component: Bulk Upload Interface

**Location**: Dashboard upload section

**Features**:
- Multi-file selector (drag-and-drop + file browser)
- Real-time progress bar showing "X of Y processed"
- Toast notifications on completion
- Link to view batch results

**Implementation**: Enhance existing upload form with JavaScript for multi-file handling and AJAX polling for progress updates

---

### 2. Manual Data Entry Fallback

#### Component: ManualEntryService

**Purpose**: Handle AI extraction failures gracefully with user-assisted data entry

**Key Methods**:
```python
class ManualEntryService:
    def flag_for_manual_entry(invoice: Invoice, reason: str):
        """
        Marks invoice as requiring manual entry and stores failure reason
        """
        
    def validate_manual_entry(data: dict) -> tuple[bool, list]:
        """
        Validates manually entered data against business rules
        Returns: (is_valid, error_messages)
        """
```

**Database Extension**:
```python
# Add to Invoice model
extraction_method = models.CharField(
    max_length=20,
    choices=[('AI', 'AI Extracted'), ('MANUAL', 'Manual Entry')],
    default='AI'
)
extraction_failure_reason = models.TextField(null=True, blank=True)
```

#### UI Component: Manual Entry Form

**Location**: Dedicated page accessible from invoice detail view when extraction fails

**Form Fields**:
- Invoice Number, Date, Vendor Name, Vendor GSTIN
- Buyer GSTIN, Grand Total
- Line Items (dynamic formset): Description, HSN/SAC, Quantity, Unit Price, GST Rate

**Validation**: Client-side validation for GSTIN format, date ranges, numeric fields

---

### 3. Smart Duplicate Management

#### Component: DuplicateLinkingService

**Purpose**: Automatically link duplicate invoices to originals instead of just flagging

**Key Methods**:
```python
class DuplicateLinkingService:
    def find_original_invoice(vendor_gstin: str, invoice_id: str) -> Invoice:
        """
        Finds the first occurrence of an invoice with matching identifiers
        """
        
    def link_duplicate(duplicate: Invoice, original: Invoice):
        """
        Creates a link between duplicate and original, copies verification status
        """
```

**Database Model**:
```python
class InvoiceDuplicateLink(models.Model):
    duplicate_invoice = models.OneToOneField(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='duplicate_link'
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
```

**Integration**: Modify existing duplicate detection logic to create links instead of just flags

---

### 4. Automated GST Verification Cache

#### Component: GSTCacheService

**Purpose**: Maintain internal database of verified GST numbers to bypass CAPTCHA for known vendors

**Key Methods**:
```python
class GSTCacheService:
    def lookup_gstin(gstin: str) -> Optional[GSTCacheEntry]:
        """
        Checks if GSTIN exists in cache and returns cached data
        """
        
    def add_to_cache(gstin: str, verification_data: dict):
        """
        Stores verified GSTIN data in cache after successful verification
        """
        
    def refresh_cache_entry(gstin: str) -> bool:
        """
        Re-fetches data from government portal to update cache
        """
```

**Database Model**:
```python
class GSTCacheEntry(models.Model):
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
```

**Integration**: Modify GST verification flow to check cache first before initiating CAPTCHA-based verification

---

### 5. Confidence Score System

#### Component: ConfidenceScoreCalculator

**Purpose**: Calculate and display AI extraction confidence for transparency

**Key Methods**:
```python
class ConfidenceScoreCalculator:
    def calculate_confidence(extraction_result: dict) -> float:
        """
        Analyzes Gemini API response to determine confidence (0-100%)
        Factors: field completeness, OCR quality indicators, response certainty
        """
        
    def get_confidence_level(score: float) -> str:
        """
        Returns: 'HIGH' (>80%), 'MEDIUM' (50-80%), 'LOW' (<50%)
        """
```

**Database Extension**:
```python
# Add to Invoice model
ai_confidence_score = models.DecimalField(
    max_digits=5, 
    decimal_places=2, 
    null=True, 
    blank=True
)  # 0.00 to 100.00
```

**UI Display**: Badge on invoice detail page with color coding (green/yellow/red)

---

### 6. Invoice Health Score System

#### Component: InvoiceHealthScoreEngine

**Purpose**: Calculate comprehensive risk score using weighted rubric

**Scoring Rubric**:

| Category | Weight | Criteria |
|----------|--------|----------|
| Data Completeness | 25% | All required fields present, no missing data |
| Vendor & Buyer Verification | 30% | Valid GSTIN, verified in cache/portal |
| Compliance & Legal Checks | 25% | Correct HSN rates, arithmetic accuracy |
| Fraud & Anomaly Detection | 15% | No duplicates, prices within normal range |
| AI Confidence & Document Quality | 5% | High confidence score, clear document |

**Key Methods**:
```python
class InvoiceHealthScoreEngine:
    def calculate_health_score(invoice: Invoice) -> dict:
        """
        Returns: {
            'score': float (0-10),
            'status': str ('HEALTHY', 'REVIEW', 'AT_RISK'),
            'breakdown': dict (scores by category),
            'key_flags': list (specific issues)
        }
        """
        
    def _score_data_completeness(invoice: Invoice) -> float:
        """Checks for missing required fields"""
        
    def _score_verification(invoice: Invoice) -> float:
        """Checks GST verification status"""
        
    def _score_compliance(invoice: Invoice) -> float:
        """Checks compliance flags"""
        
    def _score_fraud_detection(invoice: Invoice) -> float:
        """Checks for duplicates and anomalies"""
        
    def _score_ai_confidence(invoice: Invoice) -> float:
        """Uses AI confidence score"""
```

**Database Model**:
```python
class InvoiceHealthScore(models.Model):
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name='health_score')
    overall_score = models.DecimalField(max_digits=3, decimal_places=1)  # 0.0 to 10.0
    status = models.CharField(
        max_length=20,
        choices=[
            ('HEALTHY', 'Healthy (8.0-10.0)'),
            ('REVIEW', 'Review (5.0-7.9)'),
            ('AT_RISK', 'At Risk (0.0-4.9)')
        ]
    )
    data_completeness_score = models.DecimalField(max_digits=4, decimal_places=2)
    verification_score = models.DecimalField(max_digits=4, decimal_places=2)
    compliance_score = models.DecimalField(max_digits=4, decimal_places=2)
    fraud_detection_score = models.DecimalField(max_digits=4, decimal_places=2)
    ai_confidence_score_component = models.DecimalField(max_digits=4, decimal_places=2)
    key_flags = models.JSONField(default=list)  # List of issue descriptions
    calculated_at = models.DateTimeField(auto_now=True)
```

**Integration**: Calculate health score after all compliance checks complete, display on invoice list and detail pages

---

### 7. Enhanced Analytical Dashboard

#### Component: DashboardAnalyticsService

**Purpose**: Generate data for dashboard visualizations

**Key Methods**:
```python
class DashboardAnalyticsService:
    def get_invoice_per_day_data(days: int = 5) -> dict:
        """
        Returns: {
            'dates': list,
            'genuine_counts': list,
            'at_risk_counts': list
        }
        """
        
    def get_money_flow_by_hsn(limit: int = 5) -> list:
        """
        Returns top HSN/SAC codes by total spend with percentages
        """
        
    def get_company_leaderboard(limit: int = 5) -> list:
        """
        Returns top vendors by total amount and invoice count
        """
        
    def get_red_flag_list(limit: int = 5) -> list:
        """
        Returns invoices with lowest health scores
        """
```

#### UI Components

**1. Invoice Per Day Chart**
- Type: Grouped bar chart
- Data: Last 5-14 days, genuine vs. at-risk invoices
- Library: Chart.js
- Update: Real-time via AJAX polling or WebSocket

**2. Money Flow Donut Chart**
- Type: Donut/pie chart with legend
- Data: Top 5 HSN/SAC categories by spend
- Colors: Grayscale gradient (matching reference UI)
- Interaction: Hover to show exact amounts

**3. Company Leaderboard Table**
- Columns: Company Name, Total Amount, Invoice Count
- Sorting: By amount (descending)
- Limit: Top 5 vendors

**4. Red Flag List Table**
- Columns: Company Name, Date, Health Score
- Sorting: By health score (ascending)
- Color coding: Red background for critical scores
- Link: Click to view invoice details

**Implementation**: Use reference UI code (referenceUIcode.html) as template, integrate with Django template system

---

### 8. GST Cache Management Page

#### Component: GSTCacheView

**Purpose**: Provide UI for viewing and managing cached GST entries

**Features**:
- Searchable table (by GSTIN, legal name, trade name)
- Filterable by status (Active/Inactive)
- Sortable columns
- Refresh button for individual entries
- Export to CSV

**UI Layout**:
- Sidebar navigation link: "GST Verified Cache"
- Table with columns: GSTIN, Legal Name, Trade Name, Status, Registration Date, Business Constitution, Last Verified
- Search bar at top
- Pagination for large datasets

---

### 9. User Profile Management

#### Component: UserProfileService

**Purpose**: Manage user profile information and preferences

**Database Model**:
```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
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
```

**UI Page**: Profile page with form for editing name, username, email, profile picture

---

### 10. Comprehensive Settings Management

#### Component: SettingsView

**Purpose**: Centralized settings page for all user preferences

**UI Sections** (based on reference UI):
1. **Account Settings**: Profile picture, name, username, email
2. **Connected Services**: Facebook Connect, Google+ Connect (toggle switches)
3. **Preferences**: Sound effects, Animations, Motivational messages, Listening exercises (toggle switches)
4. **Account Actions**: Logout, Export My Data, Delete My Account

**Implementation**: Use reference UI code (referenceUIcode.html) settings page as template

---

### 11. Data Export Capability

#### Component: DataExportService

**Purpose**: Generate CSV/Excel exports of invoice and GST cache data

**Key Methods**:
```python
class DataExportService:
    def export_invoices_to_csv(queryset, fields: list) -> HttpResponse:
        """
        Exports filtered invoice queryset to CSV
        """
        
    def export_gst_cache_to_csv() -> HttpResponse:
        """
        Exports entire GST cache to CSV
        """
```

**UI Integration**: "Export" button on invoice list and GST cache pages

---

### 12. Multiple API Key Management

#### Component: APIKeyManager

**Purpose**: Manage pool of Gemini API keys with automatic failover

**Key Methods**:
```python
class APIKeyManager:
    def get_active_key(self) -> str:
        """
        Returns next available API key from pool
        """
        
    def mark_key_exhausted(self, key: str):
        """
        Marks key as exhausted, triggers failover to next key
        """
        
    def reset_key_pool(self):
        """
        Resets all keys (called daily or on manual trigger)
        """
```

**Configuration**:
```python
# settings.py
GEMINI_API_KEYS = os.environ.get('GEMINI_API_KEYS', '').split(',')
```

**Database Model**:
```python
class APIKeyUsage(models.Model):
    key_hash = models.CharField(max_length=64, unique=True)  # SHA256 hash for security
    is_active = models.BooleanField(default=True)
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    exhausted_at = models.DateTimeField(null=True, blank=True)
```

**Integration**: Modify GeminiService to use APIKeyManager instead of single key

---

### 13. Coming Soon Pages

#### Component: ComingSoonView

**Purpose**: Professional placeholder for non-functional features

**UI Elements**:
- Centered message: "This feature is coming soon!"
- Brief description of planned functionality
- "Return to Dashboard" button
- Optional: Email signup for feature launch notification

**Implementation**: Simple Django template view

## Data Models

### New Models Summary

1. **InvoiceBatch**: Track bulk upload batches
2. **InvoiceDuplicateLink**: Link duplicates to originals
3. **GSTCacheEntry**: Store verified GST data
4. **InvoiceHealthScore**: Store calculated health scores
5. **UserProfile**: Extended user information and preferences
6. **APIKeyUsage**: Track API key usage and status

### Modified Models

**Invoice** (additions):
- `extraction_method`: AI vs. Manual
- `extraction_failure_reason`: Why AI failed
- `ai_confidence_score`: Extraction confidence
- `batch`: ForeignKey to InvoiceBatch (optional)

## Error Handling

### Bulk Upload Failures
- Individual invoice failures don't block batch
- Failed invoices flagged for manual review
- Batch summary shows success/failure counts

### API Key Exhaustion
- Automatic failover to next key
- User notification when all keys exhausted
- Graceful degradation: queue invoices for later processing

### Cache Misses
- Fall back to standard CAPTCHA verification
- Log cache miss rate for monitoring

### Asynchronous Task Failures
- Celery retry mechanism (3 attempts with exponential backoff)
- Failed tasks logged with full error details
- User notification for persistent failures

## Testing Strategy

### Unit Tests
- Scoring engine calculations
- API key manager failover logic
- Duplicate linking logic
- Data export formatting

### Integration Tests
- Bulk upload end-to-end flow
- GST cache lookup and fallback
- Health score calculation with real data
- Manual entry form submission and validation

### UI Tests
- Dashboard chart rendering
- Settings page toggle functionality
- Profile picture upload
- Export button functionality

### Performance Tests
- Bulk upload with 50+ files
- Dashboard load time with large datasets
- Cache lookup performance
- Celery task throughput

## Security Considerations

1. **API Key Storage**: Hash keys in database, never log full keys
2. **File Upload Validation**: Strict file type and size limits for bulk uploads
3. **CSRF Protection**: All forms include CSRF tokens
4. **Data Export Authorization**: Verify user owns data before export
5. **Profile Picture Upload**: Validate image format, scan for malware
6. **Account Deletion**: Soft delete with data retention policy compliance

## Performance Optimization

1. **Database Indexing**: Add indexes on frequently queried fields (health score status, batch ID)
2. **Query Optimization**: Use select_related and prefetch_related for dashboard queries
3. **Caching**: Redis cache for dashboard analytics (5-minute TTL)
4. **Pagination**: Limit table results to 25-50 per page
5. **Lazy Loading**: Load charts on-demand, not on initial page load
6. **Background Processing**: All heavy operations (AI extraction, compliance checks) run asynchronously

## Deployment Considerations

### New Infrastructure Requirements
- **Redis Server**: For Celery message broker
- **Celery Workers**: At least 2 worker processes for parallel processing
- **Increased Storage**: For profile pictures and larger invoice volumes

### Configuration
- Environment variables for multiple API keys
- Redis connection settings
- Celery worker configuration (concurrency, task time limits)

### Migration Strategy
1. Deploy new models with migrations
2. Start Celery workers
3. Enable bulk upload feature flag
4. Gradually roll out new dashboard
5. Monitor performance and error rates

## Future Enhancements (Post-Phase 2)

- Real-time WebSocket updates for bulk upload progress
- Machine learning for improved price anomaly detection
- Advanced reporting with custom date ranges and filters
- Mobile-responsive dashboard
- API for third-party integrations
- Multi-language support
