# Docker Deployment Guide (New Service)

## Create a New Docker Service on Render

Since you want to start fresh, follow these steps to create a **new** service running with Docker.

### 1. Push Your Code
Ensure your latest Docker configuration is on GitHub:
```bash
git push origin main
```

### 2. Create New Web Service
1.  Go to the [Render Dashboard](https://dashboard.render.com/).
2.  Click **New +** and select **Web Service**.
3.  Connect your `SmartIInvoice` repository.

### 3. Configure Service
Render will auto-detect the `Dockerfile`. Ensure these settings:

*   **Name**: `smartinvoice-docker` (or any name you like)
*   **Region**: Choose the one closest to you (e.g., Singapore, Frankfurt)
*   **Runtime**: **Docker** (This is crucial!)
*   **Instance Type**: **Free**

### 4. Environment Variables
You must add these variables again for the new service.
*   **Key**: `SECRET_KEY`
    *   **Value**: (Paste your generated secret key)
*   **Key**: `GEMINI_API_KEY`
    *   **Value**: (Your Google Gemini API Key)
*   **Key**: `DEBUG`
    *   **Value**: `False`
*   **Key**: `ALLOWED_HOSTS`
    *   **Value**: `*` (We set this in settings.py, but good to have here too)
*   **Key**: `DATABASE_URL`
    *   **Value**: (Copy the "Internal Connection String" from your existing PostgreSQL database on Render)
*   **Key**: `CELERY_BROKER_URL`
    *   **Value**: (Copy the "Internal Connection String" from your existing Redis on Render)

### 5. Deploy
Click **Create Web Service**.

Render will start building your Docker image. This takes a bit longer than a standard Python build (about 3-5 minutes), but it's much more reliable.

### 6. Verify
Once the build finishes and you see the green **Live** badge, click the URL to test your fresh Docker deployment!
