from django.test import TestCase
from unittest.mock import patch, Mock
from datetime import datetime
from django.utils import timezone

from invoice_processor.services.api_key_manager import APIKeyManager
from invoice_processor.models import APIKeyUsage


class APIKeyManagerTests(TestCase):
    """Test cases for API Key Manager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_keys = [
            "test_key_1_abcdefghijklmnop",
            "test_key_2_qrstuvwxyz123456",
            "test_key_3_7890abcdefghijkl"
        ]
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_initialization_with_multiple_keys(self, mock_config):
        """Test APIKeyManager initialization with multiple keys"""
        # Mock GEMINI_API_KEYS environment variable
        mock_config.side_effect = lambda key, default=None: (
            ','.join(self.test_keys) if key == 'GEMINI_API_KEYS' else None
        )
        
        manager = APIKeyManager()
        
        self.assertEqual(len(manager.api_keys), 3)
        self.assertEqual(manager.api_keys, self.test_keys)
        self.assertEqual(manager._current_key_index, 0)
        
        # Verify database records were created
        self.assertEqual(APIKeyUsage.objects.count(), 3)
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_initialization_with_single_key(self, mock_config):
        """Test APIKeyManager initialization with single key (backward compatibility)"""
        # Mock GEMINI_API_KEY environment variable
        mock_config.side_effect = lambda key, default=None: (
            self.test_keys[0] if key == 'GEMINI_API_KEY' else None
        )
        
        manager = APIKeyManager()
        
        self.assertEqual(len(manager.api_keys), 1)
        self.assertEqual(manager.api_keys[0], self.test_keys[0])
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_initialization_no_keys(self, mock_config):
        """Test APIKeyManager initialization fails without keys"""
        # Mock no keys configured
        mock_config.return_value = None
        
        with self.assertRaises(ValueError) as context:
            APIKeyManager()
        
        self.assertIn("No API keys found", str(context.exception))
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_get_active_key_round_robin(self, mock_config):
        """Test get_active_key uses round-robin selection"""
        mock_config.side_effect = lambda key, default=None: (
            ','.join(self.test_keys) if key == 'GEMINI_API_KEYS' else None
        )
        
        manager = APIKeyManager()
        
        # Get keys in sequence
        key1 = manager.get_active_key()
        key2 = manager.get_active_key()
        key3 = manager.get_active_key()
        key4 = manager.get_active_key()  # Should wrap around to first key
        
        self.assertEqual(key1, self.test_keys[0])
        self.assertEqual(key2, self.test_keys[1])
        self.assertEqual(key3, self.test_keys[2])
        self.assertEqual(key4, self.test_keys[0])  # Round-robin
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_get_active_key_updates_usage(self, mock_config):
        """Test get_active_key updates usage tracking"""
        mock_config.side_effect = lambda key, default=None: (
            ','.join(self.test_keys) if key == 'GEMINI_API_KEYS' else None
        )
        
        manager = APIKeyManager()
        key_hash = manager._hash_key(self.test_keys[0])
        
        # Get initial usage count
        key_usage = APIKeyUsage.objects.get(key_hash=key_hash)
        initial_count = key_usage.usage_count
        
        # Get active key
        manager.get_active_key()
        
        # Verify usage was updated
        key_usage.refresh_from_db()
        self.assertEqual(key_usage.usage_count, initial_count + 1)
        self.assertIsNotNone(key_usage.last_used)
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_get_active_key_skips_exhausted(self, mock_config):
        """Test get_active_key skips exhausted keys"""
        mock_config.side_effect = lambda key, default=None: (
            ','.join(self.test_keys) if key == 'GEMINI_API_KEYS' else None
        )
        
        manager = APIKeyManager()
        
        # Mark first key as exhausted
        key_hash = manager._hash_key(self.test_keys[0])
        key_usage = APIKeyUsage.objects.get(key_hash=key_hash)
        key_usage.is_active = False
        key_usage.save()
        
        # Get active keys - should skip first one
        key1 = manager.get_active_key()
        key2 = manager.get_active_key()
        key3 = manager.get_active_key()
        
        self.assertEqual(key1, self.test_keys[1])
        self.assertEqual(key2, self.test_keys[2])
        self.assertEqual(key3, self.test_keys[1])  # Round-robin among active keys
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_get_active_key_all_exhausted(self, mock_config):
        """Test get_active_key returns None when all keys exhausted"""
        mock_config.side_effect = lambda key, default=None: (
            ','.join(self.test_keys) if key == 'GEMINI_API_KEYS' else None
        )
        
        manager = APIKeyManager()
        
        # Mark all keys as exhausted
        APIKeyUsage.objects.all().update(is_active=False)
        
        # Should return None
        result = manager.get_active_key()
        self.assertIsNone(result)
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_mark_key_exhausted(self, mock_config):
        """Test mark_key_exhausted marks key as inactive"""
        mock_config.side_effect = lambda key, default=None: (
            ','.join(self.test_keys) if key == 'GEMINI_API_KEYS' else None
        )
        
        manager = APIKeyManager()
        key_to_exhaust = self.test_keys[0]
        key_hash = manager._hash_key(key_to_exhaust)
        
        # Verify key is initially active
        key_usage = APIKeyUsage.objects.get(key_hash=key_hash)
        self.assertTrue(key_usage.is_active)
        self.assertIsNone(key_usage.exhausted_at)
        
        # Mark as exhausted
        manager.mark_key_exhausted(key_to_exhaust, "Quota exceeded")
        
        # Verify key is now inactive
        key_usage.refresh_from_db()
        self.assertFalse(key_usage.is_active)
        self.assertIsNotNone(key_usage.exhausted_at)
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_mark_key_exhausted_failover(self, mock_config):
        """Test mark_key_exhausted triggers failover to next key"""
        mock_config.side_effect = lambda key, default=None: (
            ','.join(self.test_keys) if key == 'GEMINI_API_KEYS' else None
        )
        
        manager = APIKeyManager()
        
        # Get first key
        key1 = manager.get_active_key()
        self.assertEqual(key1, self.test_keys[0])
        
        # Mark it as exhausted
        manager.mark_key_exhausted(key1, "Quota exceeded")
        
        # Next call should skip the exhausted key and return next available key
        # Since round-robin continues from index 1, it will get key at index 2
        key2 = manager.get_active_key()
        # Should be one of the remaining active keys (not the exhausted one)
        self.assertIn(key2, [self.test_keys[1], self.test_keys[2]])
        self.assertNotEqual(key2, self.test_keys[0])
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_reset_key_pool(self, mock_config):
        """Test reset_key_pool reactivates all keys"""
        mock_config.side_effect = lambda key, default=None: (
            ','.join(self.test_keys) if key == 'GEMINI_API_KEYS' else None
        )
        
        manager = APIKeyManager()
        
        # Mark all keys as exhausted
        APIKeyUsage.objects.all().update(
            is_active=False,
            exhausted_at=timezone.now()
        )
        
        # Verify all keys are inactive
        self.assertEqual(APIKeyUsage.objects.filter(is_active=False).count(), 3)
        
        # Reset pool
        reset_count = manager.reset_key_pool()
        
        # Verify all keys are now active
        self.assertEqual(reset_count, 3)
        self.assertEqual(APIKeyUsage.objects.filter(is_active=True).count(), 3)
        self.assertEqual(APIKeyUsage.objects.filter(exhausted_at__isnull=False).count(), 0)
        
        # Verify round-robin index was reset
        self.assertEqual(manager._current_key_index, 0)
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_reset_key_pool_partial(self, mock_config):
        """Test reset_key_pool only resets exhausted keys"""
        mock_config.side_effect = lambda key, default=None: (
            ','.join(self.test_keys) if key == 'GEMINI_API_KEYS' else None
        )
        
        manager = APIKeyManager()
        
        # Mark only first two keys as exhausted
        for i in range(2):
            key_hash = manager._hash_key(self.test_keys[i])
            key_usage = APIKeyUsage.objects.get(key_hash=key_hash)
            key_usage.is_active = False
            key_usage.exhausted_at = timezone.now()
            key_usage.save()
        
        # Reset pool
        reset_count = manager.reset_key_pool()
        
        # Should have reset 2 keys
        self.assertEqual(reset_count, 2)
        self.assertEqual(APIKeyUsage.objects.filter(is_active=True).count(), 3)
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_get_key_status(self, mock_config):
        """Test get_key_status returns status for all keys"""
        mock_config.side_effect = lambda key, default=None: (
            ','.join(self.test_keys) if key == 'GEMINI_API_KEYS' else None
        )
        
        manager = APIKeyManager()
        
        # Use first key
        manager.get_active_key()
        
        # Mark second key as exhausted
        manager.mark_key_exhausted(self.test_keys[1], "Quota exceeded")
        
        # Get status
        status_list = manager.get_key_status()
        
        # Verify status list
        self.assertEqual(len(status_list), 3)
        
        # Check first key (used)
        self.assertTrue(status_list[0]['is_active'])
        self.assertEqual(status_list[0]['usage_count'], 1)
        self.assertIsNotNone(status_list[0]['last_used'])
        
        # Check second key (exhausted)
        self.assertFalse(status_list[1]['is_active'])
        self.assertIsNotNone(status_list[1]['exhausted_at'])
        
        # Check third key (unused)
        self.assertTrue(status_list[2]['is_active'])
        self.assertEqual(status_list[2]['usage_count'], 0)
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_hash_key_consistency(self, mock_config):
        """Test _hash_key produces consistent hashes"""
        mock_config.side_effect = lambda key, default=None: (
            self.test_keys[0] if key == 'GEMINI_API_KEY' else None
        )
        
        manager = APIKeyManager()
        
        # Hash same key multiple times
        hash1 = manager._hash_key(self.test_keys[0])
        hash2 = manager._hash_key(self.test_keys[0])
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # SHA256 produces 64 character hex string
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_hash_key_uniqueness(self, mock_config):
        """Test _hash_key produces unique hashes for different keys"""
        mock_config.side_effect = lambda key, default=None: (
            ','.join(self.test_keys) if key == 'GEMINI_API_KEYS' else None
        )
        
        manager = APIKeyManager()
        
        # Hash different keys
        hash1 = manager._hash_key(self.test_keys[0])
        hash2 = manager._hash_key(self.test_keys[1])
        hash3 = manager._hash_key(self.test_keys[2])
        
        # All hashes should be unique
        self.assertNotEqual(hash1, hash2)
        self.assertNotEqual(hash2, hash3)
        self.assertNotEqual(hash1, hash3)
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_initialization_strips_whitespace(self, mock_config):
        """Test initialization strips whitespace from keys"""
        # Mock keys with extra whitespace
        keys_with_whitespace = f"  {self.test_keys[0]}  ,  {self.test_keys[1]}  ,  {self.test_keys[2]}  "
        mock_config.side_effect = lambda key, default=None: (
            keys_with_whitespace if key == 'GEMINI_API_KEYS' else None
        )
        
        manager = APIKeyManager()
        
        # Verify keys were stripped
        self.assertEqual(manager.api_keys[0], self.test_keys[0])
        self.assertEqual(manager.api_keys[1], self.test_keys[1])
        self.assertEqual(manager.api_keys[2], self.test_keys[2])
    
    @patch('invoice_processor.services.api_key_manager.config')
    def test_initialization_ignores_empty_keys(self, mock_config):
        """Test initialization ignores empty keys in comma-separated list"""
        # Mock keys with empty entries
        keys_with_empty = f"{self.test_keys[0]},,{self.test_keys[1]}, ,{self.test_keys[2]}"
        mock_config.side_effect = lambda key, default=None: (
            keys_with_empty if key == 'GEMINI_API_KEYS' else None
        )
        
        manager = APIKeyManager()
        
        # Should only have 3 valid keys
        self.assertEqual(len(manager.api_keys), 3)
        self.assertEqual(manager.api_keys, self.test_keys)
