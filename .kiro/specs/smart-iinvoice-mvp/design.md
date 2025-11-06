# Design Document

## Overview

Smart iInvoice is a Django-based web application that leverages AI for intelligent invoice processing and compliance checking. The system architecture consists of two main components:

1. **Django Web Application**: Handles user authentication, invoice management, data analysis, and UI rendering
2. **Flask GST Microservice**: Provides GST verification through the government portal

The application follows Django's MVT (Model-View-Template) architecture with a clear separation of concerns. The frontend uses Tailwind CSS for modern, responsive styling. The Gemini API integration enables intelligent data extraction from invoice images, while the analysis engine performs multiple compliance checks.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Browser                          │
│                    (Tailwind CSS UI)                         │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/AJAX
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Django Web Application                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │    Views     │  │   Models     │  │  Templates   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘      │
│         │                  │                                 │
│  ┌──────▼──────────────────▼───────┐                        │
│  │      Business Logic Layer       │                        │
│  │  - Invoice Processor            │                        │
│  │  - Analysis Engine              │                        │
│  │  - GST Client                   │                        │
│  │  - Gemini Service               │                        │
│  └─────────────────────────────────┘                        │
└───────────┬─────────────────────────┬───────────────────────┘
            │                         │
            │                         │ HTTP API
            ▼                         ▼
    ┌───────────────┐      ┌──────────────────────┐
    │   SQLite DB   │      │  Flask GST Service   │
    └───────────────┘      │  - CAPTCHA Handler   │
                           │  - Session Manager   │
                           └──────────┬───────────┘
                                      │
                                      ▼
                           ┌──────────────────────┐
                           │  Government GST      │
                           │  Portal API          │
                           └──────────────────────┘
            
            External Services:
            - Google Gemini API (for OCR/extraction)
```


### Technology Stack

- **Backend Framework**: Django 4.x
- **Frontend**: HTML templates with Tailwind CSS
- **Database**: SQLite (for MVP)
- **AI/OCR**: Google Gemini API (gemini-1.5-flash-latest)
- **GST Verification**: Flask microservice (separate process)
- **HTTP Client**: Python requests library
- **Authentication**: Django built-in authentication system

### Directory Structure

```
smartinvoice/
├── manage.py
├── smartinvoice/              # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── invoice_processor/         # Main Django app
│   ├── models.py             # Database models
│   ├── views.py              # View controllers
│   ├── urls.py               # URL routing
│   ├── forms.py              # Form definitions
│   ├── services/             # Business logic layer
│   │   ├── gemini_service.py
│   │   ├── analysis_engine.py
│   │   └── gst_client.py
│   ├── templates/            # HTML templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── gst_verification.html
│   │   ├── login.html
│   │   └── register.html
│   └── static/               # Static files
│       ├── css/
│       └── js/
├── gst_microservice/         # Flask GST service
│   ├── app.py
│   └── requirements.txt
├── data/                     # Master data files
│   ├── GST_Goods_Rates.csv
│   └── GST_Services_Rates.csv
└── requirements.txt          # Django dependencies
```

## Components and Interfaces

### 1. Django Models (invoice_processor/models.py)

#### User Model
Uses Django's built-in User model for authentication.

#### Django Forms (invoice_processor/forms.py)

**Purpose**: Define forms for user input validation, such as the user registration form and login form.

#### Invoice Model
```python
class Invoice(models.Model):
    invoice_id = models.CharField(max_length=100, db_index=True)  # Extracted invoice number
    invoice_date = models.DateField()        # Invoice date
    vendor_name = models.CharField(max_length=255)  # Vendor name
    vendor_gstin = models.CharField(max_length=15, db_index=True)  # Vendor GST number
    billed_company_gstin = models.CharField(max_length=15)  # Buyer GST number
    grand_total = models.DecimalField(max_digits=12, decimal_places=2)  # Total invoice amount
    status = models.CharField(max_length=20, default='PENDING_ANALYSIS')  # Pending Analysis, Cleared, Has Anomalies
    gst_verification_status = models.CharField(max_length=20, default='PENDING')  # Pending, Verified, Failed
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)  # User who uploaded
    uploaded_at = models.DateTimeField(auto_now_add=True)  # Upload timestamp
    file_path = models.FileField(upload_to='invoices/')  # Stored invoice file
```

#### LineItem Model
```python
class LineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')  # Parent invoice
    description = models.CharField(max_length=500)  # Item description
    normalized_key = models.CharField(max_length=255, db_index=True)  # Normalized product key for price comparison
    hsn_sac_code = models.CharField(max_length=20)  # HSN/SAC code
    quantity = models.DecimalField(max_digits=10, decimal_places=2)  # Quantity
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)  # Price per unit
    billed_gst_rate = models.DecimalField(max_digits=5, decimal_places=2)  # GST rate on invoice
    line_total = models.DecimalField(max_digits=12, decimal_places=2)  # Total for this line
    created_at = models.DateTimeField(auto_now_add=True)  # When line item was created (for price trend analysis)
```

#### ComplianceFlag Model
```python
class ComplianceFlag(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='compliance_flags')  # Parent invoice
    line_item = models.ForeignKey(LineItem, on_delete=models.CASCADE, null=True, blank=True)  # Optional line item reference
    flag_type = models.CharField(max_length=50, db_index=True)  # Duplicate, Arithmetic Error, HSN Mismatch, Price Anomaly, Unknown HSN/SAC
    severity = models.CharField(max_length=10, db_index=True)  # Critical, Warning, Info
    description = models.TextField()  # Human-readable description
    created_at = models.DateTimeField(auto_now_add=True)  # When flag was created
```


### 2. Gemini Service (invoice_processor/services/gemini_service.py)

**Purpose**: Interface with Google Gemini API for invoice data extraction

**Key Functions**:

```python
def extract_data_from_image(image_file) -> dict:
    """
    Sends invoice image to Gemini API and returns structured data
    
    Args:
        image_file: Uploaded file object (image or PDF)
    
    Returns:
        dict: Extracted invoice data or {"is_invoice": false}
    """
```

**System Prompt Design**:
The prompt instructs Gemini to:
- Identify if the image is an invoice
- Extract specific fields with exact field names
- Return null for missing fields (never invent data)
- Return structured JSON matching our data model

**Error Handling**:
- API timeout: Retry once, then fail gracefully
- Invalid response: Log error and return extraction failure
- Rate limiting: Implement exponential backoff

### 3. Analysis Engine (invoice_processor/services/analysis_engine.py)

**Purpose**: Perform all compliance checks on extracted invoice data

**Key Functions**:

```python
def run_all_checks(invoice_data: dict, invoice_obj: Invoice) -> list:
    """
    Orchestrates all compliance checks
    
    Args:
        invoice_data: Extracted data from Gemini
        invoice_obj: Saved Invoice model instance
    
    Returns:
        list: ComplianceFlag objects to be saved
    """

def check_duplicates(invoice_data: dict) -> ComplianceFlag or None:
    """
    Checks for duplicate invoices by invoice_id and vendor_gstin
    """

def check_arithmetics(invoice_data: dict) -> list:
    """
    Verifies line item calculations and grand total
    Returns list of ComplianceFlag objects for any errors
    """

def check_hsn_rates(invoice_data: dict) -> list:
    """
    Validates HSN/SAC codes against master data
    Returns list of ComplianceFlag objects for mismatches
    """

def check_price_outliers(invoice_data: dict, vendor_gstin: str) -> list:
    """
    Detects price anomalies using historical data
    Returns list of ComplianceFlag objects for outliers
    """

def normalize_product_key(description: str) -> str:
    """
    Normalizes item description for consistent matching
    - Convert to lowercase
    - Remove extra whitespace
    - Remove common words (the, a, an, etc.)
    - Remove special characters
    """
```

**HSN Master Data Loading**:
- Load CSV files on application startup
- Store in memory as dictionary: {hsn_code: gst_rate}
- Handle both goods and services codes

**Price Anomaly Algorithm**:
1. Normalize item description to create product key
2. Query database for same product key + vendor
3. If >= 3 historical records exist:
   - Calculate average price
   - Calculate deviation percentage
   - Flag if deviation > 25%


### 4. GST Client (invoice_processor/services/gst_client.py)

**Purpose**: Interface with Flask GST microservice

**Key Functions**:

```python
def get_captcha() -> dict:
    """
    Requests CAPTCHA from GST microservice
    
    Returns:
        dict: {
            "sessionId": "uuid-string",
            "image": "data:image/png;base64,..."
        }
    """

def verify_gstin(session_id: str, gstin: str, captcha: str) -> dict:
    """
    Submits GST verification request
    
    Args:
        session_id: Session ID from get_captcha()
        gstin: GST number to verify
        captcha: User-entered CAPTCHA text
    
    Returns:
        dict: Response from government portal
    """
```

**Configuration**:
- GST Microservice URL: http://127.0.0.1:5001
- Timeout: 30 seconds
- Retry logic: 1 retry on connection error

### 5. Flask GST Microservice (gst_microservice/app.py)

**Purpose**: Handle GST verification with government portal

**Existing Implementation** (already working):
- `/api/v1/getCaptcha` - GET endpoint for CAPTCHA
- `/api/v1/getGSTDetails` - POST endpoint for verification
- Session management using in-memory dictionary
- UUID-based session identifiers

**No changes needed** - this component is already implemented and functional.

### 6. Views (invoice_processor/views.py)

**Dashboard View**:
- Calculate metrics (awaiting verification count, anomalies this week, total amount)
- Query recent invoices
- Query suspected invoices (with Critical flags)
- Aggregate compliance flags for donut chart
- Render dashboard.html

**Upload Invoice View**:
- Handle file upload (POST)
- Validate file type and size
- Call gemini_service.extract_data_from_image()
- Save Invoice and LineItem records
- Trigger analysis_engine.run_all_checks() **(Note: For the MVP, this will be a synchronous operation within the request. A loading indicator will be shown on the UI.)**
- Update invoice status based on flags
- Return JSON response for AJAX

**GST Verification View**:
- List invoices with pagination
- Filter by verification status
- Handle CAPTCHA request (AJAX)
- Handle verification submission (AJAX)
- Update invoice.gst_verification_status

**Authentication Views**:
- Login view (Django built-in with custom template)
- Register view (custom form and logic)
- Logout view (Django built-in)


## Data Models

### Entity Relationship Diagram

```
┌─────────────┐
│    User     │
│ (Django)    │
└──────┬──────┘
       │
       │ 1:N
       │
       ▼
┌─────────────────────┐
│      Invoice        │
│─────────────────────│
│ invoice_id          │
│ invoice_date        │
│ vendor_name         │
│ vendor_gstin        │
│ billed_company_gstin│
│ grand_total         │
│ status              │
│ gst_verification_   │
│   status            │
│ uploaded_by (FK)    │
│ uploaded_at         │
│ file_path           │
└──────┬──────────────┘
       │
       │ 1:N
       ├──────────────────────┐
       │                      │
       ▼                      ▼
┌─────────────────┐   ┌──────────────────┐
│    LineItem     │   │ ComplianceFlag   │
│─────────────────│   │──────────────────│
│ invoice (FK)    │   │ invoice (FK)     │
│ description     │   │ line_item (FK)   │
│ normalized_key  │   │ flag_type        │
│ hsn_sac_code    │   │ severity         │
│ quantity        │   │ description      │
│ unit_price      │   │ created_at       │
│ billed_gst_rate │   └──────────────────┘
│ line_total      │
└─────────────────┘
```

### Status Enumerations

**Invoice.status**:
- `PENDING_ANALYSIS`: Initial state after upload
- `CLEARED`: No compliance issues found
- `HAS_ANOMALIES`: One or more compliance flags exist

**Invoice.gst_verification_status**:
- `PENDING`: Not yet verified
- `VERIFIED`: Successfully verified with government portal
- `FAILED`: Verification failed (invalid GSTIN or CAPTCHA error)

**ComplianceFlag.flag_type**:
- `DUPLICATE`: Duplicate invoice detected
- `ARITHMETIC_ERROR`: Calculation mismatch
- `HSN_MISMATCH`: GST rate doesn't match official rate
- `UNKNOWN_HSN`: HSN/SAC code not found in master data
- `PRICE_ANOMALY`: Price deviates significantly from historical average

**ComplianceFlag.severity**:
- `CRITICAL`: Requires immediate attention (e.g., duplicate, arithmetic error)
- `WARNING`: Should be reviewed (e.g., price anomaly)
- `INFO`: Informational (e.g., unknown HSN code)

## Error Handling

### Gemini API Errors

**Scenario**: API timeout or rate limiting
- **Handling**: Retry once with exponential backoff
- **User Feedback**: "Invoice extraction is taking longer than expected. Please wait..."
- **Fallback**: After retry fails, save invoice with status "EXTRACTION_FAILED" and notify user

**Scenario**: Invalid JSON response
- **Handling**: Log full response for debugging
- **User Feedback**: "Unable to extract data from this invoice. Please try a clearer image."
- **Fallback**: Allow manual data entry option (future enhancement)

### GST Microservice Errors

**Scenario**: Microservice is down
- **Handling**: Catch connection error
- **User Feedback**: "GST verification service is temporarily unavailable. Please try again later."
- **Fallback**: Allow user to retry or skip verification

**Scenario**: Invalid CAPTCHA
- **Handling**: Return error from government portal
- **User Feedback**: "CAPTCHA verification failed. Please try again."
- **Fallback**: Allow user to request new CAPTCHA

### Database Errors

**Scenario**: Database write failure
- **Handling**: Rollback transaction, log error
- **User Feedback**: "An error occurred while saving the invoice. Please try again."
- **Fallback**: Preserve uploaded file for retry

### File Upload Errors

**Scenario**: Invalid file type
- **Handling**: Validate before processing
- **User Feedback**: "Please upload a valid image (PNG, JPG) or PDF file."

**Scenario**: File too large (>10MB)
- **Handling**: Validate file size
- **User Feedback**: "File size must be less than 10MB."


## Testing Strategy

### Unit Testing

**Models Testing**:
- Test model field validations
- Test model methods and properties
- Test model relationships (ForeignKey integrity)

**Services Testing**:
- Mock Gemini API responses and test gemini_service
- Test analysis_engine functions with sample invoice data
- Test normalize_product_key with various inputs
- Mock GST microservice and test gst_client

**Test Coverage Goals**:
- Business logic (services): 80%+ coverage
- Models: 70%+ coverage
- Views: 60%+ coverage (focus on critical paths)

### Integration Testing

**Invoice Processing Flow**:
1. Upload invoice → Extract data → Run checks → Save to DB
2. Verify status transitions (PENDING_ANALYSIS → CLEARED/HAS_ANOMALIES)
3. Verify compliance flags are created correctly

**GST Verification Flow**:
1. Request CAPTCHA → Display modal → Submit verification
2. Verify session management works correctly
3. Verify status updates after verification

### Manual Testing Checklist

**Authentication**:
- [ ] User can register with valid credentials
- [ ] User cannot register with duplicate email
- [ ] User can login with correct credentials
- [ ] User cannot login with incorrect credentials
- [ ] Protected pages redirect to login when not authenticated

**Dashboard**:
- [ ] Metrics display correct counts
- [ ] Donut chart shows correct distribution
- [ ] Recent activity shows latest invoices
- [ ] Suspected list shows invoices with Critical flags

**Invoice Upload**:
- [ ] Upload modal opens and closes correctly
- [ ] Drag-and-drop works for valid files
- [ ] Invalid file types are rejected
- [ ] Large files (>10MB) are rejected
- [ ] Successful upload shows in recent activity
- [ ] Duplicate invoice is flagged

**GST Verification**:
- [ ] Table displays all invoices with correct data
- [ ] Filters work correctly (All, Pending, Verified, Failed)
- [ ] CAPTCHA modal displays image correctly
- [ ] Verification updates status correctly
- [ ] Error messages display for invalid CAPTCHA

**Compliance Checks**:
- [ ] Arithmetic errors are detected
- [ ] HSN rate mismatches are flagged
- [ ] Unknown HSN codes are flagged
- [ ] Price anomalies are detected (with sufficient history)
- [ ] Duplicate invoices are flagged

## UI/UX Design Specifications

### Color Palette

**Primary Colors**:
- Background: `#F5F7FA` (light grey)
- Card Background: `#FFFFFF` (white)
- Primary Accent: `#5B8DEF` (blue)
- Secondary Accent: `#8B7FE8` (purple)
- Success Accent: `#4ECDC4` (teal)

**Status Colors**:
- Success/Verified: `#10B981` (green)
- Warning/Pending: `#F59E0B` (amber)
- Error/Failed: `#EF4444` (red)
- Info: `#3B82F6` (blue)

### Typography

- **Font Family**: Inter, system-ui, sans-serif
- **Headings**: 
  - H1: 2rem (32px), font-weight: 600
  - H2: 1.5rem (24px), font-weight: 600
  - H3: 1.25rem (20px), font-weight: 500
- **Body**: 0.875rem (14px), font-weight: 400
- **Small**: 0.75rem (12px), font-weight: 400

### Layout Components

**Sidebar**:
- Width: 240px
- Background: White
- Logo at top with "Smart iInvoice" text
- Navigation items with icons
- Active state: Blue background with white text

**Top Bar**:
- Height: 64px
- Background: White
- Search bar (left)
- Notifications icon (right)
- User profile dropdown (right)

**Cards**:
- Border radius: 8px
- Shadow: 0 1px 3px rgba(0,0,0,0.1)
- Padding: 1.5rem (24px)

**Buttons**:
- Primary: Blue background, white text, rounded
- Secondary: White background, blue border, blue text
- Danger: Red background, white text, rounded

**Tables**:
- Striped rows for readability
- Hover effect on rows
- Pagination at bottom (10 rows per page)
- Status badges with appropriate colors

**Modals**:
- Overlay: Semi-transparent dark background
- Content: White card centered on screen
- Close button (X) in top-right corner
- Actions at bottom (Cancel, Submit)

### Responsive Design

**Breakpoints**:
- Mobile: < 640px
- Tablet: 640px - 1024px
- Desktop: > 1024px

**Mobile Adaptations**:
- Sidebar collapses to hamburger menu
- Tables scroll horizontally
- Cards stack vertically
- Reduced padding and font sizes

## Security Considerations

### Authentication & Authorization

- Use Django's built-in authentication system
- Enforce login_required decorator on all protected views
- Use CSRF protection on all forms
- Implement password strength requirements

### API Security

- Store Gemini API key in environment variables (never in code)
- Validate all user inputs before processing
- Sanitize file uploads (check file type, size, content)
- Rate limit API calls to prevent abuse

### Data Protection

- Store uploaded invoices in secure directory outside web root
- Use Django's FileField with upload_to parameter
- Implement proper file permissions (read-only for web server)
- Consider encryption for sensitive invoice data (future enhancement)

### GST Microservice Security

- Run on localhost only (not exposed to internet)
- Implement request validation
- Clear session data after verification or timeout
- Consider adding authentication between Django and Flask (future enhancement)

## Performance Considerations

### Database Optimization

- Index frequently queried fields:
  - Invoice: vendor_gstin, status, gst_verification_status, uploaded_at
  - LineItem: normalized_key, hsn_sac_code
  - ComplianceFlag: flag_type, severity
- Use select_related() for ForeignKey queries
- Use prefetch_related() for reverse ForeignKey queries

### Caching Strategy

- Cache HSN master data in memory (load once on startup)
- Cache dashboard metrics (refresh every 5 minutes)
- Use Django's cache framework for frequently accessed data

### File Handling

- Limit file upload size to 10MB
- Process files asynchronously (future enhancement with Celery)
- Store files efficiently (consider compression for PDFs)

### API Rate Limiting

- Implement rate limiting for Gemini API calls
- Queue invoice processing if rate limit is reached
- Display queue position to user

## Deployment Considerations

### Environment Variables

```
SECRET_KEY=<django-secret-key>
DEBUG=False
ALLOWED_HOSTS=<domain-name>
GEMINI_API_KEY=<api-key>
GST_SERVICE_URL=http://127.0.0.1:5001
DATABASE_URL=<database-connection-string>
```

### Process Management

- Django application: Run with Gunicorn or uWSGI
- Flask microservice: Run as separate process with Uvicorn
- Use supervisor or systemd to manage both processes

### Static Files

- Collect static files: `python manage.py collectstatic`
- Serve with Nginx or Apache in production
- Use CDN for better performance (future enhancement)

### Database Migration

- Run migrations: `python manage.py migrate`
- Create superuser: `python manage.py createsuperuser`
- Load HSN master data on first deployment

## Future Enhancements

### Phase 2 Enhancements

1. **Asynchronous Processing**: Use Celery for background invoice processing
2. **Email Notifications**: Send alerts for critical compliance flags
3. **Bulk Upload**: Allow multiple invoice uploads at once
4. **Export Reports**: Generate PDF/Excel reports of compliance issues
5. **Advanced Analytics**: Trend analysis, vendor comparison charts
6. **Mobile App**: Native mobile application for on-the-go access

### Phase 3 Enhancements

1. **Machine Learning**: Improve price anomaly detection with ML models
2. **OCR Improvements**: Train custom model for better extraction accuracy
3. **Workflow Automation**: Approval workflows for flagged invoices
4. **Integration APIs**: REST API for third-party integrations
5. **Multi-tenancy**: Support multiple organizations
6. **Audit Trail**: Complete audit log of all actions

## Design Decisions & Rationale

### Why Django?

- Mature framework with excellent documentation
- Built-in admin interface for data management
- Strong ORM for database operations
- Robust authentication system
- Large ecosystem of packages

### Why Separate Flask Microservice?

- GST verification requires session management with government portal
- Isolates external dependency from main application
- Can be scaled independently if needed
- Existing working implementation can be reused

### Why SQLite for MVP?

- Zero configuration required
- Sufficient for MVP scale (< 10,000 invoices)
- Easy to migrate to PostgreSQL later
- Simplifies deployment

### Why Gemini API?

- State-of-the-art vision and language understanding
- Structured output capability (JSON mode)
- Cost-effective for MVP
- Easy to switch to other providers if needed

### Why Tailwind CSS?

- Rapid UI development with utility classes
- Consistent design system
- Small bundle size with purging
- Easy to customize and maintain
