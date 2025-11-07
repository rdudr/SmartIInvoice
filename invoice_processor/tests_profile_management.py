"""
Integration tests for User Profile Management

Tests profile viewing, updates, profile picture upload, and validation.
Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from io import BytesIO
import os

from invoice_processor.models import UserProfile
from invoice_processor.services.user_profile_service import user_profile_service


class ProfileManagementIntegrationTests(TestCase):
    """Integration tests for profile management functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.profile_url = reverse('user_profile')
    
    def create_test_image(self, size=(100, 100), format='PNG'):
        """Helper method to create a test image file"""
        image = Image.new('RGB', size, color='red')
        image_io = BytesIO()
        image.save(image_io, format=format)
        image_io.seek(0)
        image_io.name = f'test_image.{format.lower()}'
        return SimpleUploadedFile(
            image_io.name,
            image_io.read(),
            content_type=f'image/{format.lower()}'
        )
    
    # Test Profile Viewing (Requirement 9.1)
    
    def test_profile_page_requires_authentication(self):
        """Test that profile page requires user to be logged in"""
        response = self.client.get(self.profile_url)
        
        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
    
    def test_profile_page_displays_for_authenticated_user(self):
        """Test that authenticated user can view profile page"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profile.html')
        self.assertIn('form', response.context)
    
    def test_profile_page_displays_current_user_data(self):
        """Test that profile page displays current user information"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create profile with data
        profile = user_profile_service.get_or_create_profile(self.user)
        profile.phone_number = '+1234567890'
        profile.company_name = 'Test Company'
        profile.save()
        
        response = self.client.get(self.profile_url)
        
        form = response.context['form']
        self.assertEqual(form.initial['first_name'], 'Test')
        self.assertEqual(form.initial['last_name'], 'User')
        self.assertEqual(form.initial['email'], 'test@example.com')
        self.assertEqual(form.initial['username'], 'testuser')
        self.assertEqual(form.initial['phone_number'], '+1234567890')
        self.assertEqual(form.initial['company_name'], 'Test Company')
    
    def test_profile_auto_created_on_first_access(self):
        """Test that UserProfile is automatically created on first access"""
        self.client.login(username='testuser', password='testpass123')
        
        # Ensure no profile exists
        UserProfile.objects.filter(user=self.user).delete()
        
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, 200)
        # Profile should be created
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())
    
    # Test Profile Updates (Requirements 9.2, 9.4)
    
    def test_update_basic_user_info(self):
        """Test updating user's basic information (name, email)"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(self.profile_url, {
            'first_name': 'Updated',
            'last_name': 'Name',
            'email': 'updated@example.com',
            'username': 'testuser',  # Username is readonly but included in form
            'phone_number': '',
            'company_name': ''
        })
        
        # Should redirect back to profile page
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.profile_url)
        
        # Verify user data was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Name')
        self.assertEqual(self.user.email, 'updated@example.com')
    
    def test_update_profile_fields(self):
        """Test updating profile-specific fields (phone, company)"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(self.profile_url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'username': 'testuser',
            'phone_number': '+9876543210',
            'company_name': 'New Company Ltd'
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify profile data was updated
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.phone_number, '+9876543210')
        self.assertEqual(profile.company_name, 'New Company Ltd')
    
    def test_update_all_fields_together(self):
        """Test updating both user and profile fields in one request"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(self.profile_url, {
            'first_name': 'Complete',
            'last_name': 'Update',
            'email': 'complete@example.com',
            'username': 'testuser',
            'phone_number': '+1111111111',
            'company_name': 'Complete Company'
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify all updates
        self.user.refresh_from_db()
        profile = UserProfile.objects.get(user=self.user)
        
        self.assertEqual(self.user.first_name, 'Complete')
        self.assertEqual(self.user.last_name, 'Update')
        self.assertEqual(self.user.email, 'complete@example.com')
        self.assertEqual(profile.phone_number, '+1111111111')
        self.assertEqual(profile.company_name, 'Complete Company')
    
    def test_update_with_success_message(self):
        """Test that successful update shows success message"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(self.profile_url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'username': 'testuser',
            'phone_number': '',
            'company_name': ''
        }, follow=True)
        
        # Check for success message
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertIn('Profile updated successfully', str(messages[0]))
    
    # Test Profile Picture Upload (Requirements 9.3, 9.4)
    
    def test_upload_valid_profile_picture(self):
        """Test uploading a valid profile picture"""
        self.client.login(username='testuser', password='testpass123')
        
        test_image = self.create_test_image()
        
        response = self.client.post(self.profile_url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'username': 'testuser',
            'phone_number': '',
            'company_name': '',
            'profile_picture': test_image
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify profile picture was saved
        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.profile_picture)
        self.assertTrue(os.path.exists(profile.profile_picture.path))
        
        # Clean up
        if profile.profile_picture:
            os.remove(profile.profile_picture.path)
    
    def test_upload_profile_picture_jpeg(self):
        """Test uploading JPEG profile picture"""
        self.client.login(username='testuser', password='testpass123')
        
        test_image = self.create_test_image(format='JPEG')
        
        response = self.client.post(self.profile_url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'username': 'testuser',
            'phone_number': '',
            'company_name': '',
            'profile_picture': test_image
        })
        
        self.assertEqual(response.status_code, 302)
        
        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.profile_picture)
        
        # Clean up
        if profile.profile_picture:
            os.remove(profile.profile_picture.path)
    
    def test_upload_replaces_old_profile_picture(self):
        """Test that uploading new picture replaces old one"""
        self.client.login(username='testuser', password='testpass123')
        
        # Upload first picture
        first_image = self.create_test_image()
        self.client.post(self.profile_url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'username': 'testuser',
            'phone_number': '',
            'company_name': '',
            'profile_picture': first_image
        })
        
        profile = UserProfile.objects.get(user=self.user)
        first_picture_name = profile.profile_picture.name
        
        # Upload second picture
        second_image = self.create_test_image(size=(200, 200))
        self.client.post(self.profile_url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'username': 'testuser',
            'phone_number': '',
            'company_name': '',
            'profile_picture': second_image
        })
        
        profile.refresh_from_db()
        second_picture_name = profile.profile_picture.name
        
        # Profile picture should be updated (different file)
        self.assertNotEqual(first_picture_name, second_picture_name)
        # New file should exist
        self.assertTrue(os.path.exists(profile.profile_picture.path))
        
        # Clean up
        if profile.profile_picture:
            os.remove(profile.profile_picture.path)
    
    def test_profile_update_without_picture_preserves_existing(self):
        """Test that updating profile without picture preserves existing picture"""
        self.client.login(username='testuser', password='testpass123')
        
        # Upload picture first
        test_image = self.create_test_image()
        self.client.post(self.profile_url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'username': 'testuser',
            'phone_number': '',
            'company_name': '',
            'profile_picture': test_image
        })
        
        profile = UserProfile.objects.get(user=self.user)
        picture_path = profile.profile_picture.path
        
        # Update profile without picture
        self.client.post(self.profile_url, {
            'first_name': 'Updated',
            'last_name': 'User',
            'email': 'test@example.com',
            'username': 'testuser',
            'phone_number': '+1234567890',
            'company_name': 'Test Company'
        })
        
        profile.refresh_from_db()
        
        # Picture should still exist
        self.assertTrue(profile.profile_picture)
        self.assertEqual(profile.profile_picture.path, picture_path)
        self.assertTrue(os.path.exists(picture_path))
        
        # Other fields should be updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(profile.phone_number, '+1234567890')
        
        # Clean up
        if profile.profile_picture:
            os.remove(profile.profile_picture.path)
    
    # Test Validation (Requirement 9.5)
    
    def test_validation_required_fields(self):
        """Test validation for required fields"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(self.profile_url, {
            'first_name': '',  # Required
            'last_name': '',   # Required
            'email': '',       # Required
            'username': 'testuser',
            'phone_number': '',
            'company_name': ''
        })
        
        # Should not redirect (form has errors)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'first_name', 'This field is required.')
        self.assertFormError(response, 'form', 'last_name', 'This field is required.')
        self.assertFormError(response, 'form', 'email', 'This field is required.')
    
    def test_validation_invalid_email(self):
        """Test validation for invalid email format"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(self.profile_url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'invalid-email',  # Invalid format
            'username': 'testuser',
            'phone_number': '',
            'company_name': ''
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'email', 'Enter a valid email address.')
    
    def test_validation_duplicate_email(self):
        """Test validation prevents duplicate email addresses"""
        # Create another user with different email
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        # Try to use other user's email
        response = self.client.post(self.profile_url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'other@example.com',  # Already taken
            'username': 'testuser',
            'phone_number': '',
            'company_name': ''
        }, follow=True)
        
        # Should show error message
        messages = list(response.context['messages'])
        self.assertTrue(any('already in use' in str(msg) for msg in messages))
        
        # Email should not be changed
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'test@example.com')
    
    def test_validation_profile_picture_too_large(self):
        """Test validation rejects profile pictures over 1MB"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create a file that's actually over 1MB in file size
        # We need to create a large enough image that even compressed is over 1MB
        large_image = Image.new('RGB', (5000, 5000), color='red')
        image_io = BytesIO()
        # Save with minimal compression to ensure large file size
        large_image.save(image_io, format='PNG', compress_level=0)
        image_io.seek(0)
        
        # Verify it's actually over 1MB
        file_size = len(image_io.getvalue())
        self.assertGreater(file_size, 1024 * 1024, "Test image should be over 1MB")
        
        large_file = SimpleUploadedFile(
            'large_image.png',
            image_io.read(),
            content_type='image/png'
        )
        
        response = self.client.post(self.profile_url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'username': 'testuser',
            'phone_number': '',
            'company_name': '',
            'profile_picture': large_file
        }, follow=True)
        
        # Should show error message
        messages = list(response.context['messages'])
        self.assertTrue(any('1MB limit' in str(msg) or 'exceeds' in str(msg) for msg in messages))
    
    def test_validation_profile_picture_invalid_format(self):
        """Test validation rejects invalid image formats"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create invalid file (text file pretending to be image)
        invalid_file = SimpleUploadedFile(
            'test.txt',
            b'This is not an image',
            content_type='text/plain'
        )
        
        response = self.client.post(self.profile_url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'username': 'testuser',
            'phone_number': '',
            'company_name': '',
            'profile_picture': invalid_file
        })
        
        # Should have form errors
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertTrue(form.errors)
    
    def test_validation_phone_number_format(self):
        """Test validation for phone number format"""
        self.client.login(username='testuser', password='testpass123')
        
        # Invalid phone number with letters
        response = self.client.post(self.profile_url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'username': 'testuser',
            'phone_number': 'abc123xyz',  # Invalid
            'company_name': ''
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'phone_number', 
                           'Phone number should contain only digits and optional + prefix')
    
    def test_validation_phone_number_accepts_valid_formats(self):
        """Test that valid phone number formats are accepted"""
        self.client.login(username='testuser', password='testpass123')
        
        valid_numbers = [
            '+1234567890',
            '1234567890',
            '+91-9876543210',
            '(123) 456-7890'
        ]
        
        for phone_number in valid_numbers:
            response = self.client.post(self.profile_url, {
                'first_name': 'Test',
                'last_name': 'User',
                'email': 'test@example.com',
                'username': 'testuser',
                'phone_number': phone_number,
                'company_name': ''
            })
            
            # Should succeed (redirect)
            self.assertEqual(response.status_code, 302, 
                           f"Failed for phone number: {phone_number}")
    
    def test_validation_error_message_displayed(self):
        """Test that validation errors are displayed to user"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(self.profile_url, {
            'first_name': '',  # Invalid
            'last_name': 'User',
            'email': 'invalid-email',  # Invalid
            'username': 'testuser',
            'phone_number': '',
            'company_name': ''
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Check for error message
        messages = list(response.context['messages'])
        self.assertTrue(any('correct the errors' in str(msg).lower() for msg in messages))
    
    # Test Edge Cases
    
    def test_profile_update_with_whitespace_trimming(self):
        """Test that whitespace is trimmed from input fields"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(self.profile_url, {
            'first_name': '  Trimmed  ',
            'last_name': '  Name  ',
            'email': '  trimmed@example.com  ',
            'username': 'testuser',
            'phone_number': '  +1234567890  ',
            'company_name': '  Trimmed Company  '
        })
        
        self.assertEqual(response.status_code, 302)
        
        self.user.refresh_from_db()
        profile = UserProfile.objects.get(user=self.user)
        
        # Whitespace should be trimmed
        self.assertEqual(self.user.first_name, 'Trimmed')
        self.assertEqual(self.user.last_name, 'Name')
        self.assertEqual(self.user.email, 'trimmed@example.com')
    
    def test_profile_update_preserves_username(self):
        """Test that username cannot be changed through profile update"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(self.profile_url, {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'username': 'differentusername',  # Attempt to change
            'phone_number': '',
            'company_name': ''
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Username should remain unchanged
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'testuser')
    
    def test_concurrent_profile_updates(self):
        """Test that concurrent updates don't cause data loss"""
        self.client.login(username='testuser', password='testpass123')
        
        # First update
        self.client.post(self.profile_url, {
            'first_name': 'First',
            'last_name': 'Update',
            'email': 'first@example.com',
            'username': 'testuser',
            'phone_number': '+1111111111',
            'company_name': 'First Company'
        })
        
        # Second update (simulating concurrent request)
        self.client.post(self.profile_url, {
            'first_name': 'Second',
            'last_name': 'Update',
            'email': 'second@example.com',
            'username': 'testuser',
            'phone_number': '+2222222222',
            'company_name': 'Second Company'
        })
        
        # Last update should win
        self.user.refresh_from_db()
        profile = UserProfile.objects.get(user=self.user)
        
        self.assertEqual(self.user.first_name, 'Second')
        self.assertEqual(self.user.email, 'second@example.com')
        self.assertEqual(profile.phone_number, '+2222222222')
        self.assertEqual(profile.company_name, 'Second Company')
