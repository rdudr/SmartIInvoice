@echo off
REM Redis Server Startup Script for Windows
REM This script starts Redis server for Celery message broker

echo Starting Redis Server...
echo.
echo Note: You need to have Redis installed on your system.
echo For Windows, download from: https://github.com/microsoftarchive/redis/releases
echo Or use WSL (Windows Subsystem for Linux) to run Redis.
echo.

REM If Redis is in PATH, this will start it
redis-server

REM If Redis is not in PATH, specify the full path:
REM "C:\Program Files\Redis\redis-server.exe"

pause
