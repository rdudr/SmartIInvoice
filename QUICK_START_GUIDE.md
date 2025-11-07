# Smart iInvoice - Quick Start Guide

## 🚀 One-Command Setup and Run

This guide will help you get Smart iInvoice up and running in minutes using our automated scripts.

---

## 📋 Prerequisites

### Windows
- **Python 3.8+** - [Download](https://www.python.org/downloads/)
- **Redis** (Optional, for Celery) - [Download](https://github.com/microsoftarchive/redis/releases) or use Docker
- **Git** (to clone the repository)

### Linux/Mac
- **Python 3.8+** - Usually pre-installed, or install via package manager
- **Redis** (Optional, for Celery) - Install via package manager
- **Git** (to clone the repository)

---

## 🪟 Windows Setup

### Step 1: Initial Setup (One-Time)

Open Command Prompt or PowerShell in the project directory and run:

```cmd
setup.bat
```

**What it does:**
- ✅ Checks Python installation
- ✅ Checks/installs Redis (optional)
- ✅ Creates Python virtual environment
- ✅ Installs all dependencies
- ✅ Sets up environment variables (.env)
- ✅ Runs database migrations
- ✅ Collects static files
- ✅ Optionally creates superuser account
- ✅ Verifies installation

**Duration:** 5-10 minutes (depending on internet speed)

**Log File:** `logs/setup_YYYYMMDD_HHMMSS.log`

### Step 2: Configure API Keys

Edit the `.env` file and add your API keys:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### Step 3: Run the Application

```cmd
run.bat
```

**What it does:**
- ✅ Activates virtual environment
- ✅ Starts Redis (if available)
- ✅ Starts Celery worker (if Redis is running)
- ✅ Runs database migrations (if needed)
- ✅ Starts Django development server
- ✅ Opens browser automatically to http://127.0.0.1:8000
- ✅ Monitors all services

**Log Files:**
- Main: `logs/run_YYYYMMDD_HHMMSS.log`
- Django: `logs/django_YYYYMMDD_HHMMSS.log`
- Celery: `logs/celery_YYYYMMDD_HHMMSS.log`
- Redis: `logs/redis_YYYYMMDD_HHMMSS.log`

### Step 4: Stop the Application

Press `Ctrl+C` in the terminal, or close the terminal window.

---

## 🐧 Linux/Mac Setup

### Step 1: Make Scripts Executable

```bash
chmod +x setup.sh run.sh
```

### Step 2: Initial Setup (One-Time)

```bash
./setup.sh
```

**What it does:**
- ✅ Checks Python installation
- ✅ Checks/installs Redis (optional)
- ✅ Creates Python virtual environment
- ✅ Installs all dependencies
- ✅ Sets up environment variables (.env)
- ✅ Runs database migrations
- ✅ Collects static files
- ✅ Optionally creates superuser account
- ✅ Verifies installation

**Duration:** 5-10 minutes (depending on internet speed)

**Log File:** `logs/setup_YYYYMMDD_HHMMSS.log`

### Step 3: Configure API Keys

Edit the `.env` file and add your API keys:

```bash
nano .env
# or
vim .env
# or use your favorite editor
```

Add:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### Step 4: Run the Application

```bash
./run.sh
```

**What it does:**
- ✅ Activates virtual environment
- ✅ Starts Redis (if available)
- ✅ Starts Celery worker (if Redis is running)
- ✅ Runs database migrations (if needed)
- ✅ Starts Django development server
- ✅ Opens browser automatically to http://127.0.0.1:8000
- ✅ Monitors all services

**Log Files:**
- Main: `logs/run_YYYYMMDD_HHMMSS.log`
- Django: `logs/django_YYYYMMDD_HHMMSS.log`
- Celery: `logs/celery_YYYYMMDD_HHMMSS.log`
- Redis: `logs/redis_YYYYMMDD_HHMMSS.log`

### Step 5: Stop the Application

Press `Ctrl+C` in the terminal.

---

## 🔧 Troubleshooting

### Issue: "Python not found"

**Windows:**
1. Download Python from https://www.python.org/downloads/
2. During installation, check "Add Python to PATH"
3. Restart Command Prompt and try again

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo apt-get install python3 python3-pip python3-venv

# macOS
brew install python3

# Fedora
sudo dnf install python3 python3-pip
```

### Issue: "Redis not found"

**Windows:**
- Download from: https://github.com/microsoftarchive/redis/releases
- Or use Docker: `docker run -d -p 6379:6379 redis`
- Or use WSL: `wsl -d Ubuntu sudo service redis-server start`

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis-server

# Fedora
sudo dnf install redis
sudo systemctl start redis
```

**macOS:**
```bash
brew install redis
brew services start redis
```

### Issue: "Port 8000 already in use"

**Windows:**
```cmd
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**Linux/Mac:**
```bash
lsof -ti:8000 | xargs kill -9
```

### Issue: "Permission denied" (Linux/Mac)

```bash
chmod +x setup.sh run.sh
```

### Issue: "Virtual environment activation failed"

**Windows:**
```cmd
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### Issue: "Database locked"

Stop all running instances and delete `db.sqlite3`, then run setup again:

```bash
# Linux/Mac
rm db.sqlite3
./setup.sh

# Windows
del db.sqlite3
setup.bat
```

---

## 📊 Log Files

All operations are logged for debugging:

### Log Directory Structure
```
logs/
├── setup_YYYYMMDD_HHMMSS.log      # Setup script logs
├── run_YYYYMMDD_HHMMSS.log        # Main run script logs
├── django_YYYYMMDD_HHMMSS.log     # Django server logs
├── celery_YYYYMMDD_HHMMSS.log     # Celery worker logs
└── redis_YYYYMMDD_HHMMSS.log      # Redis server logs
```

### Viewing Logs

**Windows:**
```cmd
type logs\django_YYYYMMDD_HHMMSS.log
```

**Linux/Mac:**
```bash
tail -f logs/django_YYYYMMDD_HHMMSS.log
```

---

## 🌐 Accessing the Application

Once running, access these URLs:

- **Main Application:** http://127.0.0.1:8000
- **Admin Panel:** http://127.0.0.1:8000/admin
- **Dashboard:** http://127.0.0.1:8000/
- **API Documentation:** http://127.0.0.1:8000/api/docs (if enabled)

---

## 👤 Creating Admin User

### During Setup
The setup script will ask if you want to create a superuser. Answer 'y' and follow prompts.

### After Setup

**Windows:**
```cmd
venv\Scripts\activate
python manage.py createsuperuser
```

**Linux/Mac:**
```bash
source venv/bin/activate
python manage.py createsuperuser
```

---

## 🔄 Updating the Application

### Pull Latest Changes
```bash
git pull origin main
```

### Update Dependencies

**Windows:**
```cmd
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
```

**Linux/Mac:**
```bash
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
```

Or simply run `setup.bat` / `./setup.sh` again.

---

## 🧪 Running Tests

**Windows:**
```cmd
venv\Scripts\activate
python manage.py test
```

**Linux/Mac:**
```bash
source venv/bin/activate
python manage.py test
```

---

## 🐳 Docker Alternative (Optional)

If you prefer Docker:

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## 📝 Manual Commands

If you prefer manual control:

### Activate Virtual Environment

**Windows:**
```cmd
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### Start Services Manually

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Celery
celery -A smart_invoice worker --loglevel=info

# Terminal 3: Django
python manage.py runserver
```

---

## 🎯 Quick Reference

### First Time Setup
```bash
# Windows
setup.bat

# Linux/Mac
chmod +x setup.sh && ./setup.sh
```

### Run Application
```bash
# Windows
run.bat

# Linux/Mac
./run.sh
```

### Stop Application
```
Press Ctrl+C
```

### View Logs
```bash
# Windows
type logs\django_*.log

# Linux/Mac
tail -f logs/django_*.log
```

---

## 🆘 Getting Help

1. **Check Logs:** All operations are logged in the `logs/` directory
2. **Read Error Messages:** Scripts provide detailed error messages
3. **Check Documentation:** See README.md for detailed information
4. **GitHub Issues:** Report bugs at [repository URL]

---

## ✅ Success Indicators

When everything is working correctly, you should see:

```
============================================================================
              Smart iInvoice is now running!
============================================================================

Running Services:
   ✓ Django Server:    http://127.0.0.1:8000
   ✓ Redis Server:     localhost:6379
   ✓ Celery Worker:    Running in background

Useful URLs:
   - Application:   http://127.0.0.1:8000
   - Admin Panel:   http://127.0.0.1:8000/admin
   - Dashboard:     http://127.0.0.1:8000/
```

---

## 🎉 You're All Set!

Your Smart iInvoice application is now running. Open http://127.0.0.1:8000 in your browser to get started!

For detailed feature documentation, see the main README.md file.
