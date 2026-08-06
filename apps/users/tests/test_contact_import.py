import io
import pandas as pd
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import CustomUser, RoleChoices
from apps.users.models import Staff, Department


class ContactImportTestCase(TestCase):
    """
    Test suite verifying Enterprise Contact Excel Import feature:
    - Security and 403 Forbidden checks.
    - Required column validation (Name, Number).
    - Optional Department column handling (absent, blank cells, populated).
    - Existing Department linking & automatic new Department creation (case-insensitive).
    - Indian mobile number validation and normalization.
    - Duplicate detection and skipping.
    - End-to-end bulk import.
    """

    def setUp(self):
        self.client = Client()
        self.admin = CustomUser.objects.create_superuser(
            username='admin_import',
            email='admin@example.com',
            password='password123',
            role=RoleChoices.ADMIN
        )
        self.staff_user = CustomUser.objects.create_user(
            username='regular_staff',
            email='staff@example.com',
            password='password123',
            role=RoleChoices.STAFF
        )
        self.dept_cse = Department.objects.create(name='CSE', code='CSE')
        self.existing_contact = Staff.objects.create(
            name='Existing User',
            mobile_number='9876543210',
            department=self.dept_cse
        )
        self.import_url = reverse('users:contact_import')

    def _create_excel_file(self, rows, columns=['Name', 'Number', 'Department']):
        """Helper to create an in-memory Excel file (.xlsx)."""
        df = pd.DataFrame(rows, columns=columns)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        return SimpleUploadedFile(
            'test_contacts.xlsx',
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    def test_unauthorized_access(self):
        """Verify unauthenticated or unauthorized users are denied access."""
        # Unauthenticated
        response = self.client.get(self.import_url)
        self.assertEqual(response.status_code, 302)

        # Unauthorized non-admin/staff role
        self.client.login(username='regular_staff', password='password123')
        response = self.client.get(self.import_url)
        self.assertEqual(response.status_code, 403)

    def test_upload_screen_access_for_admin(self):
        """Verify Admin can access upload screen."""
        self.client.login(username='admin_import', password='password123')
        response = self.client.get(self.import_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Import Contacts")

    def test_missing_required_column_validation(self):
        """Verify error when required 'Number' column is missing."""
        self.client.login(username='admin_import', password='password123')
        excel = self._create_excel_file(
            rows=[['Rahul', 'CSE']],
            columns=['Name', 'Department']
        )
        response = self.client.post(self.import_url, {'action': 'parse', 'excel_file': excel})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Missing Required Column:")
        self.assertContains(response, "Number")

    def test_optional_department_absent(self):
        """Verify import preview succeeds when Department column is completely absent."""
        self.client.login(username='admin_import', password='password123')
        excel = self._create_excel_file(
            rows=[['Rahul', '9876543211']],
            columns=['Name', 'Number']
        )
        response = self.client.post(self.import_url, {'action': 'parse', 'excel_file': excel})
        self.assertEqual(response.status_code, 200)
        preview_rows = self.client.session.get('contact_import_preview')
        self.assertIsNotNone(preview_rows)
        self.assertEqual(len(preview_rows), 1)
        self.assertEqual(preview_rows[0]['department'], '-')
        self.assertEqual(preview_rows[0]['status'], 'New')

    def test_optional_department_blank_cell(self):
        """Verify import preview succeeds when Department cell is blank/empty."""
        self.client.login(username='admin_import', password='password123')
        excel = self._create_excel_file(
            rows=[['Karthik', '9876543212', '']],
            columns=['Name', 'Number', 'Department']
        )
        response = self.client.post(self.import_url, {'action': 'parse', 'excel_file': excel})
        self.assertEqual(response.status_code, 200)
        preview_rows = self.client.session.get('contact_import_preview')
        self.assertEqual(preview_rows[0]['department'], '-')
        self.assertEqual(preview_rows[0]['status'], 'New')

    def test_mobile_validation_and_duplicate_checking(self):
        """Verify valid numbers, +91 normalization, invalid numbers, and duplicate detection."""
        self.client.login(username='admin_import', password='password123')
        excel = self._create_excel_file(
            rows=[
                ['Valid New', '+919876543213', 'CSE'],
                ['Duplicate', '9876543210', 'CSE'], # Already in DB
                ['Invalid Alpha', 'INVALID999', 'ECE'],
                ['Invalid Short', '12345', 'ECE']
            ]
        )
        response = self.client.post(self.import_url, {'action': 'parse', 'excel_file': excel})
        self.assertEqual(response.status_code, 200)
        summary = response.context['summary']
        self.assertEqual(summary['contacts_found'], 4)
        self.assertEqual(summary['new_contacts'], 1)
        self.assertEqual(summary['duplicates'], 1)
        self.assertEqual(summary['invalid'], 2)

    def test_end_to_end_import_and_automatic_dept_creation(self):
        """Verify full import execution, existing department linking, and automatic new department creation."""
        self.client.login(username='admin_import', password='password123')

        excel = self._create_excel_file(
            rows=[
                ['Student A', '9876543220', 'CSE'], # Existing Dept
                ['Student B', '9876543221', 'Artificial Intelligence'], # New Dept
                ['Student C', '9876543222', 'artificial intelligence'], # Duplicate case-insensitive New Dept
                ['Student D', '9876543223', ''] # Blank Dept
            ]
        )

        # Step 1: Parse
        response = self.client.post(self.import_url, {'action': 'parse', 'excel_file': excel})
        self.assertEqual(response.status_code, 200)

        # Step 2: Confirm Import
        response = self.client.post(self.import_url, {'action': 'confirm'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Import Completed Successfully")

        # Verify DB Records
        ai_dept = Department.objects.get(name__iexact='Artificial Intelligence')
        self.assertIsNotNone(ai_dept)

        staff_a = Staff.objects.get(mobile_number='9876543220')
        self.assertEqual(staff_a.department, self.dept_cse)

        staff_b = Staff.objects.get(mobile_number='9876543221')
        self.assertEqual(staff_b.department, ai_dept)

        staff_c = Staff.objects.get(mobile_number='9876543222')
        self.assertEqual(staff_c.department, ai_dept)

        staff_d = Staff.objects.get(mobile_number='9876543223')
        self.assertIsNone(staff_d.department)
