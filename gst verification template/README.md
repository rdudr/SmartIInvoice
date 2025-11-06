# GST Verification Service

This directory contains two versions of the GST verification microservice:

## 1. `app.py` - Real GST Service (Production)

Connects to the actual Indian government GST portal (`services.gst.gov.in`).

**Use when:**
- Deploying to production
- Need real GST verification
- Have proper network access to government portal

**Issues:**
- May timeout if government portal is slow
- May be blocked by firewalls or geographic restrictions
- Requires stable internet connection
- Government portal may have rate limiting

**To run:**
```bash
python app.py
```

## 2. `app_mock.py` - Mock GST Service (Development/Testing)

Simulates GST verification without connecting to the government portal.

**Use when:**
- Developing locally
- Testing the application
- Government portal is unavailable
- Want faster response times

**Features:**
- Generates mock CAPTCHA images
- Returns mock GST data for testing
- No external dependencies
- Fast and reliable

**Pre-configured Mock GSTINs:**
- `27AAPFU0939F1ZV` - ABC PRIVATE LIMITED
- `29AABCT1332L1ZZ` - XYZ CORPORATION
- Any other GSTIN will return generic mock data

**To run:**
```bash
python app_mock.py
```

## Installation

Install required dependencies:
```bash
pip install -r requirements.txt
```

## API Endpoints

Both services expose the same API:

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
  "dty": "Regular",
  ...
}
```

## Troubleshooting

### Connection Timeout Error
If you see:
```
ConnectTimeoutError: Connection to services.gst.gov.in timed out
```

**Solution:** Use `app_mock.py` instead of `app.py` for development.

### CAPTCHA Verification
- **Real service (`app.py`)**: CAPTCHA must match the government portal's image
- **Mock service (`app_mock.py`)**: CAPTCHA text is printed in the console for easy testing

## Recommendation

**For Development:** Use `app_mock.py` - it's faster, more reliable, and doesn't depend on external services.

**For Production:** Use `app.py` - connects to the real government portal for actual verification.
