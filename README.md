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

## Development

- Django admin: `http://127.0.0.1:8000/admin/`
- Main application: `http://127.0.0.1:8000/`

For development, make sure to:
1. Keep the Django server running: `python manage.py runserver`
2. Keep Tailwind CSS building: `npm run build-css` (if customizing styles)