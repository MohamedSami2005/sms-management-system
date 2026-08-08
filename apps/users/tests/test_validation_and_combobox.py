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


class StrictOfficeSelectionTestCase(TestCase):
    def setUp(self):
        self.admin_office, _ = Office.objects.get_or_create(code="ADMIN", defaults={'name': "Administration", 'is_active': True})
        self.coe_office, _ = Office.objects.get_or_create(code="COE", defaults={'name': "Controller of Examinations", 'is_active': True})
        self.inactive_office, _ = Office.objects.get_or_create(code="LEGACY", defaults={'name': "Legacy Department", 'is_active': False})

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

    def test_1_create_user_with_existing_active_office_success(self):
        """1. Existing active Office can be selected when creating a user."""
        initial_office_count = Office.objects.count()
        url = reverse('users:system_user_create')
        post_data = {
            'name': 'Active Office User',
            'employee_id': 'EMP101',
            'username': 'activeuser',
            'email': 'active@college.edu',
            'phone_number': '9876543288',
            'role': 'Administrator',
            'office': str(self.coe_office.pk),
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'is_active': True
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        user = CustomUser.objects.get(username='activeuser')
        self.assertEqual(user.office, self.coe_office)

        # 5. User creation does NOT create a new Office
        self.assertEqual(Office.objects.count(), initial_office_count)

    def test_2_update_user_with_existing_active_office_success(self):
        """2. Existing active Office can be selected when editing a user."""
        user = CustomUser.objects.create_user(
            username="edituser",
            email="edituser@college.edu",
            employee_id="EMP102",
            office=self.admin_office,
            role="STAFF"
        )
        initial_office_count = Office.objects.count()
        url = reverse('users:system_user_edit', kwargs={'pk': user.pk})
        post_data = {
            'name': 'Edited User',
            'employee_id': 'EMP102',
            'username': 'edituser',
            'email': 'edituser@college.edu',
            'phone_number': '8098778622',
            'role': 'Administrator',
            'office': str(self.coe_office.pk),
            'is_active': True
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        user.refresh_from_db()
        self.assertEqual(user.office, self.coe_office)

        # 6. User update does NOT create a new Office
        self.assertEqual(Office.objects.count(), initial_office_count)

    def test_3_non_existent_office_submission_rejected(self):
        """3. Non-existent Office ID cannot be submitted."""
        url = reverse('users:system_user_create')
        post_data = {
            'name': 'Fake Office User',
            'employee_id': 'EMP103',
            'username': 'fakeuser',
            'email': 'fake@college.edu',
            'phone_number': '7010987654',
            'role': 'Administrator',
            'office': '99999',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'is_active': True
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertIn('office', response.context['form'].errors)

    def test_4_inactive_office_submission_rejected(self):
        """4. Inactive Office cannot be selected or submitted."""
        url = reverse('users:system_user_create')
        post_data = {
            'name': 'Inactive Office User',
            'employee_id': 'EMP104',
            'username': 'inactiveuser',
            'email': 'inactive@college.edu',
            'phone_number': '6380123456',
            'role': 'Administrator',
            'office': str(self.inactive_office.pk),
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'is_active': True
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertIn('office', response.context['form'].errors)

    def test_7_existing_office_records_remain_unchanged(self):
        """7. Existing Office records remain unchanged after user creation."""
        coe_name_before = self.coe_office.name
        coe_code_before = self.coe_office.code

        url = reverse('users:system_user_create')
        post_data = {
            'name': 'Office Check User',
            'employee_id': 'EMP105',
            'username': 'officeuser',
            'email': 'officeuser@college.edu',
            'role': 'Administrator',
            'office': str(self.coe_office.pk),
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'is_active': True
        }
        self.client.post(url, post_data)

        self.coe_office.refresh_from_db()
        self.assertEqual(self.coe_office.name, coe_name_before)
        self.assertEqual(self.coe_office.code, coe_code_before)
