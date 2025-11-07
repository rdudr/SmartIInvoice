# Smart iInvoice

AI-powered invoice management and compliance platform built with Django and Tailwind CSS.

## Setup Instructions

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies for Tailwind CSS
npm install
```

### 2. Environment Configuration

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
- `GEMINI_API_KEY`: Your Google Gemini API key
- `SECRET_KEY`: Django secret key (generate a new one for production)

### 3. Database Setup

```bash
# Run migrations
python manage.py migrate

# Load HSN/SAC master data for GST rate validation
python manage.py load_hsn_data

# Create a superuser (optional)
python manage.py createsuperuser
```

### 4. Build CSS (Optional)

If you want to customize Tailwind CSS:

```bash
# Build CSS for development (with watch mode)
npm run build-css

# Or build for production (minified)
npm run build-css-prod
```

### 5. Set Up Asynchronous Processing (Optional - Required for Phase 2 Features)

For bulk upload and background processing features, you need to set up Celery and Redis:

```bash
# Install Redis (required for Celery message broker)
# Windows: Download from https://github.com/microsoftarchive/redis/releases
# Ubuntu/Debian: sudo apt-get install redis-server
# macOS: brew install redis

# Start Redis server
redis-server
# Or on Windows: start_redis.bat

# In a separate terminal, start Celery worker
celery -A smartinvoice worker --loglevel=info --pool=solo --concurrency=2
# Or on Windows: start_celery_worker.bat
# Or on Unix/Linux/macOS: ./start_celery_worker.sh

# Test Celery setup
python manage.py test_celery
```

See [CELERY_SETUP.md](CELERY_SETUP.md) for detailed setup instructions and troubleshooting.

### 6. Run the Development Server

```bash
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`

## Project Structure

```
smartinvoice/
├── smartinvoice/              # Django project settings
├── invoice_processor/         # Main Django app
│   ├── services/             # Business logic services
│   ├── templates/            # HTML templates
│   └── static/               # App-specific static files
├── templates/                # Global templates
├── static/                   # Global static files
├── media/                    # Uploaded files
├── data/                     # Master data files (GST rates)
└── requirements.txt          # Python dependencies
```

## Next Steps

This is the basic project structure. The following features will be implemented in subsequent tasks:

1. Database models for invoices and compliance
2. Authentication system
3. Gemini API integration for data extraction
4. Analysis engine for compliance checks
5. GST verification system
6. Dashboard and UI components

## Management Commands

### Test Celery Setup

Test if Celery and Redis are configured correctly:

```bash
python manage.py test_celery
```

This command will:
- Queue a test task to Celery
- Wait for the result (10 second timeout)
- Display success or error messages
- Provide troubleshooting tips if the test fails

### Load HSN/SAC Data

The `load_hsn_data` command processes GST rate CSV files and generates a cached JSON file for the analysis engine:

```bash
# Load data using default file paths
python manage.py load_hsn_data

# Specify custom file paths
python manage.py load_hsn_data --goods-file path/to/goods.csv --services-file path/to/services.csv

# Specify custom output file
python manage.py load_hsn_data --output-file data/custom_hsn_rates.json

# Force overwrite existing output file
python manage.py load_hsn_data --force

# Get help
python manage.py load_hsn_data --help
```

**Default file paths:**
- Goods: `GST_Goods_Rates.csv`
- Services: `GST_Services_Rates.csv`
- Output: `data/hsn_gst_rates.json`

The command processes:
- **Goods CSV**: Extracts HSN codes and IGST rates from the goods rates file
- **Services CSV**: Creates synthetic SAC codes and extracts IGST rates from the services file
- **Output JSON**: Generates a structured JSON file with goods, services, and metadata sections

This cached file is used by the analysis engine to validate HSN/SAC codes and GST rates during invoice processing.

## Development

- Django admin: `http://127.0.0.1:8000/admin/`
- Main application: `http://127.0.0.1:8000/`

For development, make sure to:
1. Keep the Django server running: `python manage.py runserver`
2. Keep Tailwind CSS building: `npm run build-css` (if customizing styles)
3. Load HSN data after any changes to GST rate files: `python manage.py load_hsn_data --force`
4. For Phase 2 features (bulk upload, background processing):
   - Keep Redis running: `redis-server`
   - Keep Celery worker running: `celery -A smartinvoice worker --loglevel=info --pool=solo`

## Phase 2 Features

Phase 2 transforms Smart iInvoice into an intelligent business analytics platform with advanced automation and insights.

### Key Features

#### 1. Bulk Invoice Upload
- Upload and process multiple invoices simultaneously
- Real-time progress tracking with visual indicators
- Asynchronous background processing for better performance
- Batch status monitoring and completion notifications

#### 2. Invoice Health Score System
- Comprehensive risk assessment (0-10 scale)
- Weighted scoring across 5 categories:
  - Data Completeness (25%)
  - Vendor & Buyer Verification (30%)
  - Compliance & Legal Checks (25%)
  - Fraud & Anomaly Detection (15%)
  - AI Confidence & Document Quality (5%)
- Color-coded status indicators (Healthy/Review/At Risk)
- Detailed breakdown with specific issue flags

#### 3. GST Verification Cache
- Automatic caching of verified GST numbers
- Instant verification for known vendors (no CAPTCHA required)
- Searchable and filterable cache management page
- Manual refresh capability for individual entries
- Export cache data to CSV

#### 4. Enhanced Analytics Dashboard
- **Invoice Per Day Chart**: Daily processing trends with health status breakdown
- **Money Flow Donut Chart**: Spending distribution by HSN/SAC categories
- **Company Leaderboard**: Top vendors by total spend and invoice volume
- **Red Flag List**: High-risk invoices requiring immediate attention
- Real-time data updates

#### 5. AI Confidence Score
- Transparency into AI extraction confidence (0-100%)
- Visual indicators for confidence levels (High/Medium/Low)
- Filtering and sorting by confidence score
- Automatic flagging of low-confidence extractions

#### 6. Manual Data Entry Fallback
- Graceful handling of AI extraction failures
- User-friendly manual entry form with validation
- Clear explanation of failure reasons
- Same compliance checks as AI-extracted invoices

#### 7. Smart Duplicate Management
- Automatic linking of duplicate invoices to originals
- Prevention of redundant GST verification
- Duplicate relationship visualization
- Audit trail for all duplicate submissions

#### 8. User Profile Management
- Customizable user profiles with profile pictures
- Personal information management
- Preference settings (notifications, sound, animations)
- Social service connections (Facebook, Google)

#### 9. Comprehensive Settings
- Centralized settings management
- Account preferences and customization
- Connected services management
- Data export and account deletion options

#### 10. Data Export Capabilities
- Export invoices to CSV with applied filters
- Export GST cache entries
- Export all user data (GDPR compliance)
- Timestamped filenames for easy organization

#### 11. Multiple API Key Management
- Support for multiple Gemini API keys
- Automatic failover when quota limits are reached
- Seamless processing without user intervention
- Usage tracking and monitoring

### Environment Variables for Phase 2

Add these to your `.env` file:

```bash
# Multiple API Keys (comma-separated)
GEMINI_API_KEYS=key1,key2,key3

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Production Settings (optional)
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

### Production Deployment

#### Celery Worker Configuration

For production environments, use the production configuration:

```bash
# Linux/Unix/macOS
./start_celery_worker.sh
# Select 'y' when prompted for production mode

# Windows
start_celery_worker.bat
# Select 'y' when prompted for production mode
```

Production configuration includes:
- 4 concurrent workers
- 30-minute task time limit
- Automatic retries (max 3 attempts)
- Memory management (restart after 1000 tasks)
- Task monitoring and logging

#### Systemd Service (Linux)

Create `/etc/systemd/system/celery-smartinvoice.service`:

```ini
[Unit]
Description=Celery Worker for Smart iInvoice
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/smartinvoice
ExecStart=/path/to/venv/bin/celery -A smartinvoice worker --config=celery_config_production --loglevel=info --concurrency=4 --detach
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable celery-smartinvoice
sudo systemctl start celery-smartinvoice
sudo systemctl status celery-smartinvoice
```

### Database Optimization

Run the database optimization command to verify indexes and analyze tables:

```bash
python manage.py optimize_db
```

This command will:
- Check all database indexes
- Run ANALYZE on tables for query optimization
- Display query statistics
- Show GST cache coverage

### Monitoring and Logging

Celery tasks are logged with detailed information:
- Task start and completion events
- Failure notifications with stack traces
- Performance metrics
- Worker status

Check logs in:
- `logs/smartinvoice.log`: Application logs
- `logs/errors.log`: Error logs
- Celery worker console output

### Troubleshooting

#### Celery Worker Not Starting
1. Ensure Redis is running: `redis-cli ping` (should return "PONG")
2. Check Celery configuration in `smartinvoice/settings.py`
3. Verify `CELERY_BROKER_URL` in `.env` file
4. Run test: `python manage.py test_celery`

#### Bulk Upload Not Working
1. Verify Celery worker is running
2. Check Redis connection
3. Review Celery worker logs for errors
4. Ensure sufficient disk space for uploaded files

#### Health Score Not Calculating
1. Check that all compliance checks are completing
2. Verify `InvoiceHealthScore` model is migrated
3. Review logs for scoring engine errors

#### GST Cache Not Working
1. Verify GST verification microservice is running
2. Check cache entries in admin panel
3. Ensure `GSTCacheEntry` model is migrated

For detailed information about Phase 2 features, see:
- Requirements: `.kiro/specs/smart-iinvoice-phase2-enhancements/requirements.md`
- Design: `.kiro/specs/smart-iinvoice-phase2-enhancements/design.md`
- Implementation Tasks: `.kiro/specs/smart-iinvoice-phase2-enhancements/tasks.md`