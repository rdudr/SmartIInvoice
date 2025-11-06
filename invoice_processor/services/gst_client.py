import logging
import requests
from typing import Dict, Any, Optional
from decouple import config

logger = logging.getLogger(__name__)


class GSTClient:
    """Client for communicating with GST verification microservice"""
    
    def __init__(self):
        """Initialize GST client with microservice URL from environment"""
        self.service_url = config('GST_SERVICE_URL', default='http://127.0.0.1:5001')
        self.timeout_seconds = 30
        self.max_retries = 1
        
        # Ensure service URL doesn't end with slash for consistent URL building
        if self.service_url:
            self.service_url = self.service_url.rstrip('/')
        else:
            self.service_url = 'http://127.0.0.1:5001'
        
        logger.info(f"GST Client initialized with service URL: {self.service_url}")
    
    def get_captcha(self) -> Dict[str, Any]:
        """
        Request CAPTCHA from GST microservice
        
        Returns:
            dict: Response containing sessionId and base64 image data
                  Format: {
                      "sessionId": "uuid-string",
                      "image": "data:image/png;base64,..."
                  }
                  Or error response: {"error": "error message"}
        """
        try:
            url = f"{self.service_url}/api/v1/getCaptcha"
            
            logger.info(f"Requesting CAPTCHA from: {url}")
            
            response = requests.get(
                url,
                timeout=self.timeout_seconds
            )
            
            # Check if request was successful
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            
            # Validate response structure
            if 'sessionId' in data and 'image' in data:
                logger.info(f"Successfully received CAPTCHA with session ID: {data['sessionId']}")
                return data
            else:
                logger.error(f"Invalid CAPTCHA response structure: {data}")
                return {"error": "Invalid response from GST service"}
                
        except requests.exceptions.ConnectionError as e:
            logger.error(f"GST microservice unavailable: {str(e)}")
            return {"error": "GST verification service is temporarily unavailable. Please try again later."}
        
        except requests.exceptions.Timeout as e:
            logger.error(f"GST microservice timeout: {str(e)}")
            return {"error": "GST verification service is taking too long to respond. Please try again."}
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from GST microservice: {str(e)}")
            return {"error": "GST verification service returned an error. Please try again."}
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error to GST microservice: {str(e)}")
            return {"error": "Failed to connect to GST verification service."}
        
        except ValueError as e:
            logger.error(f"Invalid JSON response from GST microservice: {str(e)}")
            return {"error": "Invalid response from GST verification service."}
        
        except Exception as e:
            logger.error(f"Unexpected error in get_captcha: {str(e)}")
            return {"error": "An unexpected error occurred while requesting CAPTCHA."}
    
    def verify_gstin(self, session_id: str, gstin: str, captcha: str) -> Dict[str, Any]:
        """
        Submit GST verification request to microservice
        
        Args:
            session_id: Session ID from get_captcha() response
            gstin: GST number to verify (15 characters)
            captcha: User-entered CAPTCHA text
            
        Returns:
            dict: Verification response from government portal
                  Success format varies based on government API
                  Error format: {"error": "error message"}
        """
        try:
            # Validate input parameters
            if not session_id or not gstin or not captcha:
                return {"error": "Missing required parameters for GST verification"}
            
            # Basic GSTIN format validation
            if len(gstin.strip()) != 15:
                return {"error": "Invalid GSTIN format. GSTIN must be 15 characters."}
            
            url = f"{self.service_url}/api/v1/getGSTDetails"
            
            payload = {
                "sessionId": session_id,
                "GSTIN": gstin.strip().upper(),
                "captcha": captcha.strip()
            }
            
            logger.info(f"Submitting GST verification for GSTIN: {gstin} with session: {session_id}")
            
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout_seconds,
                headers={'Content-Type': 'application/json'}
            )
            
            # Check if request was successful
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            
            # Log the response (without sensitive data)
            if 'error' in data:
                logger.warning(f"GST verification failed for {gstin}: {data.get('error')}")
            else:
                logger.info(f"GST verification completed for {gstin}")
            
            return data
                
        except requests.exceptions.ConnectionError as e:
            logger.error(f"GST microservice unavailable during verification: {str(e)}")
            return {"error": "GST verification service is temporarily unavailable. Please try again later."}
        
        except requests.exceptions.Timeout as e:
            logger.error(f"GST microservice timeout during verification: {str(e)}")
            return {"error": "GST verification is taking too long. Please try again."}
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error during GST verification: {str(e)}")
            return {"error": "GST verification service returned an error. Please try again."}
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during GST verification: {str(e)}")
            return {"error": "Failed to connect to GST verification service."}
        
        except ValueError as e:
            logger.error(f"Invalid JSON response during GST verification: {str(e)}")
            return {"error": "Invalid response from GST verification service."}
        
        except Exception as e:
            logger.error(f"Unexpected error in verify_gstin: {str(e)}")
            return {"error": "An unexpected error occurred during GST verification."}
    
    def is_service_available(self) -> bool:
        """
        Check if GST microservice is available
        
        Returns:
            bool: True if service is reachable, False otherwise
        """
        try:
            url = f"{self.service_url}/api/v1/getCaptcha"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False


# Create a singleton instance for easy import
gst_client = GSTClient()


def get_captcha() -> Dict[str, Any]:
    """
    Convenience function for requesting CAPTCHA
    
    Returns:
        dict: CAPTCHA response with sessionId and image data
    """
    return gst_client.get_captcha()


def verify_gstin(session_id: str, gstin: str, captcha: str) -> Dict[str, Any]:
    """
    Convenience function for GST verification
    
    Args:
        session_id: Session ID from get_captcha()
        gstin: GST number to verify
        captcha: User-entered CAPTCHA text
        
    Returns:
        dict: Verification response
    """
    return gst_client.verify_gstin(session_id, gstin, captcha)


def is_gst_service_available() -> bool:
    """
    Convenience function to check service availability
    
    Returns:
        bool: True if GST service is available
    """
    return gst_client.is_service_available()