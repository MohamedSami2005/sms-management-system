import csv
import io
import logging
from typing import Tuple, List, Dict, Any, Optional

from django.http import HttpResponse
from django.db import transaction
from django.utils import timezone

import pandas as pd
import openpyxl

from .models import DLTTemplate, TemplateVariable, TemplateCategoryChoices
from apps.users.models import Department
from apps.accounts.models import CustomUser

logger = logging.getLogger('django')


class TemplateService:
    """
    Business service layer for managing DLT templates and variable synchronization.
    """

    @staticmethod
    def save_template(form, user: CustomUser) -> DLTTemplate:
        with transaction.atomic():
            template = form.save(commit=False)
            if not template.pk:
                template.created_by = user
            template.updated_by = user
            template.save()
            form.save_m2m()

            # Synchronize extracted variables from content
            template.sync_variables()
            template.ensure_primary_office_in_allowed()
            logger.info(f"TEMPLATE_SAVED | DLT Template '{template.dlt_template_id}' saved by '{user.username}'.")
            return template

    @staticmethod
    def toggle_status(template: DLTTemplate) -> bool:
        template.is_active = not template.is_active
        template.save(update_fields=['is_active'])
        logger.info(f"TEMPLATE_STATUS_TOGGLE | DLT Template '{template.dlt_template_id}' active status set to {template.is_active}.")
        return template.is_active

    @staticmethod
    def delete_or_deactivate(template: DLTTemplate) -> Tuple[bool, str]:
        """
        Deletes template if never used in SMS dispatch/logs; soft-deactivates if used.
        """
        has_batches = template.batches.exists()
        has_queue = template.queued_messages.exists()
        has_logs = template.sms_logs.exists()

        if has_batches or has_queue or has_logs:
            template.is_active = False
            template.save(update_fields=['is_active'])
            logger.info(f"TEMPLATE_SOFT_DELETE | Template '{template.dlt_template_id}' deactivated because historical dispatch records exist.")
            return True, f"Template '{template.name}' was deactivated because historical SMS dispatch records exist."
        else:
            name = template.name
            template.delete()
            logger.info(f"TEMPLATE_HARD_DELETE | Template '{name}' permanently deleted.")
            return True, f"Template '{name}' was permanently deleted."


class TemplateImportService:
    """
    Service for parsing, validating, and importing official DLT Template Excel files (.xlsx, .xls).
    """

    REQUIRED_COLUMNS = [
        'HEADER', 'TEMPLATE_ID', 'TEMPLATE_NAME', 'CONSENT_ID',
        'TEMPLATE_TYPE', 'CATEGORY', 'TEMPLATE_CONTENT', 'SAMPLE_CONTENT',
        'JIO_STATUS', 'REGISTERED_BY', 'VARIABLE_COUNT', 'APPROVAL_DATE'
    ]

    @classmethod
    def parse_excel(cls, file) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """
        Parses uploaded Excel file, validates 12 required DLT columns, and checks for duplicates.
        Returns (parsed_summary_dict, list_of_errors).
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

        # Clean & normalize header names to uppercase with underscores
        header_map = {}
        for col in df.columns:
            cleaned = str(col).strip().upper().replace(' ', '_')
            header_map[cleaned] = col

        # Check required columns
        for req_col in cls.REQUIRED_COLUMNS:
            if req_col not in header_map:
                return None, [f"Missing Required Column: {req_col}"]

        # Get existing DLT Template IDs from DB for duplicate checking
        existing_dlt_ids = set(DLTTemplate.objects.values_list('dlt_template_id', flat=True))
        seen_in_file = set()

        rows = []
        new_count = 0
        duplicate_count = 0

        for idx, row in df.iterrows():
            def get_val(key_name):
                col_orig = header_map.get(key_name)
                val = row.get(col_orig)
                if pd.isna(val) or val is None:
                    return ""
                return str(val).strip()

            header = get_val('HEADER')
            raw_dlt_id = get_val('TEMPLATE_ID')

            # Standardize numeric float IDs (e.g., 1.20045e+15 -> string)
            if raw_dlt_id.endswith('.0'):
                raw_dlt_id = raw_dlt_id[:-2]
            dlt_id = raw_dlt_id

            tmpl_name = get_val('TEMPLATE_NAME')
            consent_id = get_val('CONSENT_ID')
            template_type = get_val('TEMPLATE_TYPE')
            category_raw = get_val('CATEGORY')
            template_content = get_val('TEMPLATE_CONTENT')
            sample_content = get_val('SAMPLE_CONTENT')
            jio_status = get_val('JIO_STATUS')
            registered_by = get_val('REGISTERED_BY')
            variable_count_raw = get_val('VARIABLE_COUNT')
            approval_date = get_val('APPROVAL_DATE')

            is_duplicate = False
            if dlt_id in existing_dlt_ids or dlt_id in seen_in_file:
                is_duplicate = True
                duplicate_count += 1
                status_str = "Already Exists"
            else:
                seen_in_file.add(dlt_id)
                new_count += 1
                status_str = "New"

            # Parse integer variable count
            var_cnt = 0
            try:
                if variable_count_raw:
                    var_cnt = int(float(variable_count_raw))
            except ValueError:
                var_cnt = 0

            rows.append({
                's_no': idx + 1,
                'name': tmpl_name or f"Template_{idx+1}",
                'dlt_template_id': dlt_id,
                'header_sender_id': header[:10] if header else 'CLGEXM',
                'consent_id': consent_id,
                'template_type': template_type,
                'category_raw': category_raw,
                'template_content': template_content,
                'sample_content': sample_content,
                'jio_status': jio_status,
                'registered_by': registered_by,
                'variable_count': var_cnt,
                'approval_date': approval_date,
                'status': status_str,
                'is_duplicate': is_duplicate
            })

        parsed_payload = {
            'templates_found': len(rows),
            'new_templates': new_count,
            'duplicates': duplicate_count,
            'rows': rows
        }
        return parsed_payload, []

    @classmethod
    def execute_import(cls, rows: List[Dict[str, Any]], user: CustomUser) -> Dict[str, int]:
        """
        Imports new non-duplicate templates into database in bulk with office=NULL.
        Returns execution metrics dict.
        """
        new_rows = [r for r in rows if not r.get('is_duplicate')]
        if not new_rows:
            return {
                'templates_found': len(rows),
                'imported': 0,
                'duplicates_skipped': len(rows),
                'errors': 0
            }

        # Build model objects
        templates_to_create = []
        for r in new_rows:
            # Map category
            cat_raw = str(r.get('category_raw', '')).strip().upper()
            category = TemplateCategoryChoices.SERVICE_IMPLICIT
            for choice_code, _ in TemplateCategoryChoices.choices:
                if choice_code in cat_raw:
                    category = choice_code
                    break

            tmpl = DLTTemplate(
                name=r.get('name')[:150],
                dlt_template_id=r.get('dlt_template_id')[:50],
                entity_id='1001999988887777666',
                header_sender_id=r.get('header_sender_id')[:10] or 'CLGEXM',
                template_content=r.get('template_content') or '',
                category=category,
                consent_id=r.get('consent_id')[:50] if r.get('consent_id') else None,
                template_type=r.get('template_type')[:50] if r.get('template_type') else None,
                sample_content=r.get('sample_content'),
                jio_status=r.get('jio_status')[:50] if r.get('jio_status') else None,
                registered_by=r.get('registered_by')[:150] if r.get('registered_by') else None,
                approval_date=r.get('approval_date')[:50] if r.get('approval_date') else None,
                office=None,  # Deferred Office Assignment (Intentionally NULL)
                department=None,
                is_active=True,
                created_by=user,
                updated_by=user
            )
            templates_to_create.append(tmpl)

        with transaction.atomic():
            DLTTemplate.objects.bulk_create(templates_to_create, batch_size=500)

            # Fetch created templates to synchronize template variable placeholders
            created_ids = [t.dlt_template_id for t in templates_to_create]
            created_objs = DLTTemplate.objects.filter(dlt_template_id__in=created_ids)
            for t in created_objs:
                t.sync_variables()

        imported_count = len(templates_to_create)
        skipped_count = len(rows) - imported_count
        logger.info(f"ENTERPRISE_DLT_IMPORT | User '{user.username}' imported {imported_count} templates ({skipped_count} skipped).")

        return {
            'templates_found': len(rows),
            'imported': imported_count,
            'duplicates_skipped': skipped_count,
            'errors': 0
        }


class TemplateExportService:
    """
    Service for exporting DLT templates to Excel, CSV, and PDF formats.
    """

    @staticmethod
    def export_excel(queryset) -> HttpResponse:
        data = []
        for t in queryset:
            data.append({
                'Template Name': t.name,
                'DLT Template ID': t.dlt_template_id,
                'Principal Entity ID': t.entity_id,
                'Sender ID Header': t.header_sender_id,
                'Category': t.get_category_display(),
                'Department': t.department.name if t.department else 'Global',
                'Variables Count': t.variable_count,
                'Content': t.template_content,
                'Status': 'Active' if t.is_active else 'Inactive',
                'Created At': t.created_at.strftime('%Y-%m-%d %H:%M')
            })

        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='DLT_Templates')

        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="DLT_Templates_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
        return response

    @staticmethod
    def export_csv(queryset) -> HttpResponse:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="DLT_Templates_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Template Name', 'DLT Template ID', 'Entity ID', 'Sender ID', 'Category', 'Department', 'Variables Count', 'Content', 'Status'])

        for t in queryset:
            writer.writerow([
                t.name, t.dlt_template_id, t.entity_id, t.header_sender_id,
                t.get_category_display(), t.department.name if t.department else 'Global',
                t.variable_count, t.template_content, 'Active' if t.is_active else 'Inactive'
            ])

        return response
