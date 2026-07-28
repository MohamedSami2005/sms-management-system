from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import CustomUser, RoleChoices, ScopeChoices
from apps.users.models import Department


class WebUserAdministrationTestCase(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Controller of Examinations", code="COE")

        self.admin = CustomUser.objects.create_superuser(
            username="admin_sys",
            first_name="System",
            last_name="Administrator",
            employee_id="ADM001",
            role=RoleChoices.ADMIN,
            scope_type=ScopeChoices.GLOBAL,
            department=self.dept
        )

        self.client = Client()
        self.client.force_login(self.admin)

    def test_web_user_creation(self):
        """Verifies Administrator can create a new staff account from the Web UI."""
        url = reverse('users:user_create')
        data = {
            'employee_id': 'EMP5001',
            'username': 'staff_john',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@college.edu',
            'phone_number': '9876543210',
            'department': self.dept.pk,
            'designation': 'Assistant Registrar',
            'role': RoleChoices.COE,
            'scope_type': ScopeChoices.DEPARTMENT,
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
        self.assertEqual(user.scope_type, ScopeChoices.DEPARTMENT)
        self.assertTrue(user.must_change_password)
        self.assertEqual(user.created_by, self.admin)

    def test_web_user_update(self):
        """Verifies Administrator can edit an existing user's role, scope, and department."""
        staff = CustomUser.objects.create_user(
            username='staff_edit',
            employee_id='EMP5002',
            role=RoleChoices.STAFF,
            scope_type=ScopeChoices.DEPARTMENT
        )

        url = reverse('users:user_edit', kwargs={'pk': staff.pk})
        data = {
            'employee_id': 'EMP5002',
            'username': 'staff_edit',
            'first_name': 'Updated',
            'last_name': 'Name',
            'email': 'updated@college.edu',
            'phone_number': '9876543211',
            'department': self.dept.pk,
            'designation': 'HOD Computer Science',
            'role': RoleChoices.HOD,
            'scope_type': ScopeChoices.GLOBAL,
            'is_active': True,
            'must_change_password': False
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

        staff.refresh_from_db()
        self.assertEqual(staff.role, RoleChoices.HOD)
        self.assertEqual(staff.scope_type, ScopeChoices.GLOBAL)
        self.assertEqual(staff.designation, 'HOD Computer Science')

    def test_admin_password_reset(self):
        """Verifies Administrator can reset another user's password directly from Web UI."""
        staff = CustomUser.objects.create_user(username='pass_user', password='OldPassword123')
        url = reverse('users:user_reset_password', kwargs={'pk': staff.pk})
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
        """Verifies Administrator can lock and unlock a user account from Web UI."""
        staff = CustomUser.objects.create_user(username='lock_user')
        url = reverse('users:user_toggle_lock', kwargs={'pk': staff.pk})

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
        """Verifies Administrator soft-deletes a user account."""
        staff = CustomUser.objects.create_user(username='delete_user')
        url = reverse('users:user_delete', kwargs={'pk': staff.pk})

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        staff.refresh_from_db()
        self.assertTrue(staff.is_deleted)
        self.assertFalse(staff.is_active)

    def test_force_password_change_middleware(self):
        """Verifies ForcePasswordChangeMiddleware redirects user with must_change_password=True."""
        staff = CustomUser.objects.create_user(
            username='must_change_user',
            password='InitialPassword123',
            must_change_password=True
        )

        user_client = Client()
        user_client.force_login(staff)

        # Attempt to access dashboard
        response = user_client.get(reverse('dashboard:home'))
        self.assertRedirects(response, reverse('accounts:password_change'))
