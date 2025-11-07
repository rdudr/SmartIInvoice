# Implementation Plan: Smart iInvoice Phase 2 Enhancements

## Overview

This implementation plan breaks down the Phase 2 enhancements into discrete, actionable coding tasks. Each task builds incrementally on previous work, ensuring the system remains functional throughout development. Tasks are organized by feature area and include specific references to requirements from the requirements document.

---

## Task List

- [x] 1. Set up asynchronous processing infrastructure





  - Install and configure Celery and Redis for background task processing
  - Create Celery configuration in Django settings
  - Set up Celery worker startup scripts
  - Create base task structure for invoice processing
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Implement database models for Phase 2 features




- [x] 2.1 Create InvoiceBatch model





  - Write model class with fields: batch_id, user, total_files, processed_count, failed_count, status, created_at
  - Create and run migration
  - _Requirements: 1.1_





- [x] 2.2 Create InvoiceDuplicateLink model


  - Write model class linking duplicate invoices to originals
  - Add indexes for performance
  - Create and run migration
  - _Requirements: 3.1, 3.2_


- [x] 2.3 Create GSTCacheEntry model




  - Write model class with all GST verification fields (gstin, legal_name, trade_name, status, etc.)
  - Add indexes on gstin, legal_name, and status
  - Create and run migration

  - _Requirements: 4.1, 4.2, 4.3_



- [x] 2.4 Create InvoiceHealthScore model

  - Write model class with overall_score, status, category scores, and key_flags
  - Create one-to-one relationship with Invoice

  - Create and run migration
  - _Requirements: 6.1, 6.2, 6.3_



- [x] 2.5 Create UserProfile model

  - Write model class with profile_picture, preferences, and social connections
  - Create one-to-one relationship with User

  - Create and run migration


  - _Requirements: 9.1, 9.2, 9.3_

- [x] 2.6 Create APIKeyUsage model

  - Write model class for tracking API key usage and status
  - Create and run migration



  - _Requirements: 12.1, 12.2_

- [x] 2.7 Extend Invoice model with Phase 2 fields

  - Add fields: extraction_method, extraction_failure_reason, ai_confidence_score, batch (ForeignKey)
  - Create and run migration
  - _Requirements: 2.1, 2.2, 5.1_

- [x] 3. Implement Invoice Health Score System




- [x] 3.1 Create InvoiceHealthScoreEngine class


  - Write calculate_health_score() main method
  - Implement _score_data_completeness() for 25% weight
  - Implement _score_verification() for 30% weight
  - Implement _score_compliance() for 25% weight
  - Implement _score_fraud_detection() for 15% weight
  - Implement _score_ai_confidence() for 5% weight
  - Calculate overall score (0-10) and determine status (HEALTHY/REVIEW/AT_RISK)
  - Generate key_flags list with specific issues
  - _Requirements: 6.1, 6.2, 6.3, 6.5_

- [x] 3.2 Write unit tests for health score engine


  - Test each category scoring method
  - Test overall score calculation
  - Test status determination logic
  - Test key flags generation
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 3.3 Integrate health scoring with invoice processing


  - Call health score calculation after all compliance checks complete
  - Store results in InvoiceHealthScore model
  - _Requirements: 6.1_

- [x] 3.4 Display health score in invoice list


  - Add health score column to invoice table
  - Use color-coded badges (green/yellow/red) for status
  - Show numerical score (0-10)
  - _Requirements: 6.4_

- [x] 3.5 Display health score details on invoice detail page


  - Show overall score and status prominently
  - Display breakdown by category with individual scores
  - List all key flags with descriptions
  - _Requirements: 6.4, 6.5_

- [x] 3.6 Add health score filtering


  - Add filter options for HEALTHY, REVIEW, AT_RISK statuses
  - Allow sorting by health score
  - _Requirements: 6.6_

- [x] 4. Build API Key Management System



- [x] 4.1 Implement APIKeyManager class


  - Write get_active_key() method to retrieve next available key
  - Write mark_key_exhausted() method for failover logic
  - Write reset_key_pool() method for daily reset
  - Add logging for key usage and failover events
  - _Requirements: 12.1, 12.2, 12.3_

- [x] 4.2 Write unit tests for API key management


  - Test key rotation logic
  - Test exhaustion handling
  - Test reset functionality
  - _Requirements: 12.1, 12.2_

- [x] 4.3 Integrate APIKeyManager with GeminiService


  - Modify GeminiService to use APIKeyManager instead of single key
  - Add error handling for quota exceeded errors
  - Implement automatic retry with next key on failure
  - _Requirements: 12.1, 12.2_



- [x] 5. Implement GST Verification Cache System



- [x] 5.1 Create GSTCacheService class

  - Write lookup_gstin() method to check cache
  - Write add_to_cache() method to store verified data
  - Write refresh_cache_entry() method to update from portal
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 5.2 Integrate cache with GST verification flow


  - Modify existing GST verification to check cache first
  - Add cache entry creation after successful CAPTCHA verification
  - Add fallback to CAPTCHA when cache miss occurs
  - _Requirements: 4.1, 4.2_

- [x] 5.3 Create GST Cache management page


  - Create view for displaying cached GST entries
  - Implement search functionality (by GSTIN, legal name, trade name)
  - Add filter by status (Active/Inactive)
  - Implement sortable columns
  - Add "Refresh" button for individual entries
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_



- [x] 5.4 Add GST Cache page to navigation
  - Add sidebar link to GST Cache page
  - Update URL routing
  - _Requirements: 8.1_

- [x] 5.5 Write integration tests for GST cache



  - Test cache lookup and miss scenarios
  - Test cache entry creation
  - Test refresh functionality
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 6. Build Confidence Score System







- [x] 6.1 Implement ConfidenceScoreCalculator class


  - Write calculate_confidence() method analyzing Gemini API response
  - Write get_confidence_level() method for categorization (HIGH/MEDIUM/LOW)
  - Consider factors: field completeness, OCR quality, response certainty
  - _Requirements: 5.1_

- [x] 6.2 Integrate confidence scoring with AI extraction


  - Modify invoice processing to calculate and store confidence score
  - Store score in Invoice.ai_confidence_score field
  - _Requirements: 5.1, 5.2_

- [x] 6.3 Display confidence score in UI


  - Add confidence badge to invoice detail page
  - Use color coding (green/yellow/red) based on level
  - Add visual indicators (icons) for confidence levels
  - _Requirements: 5.2, 5.3_

- [x] 6.4 Add confidence score filtering


  - Add filter option to invoice list page
  - Allow sorting by confidence score
  - _Requirements: 5.4, 5.5_

- [x] 7. Build Smart Duplicate Management System




- [ ] 7. Build Smart Duplicate Management System


- [x] 7.1 Create DuplicateLinkingService class


  - Write find_original_invoice() method to locate first occurrence
  - Write link_duplicate() method to create InvoiceDuplicateLink
  - Copy GST verification status from original to duplicate
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 7.2 Integrate duplicate linking with compliance checks


  - Modify existing duplicate detection to create links instead of just flags
  - Prevent redundant GST verification for linked duplicates
  - _Requirements: 3.1, 3.3_

- [x] 7.3 Display duplicate relationships in UI


  - Show link to original invoice on duplicate detail page
  - Show list of duplicates on original invoice detail page
  - Add visual indicator (badge) for duplicate status
  - _Requirements: 3.2, 3.5_

- [x] 7.4 Maintain duplicate history for audit


  - Ensure all duplicate submissions are logged
  - Display submission history on invoice detail page
  - _Requirements: 3.4_

-

- [ ] 8. Implement Bulk Upload System


- [x] 8.1 Create BulkUploadHandler class


  - Write handle_bulk_upload() method to accept multiple files
  - Create InvoiceBatch record for tracking
  - Queue individual invoice processing tasks
  - Return batch_id for status tracking
  - _Requirements: 1.1_

- [x] 8.2 Create Celery task for asynchronous invoice processing


  - Write process_invoice_async() task
  - Include full pipeline: AI extraction, compliance checks, GST verification, health scoring
  - Update batch progress counters
  - Handle individual invoice failures gracefully
  - _Requirements: 1.2, 1.3_

- [x] 8.3 Implement batch status tracking


  - Write get_batch_status() method returning progress data
  - Create API endpoint for AJAX polling
  - _Requirements: 1.4_

- [x] 8.4 Build bulk upload UI


  - Create multi-file selector with drag-and-drop support
  - Add file browser for selecting multiple files
  - Implement client-side file validation
  - _Requirements: 1.1_

- [x] 8.5 Add real-time progress indicators

  - Create progress bar showing "X of Y processed"
  - Implement AJAX polling to update progress
  - Display processing status (in progress, completed, failed)
  - _Requirements: 1.4_

- [x] 8.6 Add batch completion notifications


  - Show toast notification when batch completes
  - Display summary of results (success/failure counts)
  - Provide link to view batch results
  - _Requirements: 1.5_
- [x] 8.7 Write integration tests for bulk upload









- [ ] 8.7 Write integration tests for bulk upload


  - Test multi-file upload handling
  - Test asynchronous processing
  - Test progress tracking
  - Test failure scenarios
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [-] 9. Build Manual Data Entry Fallback System


- [x] 9.1 Create ManualEntryService class


  - Write flag_for_manual_entry() method to mark failed extractions
  - Write validate_manual_entry() method for data validation
  - _Requirements: 2.1, 2.4_

- [x] 9.2 Integrate manual entry flagging with AI extraction


  - Detect AI extraction failures
  - Store failure reason in Invoice.extraction_failure_reason
  - Set Invoice.extraction_method to 'MANUAL'
  - _Requirements: 2.1, 2.2_

- [x] 9.3 Create manual entry form


  - Build form with all required invoice fields
  - Add dynamic formset for line items
  - Implement client-side validation (GSTIN format, dates, numeric fields)
  - _Requirements: 2.3_

- [x] 9.4 Create manual entry page


  - Create view accessible from invoice detail when extraction fails
  - Display clear explanation of why AI extraction failed
  - Render manual entry form
  - _Requirements: 2.2, 2.3_

- [x] 9.5 Handle manual entry form submission



  - Validate submitted data using ManualEntryService
  - Run same compliance checks as AI-extracted invoices
  - Store invoice with manual entry flag
  - _Requirements: 2.4, 2.5_
-

- [x] 9.6 Write integration tests for manual entry





  - Test form validation
  - Test submission and processing
  - Test compliance checks on manual data
  - _Requirements: 2.3, 2.4_

- [x] 10. Build Enhanced Analytical Dashboard






- [x] 10.1 Create DashboardAnalyticsService class


  - Write get_invoice_per_day_data() method for bar chart
  - Write get_money_flow_by_hsn() method for donut chart
  - Write get_company_leaderboard() method for vendor ranking
  - Write get_red_flag_list() method for high-risk invoices
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 10.2 Create Invoice Per Day chart component


  - Implement grouped bar chart using Chart.js
  - Show genuine vs. at-risk invoices for last 5-14 days
  - Add date range filter
  - Use reference UI design for styling
  - _Requirements: 7.1, 7.6_

- [x] 10.3 Create Money Flow donut chart component

  - Implement donut chart showing spending by HSN/SAC category
  - Display top 5 categories with percentages
  - Add legend with HSN codes and amounts
  - Use grayscale color scheme from reference UI
  - Add hover interactions
  - _Requirements: 7.2_

- [x] 10.4 Create Company Leaderboard table

  - Display top 5 vendors by total spend
  - Show columns: Company Name, Total Amount, Invoice Count
  - Sort by amount (descending)
  - _Requirements: 7.3_

- [x] 10.5 Create Red Flag List table

  - Display invoices with lowest health scores
  - Show columns: Company Name, Date, Health Score
  - Use color coding for critical scores
  - Add links to invoice detail pages
  - _Requirements: 7.4_

- [x] 10.6 Integrate dashboard components into main dashboard page

  - Replace or enhance existing dashboard with new components
  - Use reference UI layout (referenceUIcode.html) as template
  - Ensure responsive design
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 10.7 Implement real-time dashboard updates


  - Add AJAX polling or WebSocket for live data updates
  - Update charts and tables as new invoices are processed
  - _Requirements: 7.5_

- [x] 10.8 Write unit tests for analytics service



  - Test data aggregation methods
  - Test date range filtering
  - Test sorting and limiting logic
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 11. Build User Profile Management

- [ ] 11.1 Create UserProfileService class
  - Write methods for profile CRUD operations
  - Add profile picture upload handling with validation
  - _Requirements: 9.1, 9.4_

- [ ] 11.2 Create profile page
  - Build view displaying current profile information
  - Show profile picture, name, username, email
  - Add form for editing profile data
  - Implement profile picture upload with 1MB size limit
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [ ] 11.3 Handle profile updates
  - Validate profile data on submission
  - Process profile picture uploads
  - Update UserProfile model
  - Show success/error messages
  - _Requirements: 9.4, 9.5_

- [ ] 11.4 Add profile page to navigation
  - Add link in user menu dropdown
  - Update URL routing
  - _Requirements: 9.1_

- [ ]* 11.5 Write integration tests for profile management
  - Test profile viewing
  - Test profile updates
  - Test profile picture upload
  - Test validation
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 12. Build Comprehensive Settings Management
- [ ] 12.1 Create settings page
  - Build comprehensive settings view with multiple sections
  - Implement Account Settings section (profile picture, name, username, email)
  - Add Connected Services section (Google, Facebook toggles)
  - Add Preferences section (notifications, sound, animations toggles)
  - Add Account Actions section (Logout, Export Data, Delete Account)
  - Use reference UI design (referenceUIcode.html) as template
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [ ] 12.2 Implement settings form handling
  - Process toggle switch changes for preferences
  - Handle social connection toggles (placeholder for future OAuth integration)
  - Validate and save settings to UserProfile
  - _Requirements: 10.2, 10.3_

- [ ] 12.3 Implement logout functionality
  - Add logout action to settings page
  - Clear session and redirect to login
  - _Requirements: 10.4_

- [ ] 12.4 Add settings page to navigation
  - Add sidebar link to Settings
  - Update URL routing
  - _Requirements: 10.1_

- [ ]* 12.5 Write integration tests for settings page
  - Test settings display
  - Test preference updates
  - Test logout functionality
  - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [ ] 13. Implement Data Export Capability
- [ ] 13.1 Create DataExportService class
  - Write export_invoices_to_csv() method
  - Write export_gst_cache_to_csv() method
  - Handle field selection and formatting
  - Generate proper CSV headers
  - _Requirements: 11.1, 11.2, 11.3_

- [ ] 13.2 Add export functionality to invoice list page
  - Add "Export" button to invoice list
  - Create view/endpoint for invoice export
  - Include all visible columns and filtered data
  - Generate timestamped filename
  - _Requirements: 11.1, 11.3, 11.4, 11.5_

- [ ] 13.3 Add export functionality to GST cache page
  - Add "Export" button to GST cache table
  - Create view/endpoint for GST cache export
  - Include all table columns
  - Generate timestamped filename
  - _Requirements: 11.2, 11.3, 11.4, 11.5_

- [ ] 13.4 Implement "Export My Data" in settings
  - Add comprehensive data export option in settings page
  - Export all user data (invoices, profile, preferences)
  - Generate downloadable archive
  - _Requirements: 10.5_

- [ ] 13.5 Write unit tests for data export
  - Test CSV generation
  - Test field formatting
  - Test filename generation
  - _Requirements: 11.1, 11.2, 11.3_

- [ ] 14. Implement Account Deletion
- [ ] 14.1 Create account deletion functionality
  - Add confirmation dialog with warnings
  - Implement soft delete or hard delete based on policy
  - Handle data retention requirements
  - Clear user session after deletion
  - _Requirements: 10.6_

- [ ] 14.2 Add account deletion to settings page
  - Add "Delete My Account" button
  - Implement confirmation modal
  - Show appropriate warnings
  - _Requirements: 10.6_

- [ ]* 14.3 Write integration tests for account deletion
  - Test deletion process
  - Test confirmation flow
  - Test data cleanup
  - _Requirements: 10.6_

- [ ] 15. Create Coming Soon Pages
- [ ] 15.1 Create ComingSoonView
  - Build simple template with professional message
  - Add "This feature is coming soon!" heading
  - Include brief description of planned functionality
  - Add "Return to Dashboard" button
  - _Requirements: 13.1, 13.2, 13.3_

- [ ] 15.2 Link non-functional features to Coming Soon page
  - Update "Reports" navigation link
  - Add any other placeholder features
  - _Requirements: 13.1_

- [ ] 15.3 Add optional email signup for feature notifications
  - Create simple form for email collection
  - Store interested users for future notification
  - _Requirements: 13.5_

- [ ] 16. Final Integration and Polish
- [ ] 16.1 Update navigation and routing
  - Ensure all new pages are accessible from sidebar
  - Update URL configuration
  - Add active state highlighting for current page
  - _Requirements: All_

- [ ] 16.2 Apply consistent styling across all new pages
  - Use Tailwind CSS classes from reference UI
  - Ensure responsive design for all components
  - Match color scheme and typography
  - _Requirements: All_

- [ ] 16.3 Add loading states and error messages
  - Implement loading spinners for async operations
  - Add user-friendly error messages
  - Ensure graceful degradation
  - _Requirements: All_

- [ ] 16.4 Optimize database queries
  - Add select_related and prefetch_related where needed
  - Verify all indexes are in place
  - Test query performance with large datasets
  - _Requirements: All_

- [ ] 16.5 Configure Celery for production
  - Set up proper worker configuration
  - Configure task time limits and retries
  - Set up monitoring and logging
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 16.6 Update documentation
  - Document new features in README
  - Add setup instructions for Redis and Celery
  - Document environment variables for multiple API keys
  - Create user guide for new features
  - _Requirements: All_

- [ ]* 16.7 Perform end-to-end testing
  - Test complete bulk upload workflow
  - Test manual entry fallback
  - Test dashboard with real data
  - Test all user profile and settings features
  - Verify data export functionality
  - _Requirements: All_

---

## Implementation Notes

### Task Execution Order
- Tasks should be executed in the order listed to ensure dependencies are met
- Infrastructure setup (Task 1) must be completed before any asynchronous features
- Database models (Task 2) should be created before implementing services that use them
- Core services (Tasks 3-7) should be completed before UI enhancements (Tasks 10-15)

### Optional Tasks
- Tasks marked with `*` are optional integration/end-to-end testing tasks
- Core unit tests for business logic (health scoring, API key management, analytics, data export) are required
- Integration tests can be deferred for faster initial delivery but should be completed before production deployment

### Testing Strategy
- Unit tests focus on individual service methods and calculations
- Integration tests verify end-to-end workflows
- All tests should be run before final deployment

### Dependencies
- Celery and Redis must be installed and running for bulk upload features
- Chart.js library must be included for dashboard visualizations
- Profile picture uploads require proper media file configuration

### Estimated Complexity
- High complexity: Tasks 1, 6, 8, 10 (require significant new infrastructure or logic)
- Medium complexity: Tasks 3, 4, 7, 9, 12 (extend existing functionality)
- Low complexity: Tasks 11, 13, 14, 15 (straightforward CRUD operations)
