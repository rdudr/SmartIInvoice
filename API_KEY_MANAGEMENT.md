# API Key Management System

## Overview

The Smart iInvoice platform now includes an intelligent API Key Management System that provides automatic failover when API quota limits are reached. This ensures uninterrupted invoice processing even when individual API keys are exhausted.

## Features

- **Multiple API Key Support**: Configure multiple Gemini API keys for automatic rotation
- **Automatic Failover**: When one key reaches its quota, the system automatically switches to the next available key
- **Round-Robin Selection**: Keys are used in rotation to distribute load evenly
- **Usage Tracking**: All key usage is tracked in the database for monitoring and analytics
- **Daily Reset**: Keys can be reset automatically when quota limits refresh
- **Backward Compatible**: Works with single key configuration for existing deployments

## Configuration

### Single API Key (Backward Compatible)

For simple deployments or testing, you can continue using a single API key:

```bash
# .env file
GEMINI_API_KEY=your-gemini-api-key-here
```

### Multiple API Keys (Recommended for Production)

For production deployments with high volume, configure multiple API keys:

```bash
# .env file
GEMINI_API_KEYS=key1,key2,key3,key4,key5
```

**Note**: If both `GEMINI_API_KEYS` and `GEMINI_API_KEY` are set, `GEMINI_API_KEYS` takes precedence.

## How It Works

### 1. Key Rotation

The system uses round-robin selection to distribute API calls across all available keys:

```
Request 1 → Key 1
Request 2 → Key 2
Request 3 → Key 3
Request 4 → Key 1 (wraps around)
```

### 2. Automatic Failover

When a key encounters a quota error (HTTP 429 or quota exceeded message):

1. The key is marked as exhausted in the database
2. The system immediately switches to the next available key
3. The request is retried with the new key
4. Processing continues without user intervention

### 3. Key Status Tracking

Each API key's status is tracked in the database:

- **is_active**: Whether the key is currently available for use
- **usage_count**: Total number of times the key has been used
- **last_used**: Timestamp of the last API call with this key
- **exhausted_at**: When the key was marked as exhausted (if applicable)

### 4. Daily Reset

API keys can be reset to active status when quota limits refresh (typically daily):

```python
from invoice_processor.services.api_key_manager import api_key_manager

# Reset all keys to active status
api_key_manager.reset_key_pool()
```

This can be automated using a scheduled task (e.g., Django management command with cron).

## Usage in Code

### Using the Default Service

The GeminiService automatically uses the API Key Manager:

```python
from invoice_processor.services.gemini_service import extract_data_from_image

# Automatically uses key manager with failover
result = extract_data_from_image(invoice_file)
```

### Direct API Key Manager Usage

For advanced use cases, you can interact with the API Key Manager directly:

```python
from invoice_processor.services.api_key_manager import api_key_manager

# Get an active key
key = api_key_manager.get_active_key()

# Mark a key as exhausted
api_key_manager.mark_key_exhausted(key, "Quota exceeded")

# Get status of all keys
status = api_key_manager.get_key_status()
for key_info in status:
    print(f"Key: {key_info['key_hash']}")
    print(f"Active: {key_info['is_active']}")
    print(f"Usage: {key_info['usage_count']}")

# Reset all keys
api_key_manager.reset_key_pool()
```

## Monitoring

### Check Key Status

You can monitor API key usage through the Django admin interface or by querying the `APIKeyUsage` model:

```python
from invoice_processor.models import APIKeyUsage

# Get all keys
keys = APIKeyUsage.objects.all()

# Get active keys
active_keys = APIKeyUsage.objects.filter(is_active=True)

# Get exhausted keys
exhausted_keys = APIKeyUsage.objects.filter(is_active=False)
```

### Logging

The system logs all key-related events:

- Key selection: `INFO: Selected API key {hash}... (usage count: {count})`
- Key exhaustion: `WARNING: API key {hash}... marked as exhausted. Reason: {reason}`
- Failover: `INFO: Failover available: {count} active key(s) remaining`
- All keys exhausted: `CRITICAL: ALL API KEYS EXHAUSTED! No keys available for failover.`

## Best Practices

1. **Use Multiple Keys**: Configure at least 3-5 API keys for production deployments
2. **Monitor Usage**: Regularly check key status to ensure adequate capacity
3. **Set Up Alerts**: Configure monitoring to alert when keys are exhausted
4. **Automate Resets**: Schedule daily key pool resets to align with quota refresh
5. **Rotate Keys**: Periodically rotate API keys for security

## Troubleshooting

### All Keys Exhausted

If all API keys are exhausted:

1. Check the logs for exhaustion reasons
2. Verify quota limits with your API provider
3. Add more API keys to the pool
4. Wait for quota reset (typically 24 hours)
5. Manually reset the key pool if quotas have refreshed

### Keys Not Rotating

If keys aren't rotating properly:

1. Verify `GEMINI_API_KEYS` is set correctly in `.env`
2. Check database for `APIKeyUsage` records
3. Review logs for initialization errors
4. Ensure all keys are valid and active

### Backward Compatibility Issues

If you encounter issues after upgrading:

1. The system automatically falls back to single key mode if key manager fails
2. Existing `GEMINI_API_KEY` configuration continues to work
3. No database migrations are required for basic functionality

## Security Considerations

- API keys are hashed (SHA256) before storage in the database
- Full keys are never logged or stored in plain text
- Only the first 8 characters of the hash are displayed in logs
- Keys are loaded from environment variables, not hardcoded

## Future Enhancements

Planned improvements for the API Key Management System:

- Web UI for key management and monitoring
- Automatic key health checks
- Predictive quota management
- Integration with cloud secret managers
- Real-time usage dashboards
