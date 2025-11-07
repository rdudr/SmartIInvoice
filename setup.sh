#!/bin/bash
# ============================================================================
# Smart iInvoice - Linux/Mac Setup Script
# ============================================================================
# This script sets up the entire project environment including:
# - Python virtual environment
# - All dependencies
# - Database migrations
# - Redis installation check
# - Environment configuration
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Create logs directory
mkdir -p logs

# Set log file with timestamp
LOG_FILE="logs/setup_$(date +%Y%m%d_%H%M%S).log"

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}           Smart iInvoice - Automated Setup Script${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo "Log file: $LOG_FILE"
echo ""

# Helper functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# ============================================================================
# Step 1: Check Python Installation
# ============================================================================
log "Step 1: Checking Python installation..."

if ! command -v python3 &> /dev/null; then
    error "Python 3 is not installed!"
    log "Please install Python 3.8 or higher:"
    log "  - Ubuntu/Debian: sudo apt-get install python3 python3-pip python3-venv"
    log "  - macOS: brew install python3"
    log "  - Fedora: sudo dnf install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
success "Python $PYTHON_VERSION found"

# ============================================================================
# Step 2: Check/Install Redis
# ============================================================================
log "Step 2: Checking Redis installation..."

if ! command -v redis-server &> /dev/null; then
    warning "Redis is not installed!"
    log "Redis is required for Celery task queue."
    log ""
    log "Installation commands:"
    log "  - Ubuntu/Debian: sudo apt-get install redis-server"
    log "  - macOS: brew install redis"
    log "  - Fedora: sudo dnf install redis"
    log "  - Docker: docker run -d -p 6379:6379 redis"
    log ""
    
    read -p "Do you want to continue without Redis? (Celery won't work) [y/N]: " CONTINUE
    if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
        log "Setup cancelled. Please install Redis and run setup again."
        exit 1
    fi
    warning "Continuing without Redis - Celery features will be disabled"
else
    REDIS_VERSION=$(redis-server --version 2>&1 | head -n1)
    success "Redis found: $REDIS_VERSION"
fi

# ============================================================================
# Step 3: Create Virtual Environment
# ============================================================================
log "Step 3: Setting up Python virtual environment..."

if [ -d "venv" ]; then
    warning "Virtual environment already exists. Skipping creation."
else
    log "Creating virtual environment..."
    python3 -m venv venv >> "$LOG_FILE" 2>&1
    if [ $? -ne 0 ]; then
        error "Failed to create virtual environment!"
        log "Try installing: python3-venv"
        exit 1
    fi
    success "Virtual environment created"
fi

# Activate virtual environment
log "Activating virtual environment..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    error "Failed to activate virtual environment!"
    exit 1
fi
success "Virtual environment activated"

# ============================================================================
# Step 4: Upgrade pip
# ============================================================================
log "Step 4: Upgrading pip..."
python -m pip install --upgrade pip >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    warning "Failed to upgrade pip, continuing anyway..."
else
    success "pip upgraded successfully"
fi

# ============================================================================
# Step 5: Install Python Dependencies
# ============================================================================
log "Step 5: Installing Python dependencies..."

if [ ! -f "requirements.txt" ]; then
    error "requirements.txt not found!"
    exit 1
fi

log "This may take several minutes..."
pip install -r requirements.txt >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    error "Failed to install dependencies!"
    log "Check $LOG_FILE for details"
    exit 1
fi
success "All dependencies installed successfully"

# ============================================================================
# Step 6: Setup Environment Variables
# ============================================================================
log "Step 6: Setting up environment variables..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        log "Creating .env file from .env.example..."
        cp .env.example .env >> "$LOG_FILE" 2>&1
        warning ".env file created. Please edit it with your API keys!"
        log "Required: GEMINI_API_KEY"
        log "Optional: REDIS_URL, CELERY_BROKER_URL"
    else
        error ".env.example not found!"
        log "Please create a .env file manually with required configuration"
    fi
else
    success ".env file already exists"
fi

# ============================================================================
# Step 7: Database Setup
# ============================================================================
log "Step 7: Setting up database..."

# Check if migrations exist
if [ ! -d "invoice_processor/migrations" ]; then
    log "Creating migrations directory..."
    mkdir -p invoice_processor/migrations
    touch invoice_processor/migrations/__init__.py
fi

# Make migrations
log "Creating database migrations..."
python manage.py makemigrations >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    warning "makemigrations had issues, continuing..."
fi

# Run migrations
log "Applying database migrations..."
python manage.py migrate >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    error "Failed to apply migrations!"
    log "Check $LOG_FILE for details"
    exit 1
fi
success "Database migrations completed"

# ============================================================================
# Step 8: Collect Static Files
# ============================================================================
log "Step 8: Collecting static files..."

python manage.py collectstatic --noinput >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    warning "Failed to collect static files, continuing..."
else
    success "Static files collected"
fi

# ============================================================================
# Step 9: Create Superuser (Optional)
# ============================================================================
log "Step 9: Creating superuser account..."

read -p "Do you want to create a superuser account now? [y/N]: " CREATE_SUPERUSER
if [[ "$CREATE_SUPERUSER" =~ ^[Yy]$ ]]; then
    log "Creating superuser..."
    python manage.py createsuperuser
    if [ $? -ne 0 ]; then
        warning "Superuser creation skipped or failed"
    else
        success "Superuser created successfully"
    fi
else
    log "Skipping superuser creation. You can create one later with: python manage.py createsuperuser"
fi

# ============================================================================
# Step 10: Verify Installation
# ============================================================================
log "Step 10: Verifying installation..."

log "Checking Django installation..."
python -c "import django; print('Django version:', django.get_version())" >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    error "Django verification failed!"
else
    success "Django verified"
fi

log "Checking Celery installation..."
celery --version >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    warning "Celery verification failed"
else
    success "Celery verified"
fi

log "Running Django system check..."
python manage.py check >> "$LOG_FILE" 2>&1
if [ $? -ne 0 ]; then
    warning "Django system check found issues (check log)"
else
    success "Django system check passed"
fi

# ============================================================================
# Setup Complete
# ============================================================================
echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}                    Setup Completed Successfully!${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
log "Setup completed successfully!"
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "1. Edit .env file with your API keys (especially GEMINI_API_KEY)"
echo "2. Make sure Redis is running (if you want Celery features)"
echo "3. Run the project using: ./run.sh"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "  - Start project: ./run.sh"
echo "  - Create superuser: python manage.py createsuperuser"
echo "  - Run tests: python manage.py test"
echo ""
echo "Full setup log saved to: $LOG_FILE"
echo ""

# Make run.sh executable
if [ -f "run.sh" ]; then
    chmod +x run.sh
    log "Made run.sh executable"
fi

exit 0
