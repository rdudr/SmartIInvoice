# SmartInvoice Deployment Guide

Complete guide for deploying SmartInvoice to free hosting platforms.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Platform Comparison](#platform-comparison)
- [Option 1: Deploy to Render (Recommended)](#option-1-deploy-to-render-recommended)
- [Option 2: Deploy to Railway](#option-2-deploy-to-railway)
- [Option 3: Deploy to PythonAnywhere](#option-3-deploy-to-pythonanywhere)
- [Environment Variables](#environment-variables)
- [Post-Deployment Setup](#post-deployment-setup)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before deploying, ensure you have:

1. **Git Repository**: Your code should be in a Git repository (GitHub, GitLab, or Bitbucket)
2. **API Keys**:
   - Google Gemini API key ([Get it here](https://makersuite.google.com/app/apikey))
   - Django SECRET_KEY (generate below)
3. **Account** on your chosen platform (Render/Railway/PythonAnywhere)

### Generate Django SECRET_KEY

Run this Python command to generate a secure secret key:

```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Or use this online generator: https://djecrety.ir/

---

## Platform Comparison

| Feature | Render | Railway | PythonAnywhere |
|---------|--------|---------|----------------|
| **Free Tier** | 750 hrs/month | $5 credit/month | Always free |
| **Database** | PostgreSQL ✅ | PostgreSQL ✅ | MySQL ✅ |
| **Redis/Celery** | ✅ Yes | ✅ Yes | ❌ No |
| **Sleep Policy** | After 15 min | After 15 min | No sleep |
| **Custom Domain** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Best For** | Full features | Full features | Simple apps |

**Recommendation**: Use **Render** for the best free experience with all features including background tasks.

---

## Option 1: Deploy to Render (Recommended)

### Step 1: Push Code to GitHub

```bash
# Initialize git if not already done
git init
git add .
git commit -m "Prepare for deployment"

# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/SmartInvoice.git
git branch -M main
git push -u origin main
```

### Step 2: Create Render Account

1. Go to [render.com](https://render.com)
2. Sign up with GitHub (recommended for easy integration)

### Step 3: Create PostgreSQL Database

1. Click **"New +"** → **"PostgreSQL"**
2. Configure:
   - **Name**: `smartinvoice-db`
   - **Database**: `smartinvoice`
   - **User**: `smartinvoice_user`
   - **Region**: Choose closest to you
   - **Plan**: **Free**
3. Click **"Create Database"**
4. **Save the Internal Database URL** (you'll need this later)

### Step 4: Create Redis Instance

1. Click **"New +"** → **"Redis"**
2. Configure:
   - **Name**: `smartinvoice-redis`
   - **Region**: Same as database
   - **Plan**: **Free**
3. Click **"Create Redis"**
4. **Save the Internal Redis URL**

### Step 5: Create Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository
3. Configure:
   - **Name**: `smartinvoice`
   - **Region**: Same as database
   - **Branch**: `main`
   - **Root Directory**: Leave empty
   - **Runtime**: `Python 3`
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn smartinvoice.wsgi --log-file -`
   - **Plan**: **Free**

### Step 6: Add Environment Variables

In the **Environment** section, add these variables:

```bash
SECRET_KEY=<your-generated-secret-key>
DEBUG=False
ALLOWED_HOSTS=.onrender.com
GEMINI_API_KEY=<your-gemini-api-key>
DATABASE_URL=<your-postgres-internal-url>
CELERY_BROKER_URL=<your-redis-internal-url>
CELERY_RESULT_BACKEND=<your-redis-internal-url>
GST_SERVICE_URL=http://127.0.0.1:5001
```

### Step 7: Create Celery Worker (Optional but Recommended)

1. Click **"New +"** → **"Background Worker"**
2. Connect same repository
3. Configure:
   - **Name**: `smartinvoice-worker`
   - **Region**: Same as web service
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `celery -A smartinvoice worker --loglevel=info --pool=solo --concurrency=2`
4. Add the **same environment variables** as the web service
5. Click **"Create Background Worker"**

### Step 8: Deploy

1. Click **"Create Web Service"**
2. Wait for deployment (5-10 minutes)
3. Your app will be available at: `https://smartinvoice.onrender.com`

---

## Option 2: Deploy to Railway

### Step 1: Push Code to GitHub

Same as Render Step 1.

### Step 2: Create Railway Account

1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub

### Step 3: Create New Project

1. Click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Choose your SmartInvoice repository

### Step 4: Add PostgreSQL

1. Click **"+ New"** → **"Database"** → **"Add PostgreSQL"**
2. Railway automatically creates `DATABASE_URL` environment variable

### Step 5: Add Redis

1. Click **"+ New"** → **"Database"** → **"Add Redis"**
2. Railway automatically creates `REDIS_URL` environment variable

### Step 6: Configure Environment Variables

1. Click on your web service
2. Go to **"Variables"** tab
3. Add:

```bash
SECRET_KEY=<your-generated-secret-key>
DEBUG=False
ALLOWED_HOSTS=.railway.app
GEMINI_API_KEY=<your-gemini-api-key>
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
GST_SERVICE_URL=http://127.0.0.1:5001
```

### Step 7: Configure Build

1. Go to **"Settings"** tab
2. Set:
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn smartinvoice.wsgi --log-file -`

### Step 8: Add Celery Worker

1. Click **"+ New"** → **"Empty Service"**
2. Connect same repository
3. Set **Start Command**: `celery -A smartinvoice worker --loglevel=info --pool=solo --concurrency=2`
4. Add same environment variables

### Step 9: Deploy

Railway automatically deploys. Your app will be at: `https://smartinvoice.up.railway.app`

---

## Option 3: Deploy to PythonAnywhere

> **Note**: PythonAnywhere free tier doesn't support Celery/Redis, so bulk upload and background tasks won't work.

### Step 1: Create Account

1. Go to [pythonanywhere.com](https://www.pythonanywhere.com)
2. Create a free account

### Step 2: Upload Code

**Option A: Using Git**
```bash
# In PythonAnywhere Bash console
git clone https://github.com/YOUR_USERNAME/SmartInvoice.git
cd SmartInvoice
```

**Option B: Upload ZIP**
1. Compress your project folder
2. Upload via **Files** tab
3. Extract in PythonAnywhere

### Step 3: Create Virtual Environment

```bash
mkvirtualenv smartinvoice --python=/usr/bin/python3.10
pip install -r requirements.txt
```

### Step 4: Configure Web App

1. Go to **Web** tab
2. Click **"Add a new web app"**
3. Choose **"Manual configuration"** → **Python 3.10**
4. Configure:
   - **Source code**: `/home/YOUR_USERNAME/SmartInvoice`
   - **Working directory**: `/home/YOUR_USERNAME/SmartInvoice`
   - **Virtualenv**: `/home/YOUR_USERNAME/.virtualenvs/smartinvoice`

### Step 5: Edit WSGI Configuration

Click on WSGI configuration file and replace with:

```python
import os
import sys

path = '/home/YOUR_USERNAME/SmartInvoice'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'smartinvoice.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### Step 6: Set Environment Variables

Create `.env` file in project root:

```bash
SECRET_KEY=<your-generated-secret-key>
DEBUG=False
ALLOWED_HOSTS=YOUR_USERNAME.pythonanywhere.com
GEMINI_API_KEY=<your-gemini-api-key>
GST_SERVICE_URL=http://127.0.0.1:5001
```

### Step 7: Setup Database and Static Files

```bash
python manage.py migrate
python manage.py collectstatic --no-input
python manage.py load_hsn_data
python manage.py createsuperuser
```

### Step 8: Configure Static Files

In **Web** tab, add static files mapping:
- **URL**: `/static/`
- **Directory**: `/home/YOUR_USERNAME/SmartInvoice/staticfiles`

### Step 9: Reload Web App

Click **"Reload"** button. Your app will be at: `https://YOUR_USERNAME.pythonanywhere.com`

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | `django-insecure-abc123...` |
| `DEBUG` | Debug mode (False for production) | `False` |
| `ALLOWED_HOSTS` | Allowed hostnames | `.onrender.com` or `.railway.app` |
| `GEMINI_API_KEY` | Google Gemini API key | `AIzaSy...` |

### Optional Variables (for full features)

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | SQLite (not recommended for production) |
| `CELERY_BROKER_URL` | Redis URL for Celery | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Redis URL for results | `redis://localhost:6379/0` |
| `GST_SERVICE_URL` | GST verification service | `http://127.0.0.1:5001` |

### Multiple API Keys (Advanced)

For automatic failover when quota limits are reached:

```bash
GEMINI_API_KEYS=key1,key2,key3
```

---

## Post-Deployment Setup

### 1. Create Superuser

**Render/Railway**: Use the web console or run command:
```bash
python manage.py createsuperuser
```

**PythonAnywhere**: Already done in Step 7.

### 2. Access Admin Panel

Visit: `https://your-app-url.com/admin/`

### 3. Test Invoice Upload

1. Login to your app
2. Upload a sample invoice PDF
3. Verify data extraction works
4. Check compliance analysis

### 4. Configure GST Service (Optional)

If you need GST verification:
1. Deploy the GST verification microservice separately
2. Update `GST_SERVICE_URL` environment variable
3. Restart your app

---

## Troubleshooting

### Static Files Not Loading

**Solution**: Ensure WhiteNoise is installed and configured
```bash
# Check middleware in settings.py
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Must be here
    ...
]
```

### Database Connection Error

**Render/Railway**: Verify `DATABASE_URL` is set correctly
```bash
# Should look like:
postgresql://user:password@host:5432/database
```

**PythonAnywhere**: Check database settings in settings.py

### Celery Tasks Not Running

**Check**:
1. Redis is running and accessible
2. Celery worker service is running
3. `CELERY_BROKER_URL` is correct
4. Check worker logs for errors

### App Sleeping (Render/Railway Free Tier)

**Issue**: App sleeps after 15 minutes of inactivity

**Solutions**:
1. Use a service like [UptimeRobot](https://uptimerobot.com) to ping your app every 5 minutes
2. Upgrade to paid tier ($7/month on Render)

### Build Fails

**Common causes**:
1. Missing dependencies in `requirements.txt`
2. Build script permissions: `chmod +x build.sh`
3. Python version mismatch

**Check build logs** for specific errors.

### 500 Internal Server Error

**Debug steps**:
1. Set `DEBUG=True` temporarily to see error details
2. Check application logs
3. Verify all environment variables are set
4. Check database migrations: `python manage.py migrate`

---

## Monitoring and Logs

### Render
- **Logs**: Dashboard → Your Service → Logs tab
- **Metrics**: Dashboard → Your Service → Metrics tab

### Railway
- **Logs**: Project → Service → Deployments → View Logs
- **Metrics**: Project → Service → Metrics

### PythonAnywhere
- **Error Log**: Web tab → Log files → Error log
- **Server Log**: Web tab → Log files → Server log

---

## Updating Your Deployment

### Render/Railway (Auto-deploy)
```bash
git add .
git commit -m "Update application"
git push origin main
# Automatically deploys
```

### PythonAnywhere (Manual)
```bash
# In PythonAnywhere Bash console
cd SmartInvoice
git pull origin main
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --no-input
# Click "Reload" in Web tab
```

---

## Security Best Practices

1. **Never commit secrets**: Use `.gitignore` for `.env` files
2. **Use strong SECRET_KEY**: Generate a new one for production
3. **Set DEBUG=False**: Always in production
4. **Use HTTPS**: Enabled by default on Render/Railway/PythonAnywhere
5. **Regular updates**: Keep dependencies updated
6. **Backup database**: Regular backups of production data

---

## Cost Optimization

### Free Tier Limits

**Render Free**:
- 750 hours/month (enough for 1 app running 24/7)
- 512 MB RAM
- Shared CPU
- Apps sleep after 15 min inactivity

**Railway Free**:
- $5 credit/month (~500 hours)
- After credit exhausted, requires payment

**PythonAnywhere Free**:
- Always free
- 512 MB disk space
- Limited CPU time
- No background tasks

### When to Upgrade

Consider paid tier if you need:
- No sleep/downtime
- More RAM/CPU
- Background tasks (Celery)
- Custom domain with SSL
- Better performance

**Render Starter**: $7/month (no sleep, 512 MB RAM)
**Railway Hobby**: $5/month + usage
**PythonAnywhere Hacker**: $5/month (background tasks)

---

## Next Steps

After successful deployment:

1. ✅ Test all features thoroughly
2. ✅ Set up monitoring/alerts
3. ✅ Configure custom domain (optional)
4. ✅ Set up automated backups
5. ✅ Document your deployment for team
6. ✅ Monitor usage and costs

---

## Support

- **Render Docs**: https://render.com/docs
- **Railway Docs**: https://docs.railway.app
- **PythonAnywhere Help**: https://help.pythonanywhere.com
- **Django Deployment**: https://docs.djangoproject.com/en/4.2/howto/deployment/

For SmartInvoice-specific issues, check the project README and documentation.
