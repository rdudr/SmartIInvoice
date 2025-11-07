# Smart iInvoice - Automation Scripts Documentation

## 📦 Overview

This project includes comprehensive automation scripts that handle **everything** needed to set up and run Smart iInvoice with zero manual configuration.

---

## 📁 Files Created

### Windows Scripts
1. **`setup.bat`** - Complete setup automation for Windows
2. **`run.bat`** - One-command application launcher for Windows

### Linux/Mac Scripts
3. **`setup.sh`** - Complete setup automation for Linux/Mac
4. **`run.sh`** - One-command application launcher for Linux/Mac

### Documentation
5. **`QUICK_START_GUIDE.md`** - User-friendly quick start guide
6. **`AUTOMATION_SCRIPTS_README.md`** - This file

---

## 🎯 Features

### Setup Scripts (`setup.bat` / `setup.sh`)

#### Automated Checks
- ✅ Python installation verification
- ✅ Redis availability check
- ✅ Virtual environment creation
- ✅ Dependency installation
- ✅ Environment configuration
- ✅ Database migrations
- ✅ Static files collection
- ✅ Installation verification

#### Smart Features
- 🔍 Detects missing dependencies
- 💡 Provides installation instructions
- 📝 Creates detailed log files
- ⚠️ Handles errors gracefully
- 🎨 Color-coded output
- ⏱️ Timestamps all operations
- 🔄 Idempotent (safe to run multiple times)

#### Log Output
```
logs/setup_YYYYMMDD_HHMMSS.log
```

### Run Scripts (`run.bat` / `run.sh`)

#### Automated Services
- ✅ Virtual environment activation
- ✅ Redis server startup (if available)
- ✅ Celery worker startup (if Redis available)
- ✅ Database migration check
- ✅ Django development server
- ✅ Browser auto-launch
- ✅ Service monitoring

#### Smart Features
- 🔄 Auto-starts Redis if not running
- 🔍 Monitors all services
- 📊 Real-time status display
- 🛑 Graceful shutdown on Ctrl+C
- 📝 Separate log files per service
- ⚠️ Error detection and reporting
- 🎨 Color-coded status messages

#### Log Output
```
logs/
├── run_YYYYMMDD_HHMMSS.log       # Main script log
├── django_YYYYMMDD_HHMMSS.log    # Django server log
├── celery_YYYYMMDD_HHMMSS.log    # Celery worker log
└── redis_YYYYMMDD_HHMMSS.log     # Redis server log
```

---

## 🚀 Usage

### First Time Setup

#### Windows
```cmd
setup.bat
```

#### Linux/Mac
```bash
chmod +x setup.sh
./setup.sh
```

**What happens:**
1. Checks Python 3.8+ installation
2. Checks Redis availability (optional)
3. Creates virtual environment in `venv/`
4. Upgrades pip to latest version
5. Installs all requirements from `requirements.txt`
6. Creates `.env` from `.env.example`
7. Creates database migrations
8. Applies migrations to database
9. Collects static files
10. Offers to create superuser
11. Verifies installation
12. Displays next steps

**Duration:** 5-10 minutes

### Running the Application

#### Windows
```cmd
run.bat
```

#### Linux/Mac
```bash
./run.sh
```

**What happens:**
1. Verifies setup completion
2. Activates virtual environment
3. Checks/starts Redis server
4. Starts Celery worker (if Redis available)
5. Checks for pending migrations
6. Starts Django server on port 8000
7. Opens http://127.0.0.1:8000 in browser
8. Monitors all services
9. Displays service status

**To stop:** Press `Ctrl+C`

---

## 📊 Script Architecture

### Setup Script Flow

```
┌─────────────────────────────────────┐
│  Check Python Installation          │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Check Redis (Optional)              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Create Virtual Environment          │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Install Dependencies                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Setup Environment (.env)            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Database Migrations                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Collect Static Files                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Create Superuser (Optional)         │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Verify Installation                 │
└──────────────┬──────────────────────┘
               │
               ▼
           SUCCESS!
```

### Run Script Flow

```
┌─────────────────────────────────────┐
│  Verify Setup Completion             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Activate Virtual Environment        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Check/Start Redis                   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Start Celery Worker                 │
│  (if Redis available)                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Check/Apply Migrations              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Start Django Server                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Open Browser                        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Monitor Services                    │
│  (Ctrl+C to stop)                    │
└─────────────────────────────────────┘
```

---

## 🎨 Output Examples

### Setup Script Output

```
============================================================================
           Smart iInvoice - Automated Setup Script
============================================================================

Log file: logs/setup_20241108_143022.log

[SUCCESS] Python 3.12.0 found
[SUCCESS] Redis found: Redis server v=7.0.0
[SUCCESS] Virtual environment created
[SUCCESS] Virtual environment activated
[SUCCESS] pip upgraded successfully
[SUCCESS] All dependencies installed successfully
[SUCCESS] .env file already exists
[SUCCESS] Database migrations completed
[SUCCESS] Static files collected
[SUCCESS] Superuser created successfully
[SUCCESS] Django verified
[SUCCESS] Celery verified
[SUCCESS] Django system check passed

============================================================================
                    Setup Completed Successfully!
============================================================================

Next steps:
1. Edit .env file with your API keys (especially GEMINI_API_KEY)
2. Make sure Redis is running (if you want Celery features)
3. Run the project using: run.bat

Useful commands:
  - Start project: run.bat
  - Create superuser: python manage.py createsuperuser
  - Run tests: python manage.py test
```

### Run Script Output

```
============================================================================
           Smart iInvoice - Application Launcher
============================================================================

Log file: logs/run_20241108_143530.log

[SUCCESS] Setup verification passed
[SUCCESS] Virtual environment activated
[SUCCESS] Redis is already running (PID: 12345)
[SUCCESS] Celery worker started (PID: 12346)
[SUCCESS] Database is up to date
[SUCCESS] Django server started successfully (PID: 12347)
[SUCCESS] Browser opened

============================================================================
              Smart iInvoice is now running!
============================================================================

Running Services:
   ✓ Django Server:    http://127.0.0.1:8000 (PID: 12347)
   ✓ Redis Server:     localhost:6379 (PID: 12345)
   ✓ Celery Worker:    Running (PID: 12346)

Log Files:
   - Main log:      logs/run_20241108_143530.log
   - Django log:    logs/django_20241108_143530.log
   - Celery log:    logs/celery_20241108_143530.log

Useful URLs:
   - Application:   http://127.0.0.1:8000
   - Admin Panel:   http://127.0.0.1:8000/admin
   - Dashboard:     http://127.0.0.1:8000/

To stop all services:
   Press Ctrl+C in this terminal

Monitoring services... Press Ctrl+C to stop
```

---

## 🔧 Customization

### Modifying Setup Script

Edit `setup.bat` or `setup.sh` to customize:

```bash
# Change Python version check
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')

# Add custom setup steps
log "Step X: Custom setup step..."
# Your custom commands here

# Modify dependency installation
pip install -r requirements.txt --no-cache-dir
```

### Modifying Run Script

Edit `run.bat` or `run.sh` to customize:

```bash
# Change Django port
python manage.py runserver 8080

# Add custom pre-start checks
log "Checking custom service..."
# Your custom checks here

# Modify Celery worker options
celery -A smart_invoice worker --loglevel=debug --concurrency=4
```

---

## 🐛 Debugging

### Enable Verbose Logging

**Windows:**
```cmd
set VERBOSE=1
setup.bat
```

**Linux/Mac:**
```bash
export VERBOSE=1
./setup.sh
```

### Check Specific Logs

```bash
# View Django logs
tail -f logs/django_*.log

# View Celery logs
tail -f logs/celery_*.log

# View Redis logs
tail -f logs/redis_*.log

# View setup logs
tail -f logs/setup_*.log
```

### Common Issues

#### Issue: Script fails immediately
**Solution:** Check the log file mentioned at the start of script output

#### Issue: Redis won't start
**Solution:** 
- Check if port 6379 is already in use
- Install Redis manually
- Use Docker: `docker run -d -p 6379:6379 redis`

#### Issue: Celery won't start
**Solution:**
- Ensure Redis is running
- Check Celery log file
- Try: `celery -A smart_invoice worker --loglevel=debug`

#### Issue: Django won't start
**Solution:**
- Check if port 8000 is in use
- Check Django log file
- Try: `python manage.py runserver --verbosity 3`

---

## 📈 Performance

### Setup Script
- **First run:** 5-10 minutes (downloads dependencies)
- **Subsequent runs:** 1-2 minutes (skips existing setup)

### Run Script
- **Startup time:** 10-15 seconds
- **Memory usage:** ~200-300 MB (all services)
- **CPU usage:** Low (idle), Medium (processing)

---

## 🔒 Security Notes

### Environment Variables
- `.env` file is created from `.env.example`
- **Never commit `.env` to version control**
- Contains sensitive API keys

### Log Files
- Log files may contain sensitive information
- Add `logs/` to `.gitignore`
- Rotate logs regularly in production

### Redis
- Default configuration is for development only
- Use authentication in production
- Configure firewall rules

---

## 🧪 Testing Scripts

### Test Setup Script

**Windows:**
```cmd
# Dry run (check only, don't install)
setup.bat --check-only

# Force reinstall
rmdir /s /q venv
setup.bat
```

**Linux/Mac:**
```bash
# Dry run (check only, don't install)
./setup.sh --check-only

# Force reinstall
rm -rf venv
./setup.sh
```

### Test Run Script

```bash
# Test without opening browser
# Edit run script and comment out browser opening section

# Test with custom port
# Edit run script: python manage.py runserver 8080
```

---

## 📚 Additional Resources

- **Quick Start Guide:** See `QUICK_START_GUIDE.md`
- **Main Documentation:** See `README.md`
- **Celery Setup:** See `CELERY_QUICK_START.md`
- **Environment Setup:** See `.env.example`

---

## 🤝 Contributing

To improve these scripts:

1. Test on your platform
2. Document any issues
3. Submit improvements via pull request
4. Update this documentation

---

## 📝 Changelog

### Version 1.0.0 (2024-11-08)
- ✅ Initial release
- ✅ Windows batch scripts
- ✅ Linux/Mac shell scripts
- ✅ Comprehensive logging
- ✅ Error handling
- ✅ Service monitoring
- ✅ Auto-browser launch
- ✅ Color-coded output

---

## 📄 License

These scripts are part of the Smart iInvoice project and follow the same license.

---

## 🆘 Support

For issues with these scripts:

1. Check log files in `logs/` directory
2. Review `QUICK_START_GUIDE.md`
3. Check GitHub issues
4. Create new issue with log files attached

---

**Made with ❤️ for hassle-free deployment**
