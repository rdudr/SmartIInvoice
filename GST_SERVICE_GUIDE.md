# GST Verification Service Guide

## Overview

The Smart iInvoice application includes a GST verification microservice that can run in two modes:

1. **Real Mode** (`app.py`) - Connects to actual Indian government GST portal
2. **Mock Mode** (`app_mock.py`) - Simulates GST verification for development/testing

---

## Current Configuration

**The run scripts are currently configured to use REAL GST verification (`app.py`).**

This means the application will connect to the actual government GST portal at `services.gst.gov.in`.

---

## When to Use Each Mode

### Real Mode (`app.py`) ✅ Currently Active

**Use when:**
- ✅ Deploying to production
- ✅ Need actual GST verification
- ✅ Have stable internet connection
- ✅ Can access Indian government portal

**Advantages:**
- Real, accurate GST data
- Actual CAPTCHA from government portal
- Production-ready verification

**Disadvantages:**
- May timeout if government portal is slow
- May be blocked by firewalls or geographic restrictions
- Requires stable internet connection
- Government portal may have rate limiting
- Slower response times

### Mock Mode (`app_mock.py`)

**Use when:**
- ✅ Developing locally
- ✅ Testing the application
- ✅ Government portal is unavailable
- ✅ Want faster response times
- ✅ Working offline

**Advantages:**
- Fast and reliable
- No external dependencies
- Works offline
- Predictable test data
- No rate limiting

**Disadvantages:**
- Not real GST data
- Cannot verify actual GSTINs
- Not suitable for production

---

## How to Switch Between Modes

### Option 1: Edit Run Scripts (Recommended)

#### Windows (`run.bat`)

Find this line (around line 90):
```batch
python app.py > ..\!GST_LOG! 2>&1
```

**To use Mock Mode, change to:**
```batch
python app_mock.py > ..\!GST_LOG! 2>&1
```

#### Linux/Mac (`run.sh`)

Find this line (around line 90):
```bash
python app.py > "../$GST_LOG" 2>&1 &
```

**To use Mock Mode, change to:**
```bash
python app_mock.py > "../$GST_LOG" 2>&1 &
```

### Option 2: Manual Start

Stop the automatic GST service and start manually:

#### Real Mode
```bash
# Windows
cd "gst verification template"
python app.py

# Linux/Mac
cd "gst verification template"
python app.py
```

#### Mock Mode
```bash
# Windows
cd "gst verification template"
python app_mock.py

# Linux/Mac
cd "gst verification template"
python app_mock.py
```

---

## Mock Mode Test Data

When using `app_mock.py`, these GSTINs are pre-configured:

### GSTIN: `27AAPFU0939F1ZV`
```json
{
  "gstin": "27AAPFU0939F1ZV",
  "lgnm": "ABC PRIVATE LIMITED",
  "tradeNam": "ABC Traders",
  "sts": "Active",
  "dty": "Regular",
  "rgdt": "01/07/2017",
  "ctb": "Manufacturer",
  "pradr": {
    "addr": {
      "bnm": "Building 123",
      "st": "MG Road",
      "loc": "Pune",
      "dst": "Pune",
      "stcd": "Maharashtra",
      "pncd": "411001"
    }
  }
}
```

### GSTIN: `29AABCT1332L1ZZ`
```json
{
  "gstin": "29AABCT1332L1ZZ",
  "lgnm": "XYZ CORPORATION",
  "tradeNam": "XYZ Corp",
  "sts": "Active",
  "dty": "Regular",
  "rgdt": "15/08/2017",
  "ctb": "Service Provider",
  "pradr": {
    "addr": {
      "bnm": "Tower A",
      "st": "Whitefield",
      "loc": "Bangalore",
      "dst": "Bangalore Urban",
      "stcd": "Karnataka",
      "pncd": "560066"
    }
  }
}
```

**Any other GSTIN** will return generic mock data.

---

## CAPTCHA Handling

### Real Mode (`app.py`)
- CAPTCHA image comes from government portal
- Must be solved correctly to verify GSTIN
- CAPTCHA text is not visible in logs

### Mock Mode (`app_mock.py`)
- CAPTCHA is generated locally
- **CAPTCHA text is printed in the console/log for easy testing**
- Example: `Generated CAPTCHA: ABC123 for session: uuid`
- Makes testing much easier!

---

## Troubleshooting

### Issue: Connection Timeout Error

**Error Message:**
```
ConnectTimeoutError: Connection to services.gst.gov.in timed out
```

**Solution:**
1. Switch to Mock Mode (see "How to Switch Between Modes" above)
2. Or check your internet connection
3. Or check if government portal is accessible from your location

### Issue: GST Service Not Starting

**Check the logs:**
```bash
# Windows
type logs\gst_service_*.log

# Linux/Mac
tail -f logs/gst_service_*.log
```

**Common causes:**
- Port 5001 already in use
- Missing dependencies (flask, uvicorn, asgiref)
- Python path issues

**Solution:**
```bash
# Install dependencies
pip install flask uvicorn asgiref pillow

# Check if port 5001 is free
# Windows
netstat -ano | findstr :5001

# Linux/Mac
lsof -i :5001
```

### Issue: CAPTCHA Verification Fails

**Real Mode:**
- CAPTCHA must be entered exactly as shown
- Case-sensitive
- Try refreshing CAPTCHA if unclear

**Mock Mode:**
- Check console/log for CAPTCHA text
- Case-insensitive for easier testing
- Example: If log shows "ABC123", you can enter "abc123"

---

## API Endpoints

Both modes expose the same API:

### GET `/api/v1/getCaptcha`
Returns a CAPTCHA image and session ID.

**Response:**
```json
{
  "sessionId": "uuid-string",
  "image": "data:image/png;base64,..."
}
```

### POST `/api/v1/getGSTDetails`
Verifies a GSTIN with the provided CAPTCHA.

**Request:**
```json
{
  "sessionId": "uuid-from-captcha",
  "GSTIN": "27AAPFU0939F1ZV",
  "captcha": "ABC123"
}
```

**Response:**
```json
{
  "gstin": "27AAPFU0939F1ZV",
  "lgnm": "ABC PRIVATE LIMITED",
  "sts": "Active",
  ...
}
```

### GET `/health` (Mock Mode Only)
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "Mock GST Verification Service"
}
```

---

## Performance Comparison

| Feature | Real Mode | Mock Mode |
|---------|-----------|-----------|
| Response Time | 2-5 seconds | < 100ms |
| Reliability | Depends on portal | 99.9% |
| Offline Support | ❌ No | ✅ Yes |
| Rate Limiting | ✅ Yes | ❌ No |
| Real Data | ✅ Yes | ❌ No |
| Production Ready | ✅ Yes | ❌ No |

---

## Recommendations

### For Development
**Use Mock Mode** (`app_mock.py`)
- Faster development cycle
- No external dependencies
- Predictable test data
- Works offline

### For Testing
**Use Mock Mode** (`app_mock.py`)
- Automated tests run faster
- No flaky tests due to network issues
- Consistent test data

### For Staging
**Use Real Mode** (`app.py`)
- Test actual integration
- Verify network connectivity
- Test with real government portal

### For Production
**Use Real Mode** (`app.py`)
- Only real mode provides actual verification
- Required for compliance
- Actual GST data validation

---

## Configuration in .env

The GST service URL is configured in `.env`:

```env
GST_SERVICE_URL=http://127.0.0.1:5001
```

This URL is used by the Django application to connect to the GST service.

**Note:** The URL is the same for both Real and Mock modes. Only the backend service changes.

---

## Monitoring GST Service

### Check if GST Service is Running

**Windows:**
```cmd
curl http://127.0.0.1:5001
```

**Linux/Mac:**
```bash
curl http://127.0.0.1:5001
```

### View GST Service Logs

**Using log viewer:**
```bash
# Windows
view-logs.bat
# Select option 4 (GST service log)

# Linux/Mac
./view-logs.sh
# Select option 4 (GST service log)
```

**Direct access:**
```bash
# Windows
type logs\gst_service_*.log

# Linux/Mac
tail -f logs/gst_service_*.log
```

---

## Quick Reference

### Current Setup
- ✅ **Real Mode Active** (`app.py`)
- 🌐 Connects to government portal
- 📍 Port: 5001
- 📝 Logs: `logs/gst_service_*.log`

### To Switch to Mock Mode
1. Edit `run.bat` or `run.sh`
2. Change `python app.py` to `python app_mock.py`
3. Restart the application

### Test GSTINs (Mock Mode)
- `27AAPFU0939F1ZV` - ABC PRIVATE LIMITED
- `29AABCT1332L1ZZ` - XYZ CORPORATION
- Any other GSTIN returns generic data

---

## Support

For issues with GST verification:

1. **Check logs:** `logs/gst_service_*.log`
2. **Try Mock Mode:** If real mode has issues
3. **Check connectivity:** Ensure government portal is accessible
4. **Review documentation:** See `gst verification template/README.md`

---

**Current Status:** ✅ Real GST Verification Active

**To switch to Mock Mode:** Edit run scripts as described above
