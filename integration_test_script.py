#!/usr/bin/env python
"""
Integration and Manual Testing Script for Smart iInvoice MVP

This script performs comprehensive integration testing of the Smart iInvoice system,
covering all major workflows and error scenarios as specified in task 13.

Test Coverage:
1. Complete invoice upload and processing flow
2. GST verification workflow end-to-end
3. Authentication and authorization flows
4. Status transitions verification
5. Error handling scenarios

Usage:
    python integration_test_script.py
"""

import os
import sys
import django
import json
import time
import requests
from decimal import Decimal
from datetime import date, datetime
from io import BytesIO
from PIL import Image
import subprocess
import signal

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartinvoice.settings')
django.setup()

from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from invoice_processor.models import Invoice, LineItem, ComplianceFlag
from invoice_processor.services.gemini_service import extract_