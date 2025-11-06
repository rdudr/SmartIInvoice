import os
import json
import logging
import time
from typing import Dict, Any, Optional
from decouple import config
import google.generativeai as genai
from PIL import Image
import io

logger = logging.getLogger(__name__)


class GeminiService:
    """Service for extracting invoice data using Google Gemini API"""
    
    def __init__(self):
        """Initialize Gemini service with API key from environment"""
        self.api_key = config('GEMINI_API_KEY', default=None)
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-pro-vision')
        
        # Configuration for API calls
        self.max_retries = 1
        self.timeout_seconds = 30
        
    def extract_data_from_image(self, image_file) -> Dict[str, Any]:
        """
        Extract structured invoice data from an image file using Gemini API
        
        Args:
            image_file: Uploaded file object (image or PDF)
            
        Returns:
            dict: Extracted invoice data or {"is_invoice": false} if not an invoice
        """
        try:
            # Process the image file
            image = self._process_image_file(image_file)
            if not image:
                logger.error("Failed to process uploaded image file")
                return {
                    "is_invoice": False, 
                    "error": "Unable to process the uploaded file. Please ensure it's a valid image or PDF.",
                    "error_code": "FILE_PROCESSING_ERROR"
                }
            
            # Create structured prompt for invoice extraction
            prompt = self._create_extraction_prompt()
            
            # Call Gemini API with retry logic
            response = self._call_gemini_api(prompt, image)
            
            if not response:
                logger.error("Failed to get response from Gemini API after retries")
                return {
                    "is_invoice": False, 
                    "error": "Invoice extraction service is temporarily unavailable. Please try again in a few moments.",
                    "error_code": "API_UNAVAILABLE"
                }
            
            # Parse and validate the response
            extracted_data = self._parse_gemini_response(response)
            
            return extracted_data
            
        except ValueError as e:
            logger.error(f"Validation error in extract_data_from_image: {str(e)}")
            return {
                "is_invoice": False, 
                "error": "Invalid file format or corrupted file. Please upload a clear image or PDF.",
                "error_code": "VALIDATION_ERROR"
            }
        except MemoryError as e:
            logger.error(f"Memory error processing large file: {str(e)}")
            return {
                "is_invoice": False, 
                "error": "File is too large to process. Please upload a smaller file (under 10MB).",
                "error_code": "FILE_TOO_LARGE"
            }
        except Exception as e:
            logger.error(f"Unexpected error in extract_data_from_image: {str(e)}")
            return {
                "is_invoice": False, 
                "error": "An unexpected error occurred while processing your invoice. Please try again.",
                "error_code": "UNEXPECTED_ERROR"
            } 
   
    def _process_image_file(self, image_file) -> Optional[Image.Image]:
        """
        Process uploaded file and convert to PIL Image
        
        Args:
            image_file: Uploaded file object
            
        Returns:
            PIL.Image: Processed image or None if processing fails
        """
        try:
            # Reset file pointer to beginning
            image_file.seek(0)
            
            # Read file content
            file_content = image_file.read()
            
            # Create PIL Image from file content
            image = Image.open(io.BytesIO(file_content))
            
            # Convert to RGB if necessary (for PNG with transparency)
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')
            
            return image
            
        except Exception as e:
            logger.error(f"Error processing image file: {str(e)}")
            return None
    
    def _create_extraction_prompt(self) -> str:
        """
        Create structured prompt for invoice data extraction
        
        Returns:
            str: Formatted prompt for Gemini API
        """
        return '''
You are an expert invoice data extraction system. Analyze the provided image and extract invoice information.

IMPORTANT INSTRUCTIONS:
1. First determine if this image contains an invoice. If not, return {"is_invoice": false}
2. If it is an invoice, extract the following fields exactly as specified
3. Return ONLY valid JSON - no additional text or explanations
4. Use null for any field that is not present or clearly readable
5. Never invent or guess data - only extract what is clearly visible

Required JSON structure:
{
    "is_invoice": true,
    "invoice_id": "string or null",
    "invoice_date": "YYYY-MM-DD format or null",
    "vendor_name": "string or null",
    "vendor_gstin": "15-character GST number or null",
    "billed_company_gstin": "15-character GST number or null",
    "grand_total": "decimal number or null",
    "line_items": [
        {
            "description": "string or null",
            "hsn_sac_code": "string or null",
            "quantity": "decimal number or null",
            "unit_price": "decimal number or null",
            "billed_gst_rate": "decimal percentage (e.g., 18.0) or null",
            "line_total": "decimal number or null"
        }
    ]
}

Extract data carefully and return only the JSON response.
''' 
   
    def _call_gemini_api(self, prompt: str, image: Image.Image) -> Optional[str]:
        """
        Call Gemini API with retry logic and error handling
        
        Args:
            prompt: Extraction prompt
            image: PIL Image object
            
        Returns:
            str: API response text or None if failed
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Calling Gemini API (attempt {attempt + 1}/{self.max_retries + 1})")
                
                # Generate content using Gemini
                response = self.model.generate_content([prompt, image])
                
                if response and response.text:
                    logger.info("Successfully received response from Gemini API")
                    return response.text.strip()
                else:
                    logger.warning(f"Empty response from Gemini API on attempt {attempt + 1}")
                    last_error = "Empty response from API"
                    
            except Exception as e:
                error_msg = str(e)
                last_error = error_msg
                
                # Log specific error types for better debugging
                if "quota" in error_msg.lower() or "rate" in error_msg.lower():
                    logger.error(f"Rate limit/quota exceeded on attempt {attempt + 1}: {error_msg}")
                elif "timeout" in error_msg.lower():
                    logger.error(f"Timeout error on attempt {attempt + 1}: {error_msg}")
                elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                    logger.error(f"Network error on attempt {attempt + 1}: {error_msg}")
                else:
                    logger.error(f"Gemini API call failed on attempt {attempt + 1}: {error_msg}")
                
                # If this is not the last attempt, wait before retrying
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
        
        logger.error(f"All Gemini API attempts failed. Last error: {last_error}")
        return None
    
    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse and validate Gemini API response
        
        Args:
            response_text: Raw response from Gemini API
            
        Returns:
            dict: Parsed and validated invoice data
        """
        try:
            # Clean the response text (remove any markdown formatting)
            cleaned_text = response_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Parse JSON
            data = json.loads(cleaned_text)
            
            # Validate required structure
            if not isinstance(data, dict):
                logger.error("Gemini response is not a valid JSON object")
                return {
                    "is_invoice": False, 
                    "error": "Invalid response format from extraction service.",
                    "error_code": "INVALID_RESPONSE_FORMAT"
                }
            
            # Check if it's identified as an invoice
            if not data.get('is_invoice', False):
                logger.info("File was not identified as an invoice by Gemini")
                return {
                    "is_invoice": False,
                    "error": "The uploaded file does not appear to be a valid invoice. Please upload a clear invoice image or PDF.",
                    "error_code": "NOT_AN_INVOICE"
                }
            
            # Validate and clean the extracted data
            validated_data = self._validate_extracted_data(data)
            
            return validated_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.error(f"Raw response (first 500 chars): {response_text[:500]}")
            return {
                "is_invoice": False, 
                "error": "Unable to process the invoice data. The image may be unclear or corrupted.",
                "error_code": "JSON_PARSE_ERROR"
            }
        except Exception as e:
            logger.error(f"Unexpected error parsing Gemini response: {str(e)}")
            return {
                "is_invoice": False, 
                "error": "An error occurred while processing the invoice data. Please try again.",
                "error_code": "RESPONSE_PROCESSING_ERROR"
            }    

    def _validate_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean extracted invoice data
        
        Args:
            data: Raw extracted data from Gemini
            
        Returns:
            dict: Validated and cleaned invoice data
        """
        validated = {
            "is_invoice": True,
            "invoice_id": self._clean_string(data.get('invoice_id')),
            "invoice_date": self._clean_date(data.get('invoice_date')),
            "vendor_name": self._clean_string(data.get('vendor_name')),
            "vendor_gstin": self._clean_gstin(data.get('vendor_gstin')),
            "billed_company_gstin": self._clean_gstin(data.get('billed_company_gstin')),
            "grand_total": self._clean_decimal(data.get('grand_total')),
            "line_items": []
        }
        
        # Validate line items
        line_items = data.get('line_items', [])
        if isinstance(line_items, list):
            for item in line_items:
                if isinstance(item, dict):
                    validated_item = {
                        "description": self._clean_string(item.get('description')),
                        "hsn_sac_code": self._clean_string(item.get('hsn_sac_code')),
                        "quantity": self._clean_decimal(item.get('quantity')),
                        "unit_price": self._clean_decimal(item.get('unit_price')),
                        "billed_gst_rate": self._clean_decimal(item.get('billed_gst_rate')),
                        "line_total": self._clean_decimal(item.get('line_total'))
                    }
                    validated["line_items"].append(validated_item)
        
        return validated
    
    def _clean_string(self, value: Any) -> Optional[str]:
        """Clean and validate string values"""
        if value is None or value == "":
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned if cleaned else None
        return str(value).strip() if str(value).strip() else None
    
    def _clean_date(self, value: Any) -> Optional[str]:
        """Clean and validate date values"""
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            # Basic date format validation (YYYY-MM-DD)
            if len(cleaned) == 10 and cleaned.count('-') == 2:
                return cleaned
        return None
    
    def _clean_gstin(self, value: Any) -> Optional[str]:
        """Clean and validate GSTIN values"""
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip().upper()
            # Basic GSTIN validation (15 characters)
            if len(cleaned) == 15:
                return cleaned
        return None
    
    def _clean_decimal(self, value: Any) -> Optional[float]:
        """Clean and validate decimal values"""
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                cleaned = value.strip().replace(',', '')
                return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            pass
        return None


# Create a singleton instance for easy import
gemini_service = GeminiService()


def extract_data_from_image(image_file) -> Dict[str, Any]:
    """
    Convenience function for extracting invoice data from image
    
    Args:
        image_file: Uploaded file object
        
    Returns:
        dict: Extracted invoice data
    """
    return gemini_service.extract_data_from_image(image_file)