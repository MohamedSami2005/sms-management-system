from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import CustomUser


class ForcePasswordChangeMiddlewareTestCase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="testuser",
            password="InitialPassword@123",
            must_change_password=True
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_must_change_password_redirects_protected_pages(self):
        """Verifies accessing protected page like /dashboard/ redirects to /accounts/password/change/."""
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:password_change'), response.url)

    def test_must_change_password_allows_password_change_page(self):
        """Verifies accessing /accounts/password/change/ returns 200 without infinite redirect loop."""
        url = reverse('accounts:password_change')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
