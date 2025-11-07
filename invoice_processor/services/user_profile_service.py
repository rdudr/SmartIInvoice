"""
User Profile Service

Handles user profile CRUD operations and profile picture management.
"""

import logging
import os
from typing import Optional, Tuple
from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile
from django.core.exceptions import ValidationError
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


class UserProfileService:
    """Service for managing user profiles"""
    
    # Profile picture constraints
    MAX_PROFILE_PICTURE_SIZE = 1 * 1024 * 1024  # 1MB
    ALLOWED_IMAGE_FORMATS = ['JPEG', 'PNG', 'JPG']
    MAX_IMAGE_DIMENSION = 2000  # Max width or height in pixels
    
    def get_or_create_profile(self, user: User):
        """
        Get or create user profile
        
        Args:
            user: User instance
            
        Returns:
            UserProfile instance
        """
        from invoice_processor.models import UserProfile
        
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        if created:
            logger.info(f"Created new profile for user {user.username}")
        
        return profile
    
    def update_profile(self, user: User, **kwargs) -> Tuple[bool, Optional[str]]:
        """
        Update user profile with provided data
        
        Args:
            user: User instance
            **kwargs: Profile fields to update (phone_number, company_name, preferences)
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            profile = self.get_or_create_profile(user)
            
            # Update allowed fields
            allowed_fields = [
                'phone_number', 'company_name', 
                'facebook_connected', 'google_connected',
                'enable_sound_effects', 'enable_animations', 'enable_notifications'
            ]
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    setattr(profile, field, value)
            
            profile.save()
            logger.info(f"Updated profile for user {user.username}")
            
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to update profile: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def update_user_info(self, user: User, first_name: str = None, 
                        last_name: str = None, email: str = None) -> Tuple[bool, Optional[str]]:
        """
        Update user's basic information
        
        Args:
            user: User instance
            first_name: User's first name
            last_name: User's last name
            email: User's email address
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            if first_name is not None:
                user.first_name = first_name.strip()
            
            if last_name is not None:
                user.last_name = last_name.strip()
            
            if email is not None:
                email = email.strip().lower()
                # Check if email is already taken by another user
                if User.objects.filter(email=email).exclude(id=user.id).exists():
                    return False, "This email is already in use by another account"
                user.email = email
            
            user.save()
            logger.info(f"Updated user info for {user.username}")
            
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to update user info: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def validate_profile_picture(self, image_file: UploadedFile) -> Tuple[bool, Optional[str]]:
        """
        Validate profile picture file
        
        Args:
            image_file: Uploaded image file
            
        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        # Check file size
        if image_file.size > self.MAX_PROFILE_PICTURE_SIZE:
            size_mb = image_file.size / (1024 * 1024)
            return False, f"Image size ({size_mb:.1f}MB) exceeds 1MB limit"
        
        # Check file extension
        file_extension = os.path.splitext(image_file.name)[1].lower()
        if file_extension not in ['.jpg', '.jpeg', '.png']:
            return False, "Only JPG, JPEG, and PNG images are allowed"
        
        # Validate image content
        try:
            image = Image.open(image_file)
            
            # Check format
            if image.format not in self.ALLOWED_IMAGE_FORMATS:
                return False, f"Invalid image format. Only {', '.join(self.ALLOWED_IMAGE_FORMATS)} are allowed"
            
            # Check dimensions
            width, height = image.size
            if width > self.MAX_IMAGE_DIMENSION or height > self.MAX_IMAGE_DIMENSION:
                return False, f"Image dimensions ({width}x{height}) exceed maximum allowed ({self.MAX_IMAGE_DIMENSION}x{self.MAX_IMAGE_DIMENSION})"
            
            # Reset file pointer
            image_file.seek(0)
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error validating image: {str(e)}")
            return False, "Invalid or corrupted image file"
    
    def upload_profile_picture(self, user: User, image_file: UploadedFile) -> Tuple[bool, Optional[str]]:
        """
        Upload and set user profile picture
        
        Args:
            user: User instance
            image_file: Uploaded image file
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        # Validate image
        is_valid, error_msg = self.validate_profile_picture(image_file)
        if not is_valid:
            return False, error_msg
        
        try:
            profile = self.get_or_create_profile(user)
            
            # Delete old profile picture if exists
            if profile.profile_picture:
                old_path = profile.profile_picture.path
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                        logger.info(f"Deleted old profile picture: {old_path}")
                    except Exception as e:
                        logger.warning(f"Could not delete old profile picture: {str(e)}")
            
            # Optimize image before saving
            optimized_image = self._optimize_image(image_file)
            
            # Generate filename
            file_extension = os.path.splitext(image_file.name)[1].lower()
            filename = f"user_{user.id}_profile{file_extension}"
            
            # Save new profile picture
            profile.profile_picture.save(filename, optimized_image, save=True)
            
            logger.info(f"Uploaded profile picture for user {user.username}")
            
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to upload profile picture: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def _optimize_image(self, image_file: UploadedFile) -> ContentFile:
        """
        Optimize image for web (resize if needed, compress)
        
        Args:
            image_file: Uploaded image file
            
        Returns:
            ContentFile with optimized image
        """
        try:
            image = Image.open(image_file)
            
            # Convert RGBA to RGB if needed
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Resize if too large (maintain aspect ratio)
            max_size = 800  # Max dimension for profile pictures
            if image.width > max_size or image.height > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                logger.info(f"Resized image to {image.size}")
            
            # Save to BytesIO with optimization
            output = BytesIO()
            image.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)
            
            return ContentFile(output.read())
            
        except Exception as e:
            logger.error(f"Error optimizing image: {str(e)}")
            # Return original file if optimization fails
            image_file.seek(0)
            return ContentFile(image_file.read())
    
    def delete_profile_picture(self, user: User) -> Tuple[bool, Optional[str]]:
        """
        Delete user's profile picture
        
        Args:
            user: User instance
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            profile = self.get_or_create_profile(user)
            
            if profile.profile_picture:
                # Delete file from storage
                old_path = profile.profile_picture.path
                if os.path.exists(old_path):
                    os.remove(old_path)
                
                # Clear database field
                profile.profile_picture = None
                profile.save()
                
                logger.info(f"Deleted profile picture for user {user.username}")
                return True, None
            else:
                return False, "No profile picture to delete"
                
        except Exception as e:
            error_msg = f"Failed to delete profile picture: {str(e)}"
            logger.error(error_msg)
            return False, error_msg


# Singleton instance
user_profile_service = UserProfileService()
