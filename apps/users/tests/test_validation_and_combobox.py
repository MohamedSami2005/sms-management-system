from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import CustomUser, Role
from apps.users.models import Department, Staff, Office
from apps.users.forms import UserCreateForm, UserUpdateForm, StaffForm


class MobileValidationTestCase(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Computer Science", code="CSE")

    def test_staff_mobile_validation_valid_formats(self):
        """Verifies 10-digit Indian numbers starting with 6,7,8,9 (+91 or 91 optional) pass validation."""
        valid_numbers = ['9876543210', '8098778622', '919876543210', '+919876543210', '6380123456', '7010987654']
        for num in valid_numbers:
            form = StaffForm(data={'name': 'Test Staff', 'mobile_number': num, 'department': self.dept.pk})
            self.assertTrue(form.is_valid(), f"Failed for valid number: {num} (errors: {form.errors})")

    def test_staff_mobile_validation_invalid_formats(self):
        """Verifies invalid numbers (bad start digit, bad length, non-digits) raise validation errors."""
        invalid_numbers = ['1234567890', '987654321', '98765432101', 'abcd123456', '5987654321']
        for num in invalid_numbers:
            form = StaffForm(data={'name': 'Test Staff', 'mobile_number': num, 'department': self.dept.pk})
            self.assertFalse(form.is_valid(), f"Should have failed for invalid number: {num}")
            self.assertIn('mobile_number', form.errors)

    def test_user_phone_validation_invalid(self):
        """Verifies CustomUser phone_number validation rejects invalid Indian numbers."""
        form = UserCreateForm(data={
            'name': 'New User',
            'employee_id': 'EMP999',
            'username': 'newuser',
            'email': 'newuser@college.edu',
            'phone_number': '1234567890',
            'role': 'Administrator',
            'office': 'CSE',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)


class DynamicRoleAndOfficeComboboxTestCase(TestCase):
    def setUp(self):
        self.admin_office, _ = Office.objects.get_or_create(code="ADMIN", defaults={'name': "Administration", 'is_active': True})
        self.admin = CustomUser.objects.create_superuser(
            username="admin_user",
            first_name="System",
            last_name="Admin",
            employee_id="ADM001",
            phone_number="9876543210",
            office=self.admin_office,
            role="ADMIN"
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def test_create_user_with_existing_role_and_office(self):
        """Verifies selecting existing role and office links to existing records."""
        url = reverse('users:system_user_create')
        post_data = {
            'name': 'Existing Role User',
            'employee_id': 'EMP101',
            'username': 'existuser',
            'email': 'exist@college.edu',
            'phone_number': '9876543288',
            'role': 'Administrator',
            'office': 'Administration',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'is_active': True
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        user = CustomUser.objects.get(username='existuser')
        self.assertEqual(user.office.name, 'Administration')
        self.assertEqual(user.role, 'ADMIN')

    def test_create_user_with_new_role_and_new_office(self):
        """Verifies typing new role and new office automatically creates database records without errors."""
        url = reverse('users:system_user_create')
        post_data = {
            'name': 'New Role User',
            'employee_id': 'EMP102',
            'username': 'newroleuser',
            'email': 'newrole@college.edu',
            'phone_number': '8098778622',
            'role': 'Examination Controller',
            'office': 'IQAC',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'is_active': True
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        # Check Role created
        new_role = Role.objects.filter(name__iexact='Examination Controller').first()
        self.assertIsNotNone(new_role)
        self.assertEqual(new_role.name, 'Examination Controller')

        # Check Office created
        new_office = Office.objects.filter(name__iexact='IQAC').first()
        self.assertIsNotNone(new_office)
        self.assertEqual(new_office.name, 'IQAC')

        # Check User assigned
        user = CustomUser.objects.get(username='newroleuser')
        self.assertEqual(user.role_obj, new_role)
        self.assertEqual(user.office, new_office)

    def test_case_insensitive_duplicate_prevention(self):
        """Verifies typing existing role or office in lowercase links to existing record without creating duplicate."""
        Role.objects.create(name="Accounts Officer", code="ACCOUNTS_OFFICER")
        Office.objects.create(name="Placement Cell", code="PLACEMENT_CELL")

        url = reverse('users:system_user_create')
        post_data = {
            'name': 'Case User',
            'employee_id': 'EMP103',
            'username': 'caseuser',
            'email': 'case@college.edu',
            'phone_number': '7010987654',
            'role': '  accounts officer  ',
            'office': '  placement cell  ',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'is_active': True
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        # Confirm no duplicate Role or Office was created
        self.assertEqual(Role.objects.filter(name__iexact='Accounts Officer').count(), 1)
        self.assertEqual(Office.objects.filter(name__iexact='Placement Cell').count(), 1)
