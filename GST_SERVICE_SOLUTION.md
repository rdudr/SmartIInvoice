# GST Verification Service - Solution Guide

## Problem Summary

The GST verification service (`app.py`) was failing with connection timeout errors:

```
ConnectTimeoutError: Connection to services.gst.gov.in timed out
```

**Root Cause:** The service tries to connect to the Indian government's GST portal, which:
- May be slow or unavailable
- May have geographic restrictions
- May be blocked by firewalls
- Has rate limiting

## Solution: Mock GST Service

Created `app_mock.py` - a mock GST verification service for development and testing.

### Features

✅ **No External Dependencies** - Doesn't connect to government portal
✅ **Fast & Reliable** - Instant responses
✅ **Easy Testing** - CAPTCHA text printed in console
✅ **Pre-configured Data** - Mock GSTINs for testing
✅ **Same API** - Drop-in replacement for the real service

### How to Use

#### Step 1: Stop the Real Service (if running)
Press `CTRL+C` in the terminal running `app.py`

#### Step 2: Start the Mock Service

**Option A - Using the batch file:**
```bash
cd "gst verification template"
run_mock_service.bat
```

**Option B - Using Python directly:**
```bash
cd "gst verification template"
python app_mock.py
```

#### Step 3: Start Your Django Application
In a separate terminal:
```bash
python manage.py runserver
```

### Testing GST Verification

1. **Upload an invoice** with one of these GSTINs:
   - `27AAPFU0939F1ZV` (ABC PRIVATE LIMITED)
   - `29AABCT1332L1ZZ` (XYZ CORPORATION)
   - Any other GSTIN (returns generic mock data)

2. **Go to GST Verification page**

3. **Click "Verify GST"** on an invoice

4. **Enter the CAPTCHA** - The correct text is printed in the mock service console

5. **Verification succeeds** with mock company data

### Mock Service Console Output

When you start the mock service, you'll see:
```
============================================================
Mock GST Verification Service
============================================================
This is a MOCK service for development/testing purposes
It does NOT connect to the actual government GST portal
============================================================
Available mock GSTINs:
  - 27AAPFU0939F1ZV
  - 29AABCT1332L1ZZ
============================================================
Starting server on http://0.0.0.0:5001
============================================================
```

When a CAPTCHA is requested:
```
Generated CAPTCHA: ABC123 for session: uuid-string
```

### Adding More Mock GSTINs

Edit `app_mock.py` and add entries to `MOCK_GST_DATABASE`:

```python
MOCK_GST_DATABASE = {
    "YOUR_GSTIN_HERE": {
        "gstin": "YOUR_GSTIN_HERE",
        "lgnm": "YOUR COMPANY NAME",
        "tradeNam": "Your Trade Name",
        "sts": "Active",
        "dty": "Regular",
        # ... more fields
    }
}
```

## Production Deployment

For production, use the real service (`app.py`):

1. Ensure proper network access to `services.gst.gov.in`
2. Configure firewall rules if needed
3. Consider using a VPN if geographic restrictions apply
4. Implement retry logic and timeout handling
5. Monitor for government portal availability

## Comparison

| Feature | Real Service (`app.py`) | Mock Service (`app_mock.py`) |
|---------|------------------------|------------------------------|
| **Connection** | Government portal | Local only |
| **Speed** | Slow (network dependent) | Fast (instant) |
| **Reliability** | Depends on portal | 100% reliable |
| **Data** | Real GST data | Mock data |
| **Use Case** | Production | Development/Testing |
| **Setup** | Network access required | No setup needed |

## Recommendation

✅ **Use Mock Service (`app_mock.py`) for:**
- Local development
- Testing features
- CI/CD pipelines
- When government portal is unavailable

✅ **Use Real Service (`app.py`) for:**
- Production deployment
- Actual GST verification
- When real data is required

## Current Status

✅ Mock service created and ready to use
✅ Same API as real service
✅ Easy to switch between mock and real
✅ No code changes needed in Django app
✅ Comprehensive documentation provided

## Next Steps

1. Run the mock service: `python app_mock.py`
2. Test GST verification in your application
3. Verify everything works correctly
4. For production, configure and use `app.py`
