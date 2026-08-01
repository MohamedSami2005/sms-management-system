import csv
import io
import logging
from typing import Tuple, List, Dict, Any

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
    Service for importing bulk DLT templates from Excel spreadsheets or CSV files.
    """

    REQUIRED_COLUMNS = ['template_name', 'dlt_template_id', 'entity_id', 'sender_id', 'template_content']

    @classmethod
    def import_from_file(cls, file, user: CustomUser) -> Tuple[int, int, List[str]]:
        filename = file.name.lower()
        errors = []
        imported_count = 0
        skipped_count = 0

        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(file)
            elif filename.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file)
            else:
                return 0, 0, ["Unsupported file format. Please upload .xlsx, .xls, or .csv file."]
        except Exception as e:
            return 0, 0, [f"Failed to parse file: {str(e)}"]

        # Clean column names
        df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]

        # Validate required columns exist
        missing_cols = [col for col in cls.REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            return 0, 0, [f"Missing required columns in header: {', '.join(missing_cols)}"]

        existing_dlt_ids = set(DLTTemplate.objects.values_list('dlt_template_id', flat=True))
        seen_in_file = set()

        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel 1-indexed row matching

            tmpl_name = str(row.get('template_name', '')).strip()
            dlt_id = str(row.get('dlt_template_id', '')).strip()
            entity_id = str(row.get('entity_id', '')).strip()
            sender_id = str(row.get('sender_id', '')).strip().upper()
            content = str(row.get('template_content', '')).strip()
            category_raw = str(row.get('category', 'SERVICE_IMPLICIT')).strip().upper()

            # Validation checks
            if not tmpl_name or not dlt_id or not content:
                errors.append(f"Row {row_num}: Missing required template name, DLT ID, or content.")
                skipped_count += 1
                continue

            if not dlt_id.isdigit() or not (11 <= len(dlt_id) <= 19):
                errors.append(f"Row {row_num}: Invalid DLT Template ID '{dlt_id}'. Must be 11-19 digits.")
                skipped_count += 1
                continue

            if dlt_id in existing_dlt_ids or dlt_id in seen_in_file:
                errors.append(f"Row {row_num}: Duplicate DLT Template ID '{dlt_id}' skipped.")
                skipped_count += 1
                continue

            seen_in_file.add(dlt_id)

            # Map category
            category = TemplateCategoryChoices.SERVICE_IMPLICIT
            for choice_code, _ in TemplateCategoryChoices.choices:
                if choice_code in category_raw:
                    category = choice_code
                    break

            try:
                tmpl = DLTTemplate.objects.create(
                    name=tmpl_name,
                    dlt_template_id=dlt_id,
                    entity_id=entity_id or '1001999988887777666',
                    header_sender_id=sender_id[:6] or 'CLGEXM',
                    template_content=content,
                    category=category,
                    department=getattr(user, 'department', None),
                    is_active=True,
                    created_by=user,
                    updated_by=user
                )
                tmpl.sync_variables()
                tmpl.ensure_primary_office_in_allowed()
                imported_count += 1
            except Exception as e:
                errors.append(f"Row {row_num}: Error creating template '{tmpl_name}': {str(e)}")
                skipped_count += 1

        logger.info(f"TEMPLATE_IMPORT | User '{user.username}' imported {imported_count} templates ({skipped_count} skipped).")
        return imported_count, skipped_count, errors


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
