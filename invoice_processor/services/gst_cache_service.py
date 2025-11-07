import logging
from typing import Optional, Dict, Any
from datetime import datetime
from django.utils import timezone
from invoice_processor.models import GSTCacheEntry
from invoice_processor.services.gst_client import verify_gstin, get_captcha

logger = logging.getLogger(__name__)


class GSTCacheService:
    """Service for managing GST verification cache to bypass CAPTCHA for known vendors"""
    
    def lookup_gstin(self, gstin: str) -> Optional[GSTCacheEntry]:
        """
        Check if GSTIN exists in cache and return cached data
        
        Args:
            gstin: GST number to lookup (15 characters)
            
        Returns:
            GSTCacheEntry: Cached entry if found, None otherwise
        """
        if not gstin or len(gstin.strip()) != 15:
            logger.warning(f"Invalid GSTIN format for lookup: {gstin}")
            return None
        
        try:
            gstin_normalized = gstin.strip().upper()
            cache_entry = GSTCacheEntry.objects.get(gstin=gstin_normalized)
            
            # Increment verification count
            cache_entry.verification_count += 1
            cache_entry.save(update_fields=['verification_count', 'last_verified'])
            
            logger.info(f"Cache hit for GSTIN: {gstin_normalized} (count: {cache_entry.verification_count})")
            return cache_entry
            
        except GSTCacheEntry.DoesNotExist:
            logger.info(f"Cache miss for GSTIN: {gstin_normalized}")
            return None
        except Exception as e:
            logger.error(f"Error looking up GSTIN in cache: {str(e)}")
            return None
    
    def add_to_cache(self, gstin: str, verification_data: Dict[str, Any]) -> Optional[GSTCacheEntry]:
        """
        Store verified GSTIN data in cache after successful verification
        
        Args:
            gstin: GST number (15 characters)
            verification_data: Data returned from government portal
            
        Returns:
            GSTCacheEntry: Created cache entry or None if failed
        """
        if not gstin or len(gstin.strip()) != 15:
            logger.warning(f"Invalid GSTIN format for caching: {gstin}")
            return None
        
        if not verification_data or 'error' in verification_data:
            logger.warning(f"Cannot cache invalid verification data for GSTIN: {gstin}")
            return None
        
        try:
            gstin_normalized = gstin.strip().upper()
            
            # Extract data from verification response
            # The government portal returns data in a nested structure
            legal_name = verification_data.get('lgnm', '')
            trade_name = verification_data.get('tradeNam', '')
            status = verification_data.get('sts', '')
            registration_date_str = verification_data.get('rgdt', '')
            business_constitution = verification_data.get('ctb', '')
            einvoice_status = verification_data.get('einvoiceStatus', '')
            
            # Parse registration date
            registration_date = None
            if registration_date_str:
                try:
                    # Government portal returns date in DD/MM/YYYY format
                    registration_date = datetime.strptime(registration_date_str, '%d/%m/%Y').date()
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse registration date '{registration_date_str}': {e}")
            
            # Extract principal address
            principal_address = ''
            pradr = verification_data.get('pradr', {})
            if isinstance(pradr, dict):
                adr = pradr.get('adr', '')
                if adr:
                    principal_address = adr
            
            # Create or update cache entry
            cache_entry, created = GSTCacheEntry.objects.update_or_create(
                gstin=gstin_normalized,
                defaults={
                    'legal_name': legal_name or '',
                    'trade_name': trade_name or '',
                    'status': status or '',
                    'registration_date': registration_date,
                    'business_constitution': business_constitution or '',
                    'principal_address': principal_address,
                    'einvoice_status': einvoice_status or '',
                    'verification_count': 1,
                }
            )
            
            action = "Created" if created else "Updated"
            logger.info(f"{action} cache entry for GSTIN: {gstin_normalized} - {legal_name}")
            
            return cache_entry
            
        except Exception as e:
            logger.error(f"Error adding GSTIN to cache: {str(e)}")
            return None
    
    def refresh_cache_entry(self, gstin: str, session_id: str, captcha: str) -> Dict[str, Any]:
        """
        Re-fetch data from government portal to update cache entry
        
        Args:
            gstin: GST number to refresh (15 characters)
            session_id: CAPTCHA session ID
            captcha: User-entered CAPTCHA text
            
        Returns:
            dict: Result with success status and updated data or error message
                  Format: {"success": True, "data": {...}} or {"success": False, "error": "..."}
        """
        if not gstin or len(gstin.strip()) != 15:
            return {"success": False, "error": "Invalid GSTIN format"}
        
        if not session_id or not captcha:
            return {"success": False, "error": "Session ID and CAPTCHA are required"}
        
        try:
            gstin_normalized = gstin.strip().upper()
            
            # Call GST verification service
            logger.info(f"Refreshing cache entry for GSTIN: {gstin_normalized}")
            verification_response = verify_gstin(session_id, gstin_normalized, captcha.strip())
            
            # Check for errors
            if 'error' in verification_response:
                error_msg = verification_response['error']
                logger.warning(f"Failed to refresh GSTIN {gstin_normalized}: {error_msg}")
                return {"success": False, "error": error_msg}
            
            # Update cache with new data
            cache_entry = self.add_to_cache(gstin_normalized, verification_response)
            
            if cache_entry:
                logger.info(f"Successfully refreshed cache entry for GSTIN: {gstin_normalized}")
                return {
                    "success": True,
                    "data": {
                        "gstin": cache_entry.gstin,
                        "legal_name": cache_entry.legal_name,
                        "trade_name": cache_entry.trade_name,
                        "status": cache_entry.status,
                        "last_verified": cache_entry.last_verified.isoformat(),
                    }
                }
            else:
                return {"success": False, "error": "Failed to update cache entry"}
                
        except Exception as e:
            logger.error(f"Error refreshing cache entry: {str(e)}")
            return {"success": False, "error": "An unexpected error occurred during refresh"}
    
    def get_all_entries(self, search_query: Optional[str] = None, status_filter: Optional[str] = None):
        """
        Get all cache entries with optional filtering
        
        Args:
            search_query: Search by GSTIN, legal name, or trade name
            status_filter: Filter by status (Active/Inactive)
            
        Returns:
            QuerySet: Filtered cache entries
        """
        queryset = GSTCacheEntry.objects.all()
        
        # Apply search filter
        if search_query:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(gstin__icontains=search_query) |
                Q(legal_name__icontains=search_query) |
                Q(trade_name__icontains=search_query)
            )
        
        # Apply status filter
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-last_verified')


# Create a singleton instance for easy import
gst_cache_service = GSTCacheService()
