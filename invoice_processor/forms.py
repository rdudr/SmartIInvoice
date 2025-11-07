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


class ManualInvoiceEntryForm(forms.Form):
    """Form for manual invoice data entry when AI extraction fails"""
    
    # Invoice-level fields
    invoice_id = forms.CharField(
        max_length=100,
        required=True,
        label='Invoice Number',
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
            'placeholder': 'e.g., INV-2024-001'
        })
    )
    
    invoice_date = forms.DateField(
        required=True,
        label='Invoice Date',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm'
        })
    )
    
    vendor_name = forms.CharField(
        max_length=255,
        required=True,
        label='Vendor Name',
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
            'placeholder': 'e.g., ABC Suppliers Pvt Ltd'
        })
    )
    
    vendor_gstin = forms.CharField(
        max_length=15,
        required=False,
        label='Vendor GSTIN',
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
            'placeholder': '22AAAAA0000A1Z5',
            'pattern': '[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}',
            'title': '15-character GSTIN (e.g., 22AAAAA0000A1Z5)'
        })
    )
    
    billed_company_gstin = forms.CharField(
        max_length=15,
        required=False,
        label='Billed Company GSTIN',
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
            'placeholder': '22AAAAA0000A1Z5',
            'pattern': '[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}',
            'title': '15-character GSTIN (e.g., 22AAAAA0000A1Z5)'
        })
    )
    
    grand_total = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        label='Grand Total (₹)',
        widget=forms.NumberInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        })
    )
    
    def clean_vendor_gstin(self):
        """Validate vendor GSTIN format"""
        gstin = self.cleaned_data.get('vendor_gstin', '').strip().upper()
        if gstin:
            import re
            pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
            if not re.match(pattern, gstin):
                raise ValidationError('Invalid GSTIN format. Must be 15 characters (e.g., 22AAAAA0000A1Z5)')
        return gstin
    
    def clean_billed_company_gstin(self):
        """Validate billed company GSTIN format"""
        gstin = self.cleaned_data.get('billed_company_gstin', '').strip().upper()
        if gstin:
            import re
            pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
            if not re.match(pattern, gstin):
                raise ValidationError('Invalid GSTIN format. Must be 15 characters (e.g., 22AAAAA0000A1Z5)')
        return gstin
    
    def clean_invoice_date(self):
        """Validate invoice date is not in the future"""
        from datetime import date
        invoice_date = self.cleaned_data.get('invoice_date')
        if invoice_date and invoice_date > date.today():
            raise ValidationError('Invoice date cannot be in the future')
        return invoice_date


class LineItemForm(forms.Form):
    """Form for individual line items in manual entry"""
    
    description = forms.CharField(
        max_length=500,
        required=True,
        label='Description',
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
            'placeholder': 'Item description'
        })
    )
    
    hsn_sac_code = forms.CharField(
        max_length=20,
        required=False,
        label='HSN/SAC Code',
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
            'placeholder': 'e.g., 8517'
        })
    )
    
    quantity = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        label='Quantity',
        widget=forms.NumberInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
            'placeholder': '1.00',
            'step': '0.01',
            'min': '0.01'
        })
    )
    
    unit_price = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        label='Unit Price (₹)',
        widget=forms.NumberInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        })
    )
    
    billed_gst_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=True,
        label='GST Rate (%)',
        widget=forms.NumberInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
            'placeholder': '18.00',
            'step': '0.01',
            'min': '0',
            'max': '100'
        })
    )
    
    line_total = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        label='Line Total (₹)',
        widget=forms.NumberInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0'
        })
    )
    
    def clean_quantity(self):
        """Validate quantity is positive"""
        quantity = self.cleaned_data.get('quantity')
        if quantity and quantity <= 0:
            raise ValidationError('Quantity must be greater than zero')
        return quantity
    
    def clean_billed_gst_rate(self):
        """Validate GST rate is between 0 and 100"""
        rate = self.cleaned_data.get('billed_gst_rate')
        if rate is not None and (rate < 0 or rate > 100):
            raise ValidationError('GST rate must be between 0 and 100')
        return rate


class UserProfileForm(forms.Form):
    """Form for editing user profile"""
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        label='First Name',
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary sm:text-sm',
            'placeholder': 'Enter your first name'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        label='Last Name',
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary sm:text-sm',
            'placeholder': 'Enter your last name'
        })
    )
    
    email = forms.EmailField(
        required=True,
        label='Email Address',
        widget=forms.EmailInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary sm:text-sm',
            'placeholder': 'your.email@example.com'
        })
    )
    
    username = forms.CharField(
        max_length=150,
        required=True,
        label='Username',
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm bg-gray-50 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm',
            'readonly': 'readonly',
            'disabled': 'disabled'
        })
    )
    
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        label='Phone Number',
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary sm:text-sm',
            'placeholder': '+1234567890'
        })
    )
    
    company_name = forms.CharField(
        max_length=255,
        required=False,
        label='Company Name',
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary sm:text-sm',
            'placeholder': 'Your company name'
        })
    )
    
    profile_picture = forms.ImageField(
        required=False,
        label='Profile Picture',
        widget=forms.FileInput(attrs={
            'class': 'hidden',
            'accept': 'image/jpeg,image/png,image/jpg',
            'id': 'profile-picture-input'
        }),
        help_text='Upload a profile picture (JPG, PNG). Maximum size: 1MB.'
    )
    
    def clean_email(self):
        """Validate email format"""
        email = self.cleaned_data.get('email', '').strip().lower()
        return email
    
    def clean_phone_number(self):
        """Validate phone number format"""
        phone = self.cleaned_data.get('phone_number', '').strip()
        if phone:
            # Remove common separators
            phone = phone.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
            # Basic validation - should contain only digits and optional + prefix
            if not phone.replace('+', '').isdigit():
                raise ValidationError('Phone number should contain only digits and optional + prefix')
        return phone