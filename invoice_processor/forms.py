from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import os


class CustomAuthenticationForm(AuthenticationForm):
    """Custom login form with Tailwind CSS styling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Tailwind CSS classes to form fields
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm'
            })


class CustomUserCreationForm(UserCreationForm):
    """Custom user registration form with email field"""
    email = forms.EmailField(required=True, help_text='Required. Enter a valid email address.')
    first_name = forms.CharField(max_length=30, required=True, help_text='Required.')
    last_name = forms.CharField(max_length=30, required=True, help_text='Required.')

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Tailwind CSS classes to form fields
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm'
            })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


class InvoiceUploadForm(forms.Form):
    """Form for invoice file upload with validation"""
    
    invoice_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'hidden',
            'accept': '.png,.jpg,.jpeg,.pdf',
            'id': 'invoice-file-input'
        }),
        help_text='Upload invoice image (PNG, JPG, JPEG) or PDF file. Maximum size: 10MB.'
    )
    
    def clean_invoice_file(self):
        """Validate uploaded file with comprehensive checks"""
        file = self.cleaned_data.get('invoice_file')
        
        if not file:
            raise ValidationError("Please select a file to upload.")
        
        # Check if file has a name
        if not hasattr(file, 'name') or not file.name:
            raise ValidationError("Invalid file. Please select a valid file.")
        
        # Check file size (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        if file.size > max_size:
            size_mb = file.size / (1024 * 1024)
            raise ValidationError(f"File size ({size_mb:.1f}MB) exceeds the 10MB limit. Please upload a smaller file.")
        
        # Check minimum file size (1KB to avoid empty files)
        min_size = 1024  # 1KB
        if file.size < min_size:
            raise ValidationError("File is too small. Please upload a valid invoice file.")
        
        # Check file extension
        allowed_extensions = ['.png', '.jpg', '.jpeg', '.pdf']
        file_extension = os.path.splitext(file.name)[1].lower()
        
        if not file_extension:
            raise ValidationError("File must have a valid extension. Please upload a PNG, JPG, JPEG, or PDF file.")
        
        if file_extension not in allowed_extensions:
            raise ValidationError(f"Unsupported file type '{file_extension}'. Please upload a PNG, JPG, JPEG, or PDF file.")
        
        # Check MIME type for additional security
        allowed_mime_types = [
            'image/png', 'image/jpeg', 'image/jpg', 'application/pdf'
        ]
        
        if hasattr(file, 'content_type') and file.content_type:
            if file.content_type not in allowed_mime_types:
                raise ValidationError(f"Invalid file type '{file.content_type}'. Please upload a valid image or PDF file.")
        
        # Additional file content validation
        try:
            # Reset file pointer to beginning for content validation
            file.seek(0)
            
            # Read first few bytes to validate file signature
            file_header = file.read(16)
            file.seek(0)  # Reset pointer
            
            # Check file signatures (magic numbers)
            if file_extension in ['.jpg', '.jpeg']:
                if not file_header.startswith(b'\xff\xd8\xff'):
                    raise ValidationError("File appears to be corrupted or is not a valid JPEG image.")
            elif file_extension == '.png':
                if not file_header.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValidationError("File appears to be corrupted or is not a valid PNG image.")
            elif file_extension == '.pdf':
                if not file_header.startswith(b'%PDF'):
                    raise ValidationError("File appears to be corrupted or is not a valid PDF document.")
                    
        except Exception as e:
            # If we can't validate the file content, log it but don't fail
            # This prevents issues with file-like objects that don't support seek
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not validate file content for {file.name}: {str(e)}")
        
        return file