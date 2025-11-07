# Smart iInvoice Phase 2 - User Guide

Welcome to Smart iInvoice Phase 2! This guide will help you understand and use all the new features.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Bulk Invoice Upload](#bulk-invoice-upload)
3. [Invoice Health Score](#invoice-health-score)
4. [GST Verification Cache](#gst-verification-cache)
5. [Enhanced Analytics Dashboard](#enhanced-analytics-dashboard)
6. [User Profile Management](#user-profile-management)
7. [Settings and Preferences](#settings-and-preferences)
8. [Data Export](#data-export)
9. [Manual Data Entry](#manual-data-entry)
10. [Tips and Best Practices](#tips-and-best-practices)

---

## Getting Started

### Prerequisites

Before using Phase 2 features, ensure:
- Redis server is running
- Celery worker is active
- You have a registered account and are logged in

### Quick Start

1. **Login** to your Smart iInvoice account
2. Navigate to the **Dashboard** to see the new analytics
3. Try uploading multiple invoices using the **Bulk Upload** button
4. Check the **GST Cache** page to see verified vendors
5. Customize your **Profile** and **Settings**

---

## Bulk Invoice Upload

### How to Upload Multiple Invoices

1. Click the **"Bulk Upload"** button on the dashboard
2. Select multiple invoice files (PDF, JPG, PNG)
3. Click **"Upload"** to start processing
4. Monitor the real-time progress bar
5. Receive a notification when processing completes

### Features

- **Multi-file Selection**: Upload up to 50 invoices at once
- **Drag and Drop**: Drag files directly into the upload area
- **Real-time Progress**: See how many invoices have been processed
- **Background Processing**: Continue working while invoices process
- **Batch Summary**: View success/failure counts after completion

### Tips

- Ensure files are clear and readable for best AI extraction results
- Supported formats: PDF, JPG, JPEG, PNG
- Maximum file size: 10MB per invoice
- For large batches, processing may take several minutes

---

## Invoice Health Score

### Understanding Health Scores

Every invoice receives a health score from 0 to 10 based on:

| Category | Weight | What It Checks |
|----------|--------|----------------|
| Data Completeness | 25% | All required fields present |
| Vendor & Buyer Verification | 30% | Valid and verified GST numbers |
| Compliance & Legal Checks | 25% | Correct HSN rates, arithmetic accuracy |
| Fraud & Anomaly Detection | 15% | No duplicates, normal price ranges |
| AI Confidence | 5% | High confidence in data extraction |

### Health Status Levels

- **Healthy (8.0-10.0)**: ✅ Green - Invoice is compliant and low-risk
- **Review (5.0-7.9)**: ⚠️ Yellow - Minor issues, review recommended
- **At Risk (0.0-4.9)**: ❌ Red - Critical issues, immediate attention required

### Viewing Health Scores

1. **Invoice List**: See health score badges next to each invoice
2. **Invoice Detail**: View detailed breakdown by category
3. **Dashboard**: Check the Red Flag List for high-risk invoices
4. **Filtering**: Filter invoices by health status

### Key Flags

Each invoice shows specific issues that affected its score:
- Missing required fields
- Unverified GST numbers
- Incorrect HSN/SAC rates
- Arithmetic errors
- Duplicate submissions
- Price anomalies

---

## GST Verification Cache

### What is the GST Cache?

The GST Cache stores previously verified GST numbers, allowing instant verification without CAPTCHA for known vendors.

### Benefits

- **Faster Processing**: No CAPTCHA required for cached vendors
- **Reduced Manual Work**: Automatic verification for repeat vendors
- **Data Accuracy**: Stores complete business details
- **Easy Management**: Search, filter, and refresh entries

### Using the GST Cache

#### Viewing Cache Entries

1. Navigate to **GST Cache** from the sidebar
2. Browse all cached GST numbers
3. See legal name, trade name, status, and registration date

#### Searching and Filtering

- **Search**: Enter GSTIN, legal name, or trade name
- **Filter by Status**: Active or Inactive
- **Sort**: By recent, oldest, GSTIN, or company name

#### Refreshing Entries

1. Click the **"Refresh"** button next to any entry
2. Complete the CAPTCHA verification
3. Updated information is saved automatically

#### Exporting Cache Data

Click **"Export CSV"** to download all cache entries for offline analysis.

---

## Enhanced Analytics Dashboard

### Dashboard Components

#### 1. Invoice Per Day Chart

- **What It Shows**: Daily invoice processing volume
- **Color Coding**: 
  - Dark bars: Healthy invoices
  - Light bars: At-risk invoices
- **Time Range**: Select 5, 7, 10, or 14 days
- **Use Case**: Track processing trends and identify problem days

#### 2. Money Flow Donut Chart

- **What It Shows**: Spending distribution by product/service category
- **Categories**: Top 5 HSN/SAC codes by total spend
- **Details**: Hover to see exact amounts and percentages
- **Use Case**: Understand where your money is going

#### 3. Company Leaderboard

- **What It Shows**: Top 5 vendors by total spend
- **Columns**: Company name, total amount, invoice count
- **Use Case**: Identify your biggest suppliers

#### 4. Red Flag List

- **What It Shows**: Invoices with lowest health scores
- **Details**: Company name, date, health score
- **Action**: Click to view invoice details
- **Use Case**: Prioritize invoices requiring attention

### Real-time Updates

The dashboard updates automatically as new invoices are processed, ensuring you always see the latest data.

---

## User Profile Management

### Accessing Your Profile

Click your profile picture or name in the sidebar to access your profile page.

### Profile Features

#### Profile Picture

1. Click the camera icon on your profile picture
2. Select an image (max 1MB)
3. Supported formats: JPG, PNG
4. Image is automatically uploaded and displayed

#### Personal Information

- **First Name & Last Name**: Update your display name
- **Username**: View your username (cannot be changed)
- **Email**: Update your email address
- **Phone Number**: Add or update your phone number
- **Company Name**: Add your company information

#### Saving Changes

Click **"Save Changes"** to update your profile information.

---

## Settings and Preferences

### Account Settings

- **Profile Picture**: Upload or change your profile picture
- **Name**: Update first and last name
- **Username**: View your username
- **Email**: Update email address

### Connected Services

Connect your account to social services:
- **Facebook Connect**: Link your Facebook account
- **Google+ Connect**: Link your Google account

### Preferences

Customize your experience:
- **Sound Effects**: Enable/disable sound notifications
- **Animations**: Enable/disable UI animations
- **Notifications**: Control notification preferences

### Account Actions

- **Logout**: End your current session
- **Export My Data**: Download all your data (GDPR compliance)
- **Delete My Account**: Permanently delete your account and data

---

## Data Export

### Exporting Invoices

1. Navigate to the **GST Verification** page
2. Apply any filters (status, health score, confidence)
3. Click **"Export"** button
4. CSV file downloads automatically with timestamp

### Exporting GST Cache

1. Navigate to the **GST Cache** page
2. Click **"Export CSV"** button
3. All cache entries are exported

### Exporting All Your Data

1. Go to **Settings**
2. Click **"Export My Data"**
3. Comprehensive data export includes:
   - All invoices
   - Profile information
   - Preferences
   - GST cache entries

### CSV File Format

Exported files include:
- Timestamped filename for easy organization
- All visible columns from the table
- Applied filters are reflected in the export

---

## Manual Data Entry

### When to Use Manual Entry

Manual entry is required when:
- AI extraction fails due to poor image quality
- Document format is not recognized
- Critical fields cannot be extracted

### Manual Entry Process

1. **Notification**: You'll see an alert on the invoice detail page
2. **Click "Enter Invoice Data Manually"**
3. **Fill in the form**:
   - Invoice number and date
   - Vendor information
   - Buyer GSTIN
   - Grand total
   - Line items (description, HSN/SAC, quantity, price, GST rate)
4. **Add Line Items**: Click "Add Line Item" for multiple items
5. **Submit**: Click "Submit Invoice" to process

### Validation

Manual entries undergo the same compliance checks as AI-extracted invoices:
- GSTIN format validation
- HSN/SAC rate verification
- Arithmetic accuracy checks
- Duplicate detection

---

## Tips and Best Practices

### For Best Results

1. **Upload Clear Images**: Ensure invoices are readable and well-lit
2. **Use Bulk Upload**: Process multiple invoices efficiently
3. **Monitor Health Scores**: Regularly check the Red Flag List
4. **Keep Cache Updated**: Refresh GST entries periodically
5. **Export Data Regularly**: Maintain offline backups

### Performance Tips

1. **Batch Processing**: Upload invoices in batches of 10-20 for optimal performance
2. **Off-Peak Hours**: Process large batches during off-peak hours
3. **File Size**: Compress large PDF files before uploading
4. **Browser**: Use Chrome or Firefox for best compatibility

### Security Best Practices

1. **Strong Password**: Use a strong, unique password
2. **Regular Logout**: Logout when using shared computers
3. **Data Export**: Regularly export your data for backup
4. **Profile Picture**: Use professional images only

### Troubleshooting

#### Bulk Upload Not Working
- Check that Celery worker is running
- Verify Redis connection
- Try uploading fewer files at once

#### Health Score Not Showing
- Refresh the page
- Check that invoice processing is complete
- Contact support if issue persists

#### GST Cache Not Updating
- Verify internet connection
- Try refreshing the entry manually
- Check GST verification service status

---

## Support

For additional help:
- Check the main README.md for technical documentation
- Review error logs in the application
- Contact system administrator for technical issues

---

**Version**: Phase 2.0  
**Last Updated**: November 2024  
**Platform**: Smart iInvoice
