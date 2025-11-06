"""
Management command to load HSN/SAC codes and GST rates from CSV files.

This command parses GST_Goods_Rates.csv and GST_Services_Rates.csv files
and generates a cached JSON file for the analysis engine to load into memory.
"""

import csv
import json
import os
import re
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Load HSN/SAC codes and GST rates from CSV files into cached JSON'

    def add_arguments(self, parser):
        parser.add_argument(
            '--goods-file',
            type=str,
            default='GST_Goods_Rates.csv',
            help='Path to GST goods rates CSV file (default: GST_Goods_Rates.csv)'
        )
        parser.add_argument(
            '--services-file',
            type=str,
            default='GST_Services_Rates.csv',
            help='Path to GST services rates CSV file (default: GST_Services_Rates.csv)'
        )
        parser.add_argument(
            '--output-file',
            type=str,
            default='data/hsn_gst_rates.json',
            help='Output JSON file path (default: data/hsn_gst_rates.json)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force overwrite existing output file'
        )

    def handle(self, *args, **options):
        goods_file = options['goods_file']
        services_file = options['services_file']
        output_file = options['output_file']
        force = options['force']

        # Check if input files exist
        if not os.path.exists(goods_file):
            raise CommandError(f'Goods file not found: {goods_file}')
        
        if not os.path.exists(services_file):
            raise CommandError(f'Services file not found: {services_file}')

        # Check if output file exists and force flag
        if os.path.exists(output_file) and not force:
            raise CommandError(
                f'Output file already exists: {output_file}. '
                'Use --force to overwrite.'
            )

        self.stdout.write('Loading HSN/SAC data from CSV files...')

        # Initialize the data structure
        hsn_data = {
            'goods': {},
            'services': {},
            'metadata': {
                'total_goods_codes': 0,
                'total_services_codes': 0,
                'generated_at': None
            }
        }

        # Process goods file
        goods_count = self._process_goods_file(goods_file, hsn_data['goods'])
        hsn_data['metadata']['total_goods_codes'] = goods_count

        # Process services file
        services_count = self._process_services_file(services_file, hsn_data['services'])
        hsn_data['metadata']['total_services_codes'] = services_count

        # Add generation timestamp
        from datetime import datetime
        hsn_data['metadata']['generated_at'] = datetime.now().isoformat()

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Write to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(hsn_data, f, indent=2, ensure_ascii=False)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully loaded HSN/SAC data:\n'
                f'  - Goods codes: {goods_count}\n'
                f'  - Services codes: {services_count}\n'
                f'  - Output file: {output_file}'
            )
        )

    def _process_goods_file(self, file_path, goods_dict):
        """Process GST goods rates CSV file."""
        count = 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                hsn_codes = row.get('HSN Code', '').strip()
                igst_rate = row.get('IGST Rate (%)', '').strip()
                
                if not hsn_codes or not igst_rate:
                    continue
                
                # Parse IGST rate (remove % and convert to decimal)
                try:
                    rate = self._parse_rate(igst_rate)
                    if rate is None:
                        continue
                except (ValueError, TypeError):
                    self.stdout.write(
                        self.style.WARNING(f'Invalid rate format: {igst_rate}')
                    )
                    continue
                
                # Parse HSN codes (can be comma-separated)
                codes = self._parse_hsn_codes(hsn_codes)
                
                for code in codes:
                    if code:
                        cgst_rate = self._parse_rate(row.get('CGST Rate (%)', ''))
                        sgst_rate = self._parse_rate(row.get('SGST / UTGST Rate (%)', ''))
                        
                        goods_dict[code] = {
                            'rate': float(rate),
                            'description': row.get('Description of Goods', '').strip(),
                            'cgst_rate': float(cgst_rate) if cgst_rate is not None else None,
                            'sgst_rate': float(sgst_rate) if sgst_rate is not None else None,
                            'compensation_cess': row.get('Compensation Cess', '').strip()
                        }
                        count += 1
        
        return count

    def _process_services_file(self, file_path, services_dict):
        """Process GST services rates CSV file."""
        count = 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, start=2):  # Start from 2 since header is row 1
                # Services file doesn't have explicit SAC codes in a separate column
                # We'll use the row number as a reference and create synthetic SAC codes
                s_no = row.get('S. No.', '').strip()
                igst_rate = row.get('IGST Rate (%)', '').strip()
                description = row.get('Description of Service', '').strip()
                
                # Skip rows without description or IGST rate
                if not description or not igst_rate:
                    continue
                
                # Parse IGST rate
                try:
                    rate = self._parse_rate(igst_rate)
                    if rate is None:
                        continue
                except (ValueError, TypeError):
                    continue
                
                # Create a synthetic SAC code based on row number
                # SAC codes typically start with 99 for services
                # Use row number if S. No. is not available or not numeric
                try:
                    sac_number = int(s_no) if s_no.isdigit() else row_num
                except (ValueError, TypeError):
                    sac_number = row_num
                
                sac_code = f"99{str(sac_number).zfill(4)}"
                
                # Handle duplicate SAC codes by appending a suffix
                original_sac_code = sac_code
                suffix = 1
                while sac_code in services_dict:
                    sac_code = f"{original_sac_code}_{suffix}"
                    suffix += 1
                
                cgst_rate = self._parse_rate(row.get('CGST Rate (%)', ''))
                sgst_rate = self._parse_rate(row.get('SGST / UTGST Rate (%)', ''))
                
                services_dict[sac_code] = {
                    'rate': float(rate),
                    'description': description,
                    'cgst_rate': float(cgst_rate) if cgst_rate is not None else None,
                    'sgst_rate': float(sgst_rate) if sgst_rate is not None else None,
                    'heading': row.get('Heading / Chapter', '').strip(),
                    'condition': row.get('Condition', '').strip(),
                    's_no': s_no
                }
                count += 1
        
        return count

    def _parse_rate(self, rate_str):
        """Parse GST rate string and return decimal value."""
        if not rate_str or rate_str.strip() == '':
            return None
        
        # Remove % symbol and whitespace
        rate_str = str(rate_str).replace('%', '').strip()
        
        if not rate_str or rate_str == '':
            return None
        
        try:
            # Handle cases where rate might be just whitespace or empty after cleaning
            if rate_str.replace('.', '').replace('-', '').strip() == '':
                return None
            return Decimal(rate_str)
        except (ValueError, TypeError, Exception):
            # Log the problematic value for debugging
            self.stdout.write(
                self.style.WARNING(f'Could not parse rate: "{rate_str}"')
            )
            return None

    def _parse_hsn_codes(self, hsn_codes_str):
        """Parse HSN codes string which can contain multiple comma-separated codes."""
        if not hsn_codes_str:
            return []
        
        # Split by comma and clean up each code
        codes = []
        for code in hsn_codes_str.split(','):
            # Remove whitespace and normalize
            code = code.strip()
            # Remove any extra spaces within the code
            code = re.sub(r'\s+', '', code)
            if code:
                codes.append(code)
        
        return codes