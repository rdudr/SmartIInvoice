# Requirements Document

## Introduction

This document outlines the requirements for Phase 2 enhancements to the Smart iInvoice platform. Building upon the MVP foundation, these enhancements introduce advanced intelligence, automation, sophisticated risk analysis, and a significantly upgraded user experience. The goal is to transform Smart iInvoice from a functional invoice processor into an intelligent business analytics platform that provides deep insights, automates repetitive tasks, and delivers a comprehensive, user-centric experience.

## Glossary

- **System**: The Smart iInvoice web application
- **User**: An authenticated individual using the Smart iInvoice platform
- **Invoice**: A digital document (PDF, image) containing transaction details between buyer and seller
- **GST Cache**: An internal database storing previously verified GST numbers and their associated business details
- **Invoice Health Score**: A quantitative risk assessment score (0-10) calculated using weighted compliance categories
- **Bulk Upload**: The capability to select and upload multiple invoice files simultaneously
- **Confidence Score**: A numerical value (0-100%) indicating the AI's certainty in extracted invoice data
- **Red Flag List**: A prioritized list of high-risk invoices requiring immediate attention
- **Company Leaderboard**: A ranked display of vendors by total spend and invoice volume
- **API Key Pool**: A collection of multiple Gemini API keys managed for automatic failover
- **Background Processing**: Asynchronous task execution that allows users to continue working while operations complete
- **Manual Entry Form**: A user interface for manually inputting invoice data when AI extraction fails

## Requirements

### Requirement 1: Bulk Invoice Upload

**User Story:** As a User, I want to upload multiple invoice files at once, so that I can process large batches efficiently without waiting for each file individually.

#### Acceptance Criteria

1. WHEN the User selects multiple invoice files through the upload interface, THE System SHALL accept all selected files for processing
2. WHEN multiple invoices are submitted, THE System SHALL process all invoices asynchronously in the background
3. WHILE invoices are being processed in the background, THE System SHALL allow the User to continue using other features without interruption
4. THE System SHALL display real-time progress indicators showing the number of invoices processed and remaining
5. WHEN all invoices in a batch are processed, THE System SHALL notify the User of completion with a summary of results

### Requirement 2: Manual Data Entry Fallback

**User Story:** As a User, I want to manually enter invoice data when the AI cannot read it, so that I can ensure no invoice is lost due to poor image quality or extraction failures.

#### Acceptance Criteria

1. WHEN the AI extraction fails for an invoice, THE System SHALL flag the invoice for manual review
2. THE System SHALL display a clear, user-friendly reason explaining why the AI extraction failed
3. THE System SHALL present a structured manual entry form with all required invoice fields
4. WHEN the User submits manually entered data, THE System SHALL validate the data against the same compliance rules as AI-extracted invoices
5. THE System SHALL store manually entered invoices with a flag indicating manual entry for audit purposes

### Requirement 3: Smart Duplicate Management

**User Story:** As a User, I want the system to automatically link duplicate invoices to their originals, so that I can avoid redundant verification work and maintain clean data.

#### Acceptance Criteria

1. WHEN the System detects a duplicate invoice, THE System SHALL automatically link it to the original previously processed invoice
2. THE System SHALL display the relationship between duplicate and original invoices in the invoice detail view
3. THE System SHALL prevent redundant GST verification checks for linked duplicate invoices
4. THE System SHALL maintain a history of all duplicate submissions for audit purposes
5. WHEN viewing a duplicate invoice, THE System SHALL provide a direct link to navigate to the original invoice

### Requirement 4: Automated GST Verification Cache

**User Story:** As a User, I want the system to remember previously verified GST numbers, so that I can skip the manual CAPTCHA step for known vendors and speed up processing.

#### Acceptance Criteria

1. THE System SHALL maintain an internal database storing all successfully verified GST numbers and their business details
2. WHEN processing an invoice with a GST number that exists in the cache, THE System SHALL verify the GST instantly without requiring CAPTCHA entry
3. WHEN a new GST number is successfully verified for the first time, THE System SHALL automatically add it to the cache with all fetched business details
4. THE System SHALL store the following data for each cached GST entry: GSTIN, legal name, trade name, status, registration date, business constitution, principal address, and e-invoice status
5. THE System SHALL update cached GST data periodically to ensure accuracy of business information

### Requirement 5: Confidence Score Display

**User Story:** As a User, I want to see how confident the AI was in extracting each invoice's data, so that I can prioritize reviewing invoices with low confidence scores.

#### Acceptance Criteria

1. THE System SHALL calculate a confidence score (0-100%) for each AI-extracted invoice
2. THE System SHALL display the confidence score prominently on the invoice detail page
3. THE System SHALL use visual indicators (colors, icons) to represent confidence levels (high, medium, low)
4. WHEN the confidence score is below 70%, THE System SHALL recommend manual review of the invoice
5. THE System SHALL allow Users to filter and sort invoices by confidence score

### Requirement 6: Invoice Health Score System

**User Story:** As a User, I want a clear numerical score for each invoice's compliance and quality, so that I can quickly assess risk and prioritize my review efforts.

#### Acceptance Criteria

1. THE System SHALL calculate an Invoice Health Score (0-10) for every processed invoice using a weighted rubric
2. THE System SHALL base the score on five weighted categories: Data Completeness (25%), Vendor & Buyer Verification (30%), Compliance & Legal Checks (25%), Fraud & Anomaly Detection (15%), and AI Confidence & Document Quality (5%)
3. THE System SHALL translate the numerical score into a status level: Healthy (8.0-10.0), Review (5.0-7.9), or At Risk (0.0-4.9)
4. THE System SHALL display the Invoice Health Score with color-coded visual indicators on invoice lists and detail pages
5. THE System SHALL provide a detailed breakdown showing which specific issues ("Key Flags") reduced the invoice score
6. THE System SHALL allow Users to filter invoices by health status (Healthy, Review, At Risk)

### Requirement 7: Enhanced Analytical Dashboard

**User Story:** As a User, I want a comprehensive dashboard with charts and insights, so that I can understand my business spending patterns and identify trends at a glance.

#### Acceptance Criteria

1. THE System SHALL display an "Invoice Per Day" bar chart showing daily processing volumes with genuine vs. at-risk invoice breakdown
2. THE System SHALL display a "Money Flow" donut chart visualizing spending distribution by product/service category using HSN/SAC codes
3. THE System SHALL display a "Company Leaderboard" table ranking top vendors by total spend and invoice volume
4. THE System SHALL display a "Red Flag List" showing the highest-risk invoices based on Invoice Health Score
5. THE System SHALL update all dashboard visualizations in real-time as new invoices are processed
6. THE System SHALL allow Users to filter dashboard data by date range

### Requirement 8: GST Verified Cache Management Page

**User Story:** As a User, I want to view and manage all verified GST numbers in one place, so that I can review vendor information and maintain data accuracy.

#### Acceptance Criteria

1. THE System SHALL provide a dedicated page accessible from the sidebar navigation for viewing the GST cache
2. THE System SHALL display all cached GST entries in a searchable and filterable table
3. THE System SHALL display the following columns for each entry: GSTIN, Legal Name, Trade Name, Status, Registration Date, Business Constitution, Principal Address, and e-Invoice Status
4. THE System SHALL allow Users to search GST entries by GSTIN, legal name, or trade name
5. THE System SHALL allow Users to manually refresh individual GST entries to update their information from the government portal

### Requirement 9: User Profile Management

**User Story:** As a User, I want to view and edit my personal information, so that I can keep my account details current and accurate.

#### Acceptance Criteria

1. THE System SHALL provide a dedicated profile page accessible from the user menu
2. THE System SHALL display the User's current profile picture, name, username, and email address
3. THE System SHALL allow the User to upload a new profile picture with a maximum file size of 1 MB
4. THE System SHALL allow the User to edit their name and username
5. WHEN the User saves profile changes, THE System SHALL validate the data and update the account information

### Requirement 10: Comprehensive Settings Management

**User Story:** As a User, I want a centralized settings page to manage my preferences and account options, so that I can customize my experience and control my data.

#### Acceptance Criteria

1. THE System SHALL provide a comprehensive settings page with multiple configuration sections
2. THE System SHALL allow the User to connect or disconnect third-party services (Google, Facebook)
3. THE System SHALL provide toggle controls for notification preferences, sound effects, animations, and motivational messages
4. THE System SHALL provide a "Logout" option to end the current session
5. THE System SHALL provide an "Export My Data" option to download all personal data in a standard format
6. THE System SHALL provide a "Delete My Account" option with appropriate confirmation warnings

### Requirement 11: Data Export Capability

**User Story:** As a User, I want to export invoice data and GST cache information to CSV or Excel, so that I can perform offline analysis and maintain external records.

#### Acceptance Criteria

1. THE System SHALL provide an "Export" button on the invoice list page
2. THE System SHALL provide an "Export" button on the GST cache page
3. WHEN the User clicks an export button, THE System SHALL generate a downloadable file in CSV format
4. THE System SHALL include all visible columns and filtered data in the exported file
5. THE System SHALL name exported files with a timestamp for easy identification

### Requirement 12: Multiple API Key Management

**User Story:** As a User, I want the system to automatically handle API key limits, so that I experience no interruption when one key reaches its usage quota.

#### Acceptance Criteria

1. THE System SHALL support configuration of multiple Gemini API keys in an API key pool
2. WHEN an API key reaches its usage limit or returns a quota error, THE System SHALL automatically switch to the next available key
3. THE System SHALL continue processing without user intervention during API key failover
4. THE System SHALL log API key usage and failover events for monitoring purposes
5. WHEN all API keys in the pool are exhausted, THE System SHALL notify the User with a clear error message

### Requirement 13: Coming Soon Pages

**User Story:** As a User, I want to see polished placeholder pages for upcoming features, so that I understand the platform's future direction and feel confident in its development.

#### Acceptance Criteria

1. WHEN the User navigates to a non-functional feature (e.g., "Reports"), THE System SHALL display a "Coming Soon" page
2. THE System SHALL display a professional message indicating the feature is under development
3. THE System SHALL provide a link to return to the main dashboard
4. THE System SHALL maintain consistent branding and design on the "Coming Soon" page
5. THE System SHALL optionally allow Users to sign up for notifications when the feature becomes available
