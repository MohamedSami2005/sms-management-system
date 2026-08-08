from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import CustomUser, RoleChoices
from apps.users.models import Department, Staff, Office


class WebUserAdministrationTestCase(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Computer Science", code="CSE")
        self.office, _ = Office.objects.get_or_create(code="COE", defaults={'name': "Controller of Examinations", 'is_active': True})

        self.admin = CustomUser.objects.create_superuser(
            username="admin_sys",
            first_name="System",
            last_name="Administrator",
            employee_id="ADM001",
            role=RoleChoices.ADMIN,
            office=self.office
        )

        self.client = Client()
        self.client.force_login(self.admin)

    def test_staff_recipient_creation_and_list(self):
        """Verifies creation and listing of Staff recipient master records."""
        url = reverse('users:staff_create')
        data = {
            'name': 'Mohamed Sami',
            'mobile_number': '9876543210',
            'department': self.dept.pk
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

        staff = Staff.objects.get(name='Mohamed Sami')
        self.assertEqual(staff.mobile_number, '9876543210')
        self.assertEqual(staff.department, self.dept)

        # Test Staff List view
        list_url = reverse('users:staff_list')
        list_resp = self.client.get(list_url)
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, 'Mohamed Sami')

    def test_system_user_creation(self):
        """Verifies Administrator can create a new login system user from the Web UI."""
        url = reverse('users:system_user_create')
        data = {
            'employee_id': 'EMP5001',
            'username': 'staff_john',
            'name': 'John Doe',
            'email': 'john@college.edu',
            'phone_number': '9876543299',
            'office': self.office.pk,
            'designation': 'Assistant Registrar',
            'role': RoleChoices.COE,
            'password': 'InitialPass@123',
            'confirm_password': 'InitialPass@123',
            'is_active': True,
            'must_change_password': True
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

        user = CustomUser.objects.get(username='staff_john')
        self.assertEqual(user.employee_id, 'EMP5001')
        self.assertEqual(user.role, RoleChoices.COE)
        self.assertTrue(user.must_change_password)
        self.assertEqual(user.created_by, self.admin)

    def test_system_user_update(self):
        """Verifies Administrator can edit an existing user's role and office."""
        staff = CustomUser.objects.create_user(
            username='staff_edit',
            employee_id='EMP5002',
            role=RoleChoices.STAFF,
            office=self.office
        )

        url = reverse('users:system_user_edit', kwargs={'pk': staff.pk})
        data = {
            'employee_id': 'EMP5002',
            'username': 'staff_edit',
            'name': 'Updated Name',
            'email': 'updated@college.edu',
            'phone_number': '9876543211',
            'office': self.office.pk,
            'designation': 'HOD Computer Science',
            'role': RoleChoices.HOD,
            'is_active': True,
            'must_change_password': False
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

        staff.refresh_from_db()
        self.assertEqual(staff.role, RoleChoices.HOD)
        self.assertEqual(staff.office, self.office)

    def test_admin_password_reset(self):
        """Verifies Administrator can reset another user's password directly from Web UI."""
        staff = CustomUser.objects.create_user(username='pass_user', password='OldPassword123')
        url = reverse('users:system_user_reset_password', kwargs={'pk': staff.pk})
        data = {
            'new_password': 'NewSecurePass@99',
            'confirm_password': 'NewSecurePass@99',
            'must_change_password': True
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

        staff.refresh_from_db()
        self.assertTrue(staff.check_password('NewSecurePass@99'))
        self.assertTrue(staff.must_change_password)

    def test_account_lock_and_unlock(self):
        """Verifies Administrator can lock and unlock a system user account from Web UI."""
        staff = CustomUser.objects.create_user(username='lock_user')
        url = reverse('users:system_user_toggle_lock', kwargs={'pk': staff.pk})

        # Lock
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        staff.refresh_from_db()
        self.assertTrue(staff.is_locked)

        # Unlock
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        staff.refresh_from_db()
        self.assertFalse(staff.is_locked)

    def test_soft_delete_user(self):
        """Verifies Administrator soft-deletes a system user account."""
        staff = CustomUser.objects.create_user(username='delete_user')
        url = reverse('users:system_user_delete', kwargs={'pk': staff.pk})

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        staff.refresh_from_db()
        self.assertTrue(staff.is_deleted)
        self.assertFalse(staff.is_active)
