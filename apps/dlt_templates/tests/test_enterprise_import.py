import io
import pandas as pd
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import CustomUser, Role
from apps.users.models import Office, Department
from apps.dlt_templates.models import DLTTemplate
from apps.dlt_templates.services import TemplateImportService


class EnterpriseDLTImportTestCase(TestCase):
    def setUp(self):
        self.admin_office, _ = Office.objects.get_or_create(code="ADMIN", defaults={'name': "Admin Management"})
        self.coe_office, _ = Office.objects.get_or_create(code="COE", defaults={'name': "COE"})

        self.admin_role, _ = Role.objects.get_or_create(code='ADMIN', defaults={'name': 'System Admin'})
        self.staff_role, _ = Role.objects.get_or_create(code='STAFF', defaults={'name': 'College Staff'})

        self.admin_user = CustomUser.objects.create_superuser(
            username="admin_import",
            email="admin@college.edu",
            password="adminpassword123",
            office=self.admin_office,
            role_obj=self.admin_role,
            role='ADMIN'
        )

        self.non_admin_user = CustomUser.objects.create_user(
            username="non_admin",
            password="userpassword123",
            office=self.coe_office,
            role_obj=self.staff_role,
            role='STAFF'
        )

    def create_excel_file(self, data_dict):
        df = pd.DataFrame(data_dict)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        buffer.seek(0)
        return SimpleUploadedFile(
            "DLT_Templates_Sample.xlsx",
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_permission_denied_for_non_admin(self):
        self.client.login(username="non_admin", password="userpassword123")
        response = self.client.get(reverse('dlt_templates:import'))
        self.assertEqual(response.status_code, 403)

    def test_parse_excel_missing_required_column(self):
        # Missing 'TEMPLATE_CONTENT'
        invalid_data = {
            'HEADER': ['CLGEXM'],
            'TEMPLATE_ID': ['1107160000000123456'],
            'TEMPLATE_NAME': ['Exam Fee Notice'],
            'CONSENT_ID': [''],
            'TEMPLATE_TYPE': ['Service Implicit'],
            'CATEGORY': ['Service Implicit'],
            'SAMPLE_CONTENT': ['Sample'],
            'JIO_STATUS': ['Active'],
            'REGISTERED_BY': ['Admin'],
            'VARIABLE_COUNT': [1],
            'APPROVAL_DATE': ['2026-01-01']
        }
        excel_file = self.create_excel_file(invalid_data)
        parsed_payload, errors = TemplateImportService.parse_excel(excel_file)
        self.assertIsNone(parsed_payload)
        self.assertTrue(any('Missing Required Column: TEMPLATE_CONTENT' in e for e in errors))

    def test_valid_excel_parse_and_duplicate_detection(self):
        # Pre-create a template in DB to test duplicate detection
        DLTTemplate.objects.create(
            name="Existing Template",
            dlt_template_id="1107160000000123456",
            header_sender_id="CLGEXM",
            template_content="Existing {#var#}",
            category="SERVICE_IMPLICIT"
        )

        data = {
            'HEADER': ['CLGEXM', 'CLGEXM'],
            'TEMPLATE_ID': ['1107160000000123456', '1107160000000999999'],
            'TEMPLATE_NAME': ['Existing Template', 'New Hall Ticket Notice'],
            'CONSENT_ID': ['', ''],
            'TEMPLATE_TYPE': ['Service Implicit', 'Service Implicit'],
            'CATEGORY': ['Service Implicit', 'Service Implicit'],
            'TEMPLATE_CONTENT': ['Existing {#var#}', 'Dear {#var#}, your hall ticket is ready.'],
            'SAMPLE_CONTENT': ['Sample', 'Sample'],
            'JIO_STATUS': ['Active', 'Active'],
            'REGISTERED_BY': ['Admin', 'Admin'],
            'VARIABLE_COUNT': [1, 1],
            'APPROVAL_DATE': ['2026-01-01', '2026-01-01']
        }
        excel_file = self.create_excel_file(data)
        payload, errors = TemplateImportService.parse_excel(excel_file)

        self.assertEqual(len(errors), 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload['templates_found'], 2)
        self.assertEqual(payload['new_templates'], 1)
        self.assertEqual(payload['duplicates'], 1)
        self.assertEqual(payload['rows'][0]['status'], 'Already Exists')
        self.assertEqual(payload['rows'][1]['status'], 'New')

    def test_execute_import_leaves_office_null_and_syncs_variables(self):
        rows = [
            {
                's_no': 1,
                'name': 'New Bulk Template',
                'dlt_template_id': '1107160000000777777',
                'header_sender_id': 'CLGEXM',
                'consent_id': 'CNS-101',
                'template_type': 'Implicit',
                'category_raw': 'SERVICE_IMPLICIT',
                'template_content': 'Dear {#var#}, fee of Rs.{#var#} received.',
                'sample_content': 'Dear Student, fee of Rs.5000 received.',
                'jio_status': 'Approved',
                'registered_by': 'Registrar',
                'variable_count': 2,
                'approval_date': '2026-02-01',
                'status': 'New',
                'is_duplicate': False
            }
        ]

        summary = TemplateImportService.execute_import(rows, self.admin_user)

        self.assertEqual(summary['imported'], 1)
        self.assertEqual(summary['duplicates_skipped'], 0)

        imported_tmpl = DLTTemplate.objects.get(dlt_template_id='1107160000000777777')
        self.assertEqual(imported_tmpl.name, 'New Bulk Template')
        self.assertIsNone(imported_tmpl.office)  # Confirmed Deferred Office Assignment (NULL)
        self.assertEqual(imported_tmpl.variable_count, 2)  # Confirmed automatic variable sync

    def test_assign_office_later_via_edit_template(self):
        tmpl = DLTTemplate.objects.create(
            name="Unassigned Template",
            dlt_template_id="1107160000000888888",
            entity_id="1001999988887777666",
            header_sender_id="CLGEXM",
            template_content="Unassigned content {#var#}",
            category="SERVICE_IMPLICIT",
            office=None
        )

        tmpl.sync_variables()
        self.client.login(username="admin_import", password="adminpassword123")
        var_obj = tmpl.variables.first()
        response = self.client.post(reverse('dlt_templates:edit', kwargs={'pk': tmpl.pk}), {
            'name': tmpl.name,
            'dlt_template_id': tmpl.dlt_template_id,
            'entity_id': tmpl.entity_id,
            'header_sender_id': tmpl.header_sender_id,
            'category': tmpl.category,
            'office': self.coe_office.pk,  # Assign COE office
            'template_content': tmpl.template_content,
            'is_active': True,
            'variables-TOTAL_FORMS': '1',
            'variables-INITIAL_FORMS': '1',
            'variables-MIN_NUM_FORMS': '0',
            'variables-MAX_NUM_FORMS': '1000',
            'variables-0-id': var_obj.pk if var_obj else '',
            'variables-0-position': '1',
            'variables-0-name': 'var',
            'variables-0-sample_value': 'sample'
        })

        self.assertEqual(response.status_code, 302)
        tmpl.refresh_from_db()
        self.assertEqual(tmpl.office, self.coe_office)
