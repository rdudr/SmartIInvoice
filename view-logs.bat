@echo off
REM ============================================================================
REM Smart iInvoice - Log Viewer (Windows)
REM ============================================================================

setlocal enabledelayedexpansion

set "GREEN=[92m"
set "CYAN=[96m"
set "YELLOW=[93m"
set "NC=[0m"

echo %CYAN%============================================================================%NC%
echo %CYAN%           Smart iInvoice - Log Viewer%NC%
echo %CYAN%============================================================================%NC%
echo.

if not exist "logs" (
    echo %YELLOW%No logs directory found. Run setup.bat or run.bat first.%NC%
    pause
    exit /b 1
)

echo Available log files:
echo.
dir /b /o-d logs\*.log 2>nul

if errorlevel 1 (
    echo %YELLOW%No log files found.%NC%
    pause
    exit /b 1
)

echo.
echo %GREEN%Select log type to view:%NC%
echo.
echo 1. Latest setup log
echo 2. Latest run log
echo 3. Latest Django log
echo 4. Latest GST service log
echo 5. Latest Celery log
echo 6. Latest Redis log
echo 7. All logs (combined)
echo 8. Exit
echo.

set /p CHOICE="Enter choice (1-8): "

if "%CHOICE%"=="1" (
    for /f %%i in ('dir /b /o-d logs\setup_*.log 2^>nul') do (
        set LOGFILE=logs\%%i
        goto :show_log
    )
)

if "%CHOICE%"=="2" (
    for /f %%i in ('dir /b /o-d logs\run_*.log 2^>nul') do (
        set LOGFILE=logs\%%i
        goto :show_log
    )
)

if "%CHOICE%"=="3" (
    for /f %%i in ('dir /b /o-d logs\django_*.log 2^>nul') do (
        set LOGFILE=logs\%%i
        goto :show_log
    )
)

if "%CHOICE%"=="4" (
    for /f %%i in ('dir /b /o-d logs\gst_service_*.log 2^>nul') do (
        set LOGFILE=logs\%%i
        goto :show_log
    )
)

if "%CHOICE%"=="5" (
    for /f %%i in ('dir /b /o-d logs\celery_*.log 2^>nul') do (
        set LOGFILE=logs\%%i
        goto :show_log
    )
)

if "%CHOICE%"=="6" (
    for /f %%i in ('dir /b /o-d logs\redis_*.log 2^>nul') do (
        set LOGFILE=logs\%%i
        goto :show_log
    )
)

if "%CHOICE%"=="7" (
    echo.
    echo %CYAN%Showing all logs (most recent first):%NC%
    echo.
    for /f %%i in ('dir /b /o-d logs\*.log') do (
        echo %GREEN%=== %%i ===%NC%
        type logs\%%i
        echo.
    )
    pause
    exit /b 0
)

if "%CHOICE%"=="8" (
    exit /b 0
)

echo Invalid choice.
pause
exit /b 1

:show_log
if not defined LOGFILE (
    echo %YELLOW%No log file found for this type.%NC%
    pause
    exit /b 1
)

echo.
echo %CYAN%Viewing: %LOGFILE%%NC%
echo.
type "%LOGFILE%"
echo.
pause
exit /b 0
