import os
import hashlib
import logging
from typing import Optional, List
from datetime import datetime
from django.utils import timezone
from decouple import config
from invoice_processor.models import APIKeyUsage

logger = logging.getLogger(__name__)


class APIKeyManager:
    """
    Manages a pool of Gemini API keys with automatic failover.
    Handles key rotation, exhaustion tracking, and daily resets.
    """
    
    def __init__(self):
        """Initialize API key manager with keys from environment"""
        self._load_api_keys()
        self._current_key_index = 0
        
    def _load_api_keys(self):
        """Load API keys from environment variable"""
        # Support both single key (GEMINI_API_KEY) and multiple keys (GEMINI_API_KEYS)
        single_key = config('GEMINI_API_KEY', default=None)
        multiple_keys = config('GEMINI_API_KEYS', default=None)
        
        if multiple_keys:
            # Parse comma-separated keys from GEMINI_API_KEYS
            self.api_keys = [key.strip() for key in multiple_keys.split(',') if key.strip()]
            logger.info(f"Loaded {len(self.api_keys)} API keys from GEMINI_API_KEYS")
        elif single_key:
            # Check if GEMINI_API_KEY contains comma-separated keys
            if ',' in single_key:
                # Parse comma-separated keys from GEMINI_API_KEY
                self.api_keys = [key.strip() for key in single_key.split(',') if key.strip()]
                logger.info(f"Loaded {len(self.api_keys)} API keys from GEMINI_API_KEY (comma-separated)")
            else:
                # Single key for backward compatibility
                self.api_keys = [single_key]
                logger.info("Loaded 1 API key from GEMINI_API_KEY")
        else:
            raise ValueError("No API keys found. Set GEMINI_API_KEY or GEMINI_API_KEYS environment variable")
        
        # Initialize key usage tracking in database
        self._initialize_key_tracking()
    
    def _initialize_key_tracking(self):
        """Initialize or update API key usage records in database"""
        for key in self.api_keys:
            key_hash = self._hash_key(key)
            APIKeyUsage.objects.get_or_create(
                key_hash=key_hash,
                defaults={
                    'is_active': True,
                    'usage_count': 0,
                    'last_used': None,
                    'exhausted_at': None
                }
            )
        logger.info(f"Initialized tracking for {len(self.api_keys)} API keys")
    
    def _hash_key(self, key: str) -> str:
        """
        Create SHA256 hash of API key for secure storage
        
        Args:
            key: API key to hash
            
        Returns:
            str: SHA256 hash of the key
        """
        return hashlib.sha256(key.encode()).hexdigest()
    
    def get_active_key(self) -> Optional[str]:
        """
        Retrieve the next available active API key from the pool.
        Uses round-robin selection among active keys.
        
        Returns:
            str: Active API key or None if all keys are exhausted
        """
        active_keys = []
        
        # Find all active keys
        for key in self.api_keys:
            key_hash = self._hash_key(key)
            try:
                key_usage = APIKeyUsage.objects.get(key_hash=key_hash)
                if key_usage.is_active:
                    active_keys.append(key)
            except APIKeyUsage.DoesNotExist:
                # Key not tracked yet, consider it active
                active_keys.append(key)
                logger.warning(f"API key {key_hash[:8]}... not found in database, treating as active")
        
        if not active_keys:
            logger.error("All API keys are exhausted. No active keys available.")
            return None
        
        # Round-robin selection
        selected_key = active_keys[self._current_key_index % len(active_keys)]
        self._current_key_index = (self._current_key_index + 1) % len(active_keys)
        
        # Update usage tracking
        key_hash = self._hash_key(selected_key)
        try:
            key_usage = APIKeyUsage.objects.get(key_hash=key_hash)
            key_usage.usage_count += 1
            key_usage.last_used = timezone.now()
            key_usage.save()
            
            logger.info(f"Selected API key {key_hash[:8]}... (usage count: {key_usage.usage_count})")
        except APIKeyUsage.DoesNotExist:
            logger.warning(f"Could not update usage for key {key_hash[:8]}...")
        
        return selected_key
    
    def mark_key_exhausted(self, key: str, reason: str = "Quota exceeded"):
        """
        Mark an API key as exhausted and trigger failover to the next key.
        
        Args:
            key: The API key that has been exhausted
            reason: Reason for exhaustion (for logging)
        """
        key_hash = self._hash_key(key)
        
        try:
            key_usage = APIKeyUsage.objects.get(key_hash=key_hash)
            key_usage.is_active = False
            key_usage.exhausted_at = timezone.now()
            key_usage.save()
            
            logger.warning(
                f"API key {key_hash[:8]}... marked as exhausted. "
                f"Reason: {reason}. Usage count: {key_usage.usage_count}"
            )
            
            # Check if any keys remain active
            active_count = APIKeyUsage.objects.filter(is_active=True).count()
            if active_count == 0:
                logger.critical("ALL API KEYS EXHAUSTED! No keys available for failover.")
            else:
                logger.info(f"Failover available: {active_count} active key(s) remaining")
                
        except APIKeyUsage.DoesNotExist:
            logger.error(f"Cannot mark key {key_hash[:8]}... as exhausted - not found in database")
    
    def reset_key_pool(self):
        """
        Reset all API keys to active status.
        This should be called daily or when quota limits reset.
        """
        reset_count = APIKeyUsage.objects.filter(is_active=False).update(
            is_active=True,
            exhausted_at=None
        )
        
        logger.info(f"API key pool reset: {reset_count} key(s) reactivated")
        
        # Reset the round-robin index
        self._current_key_index = 0
        
        return reset_count
    
    def get_key_status(self) -> List[dict]:
        """
        Get status information for all API keys.
        
        Returns:
            list: List of dictionaries containing key status information
        """
        status_list = []
        
        for key in self.api_keys:
            key_hash = self._hash_key(key)
            try:
                key_usage = APIKeyUsage.objects.get(key_hash=key_hash)
                status_list.append({
                    'key_hash': key_hash[:8] + '...',
                    'is_active': key_usage.is_active,
                    'usage_count': key_usage.usage_count,
                    'last_used': key_usage.last_used,
                    'exhausted_at': key_usage.exhausted_at
                })
            except APIKeyUsage.DoesNotExist:
                status_list.append({
                    'key_hash': key_hash[:8] + '...',
                    'is_active': True,
                    'usage_count': 0,
                    'last_used': None,
                    'exhausted_at': None
                })
        
        return status_list


# Create a singleton instance for easy import
api_key_manager = APIKeyManager()
