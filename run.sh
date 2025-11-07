#!/bin/bash
# ============================================================================
# Smart iInvoice - Linux/Mac Run Script
# ============================================================================
# This script starts all required services and opens the application:
# - Redis server (if available)
# - Celery worker
# - Django development server
# - Opens browser automatically
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
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="logs/run_${TIMESTAMP}.log"

echo -e "${CYAN}============================================================================${NC}"
echo -e "${CYAN}           Smart iInvoice - Application Launcher${NC}"
echo -e "${CYAN}============================================================================${NC}"
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

# Cleanup function
cleanup() {
    log "Shutting down services..."
    
    # Kill background processes
    if [ ! -z "$GST_PID" ]; then
        log "Stopping GST service (PID: $GST_PID)..."
        kill $GST_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$CELERY_PID" ]; then
        log "Stopping Celery worker (PID: $CELERY_PID)..."
        kill $CELERY_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$DJANGO_PID" ]; then
        log "Stopping Django server (PID: $DJANGO_PID)..."
        kill $DJANGO_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$REDIS_PID" ] && [ "$REDIS_STARTED_BY_SCRIPT" = "1" ]; then
        log "Stopping Redis server (PID: $REDIS_PID)..."
        redis-cli shutdown 2>/dev/null || true
    fi
    
    log "Cleanup complete"
    echo ""
    echo -e "${YELLOW}Services stopped. Check log files for any errors.${NC}"
    echo ""
    exit 0
}

# Set trap for cleanup on script exit
trap cleanup EXIT INT TERM

log "Starting Smart iInvoice application..."

# ============================================================================
# Step 1: Check if setup was run
# ============================================================================
log "Step 1: Checking if setup was completed..."

if [ ! -d "venv" ]; then
    error "Virtual environment not found!"
    log "Please run ./setup.sh first to set up the project"
    exit 1
fi

if [ ! -f ".env" ]; then
    warning ".env file not found!"
    log "Creating from .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env >> "$LOG_FILE" 2>&1
        warning "Please edit .env file with your API keys before continuing"
        read -p "Press Enter to continue after editing .env file..."
    else
        error "Neither .env nor .env.example found!"
        exit 1
    fi
fi

success "Setup verification passed"

# ============================================================================
# Step 2: Activate Virtual Environment
# ============================================================================
log "Step 2: Activating virtual environment..."

source venv/bin/activate
if [ $? -ne 0 ]; then
    error "Failed to activate virtual environment!"
    exit 1
fi
success "Virtual environment activated"

# ============================================================================
# Step 3: Check Redis
# ============================================================================
log "Step 3: Checking Redis server..."

REDIS_RUNNING=0
REDIS_STARTED_BY_SCRIPT=0

redis-cli ping &> /dev/null
if [ $? -ne 0 ]; then
    warning "Redis is not running!"
    log "Attempting to start Redis..."
    
    # Try to start Redis in background
    REDIS_LOG="logs/redis_${TIMESTAMP}.log"
    redis-server --daemonize yes --logfile "$REDIS_LOG" --port 6379 &> /dev/null
    
    # Wait a moment for Redis to start
    sleep 2
    
    # Check again
    redis-cli ping &> /dev/null
    if [ $? -ne 0 ]; then
        warning "Could not start Redis automatically"
        log "Celery features will be disabled"
        log "To enable Celery, start Redis manually: redis-server"
    else
        REDIS_RUNNING=1
        REDIS_STARTED_BY_SCRIPT=1
        REDIS_PID=$(pgrep redis-server)
        success "Redis started successfully (PID: $REDIS_PID)"
        log "Redis log: $REDIS_LOG"
    fi
else
    REDIS_RUNNING=1
    REDIS_PID=$(pgrep redis-server)
    success "Redis is already running (PID: $REDIS_PID)"
fi

# ============================================================================
# Step 4: Start GST Verification Service
# ============================================================================
log "Step 4: Starting GST Verification Service..."

GST_LOG="logs/gst_service_${TIMESTAMP}.log"
log "GST Service log: $GST_LOG"

# Check if GST service directory exists
if [ -d "gst verification template" ]; then
    # Start real GST service (connects to government portal)
    cd "gst verification template"
    python app.py > "../$GST_LOG" 2>&1 &
    GST_PID=$!
    cd ..
    
    # Wait for GST service to start
    sleep 3
    
    # Check if GST service is running
    if ps -p $GST_PID > /dev/null; then
        # Try to connect to GST service
        curl -s http://127.0.0.1:5001 &> /dev/null
        if [ $? -eq 0 ]; then
            success "GST Verification Service started (PID: $GST_PID)"
            log "GST Service logs: $GST_LOG"
            log "Using REAL GST verification (connects to government portal)"
        else
            warning "GST service started but may not be responding yet"
            log "Check $GST_LOG for details"
            log "Note: Real GST service connects to government portal"
            log "If you experience timeouts, edit run.sh to use app_mock.py instead"
        fi
    else
        warning "GST service failed to start"
        log "Check $GST_LOG for details"
        GST_PID=""
    fi
else
    warning "GST verification template directory not found"
    log "GST verification features will not be available"
    GST_PID=""
fi

# ============================================================================
# Step 5: Start Celery Worker (if Redis is running)
# ============================================================================
if [ $REDIS_RUNNING -eq 1 ]; then
    log "Step 5: Starting Celery worker..."
    
    CELERY_LOG="logs/celery_${TIMESTAMP}.log"
    log "Celery log: $CELERY_LOG"
    
    # Start Celery in background
    celery -A smart_invoice worker --loglevel=info > "$CELERY_LOG" 2>&1 &
    CELERY_PID=$!
    
    # Wait for Celery to start
    sleep 3
    
    # Check if Celery is still running
    if ps -p $CELERY_PID > /dev/null; then
        success "Celery worker started (PID: $CELERY_PID)"
        log "Celery logs: $CELERY_LOG"
    else
        warning "Celery worker failed to start"
        log "Check $CELERY_LOG for details"
        CELERY_PID=""
    fi
else
    log "Step 5: Skipping Celery (Redis not available)"
fi

# ============================================================================
# Step 6: Run Database Migrations (if needed)
# ============================================================================
log "Step 6: Checking for pending migrations..."

python manage.py migrate --check &> /dev/null
if [ $? -ne 0 ]; then
    warning "Pending migrations detected, applying..."
    python manage.py migrate >> "$LOG_FILE" 2>&1
    if [ $? -ne 0 ]; then
        error "Migration failed!"
        log "Check $LOG_FILE for details"
    else
        success "Migrations applied"
    fi
else
    success "Database is up to date"
fi

# ============================================================================
# Step 7: Start Django Development Server
# ============================================================================
log "Step 7: Starting Django development server..."

DJANGO_LOG="logs/django_${TIMESTAMP}.log"
log "Django log: $DJANGO_LOG"

# Start Django in background
python manage.py runserver 8000 > "$DJANGO_LOG" 2>&1 &
DJANGO_PID=$!

# Wait for Django to start
log "Waiting for Django server to start..."
sleep 5

# Check if Django is running
if ps -p $DJANGO_PID > /dev/null; then
    # Try to connect to Django
    curl -s http://127.0.0.1:8000 &> /dev/null
    if [ $? -eq 0 ]; then
        success "Django server started successfully (PID: $DJANGO_PID)"
    else
        warning "Django server started but may not be responding yet"
        log "Check $DJANGO_LOG for details"
    fi
else
    error "Django server failed to start!"
    log "Check $DJANGO_LOG for details"
    exit 1
fi

# ============================================================================
# Step 8: Open Browser
# ============================================================================
log "Step 8: Opening application in browser..."

sleep 2

# Detect OS and open browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open http://127.0.0.1:8000
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v xdg-open &> /dev/null; then
        xdg-open http://127.0.0.1:8000 &> /dev/null
    elif command -v gnome-open &> /dev/null; then
        gnome-open http://127.0.0.1:8000 &> /dev/null
    else
        log "Could not detect browser opener. Please open http://127.0.0.1:8000 manually"
    fi
else
    log "Unknown OS. Please open http://127.0.0.1:8000 manually"
fi

success "Browser opened"

# ============================================================================
# Display Running Services
# ============================================================================
echo ""
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}              Smart iInvoice is now running!${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo ""
echo -e "${CYAN}Running Services:${NC}"
echo ""
echo -e "   ${GREEN}✓${NC} Django Server:    http://127.0.0.1:8000 (PID: $DJANGO_PID)"
if [ ! -z "$GST_PID" ]; then
    echo -e "   ${GREEN}✓${NC} GST Service:      http://127.0.0.1:5001 (PID: $GST_PID)"
else
    echo -e "   ${YELLOW}✗${NC} GST Service:      Not running"
fi
if [ $REDIS_RUNNING -eq 1 ]; then
    echo -e "   ${GREEN}✓${NC} Redis Server:     localhost:6379 (PID: $REDIS_PID)"
    if [ ! -z "$CELERY_PID" ]; then
        echo -e "   ${GREEN}✓${NC} Celery Worker:    Running (PID: $CELERY_PID)"
    fi
else
    echo -e "   ${YELLOW}✗${NC} Redis Server:     Not running"
    echo -e "   ${YELLOW}✗${NC} Celery Worker:    Disabled"
fi
echo ""
echo -e "${CYAN}Log Files:${NC}"
echo "   - Main log:      $LOG_FILE"
echo "   - Django log:    $DJANGO_LOG"
if [ ! -z "$GST_PID" ]; then
    echo "   - GST log:       $GST_LOG"
fi
if [ $REDIS_RUNNING -eq 1 ]; then
    if [ ! -z "$CELERY_PID" ]; then
        echo "   - Celery log:    $CELERY_LOG"
    fi
    if [ "$REDIS_STARTED_BY_SCRIPT" = "1" ]; then
        echo "   - Redis log:     $REDIS_LOG"
    fi
fi
echo ""
echo -e "${CYAN}Useful URLs:${NC}"
echo "   - Application:   http://127.0.0.1:8000"
echo "   - Admin Panel:   http://127.0.0.1:8000/admin"
echo "   - Dashboard:     http://127.0.0.1:8000/"
echo ""
echo -e "${YELLOW}To stop all services:${NC}"
echo "   Press Ctrl+C in this terminal"
echo ""
echo -e "${BLUE}Monitoring services... Press Ctrl+C to stop${NC}"
echo ""

# ============================================================================
# Monitor Services
# ============================================================================
log "Monitoring services... Press Ctrl+C to exit"

while true; do
    sleep 10
    
    # Check Django
    if ! ps -p $DJANGO_PID > /dev/null; then
        error "Django server stopped unexpectedly!"
        log "Check $DJANGO_LOG for details"
        break
    fi
    
    # Check Celery (if it was running)
    if [ ! -z "$CELERY_PID" ]; then
        if ! ps -p $CELERY_PID > /dev/null; then
            warning "Celery worker stopped!"
            log "Check $CELERY_LOG for details"
            CELERY_PID=""
        fi
    fi
    
    # Check Redis (if it was running)
    if [ $REDIS_RUNNING -eq 1 ]; then
        redis-cli ping &> /dev/null
        if [ $? -ne 0 ]; then
            warning "Redis server stopped!"
            REDIS_RUNNING=0
        fi
    fi
done

# Cleanup will be called automatically by trap
