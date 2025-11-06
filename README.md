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

### 5. Run the Development Server

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