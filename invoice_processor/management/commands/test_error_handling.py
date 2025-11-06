from django.core.management.base import BaseCommand
from django.test import Client
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test error handling and user feedback systems'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--test-type',
            type=str,
            choices=['gemini', 'gst', 'upload', 'all'],
            default='all',
            help='Type of error handling to test'
        )
    
    def handle(self, *args, **options):
        test_type = options['test_type']
        
        self.stdout.write(
            self.style.SUCCESS(f'Testing error handling: {test_type}')
        )
        
        if test_type in ['gemini', 'all']:
            self.test_gemini_error_handling()
        
        if test_type in ['gst', 'all']:
            self.test_gst_error_handling()
        
        if test_type in ['upload', 'all']:
            self.test_upload_error_handling()
        
        self.stdout.write(
            self.style.SUCCESS('Error handling tests completed')
        )
    
    def test_gemini_error_handling(self):
        """Test Gemini API error handling"""
        self.stdout.write('Testing Gemini API error handling...')
        
        from invoice_processor.services.gemini_service import GeminiService
        
        # Test with invalid API key
        try:
            service = GeminiService()
            service.api_key = 'invalid_key'
            
            # This should handle the error gracefully
            result = service.extract_data_from_image(None)
            
            if 'error' in result:
                self.stdout.write(
                    self.style.SUCCESS('✓ Gemini error handling working correctly')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('✗ Gemini error handling not working')
                )
        except Exception as e:
            logger.error(f"Error testing Gemini error handling: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f'✗ Gemini test failed: {str(e)}')
            )
    
    def test_gst_error_handling(self):
        """Test GST service error handling"""
        self.stdout.write('Testing GST service error handling...')
        
        from invoice_processor.services.gst_client import GSTClient
        
        try:
            client = GSTClient()
            client.service_url = 'http://invalid-url:9999'
            
            # This should handle the connection error gracefully
            result = client.get_captcha()
            
            if 'error' in result:
                self.stdout.write(
                    self.style.SUCCESS('✓ GST error handling working correctly')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('✗ GST error handling not working')
                )
        except Exception as e:
            logger.error(f"Error testing GST error handling: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f'✗ GST test failed: {str(e)}')
            )
    
    def test_upload_error_handling(self):
        """Test file upload error handling"""
        self.stdout.write('Testing file upload error handling...')
        
        try:
            # Create a test user
            user, created = User.objects.get_or_create(
                username='test_user',
                defaults={'email': 'test@example.com'}
            )
            
            client = Client()
            client.force_login(user)
            
            # Test with invalid file
            response = client.post('/upload/', {
                'invoice_file': 'invalid_file_content'
            })
            
            if response.status_code == 400:
                self.stdout.write(
                    self.style.SUCCESS('✓ Upload error handling working correctly')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('✗ Upload error handling not working')
                )
                
        except Exception as e:
            logger.error(f"Error testing upload error handling: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f'✗ Upload test failed: {str(e)}')
            )