# Requirements Document

## Introduction

Smart iInvoice is an AI-powered invoice management and compliance platform that enables users to upload invoices, extract data using Google's Gemini API, perform automated compliance checks, and verify GST numbers through a semi-automated process. The system consists of a Django web application with a Tailwind CSS frontend and a Flask microservice for GST verification.

## Glossary

- **Smart iInvoice System**: The complete invoice management platform including Django web application and Flask GST microservice
- **Django Application**: The main web application built using Django MVT architecture
- **GST Microservice**: The Flask-based service that handles GST number verification via government portal
- **Gemini API**: Google's AI service used for extracting structured data from invoice images
- **Invoice Processor**: The Django component responsible for processing uploaded invoices
- **Analysis Engine**: The module that performs compliance checks on extracted invoice data
- **Compliance Flag**: An indicator of potential issues found during invoice analysis
- **GSTIN**: Goods and Services Tax Identification Number
- **HSN Code**: Harmonized System of Nomenclature code for goods
- **SAC Code**: Services Accounting Code for services
- **CAPTCHA Modal**: The interactive UI component for GST verification requiring user input

## Requirements

### Requirement 1

**User Story:** As a business user, I want to upload invoice images or PDFs to the system, so that I can automatically extract and analyze invoice data without manual data entry.

#### Acceptance Criteria

1. WHEN the user accesses the dashboard, THE Smart iInvoice System SHALL display an "Upload Invoice" button prominently
2. WHEN the user clicks the upload button, THE Smart iInvoice System SHALL present a modal with drag-and-drop functionality for file selection
3. WHEN the user uploads a file, THE Smart iInvoice System SHALL accept image formats (PNG, JPG, JPEG) and PDF format
4. WHEN the file upload is complete, THE Smart iInvoice System SHALL send the file to the Gemini API for data extraction
5. WHEN the Gemini API returns extracted data, THE Smart iInvoice System SHALL save the invoice record to the database with an initial status of "Pending Analysis" and immediately trigger the Analysis Engine, and upon completion of all checks, the status SHALL be updated to either "Cleared" or "Has Anomalies"

### Requirement 2

**User Story:** As a business user, I want the system to automatically extract structured data from invoice images, so that I can review invoice details without manual transcription.

#### Acceptance Criteria

1. WHEN the Invoice Processor receives an invoice image, THE Smart iInvoice System SHALL send the image to the Gemini API with a structured extraction prompt
2. WHEN the uploaded file is not an invoice, THE Gemini API SHALL return a JSON response with "is_invoice" field set to false
3. WHEN the uploaded file is a valid invoice, THE Gemini API SHALL return JSON containing invoice_id, invoice_date, vendor_name, vendor_gstin, billed_company_gstin, and line_items array
4. WHEN extracting line items, THE Gemini API SHALL include description, hsn_sac_code, quantity, unit_price, and billed_gst_rate for each item
5. WHEN a field is not present in the invoice, THE Gemini API SHALL return null for that field rather than inventing data

### Requirement 3

**User Story:** As a compliance officer, I want the system to automatically check for duplicate invoices, so that I can prevent processing the same invoice multiple times.

#### Acceptance Criteria

1. WHEN the Analysis Engine processes an invoice, THE Smart iInvoice System SHALL query the database for existing records with matching invoice_id and vendor_gstin
2. WHEN a duplicate invoice is found, THE Smart iInvoice System SHALL create a compliance flag with type "Duplicate"
3. WHEN a duplicate invoice is found, THE Smart iInvoice System SHALL mark the invoice with "Has Anomalies" status
4. WHEN no duplicate is found, THE Smart iInvoice System SHALL proceed with other compliance checks
5. WHEN displaying the dashboard, THE Smart iInvoice System SHALL show duplicate invoices in the "Suspected Invoices List"

### Requirement 4

**User Story:** As a compliance officer, I want the system to verify arithmetic calculations on invoices, so that I can identify billing errors automatically.

#### Acceptance Criteria

1. WHEN the Analysis Engine processes an invoice, THE Smart iInvoice System SHALL calculate the expected total for each line item based on quantity, unit_price, and billed_gst_rate
2. WHEN the calculated total differs from the extracted total, THE Smart iInvoice System SHALL create a compliance flag with type "Arithmetic Error"
3. WHEN the Analysis Engine verifies the grand total, THE Smart iInvoice System SHALL sum all line item totals and compare with the invoice grand total
4. WHEN the grand total verification fails, THE Smart iInvoice System SHALL create a compliance flag with type "Arithmetic Error"
5. WHEN all arithmetic checks pass, THE Smart iInvoice System SHALL proceed to the next compliance check

### Requirement 5

**User Story:** As a compliance officer, I want the system to validate HSN/SAC codes against official GST rates, so that I can detect incorrect tax rates on invoices.

#### Acceptance Criteria

1. WHEN the Analysis Engine initializes, THE Smart iInvoice System SHALL load GST rates from GST_Goods_Rates.csv and GST_Services_Rates.csv files
2. WHEN processing a line item, THE Smart iInvoice System SHALL look up the hsn_sac_code in the loaded GST master data
3. WHEN the billed_gst_rate differs from the official rate, THE Smart iInvoice System SHALL create a compliance flag with type "HSN Rate Mismatch"
4. WHEN the hsn_sac_code is not found in master data, THE Smart iInvoice System SHALL create a compliance flag with type "Unknown HSN/SAC Code"

### Requirement 6

**User Story:** As a procurement manager, I want the system to detect price anomalies by comparing against historical data, so that I can identify potentially fraudulent or erroneous pricing.

#### Acceptance Criteria

1. WHEN the Analysis Engine processes a line item, THE Smart iInvoice System SHALL normalize the item description to create a consistent product key by converting to lowercase and removing non-essential words
2. WHEN the product key is created, THE Smart iInvoice System SHALL query the database for historical prices for this product key from the same vendor
3. WHEN sufficient historical data exists (minimum three previous invoices), THE Smart iInvoice System SHALL calculate the average historical price
4. WHEN the current unit_price deviates by more than twenty-five percent from the historical average, THE Smart iInvoice System SHALL create a compliance flag with type "Price Anomaly"
5. WHEN insufficient historical data exists, THE Smart iInvoice System SHALL skip the price anomaly check for that item

### Requirement 7

**User Story:** As a business user, I want to view a dashboard with key metrics and visualizations, so that I can quickly understand the status of invoice processing and compliance.

#### Acceptance Criteria

1. WHEN the user accesses the dashboard page, THE Smart iInvoice System SHALL display a metrics card showing "Invoices Awaiting Verification", "Anomalies Found This Week", and "Total Amount Processed"
2. WHEN displaying anomaly breakdown, THE Smart iInvoice System SHALL render a donut chart showing distribution of Duplicate, Price Anomaly, HSN Mismatch, and Arithmetic Error flags
3. WHEN showing recent activity, THE Smart iInvoice System SHALL display the five most recently processed invoices with their status
4. WHEN displaying suspected invoices, THE Smart iInvoice System SHALL show the top five invoices with "Critical" compliance flags
5. WHEN the user clicks "View Report" on any widget, THE Smart iInvoice System SHALL navigate to the detailed report page

### Requirement 8

**User Story:** As a compliance officer, I want to verify vendor GST numbers through the government portal, so that I can ensure vendors are legitimate and registered.

#### Acceptance Criteria

1. WHEN the user accesses the GST Verification page, THE Smart iInvoice System SHALL display a table of all invoices with columns for Invoice Number, Vendor Name, Vendor GSTIN, Date, and Verification Status
2. WHEN the user applies a filter, THE Smart iInvoice System SHALL show only invoices matching the selected status (All, Pending Verification, Verified, Verification Failed)
3. WHEN the user clicks "Verify" on a pending invoice, THE Django Application SHALL call the GST Microservice to request a CAPTCHA
4. WHEN the GST Microservice returns a CAPTCHA, THE Smart iInvoice System SHALL display a modal with the CAPTCHA image and an input field
5. WHEN the user submits the CAPTCHA and GSTIN, THE Django Application SHALL send the verification request to the GST Microservice and update the invoice verification status based on the response

### Requirement 9

**User Story:** As a system administrator, I want the GST microservice to maintain session state for CAPTCHA verification, so that the verification process works correctly with the government portal.

#### Acceptance Criteria

1. WHEN the GST Microservice receives a CAPTCHA request, THE GST Microservice SHALL create a new session with the government GST portal
2. WHEN creating a session, THE GST Microservice SHALL generate a unique session identifier using UUID
3. WHEN fetching the CAPTCHA, THE GST Microservice SHALL store the session object in memory mapped to the session identifier
4. WHEN returning the CAPTCHA response, THE GST Microservice SHALL include the session identifier and base64-encoded CAPTCHA image
5. WHEN receiving a verification request, THE GST Microservice SHALL retrieve the stored session using the provided session identifier and submit the GSTIN and CAPTCHA to the government portal

### Requirement 10

**User Story:** As a business user, I want to register and log in to the system, so that my invoice data is secure and accessible only to authorized users.

#### Acceptance Criteria

1. WHEN the user accesses the application without authentication, THE Smart iInvoice System SHALL redirect to the login page
2. WHEN the user submits valid credentials, THE Smart iInvoice System SHALL authenticate the user and redirect to the dashboard
3. WHEN the user submits invalid credentials, THE Smart iInvoice System SHALL display an error message and remain on the login page
4. WHEN the user clicks "Register", THE Smart iInvoice System SHALL display a registration form with fields for username, email, and password
5. WHEN the user completes registration, THE Smart iInvoice System SHALL create a new user account and redirect to the login page

### Requirement 11

**User Story:** As a business user, I want the interface to follow a modern, clean design with consistent styling, so that the application is easy to use and visually appealing.

#### Acceptance Criteria

1. WHEN rendering any page, THE Smart iInvoice System SHALL apply Tailwind CSS classes for consistent styling
2. WHEN displaying the sidebar, THE Smart iInvoice System SHALL show navigation links for Dashboard, GST Verification, Reports, and Settings
3. WHEN rendering cards and widgets, THE Smart iInvoice System SHALL use light grey backgrounds with blue, purple, and teal accent colors
4. WHEN displaying data tables, THE Smart iInvoice System SHALL implement pagination with maximum ten rows per page
5. WHEN showing status badges, THE Smart iInvoice System SHALL use color coding (green for Verified, yellow for Pending, red for Failed)

### Requirement 12

**User Story:** As a developer, I want the system to handle errors gracefully, so that users receive helpful feedback when issues occur.

#### Acceptance Criteria

1. WHEN the Gemini API fails to respond, THE Smart iInvoice System SHALL log the error and display a user-friendly message indicating extraction failure
2. WHEN the GST Microservice is unavailable, THE Smart iInvoice System SHALL display an error message and allow the user to retry verification
3. WHEN file upload fails, THE Smart iInvoice System SHALL display an error message indicating the specific issue (file size, format, etc.)
4. WHEN database operations fail, THE Smart iInvoice System SHALL log the error and display a generic error message to the user
5. WHEN any exception occurs, THE Smart iInvoice System SHALL prevent sensitive error details from being displayed to end users
