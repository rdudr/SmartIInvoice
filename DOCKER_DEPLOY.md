# Docker Deployment Guide

## Deploy to Render using Docker

1.  **Push your code to GitHub**:
    ```bash
    git add .
    git commit -m "Add Docker configuration"
    git push origin main
    ```

2.  **Go to Render Dashboard**:
    *   Click on your Service.
    *   Go to **Settings**.
    *   Scroll down to **Runtime**.
    *   Change it from **Python 3** to **Docker**.
    *   Click **Save Changes**.

3.  **Wait for Build**:
    *   Render will now build your application using the `Dockerfile`.
    *   This might take a few minutes the first time.

4.  **Verify**:
    *   Once the build finishes, your site will be live!

## Why Docker?
*   **Consistency**: Runs the same everywhere.
*   **Isolation**: No conflicts with system libraries.
*   **Simplicity**: No need to configure Python versions or build commands manually (it's all in the Dockerfile).

## Local Testing (Optional)
If you have Docker installed locally, you can test it:
```bash
docker-compose up --build
```
