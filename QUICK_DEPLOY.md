# Quick Deployment Reference

## 🚀 Fastest Way to Deploy (Render - Recommended)

### Prerequisites
1. Push your code to GitHub
2. Get your Gemini API key: https://makersuite.google.com/app/apikey
3. Generate SECRET_KEY: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`

### Deploy in 5 Steps

1. **Sign up at [render.com](https://render.com)** with GitHub

2. **Create PostgreSQL Database**
   - New + → PostgreSQL → Free tier
   - Save the "Internal Database URL"

3. **Create Redis**
   - New + → Redis → Free tier
   - Save the "Internal Redis URL"

4. **Create Web Service**
   - New + → Web Service
   - Connect your GitHub repo
   - Build Command: `./build.sh`
   - Start Command: `gunicorn smartinvoice.wsgi --log-file -`

5. **Add Environment Variables**
   ```
   SECRET_KEY=<your-generated-secret-key>
   DEBUG=False
   ALLOWED_HOSTS=.onrender.com
   GEMINI_API_KEY=<your-gemini-api-key>
   DATABASE_URL=<postgres-internal-url>
   CELERY_BROKER_URL=<redis-internal-url>
   CELERY_RESULT_BACKEND=<redis-internal-url>
   ```

6. **Deploy!** 🎉
   - Click "Create Web Service"
   - Wait 5-10 minutes
   - Your app is live at `https://smartinvoice.onrender.com`

### Optional: Add Celery Worker (for bulk uploads)
- New + → Background Worker
- Start Command: `celery -A smartinvoice worker --loglevel=info --pool=solo --concurrency=2`
- Add same environment variables

---

## 📝 What Was Changed

### New Files Created
- ✅ `Procfile` - Process configuration
- ✅ `runtime.txt` - Python version
- ✅ `build.sh` - Build automation script
- ✅ `DEPLOYMENT.md` - Full deployment guide

### Files Updated
- ✅ `requirements.txt` - Added production dependencies (gunicorn, whitenoise, etc.)
- ✅ `smartinvoice/settings.py` - Added WhiteNoise for static files

---

## 🔧 Platform Comparison

| Platform | Best For | Free Tier | Celery Support |
|----------|----------|-----------|----------------|
| **Render** | Full features | 750 hrs/mo | ✅ Yes |
| **Railway** | Alternative | $5 credit/mo | ✅ Yes |
| **PythonAnywhere** | Simple apps | Always free | ❌ No |

---

## 📚 Full Documentation

See [DEPLOYMENT.md](DEPLOYMENT.md) for:
- Detailed step-by-step instructions for all platforms
- Environment variable reference
- Troubleshooting guide
- Security best practices
- Cost optimization tips

---

## 🆘 Quick Troubleshooting

**Static files not loading?**
→ Check WhiteNoise is in MIDDLEWARE (already configured)

**Database error?**
→ Verify DATABASE_URL is set correctly

**App sleeping?**
→ Normal on free tier after 15 min inactivity
→ Use UptimeRobot to keep it awake

**Build fails?**
→ Check build logs for specific error
→ Ensure all environment variables are set

---

## 🎯 Next Steps After Deployment

1. Create superuser: `python manage.py createsuperuser`
2. Access admin: `https://your-app.com/admin/`
3. Test invoice upload
4. Configure custom domain (optional)
5. Set up monitoring

---

**Need help?** Check the full [DEPLOYMENT.md](DEPLOYMENT.md) guide!
