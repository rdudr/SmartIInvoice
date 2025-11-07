@echo off
REM ============================================================================
REM Smart iInvoice - Windows Run Script
REM ============================================================================
REM This script starts all required services and opens the application:
REM - Redis server (if available)
REM - Celery worker
REM - Django development server
REM - Opens browser automatically
REM ============================================================================

setlocal enabledelayedexpansion

REM Set colors for output
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "CYAN=[96m"
set "NC=[0m"

REM Create logs directory
if not exist "logs" mkdir logs

REM Set log file with timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set LOG_FILE=logs\run_%datetime:~0,8%_%datetime:~8,6%.log

echo %CYAN%============================================================================%NC%
echo %CYAN%           Smart iInvoice - Application Launcher%NC%
echo %CYAN%============================================================================%NC%
echo.
echo Log file: %LOG_FILE%
echo.

call :log "Starting Smart iInvoice application..."

REM ============================================================================
REM Step 1: Check if setup was run
REM ============================================================================
call :log "Step 1: Checking if setup was completed..."

if not exist "venv" (
    call :error "Virtual environment not found!"
    call :log "Please run setup.bat first to set up the project"
    pause
    exit /b 1
)

if not exist ".env" (
    call :warning ".env file not found!"
    call :log "Creating from .env.example..."
    if exist ".env.example" (
        copy .env.example .env >> "%LOG_FILE%" 2>&1
        call :warning "Please edit .env file with your API keys before continuing"
        pause
    ) else (
        call :error "Neither .env nor .env.example found!"
        pause
        exit /b 1
    )
)

call :success "Setup verification passed"

REM ============================================================================
REM Step 2: Activate Virtual Environment
REM ============================================================================
call :log "Step 2: Activating virtual environment..."

call venv\Scripts\activate.bat
if errorlevel 1 (
    call :error "Failed to activate virtual environment!"
    pause
    exit /b 1
)
call :success "Virtual environment activated"

REM ============================================================================
REM Step 3: Check Redis
REM ============================================================================
call :log "Step 3: Checking Redis server..."

set REDIS_RUNNING=0
redis-cli ping >nul 2>&1
if errorlevel 1 (
    call :warning "Redis is not running!"
    call :log "Attempting to start Redis..."
    
    REM Try to start Redis in background
    start /B redis-server --port 6379 >> "logs\redis_%datetime:~0,8%_%datetime:~8,6%.log" 2>&1
    
    REM Wait a moment for Redis to start
    timeout /t 2 /nobreak >nul
    
    REM Check again
    redis-cli ping >nul 2>&1
    if errorlevel 1 (
        call :warning "Could not start Redis automatically"
        call :log "Celery features will be disabled"
        call :log "To enable Celery, start Redis manually: redis-server"
    ) else (
        set REDIS_RUNNING=1
        call :success "Redis started successfully"
    )
) else (
    set REDIS_RUNNING=1
    call :success "Redis is already running"
)

REM ============================================================================
REM Step 4: Start GST Verification Service
REM ============================================================================
call :log "Step 4: Starting GST Verification Service..."

set GST_LOG=logs\gst_service_%datetime:~0,8%_%datetime:~8,6%.log
call :log "GST Service log: !GST_LOG!"

REM Check if GST service directory exists
if exist "gst verification template" (
    REM Start mock GST service (recommended for development)
    start "GST Service" cmd /c "cd "gst verification template" && ..\venv\Scripts\activate.bat && python app_mock.py > ..\!GST_LOG! 2>&1"
    
    REM Wait for GST service to start
    timeout /t 3 /nobreak >nul
    
    REM Check if GST service is running
    curl -s http://127.0.0.1:5001/health >nul 2>&1
    if errorlevel 1 (
        call :warning "GST service may not have started properly"
        call :log "Check !GST_LOG! for details"
    ) else (
        call :success "GST Verification Service started on port 5001"
        call :log "GST Service logs: !GST_LOG!"
    )
) else (
    call :warning "GST verification template directory not found"
    call :log "GST verification features will not be available"
)

REM ============================================================================
REM Step 5: Start Celery Worker (if Redis is running)
REM ============================================================================
if !REDIS_RUNNING!==1 (
    call :log "Step 5: Starting Celery worker..."
    
    set CELERY_LOG=logs\celery_%datetime:~0,8%_%datetime:~8,6%.log
    call :log "Celery log: !CELERY_LOG!"
    
    start "Celery Worker" cmd /c "venv\Scripts\activate.bat && celery -A smart_invoice worker --loglevel=info --pool=solo > !CELERY_LOG! 2>&1"
    
    REM Wait for Celery to start
    timeout /t 3 /nobreak >nul
    
    call :success "Celery worker started in background"
    call :log "Celery logs: !CELERY_LOG!"
) else (
    call :log "Step 5: Skipping Celery (Redis not available)"
)

REM ============================================================================
REM Step 6: Run Database Migrations (if needed)
REM ============================================================================
call :log "Step 6: Checking for pending migrations..."

python manage.py migrate --check >nul 2>&1
if errorlevel 1 (
    call :warning "Pending migrations detected, applying..."
    python manage.py migrate >> "%LOG_FILE%" 2>&1
    if errorlevel 1 (
        call :error "Migration failed!"
        call :log "Check %LOG_FILE% for details"
    ) else (
        call :success "Migrations applied"
    )
) else (
    call :success "Database is up to date"
)

REM ============================================================================
REM Step 7: Start Django Development Server
REM ============================================================================
call :log "Step 7: Starting Django development server..."

set DJANGO_LOG=logs\django_%datetime:~0,8%_%datetime:~8,6%.log
call :log "Django log: !DJANGO_LOG!"

REM Start Django in a new window
start "Django Server" cmd /c "venv\Scripts\activate.bat && python manage.py runserver 8000 > !DJANGO_LOG! 2>&1"

REM Wait for Django to start
call :log "Waiting for Django server to start..."
timeout /t 5 /nobreak >nul

REM Check if Django is running
curl -s http://127.0.0.1:8000 >nul 2>&1
if errorlevel 1 (
    call :warning "Django server may not have started properly"
    call :log "Check !DJANGO_LOG! for details"
) else (
    call :success "Django server started successfully"
)

REM ============================================================================
REM Step 8: Open Browser
REM ============================================================================
call :log "Step 8: Opening application in browser..."

timeout /t 2 /nobreak >nul
start http://127.0.0.1:8000

call :success "Browser opened"

REM ============================================================================
REM Display Running Services
REM ============================================================================
echo.
echo %GREEN%============================================================================%NC%
echo %GREEN%              Smart iInvoice is now running!%NC%
echo %GREEN%============================================================================%NC%
echo.
echo %CYAN%Running Services:%NC%
echo.
echo   %GREEN%✓%NC% Django Server:    http://127.0.0.1:8000
echo   %GREEN%✓%NC% GST Service:      http://127.0.0.1:5001
if !REDIS_RUNNING!==1 (
    echo   %GREEN%✓%NC% Redis Server:     localhost:6379
    echo   %GREEN%✓%NC% Celery Worker:    Running in background
) else (
    echo   %YELLOW%✗%NC% Redis Server:     Not running
    echo   %YELLOW%✗%NC% Celery Worker:    Disabled
)
echo.
echo %CYAN%Log Files:%NC%
echo   - Main log:      %LOG_FILE%
echo   - Django log:    !DJANGO_LOG!
echo   - GST log:       !GST_LOG!
if !REDIS_RUNNING!==1 (
    echo   - Celery log:    !CELERY_LOG!
    echo   - Redis log:     logs\redis_%datetime:~0,8%_%datetime:~8,6%.log
)
echo.
echo %CYAN%Useful URLs:%NC%
echo   - Application:   http://127.0.0.1:8000
echo   - Admin Panel:   http://127.0.0.1:8000/admin
echo   - Dashboard:     http://127.0.0.1:8000/
echo.
echo %YELLOW%To stop all services:%NC%
echo   1. Close this window
echo   2. Close the "Django Server" window
echo   3. Close the "GST Service" window
if !REDIS_RUNNING!==1 (
    echo   4. Close the "Celery Worker" window
    echo   5. Stop Redis: redis-cli shutdown
)
echo.
echo %BLUE%Press Ctrl+C to stop monitoring (services will continue running)%NC%
echo.

REM ============================================================================
REM Monitor Services
REM ============================================================================
call :log "Monitoring services... Press Ctrl+C to exit"

:monitor_loop
timeout /t 10 /nobreak >nul

REM Check Django
curl -s http://127.0.0.1:8000 >nul 2>&1
if errorlevel 1 (
    call :error "Django server stopped!"
    goto :cleanup
)

REM Check Redis (if it was running)
if !REDIS_RUNNING!==1 (
    redis-cli ping >nul 2>&1
    if errorlevel 1 (
        call :warning "Redis server stopped!"
    )
)

goto :monitor_loop

REM ============================================================================
REM Cleanup
REM ============================================================================
:cleanup
call :log "Shutting down services..."

REM Try to stop GST Service gracefully
taskkill /FI "WINDOWTITLE eq GST Service*" /T /F >nul 2>&1

REM Try to stop Celery gracefully
taskkill /FI "WINDOWTITLE eq Celery Worker*" /T /F >nul 2>&1

REM Try to stop Django gracefully
taskkill /FI "WINDOWTITLE eq Django Server*" /T /F >nul 2>&1

call :log "Cleanup complete"
echo.
echo %YELLOW%Services stopped. Check log files for any errors.%NC%
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
