@echo off
REM ============================================================================
REM Smart iInvoice - Windows Setup Script
REM ============================================================================
REM This script sets up the entire project environment including:
REM - Python virtual environment
REM - All dependencies
REM - Database migrations
REM - Redis installation check
REM - Environment configuration
REM ============================================================================

setlocal enabledelayedexpansion

REM Set colors for output
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

REM Create logs directory
if not exist "logs" mkdir logs

REM Set log file with timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set LOG_FILE=logs\setup_%datetime:~0,8%_%datetime:~8,6%.log

echo %BLUE%============================================================================%NC%
echo %BLUE%           Smart iInvoice - Automated Setup Script%NC%
echo %BLUE%============================================================================%NC%
echo.
echo Log file: %LOG_FILE%
echo.

REM Redirect all output to log file while also displaying on screen
call :log "Starting setup process..."

REM ============================================================================
REM Step 1: Check Python Installation
REM ============================================================================
call :log "Step 1: Checking Python installation..."

python --version >nul 2>&1
if errorlevel 1 (
    call :error "Python is not installed or not in PATH!"
    call :log "Please install Python 3.8 or higher from https://www.python.org/"
    call :log "Make sure to check 'Add Python to PATH' during installation"
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
call :success "Python %PYTHON_VERSION% found"

REM ============================================================================
REM Step 2: Check/Install Redis
REM ============================================================================
call :log "Step 2: Checking Redis installation..."

redis-server --version >nul 2>&1
if errorlevel 1 (
    call :warning "Redis is not installed!"
    call :log "Redis is required for Celery task queue."
    call :log ""
    call :log "Installation options:"
    call :log "1. Download Redis for Windows from: https://github.com/microsoftarchive/redis/releases"
    call :log "2. Or use WSL (Windows Subsystem for Linux) to run Redis"
    call :log "3. Or use Docker: docker run -d -p 6379:6379 redis"
    call :log ""
    
    set /p CONTINUE="Do you want to continue without Redis? (Celery won't work) [y/N]: "
    if /i not "!CONTINUE!"=="y" (
        call :log "Setup cancelled. Please install Redis and run setup again."
        pause
        exit /b 1
    )
    call :warning "Continuing without Redis - Celery features will be disabled"
) else (
    for /f "tokens=*" %%i in ('redis-server --version 2^>^&1') do set REDIS_VERSION=%%i
    call :success "Redis found: !REDIS_VERSION!"
)

REM ============================================================================
REM Step 3: Create Virtual Environment
REM ============================================================================
call :log "Step 3: Setting up Python virtual environment..."

if exist "venv" (
    call :warning "Virtual environment already exists. Skipping creation."
) else (
    call :log "Creating virtual environment..."
    python -m venv venv >> "%LOG_FILE%" 2>&1
    if errorlevel 1 (
        call :error "Failed to create virtual environment!"
        pause
        exit /b 1
    )
    call :success "Virtual environment created"
)

REM Activate virtual environment
call :log "Activating virtual environment..."
call venv\Scripts\activate.bat
if errorlevel 1 (
    call :error "Failed to activate virtual environment!"
    pause
    exit /b 1
)
call :success "Virtual environment activated"

REM ============================================================================
REM Step 4: Upgrade pip
REM ============================================================================
call :log "Step 4: Upgrading pip..."
python -m pip install --upgrade pip >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :warning "Failed to upgrade pip, continuing anyway..."
) else (
    call :success "pip upgraded successfully"
)

REM ============================================================================
REM Step 5: Install Python Dependencies
REM ============================================================================
call :log "Step 5: Installing Python dependencies..."

if not exist "requirements.txt" (
    call :error "requirements.txt not found!"
    pause
    exit /b 1
)

call :log "This may take several minutes..."
pip install -r requirements.txt >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :error "Failed to install dependencies!"
    call :log "Check %LOG_FILE% for details"
    pause
    exit /b 1
)
call :success "All dependencies installed successfully"

REM ============================================================================
REM Step 6: Setup Environment Variables
REM ============================================================================
call :log "Step 6: Setting up environment variables..."

if not exist ".env" (
    if exist ".env.example" (
        call :log "Creating .env file from .env.example..."
        copy .env.example .env >> "%LOG_FILE%" 2>&1
        call :warning ".env file created. Please edit it with your API keys!"
        call :log "Required: GEMINI_API_KEY"
        call :log "Optional: REDIS_URL, CELERY_BROKER_URL"
    ) else (
        call :error ".env.example not found!"
        call :log "Please create a .env file manually with required configuration"
    )
) else (
    call :success ".env file already exists"
)

REM ============================================================================
REM Step 7: Database Setup
REM ============================================================================
call :log "Step 7: Setting up database..."

REM Check if migrations exist
if not exist "invoice_processor\migrations" (
    call :log "Creating migrations directory..."
    mkdir invoice_processor\migrations
    type nul > invoice_processor\migrations\__init__.py
)

REM Make migrations
call :log "Creating database migrations..."
python manage.py makemigrations >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :warning "makemigrations had issues, continuing..."
)

REM Run migrations
call :log "Applying database migrations..."
python manage.py migrate >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :error "Failed to apply migrations!"
    call :log "Check %LOG_FILE% for details"
    pause
    exit /b 1
)
call :success "Database migrations completed"

REM ============================================================================
REM Step 8: Collect Static Files
REM ============================================================================
call :log "Step 8: Collecting static files..."

python manage.py collectstatic --noinput >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :warning "Failed to collect static files, continuing..."
) else (
    call :success "Static files collected"
)

REM ============================================================================
REM Step 9: Create Superuser (Optional)
REM ============================================================================
call :log "Step 9: Creating superuser account..."

set /p CREATE_SUPERUSER="Do you want to create a superuser account now? [y/N]: "
if /i "!CREATE_SUPERUSER!"=="y" (
    call :log "Creating superuser..."
    python manage.py createsuperuser
    if errorlevel 1 (
        call :warning "Superuser creation skipped or failed"
    ) else (
        call :success "Superuser created successfully"
    )
) else (
    call :log "Skipping superuser creation. You can create one later with: python manage.py createsuperuser"
)

REM ============================================================================
REM Step 10: Setup GST Verification Service
REM ============================================================================
call :log "Step 10: Setting up GST Verification Service..."

if exist "gst verification template" (
    call :log "Installing GST service dependencies..."
    pip install flask uvicorn asgiref pillow >> "%LOG_FILE%" 2>&1
    if errorlevel 1 (
        call :warning "Failed to install GST service dependencies"
    ) else (
        call :success "GST service dependencies installed"
    )
) else (
    call :warning "GST verification template directory not found"
)

REM ============================================================================
REM Step 11: Verify Installation
REM ============================================================================
call :log "Step 11: Verifying installation..."

call :log "Checking Django installation..."
python -c "import django; print('Django version:', django.get_version())" >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :error "Django verification failed!"
) else (
    call :success "Django verified"
)

call :log "Checking Celery installation..."
celery --version >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :warning "Celery verification failed"
) else (
    call :success "Celery verified"
)

call :log "Running Django system check..."
python manage.py check >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    call :warning "Django system check found issues (check log)"
) else (
    call :success "Django system check passed"
)

REM ============================================================================
REM Setup Complete
REM ============================================================================
echo.
echo %GREEN%============================================================================%NC%
echo %GREEN%                    Setup Completed Successfully!%NC%
echo %GREEN%============================================================================%NC%
echo.
call :log "Setup completed successfully!"
echo %YELLOW%Next steps:%NC%
echo.
echo 1. Edit .env file with your API keys (especially GEMINI_API_KEY)
echo 2. Make sure Redis is running (if you want Celery features)
echo 3. Run the project using: run.bat
echo.
echo %BLUE%Useful commands:%NC%
echo   - Start project: run.bat
echo   - Create superuser: python manage.py createsuperuser
echo   - Run tests: python manage.py test
echo.
echo Full setup log saved to: %LOG_FILE%
echo.
pause
exit /b 0

REM ============================================================================
REM Helper Functions
REM ============================================================================

:log
echo [%date% %time%] %~1
echo [%date% %time%] %~1 >> "%LOG_FILE%" 2>&1
exit /b 0

:success
echo %GREEN%[SUCCESS]%NC% %~1
echo [%date% %time%] [SUCCESS] %~1 >> "%LOG_FILE%" 2>&1
exit /b 0

:error
echo %RED%[ERROR]%NC% %~1
echo [%date% %time%] [ERROR] %~1 >> "%LOG_FILE%" 2>&1
exit /b 0

:warning
echo %YELLOW%[WARNING]%NC% %~1
echo [%date% %time%] [WARNING] %~1 >> "%LOG_FILE%" 2>&1
exit /b 0
