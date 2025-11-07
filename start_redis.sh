#!/bin/bash
# Redis Server Startup Script for Unix/Linux/macOS
# This script starts Redis server for Celery message broker

echo "Starting Redis Server..."
echo ""
echo "Note: You need to have Redis installed on your system."
echo "Install with: sudo apt-get install redis-server (Ubuntu/Debian)"
echo "Or: brew install redis (macOS)"
echo ""

# Start Redis server
redis-server

# For production, you might want to use a configuration file:
# redis-server /path/to/redis.conf
