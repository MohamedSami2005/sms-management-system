import io
import re
import logging
from typing import Tuple, List, Dict, Any, Optional
import pandas as pd
import openpyxl
from django.http import HttpResponse

from apps.users.contact_import_service import ContactImportService

logger = logging.getLogger('apps.sms')


class BulkExcelImportService:
    """
    Service layer for parsing and validating dynamic Excel files (.xlsx, .xls)
    uploaded directly for Bulk SMS dispatch without persisting contacts to the database.
    """

    NAME_HEADER_ALIASES = [
        'name', 'full name', 'fullname', 'staff name', 'student name',
        'contact name', 'recipient name', 'person name'
    ]

    NUMBER_HEADER_ALIASES = [
        'number', 'mobile', 'mobile number', 'mobile_number', 'phone',
        'phone number', 'phone_number', 'contact number', 'contact_number'
    ]

    @classmethod
    def generate_sample_excel(cls) -> HttpResponse:
        """
        Generates sample Excel (.xlsx) with dynamic columns for Bulk SMS.
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Bulk SMS Sample"

        headers = ['Name', 'Number', 'Department', 'Exam', 'Date', 'Venue', 'Room']
        ws.append(headers)

        sample_rows = [
            ['Mohamed Sami', '9876543210', 'CSE', 'Mathematics', '12-Aug-2026', 'Main Hall', 'Room 101'],
            ['Jane Smith', '9876543211', 'ECE', 'Electronics', '13-Aug-2026', 'Science Block', 'Room 204']
        ]

        for r in sample_rows:
            ws.append(r)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="bulk_sms_sample.xlsx"'
        return response

    @classmethod
    def parse_excel(cls, file) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """
        Parses uploaded Excel file, dynamically identifies Name and Number columns,
        captures all other columns as dynamic variable sources, and validates numbers.

        Returns (parsed_data_dict, error_messages).
        """
        filename = file.name.lower()
        if not filename.endswith(('.xlsx', '.xls')):
            return None, ["Invalid file format. Please upload an Excel file (.xlsx or .xls)."]

        try:
            df = pd.read_excel(file)
        except Exception as e:
            return None, [f"Failed to read Excel file: {str(e)}"]

        if df.empty:
            return None, ["The uploaded Excel file contains no data rows."]

        # Clean header strings
        original_headers = [str(col).strip() for col in df.columns]
        header_lower_map = {h.lower(): h for h in original_headers}

        # Identify Name Column
        name_col = None
        for alias in cls.NAME_HEADER_ALIASES:
            if alias in header_lower_map:
                name_col = header_lower_map[alias]
                break

        # Identify Number Column
        number_col = None
        for alias in cls.NUMBER_HEADER_ALIASES:
            if alias in header_lower_map:
                number_col = header_lower_map[alias]
                break

        missing_errors = []
        if not name_col:
            missing_errors.append("Could not automatically identify the 'Name' column. Please ensure your Excel header includes 'Name' or 'Full Name'.")
        if not number_col:
            missing_errors.append("Could not automatically identify the 'Mobile Number' column. Please ensure your Excel header includes 'Number', 'Mobile', or 'Phone'.")

        if missing_errors:
            return None, missing_errors

        valid_rows = []
        invalid_rows = []
        seen_mobiles = set()

        for idx, row in df.iterrows():
            row_num = idx + 2  # 1-indexed including header row
            name_val = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""
            num_raw = row[number_col]

            valid_mobile = ContactImportService.validate_mobile_number(num_raw)

            # Build dict of all cell values for this row using original header names
            row_dict = {}
            for col in original_headers:
                val = row[col]
                if pd.isna(val) or val is None:
                    row_dict[col] = ""
                else:
                    val_str = str(val).strip()
                    if val_str.endswith('.0') and isinstance(val, (float, int)):
                        val_str = val_str[:-2]
                    row_dict[col] = val_str

            if not valid_mobile:
                invalid_rows.append({
                    'row_num': row_num,
                    'name': name_val or "—",
                    'mobile_raw': str(num_raw).strip() if pd.notna(num_raw) else "Empty",
                    'reason': "Invalid mobile number format"
                })
                continue

            if not name_val:
                name_val = f"Recipient ({valid_mobile})"

            row_dict['__normalized_mobile'] = valid_mobile
            row_dict['__normalized_name'] = name_val
            row_dict['mobile_val'] = valid_mobile
            row_dict['name_val'] = name_val
            row_dict['__row_index'] = len(valid_rows) + 1

            valid_rows.append(row_dict)
            seen_mobiles.add(valid_mobile)

        if not valid_rows:
            return None, ["No valid recipient rows with valid mobile numbers were found in the uploaded file."]

        result_data = {
            'total_rows': len(df),
            'valid_count': len(valid_rows),
            'invalid_count': len(invalid_rows),
            'name_column': name_col,
            'number_column': number_col,
            'all_headers': original_headers,
            'rows': valid_rows,
            'invalid_details': invalid_rows
        }

        return result_data, []
