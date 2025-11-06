# Implementation Plan

- [x] 1. Set up Django project structure and configuration





  - Create Django project named 'smartinvoice' with initial settings
  - Create 'invoice_processor' Django app
  - Configure Tailwind CSS integration for styling
  - Set up environment variables for API keys and configuration
  - Create directory structure for services, templates, and static files
  - _Requirements: 10.1, 10.2, 11.1_

- [x] 2. Implement database models and migrations





  - Define Invoice model with all required fields and indexes
  - Define LineItem model with normalized_key field for price comparison
  - Define ComplianceFlag model with severity and flag_type fields
  - Create and run initial database migrations
  - _Requirements: 1.5, 2.3, 3.2, 4.2, 5.3, 6.3, 8.5_

- [x] 2b. Create management command for HSN data loading





  - Create custom Django management command (e.g., python manage.py load_hsn_data)
  - Write script to parse GST_Goods_Rates.csv and GST_Services_Rates.csv files
  - Generate cached file (JSON or pickle) for analysis engine to load into memory
  - Document command usage in README
  - _Requirements: 5.1_

- [x] 3. Build authentication system





  - Create user registration form and view
  - Create login page with custom template
  - Implement logout functionality
  - Add login_required decorators to protected views
  - Create base template with navigation for authenticated users
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 4. Implement Gemini API integration service






  - Create gemini_service.py module in services directory
  - Implement extract_data_from_image function with structured prompt
  - Configure API key from environment variables
  - Add error handling for API timeouts and invalid responses
  - Test with sample invoice images to verify extraction accuracy
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 12.1_

- [x] 5. Build analysis engine for compliance checks





  - Create analysis_engine.py module in services directory
  - Implement run_all_checks orchestration function
  - Implement check_duplicates function to detect duplicate invoices
  - Implement check_arithmetics function for calculation verification
  - Load HSN/SAC master data on startup (e.g., within AppConfig.ready() method to populate an in-memory dictionary)
  - Implement check_hsn_rates function with master data lookup
  - Implement normalize_product_key function for consistent matching
  - Implement check_price_outliers function with historical price comparison
  - _Requirements: 3.1, 3.2, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4_

- [x] 6. Create invoice upload functionality





  - Create upload modal UI component with drag-and-drop
  - Implement file upload view with validation (type, size)
  - Integrate gemini_service for data extraction
  - Save Invoice and LineItem records to database
  - Trigger analysis_engine synchronously and update invoice status
  - Return JSON response with upload status for AJAX handling
  - Add loading indicator for user feedback during processing
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 12.3_

- [x] 7. Build dashboard page with metrics and visualizations





  - Create dashboard view with metrics calculation logic
  - Implement metrics card showing key statistics
  - Create donut chart component for anomaly breakdown
  - Build recent activity feed showing latest invoices
  - Create suspected invoices list with critical flags
  - Style dashboard with Tailwind CSS following design specifications
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 11.1, 11.2, 11.3_

- [x] 8. Implement GST client for microservice communication





  - Create gst_client.py module in services directory
  - Implement get_captcha function to request CAPTCHA from Flask service
  - Implement verify_gstin function to submit verification request
  - Add error handling for microservice unavailability
  - Configure GST microservice URL from environment variables
  - _Requirements: 8.3, 8.4, 9.4, 12.2_
-

- [x] 9. Create GST verification page and workflow




  - Build GST verification page template with invoice table
  - Implement table with pagination (10 rows per page)
  - Add filter functionality (All, Pending, Verified, Failed)
  - Create CAPTCHA modal component with image display
  - Implement AJAX handlers for CAPTCHA request and verification submission
  - Update invoice gst_verification_status based on response
  - Add status badges with color coding (green, yellow, red)
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5, 11.4, 11.5_

- [x] 10. Implement error handling and user feedback




  - Add try-catch blocks for Gemini API calls with retry logic
  - Implement error messages for GST microservice failures
  - Add validation error messages for file uploads
  - Create user-friendly error pages for common errors
  - Ensure sensitive error details are not exposed to users
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [x] 11. Style application with Tailwind CSS





  - Create base template with sidebar and top bar navigation
  - Apply color palette (light grey, blue, purple, teal accents)
  - Style all cards, buttons, and form elements consistently
  - Implement responsive design for mobile and tablet
  - Add hover effects and transitions for better UX
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 12. Write unit tests for core functionality





  - Write tests for model validations and relationships
  - Write tests for gemini_service with mocked API responses
  - Write tests for analysis_engine functions with sample data
  - Write tests for normalize_product_key function
  - Write tests for gst_client with mocked microservice
  - _Requirements: All requirements (validation)_

- [x] 13. Perform integration and manual testing





  - Test complete invoice upload and processing flow
  - Test GST verification workflow end-to-end
  - Test authentication and authorization flows
  - Verify status transitions work correctly
  - Test error handling scenarios
  - _Requirements: All requirements (validation)_

- [ ] 14. Create deployment configuration


  - Set up environment variables template file
  - Create requirements.txt with all dependencies
  - Document process for running Django and Flask services
  - Create instructions for database migrations
  - Add README with setup and deployment instructions
  - _Requirements: All requirements (deployment)_
