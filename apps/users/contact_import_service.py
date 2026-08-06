import re
import logging
from typing import Tuple, List, Dict, Any, Optional

import pandas as pd
from django.db import transaction

from .models import Staff, Department
from apps.accounts.models import CustomUser

logger = logging.getLogger('django')


class ContactImportService:
    """
    Service layer for parsing, validating, and bulk importing Enterprise Contact Excel files (.xlsx, .xls).
    Supports optional department assignment, automatic department creation, and Indian mobile number validation.
    """

    @staticmethod
    def validate_mobile_number(val: Any) -> Optional[str]:
        """
        Validates and normalizes Indian mobile numbers.
        Accepts: 9876543210, +919876543210, 919876543210.
        Rejects: non-numeric, invalid length, invalid starting digit (<6).
        Returns normalized 10-digit string or None.
        """
        if pd.isna(val) or val is None:
            return None

        num_str = str(val).strip()

        # Strip floating point format if read as float from pandas (e.g. 9876543210.0)
        if num_str.endswith('.0'):
            num_str = num_str[:-2]

        # Strip spaces, hyphens, and leading '+'
        num_str = re.sub(r'[\s\-\+]', '', num_str)

        # Handle 12-digit numbers starting with 91 (e.g. 919876543210)
        if len(num_str) == 12 and num_str.startswith('91'):
            num_str = num_str[2:]

        # Validate 10-digit Indian mobile number starting with 6, 7, 8, or 9
        if len(num_str) == 10 and num_str.isdigit() and num_str[0] in ['6', '7', '8', '9']:
            return num_str

        return None

    @classmethod
    def parse_excel(cls, file) -> Tuple[Optional[List[Dict[str, Any]]], Optional[Dict[str, int]], List[str]]:
        """
        Parses uploaded Excel file, validates required Name & Number columns (Department is optional),
        checks for duplicates and mobile validity.
        Returns (preview_rows, summary_dict, error_messages).
        """
        filename = file.name.lower()
        if not filename.endswith(('.xlsx', '.xls')):
            return None, None, ["Invalid file format. Please upload an Excel file (.xlsx or .xls)."]

        try:
            df = pd.read_excel(file)
        except Exception as e:
            return None, None, [f"Failed to read Excel file: {str(e)}"]

        if df.empty:
            return None, None, ["The uploaded Excel file contains no data rows."]

        # Clean & normalize header names
        header_map = {}
        for col in df.columns:
            cleaned_header = str(col).strip()
            header_map[cleaned_header.lower()] = col

        # Check required columns: Name and Number
        name_col = header_map.get('name')
        number_col = header_map.get('number') or header_map.get('mobile') or header_map.get('mobile_number') or header_map.get('mobile number')

        missing_columns = []
        if not name_col:
            missing_columns.append("Name")
        if not number_col:
            missing_columns.append("Number")

        if missing_columns:
            errors = [f"Missing Required Column:\n{col}" for col in missing_columns]
            return None, None, errors

        # Department column is optional
        dept_col = header_map.get('department') or header_map.get('dept')

        # Pre-fetch existing mobile numbers from database
        existing_mobiles = set(
            Staff.objects.values_list('mobile_number', flat=True)
        )

        seen_in_file = set()
        preview_rows = []
        new_count = 0
        duplicate_count = 0
        invalid_count = 0

        for idx, row in df.iterrows():
            name_val = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""
            num_raw = row[number_col]
            dept_val = str(row[dept_col]).strip() if dept_col and pd.notna(row[dept_col]) else ""

            valid_mobile = cls.validate_mobile_number(num_raw)

            if not valid_mobile or not name_val:
                status = "Invalid Mobile Number"
                display_mobile = str(num_raw).strip() if pd.notna(num_raw) else "-"
                invalid_count += 1
            else:
                display_mobile = valid_mobile
                if valid_mobile in existing_mobiles or valid_mobile in seen_in_file:
                    status = "Already Exists"
                    duplicate_count += 1
                else:
                    status = "New"
                    new_count += 1
                    seen_in_file.add(valid_mobile)

            dept_display = dept_val if dept_val else "-"

            preview_rows.append({
                's_no': idx + 1,
                'name': name_val,
                'mobile_number': display_mobile,
                'department': dept_display,
                'dept_val': dept_val,
                'status': status
            })

        summary = {
            'contacts_found': len(preview_rows),
            'new_contacts': new_count,
            'duplicates': duplicate_count,
            'invalid': invalid_count
        }

        return preview_rows, summary, []

    @classmethod
    def execute_import(cls, preview_rows: List[Dict[str, Any]], user: CustomUser) -> Dict[str, int]:
        """
        Executes bulk import for all 'New' valid contacts.
        Automatically creates non-existent Departments case-insensitively.
        Uses bulk_create() inside a database transaction for optimal performance.
        """
        new_rows = [r for r in preview_rows if r.get('status') == 'New']

        if not new_rows:
            duplicate_count = sum(1 for r in preview_rows if r.get('status') == 'Already Exists')
            invalid_count = sum(1 for r in preview_rows if r.get('status') == 'Invalid Mobile Number')
            return {
                'contacts_found': len(preview_rows),
                'imported': 0,
                'duplicates_skipped': duplicate_count,
                'invalid_rows': invalid_count,
                'errors': 0
            }

        # Department resolution & automatic creation
        existing_depts = Department.objects.all()
        dept_map = {}
        for d in existing_depts:
            dept_map[d.name.lower()] = d
            dept_map[d.code.lower()] = d

        # Find unique new departments to create (case-insensitive deduplication)
        unique_new_depts = {}
        for r in new_rows:
            val = r['dept_val'].strip() if r.get('dept_val') else ''
            if val:
                key = val.lower()
                if key not in dept_map and key not in unique_new_depts:
                    unique_new_depts[key] = val

        with transaction.atomic():
            for dept_key, new_dept_name in unique_new_depts.items():
                # Generate unique code
                base_code = re.sub(r'[^A-Z0-9]', '', new_dept_name.upper())[:15] or "DEPT"
                code = base_code
                counter = 1
                while Department.objects.filter(code=code).exists():
                    code = f"{base_code[:12]}_{counter}"
                    counter += 1

                dept_obj = Department.objects.create(
                    name=new_dept_name,
                    code=code,
                    created_by=user,
                    updated_by=user
                )
                dept_map[dept_key] = dept_obj

            # Prepare Staff instances for bulk_create
            staff_instances = []
            for r in new_rows:
                dept_obj = dept_map.get(r['dept_val'].lower()) if r['dept_val'] else None
                staff_instances.append(
                    Staff(
                        name=r['name'],
                        mobile_number=r['mobile_number'],
                        department=dept_obj,
                        is_active=True,
                        created_by=user,
                        updated_by=user
                    )
                )

            Staff.objects.bulk_create(staff_instances, batch_size=1000)

        duplicate_count = sum(1 for r in preview_rows if r.get('status') == 'Already Exists')
        invalid_count = sum(1 for r in preview_rows if r.get('status') == 'Invalid Mobile Number')

        logger.info(
            f"ENTERPRISE_CONTACT_IMPORT | User '{user.username}' imported {len(staff_instances)} contacts "
            f"({duplicate_count} skipped duplicates, {invalid_count} invalid)."
        )

        return {
            'contacts_found': len(preview_rows),
            'imported': len(staff_instances),
            'duplicates_skipped': duplicate_count,
            'invalid_rows': invalid_count,
            'errors': 0
        }
