from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import CustomUser, RoleChoices
from apps.settings_app.models import SMSGatewayConfig
from apps.dashboard.services import DashboardService


class DashboardMetricsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = CustomUser.objects.create_superuser(
            username='dashboard_admin',
            email='admin@example.com',
            password='password123',
            role=RoleChoices.ADMIN
        )
        self.config = SMSGatewayConfig.objects.create(
            provider_name="Test Gateway",
            api_url="https://text.draft4sms.com/vb/apikey.php",
            balance_api_url="https://text.draft4sms.com/vb/http-credit.php",
            api_key="TEST_API_KEY_12345",
            total_sms_allowed="50000",
            is_active=True
        )

    @patch('requests.get')
    def test_dashboard_service_returns_total_and_balance_sms(self, mock_get):
        """Verifies DashboardService returns formatted total_sms_allowed and balance_sms."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status":"Success","code":"011","balance":25000}'
        mock_get.return_value = mock_resp

        metrics = DashboardService.get_summary_metrics(user=self.admin_user)

        self.assertEqual(metrics['balance_sms'], '25,000')
        self.assertEqual(metrics['total_sms_allowed'], '50,000')

    @patch('requests.get')
    def test_dashboard_view_renders_cards(self, mock_get):
        """Verifies GET /dashboard/ renders Balance SMS card and does not contain Total SMS Allowed card."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status":"Success","code":"011","balance":25000}'
        mock_get.return_value = mock_resp

        self.client.login(username='dashboard_admin', password='password123')
        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Balance SMS")
        self.assertContains(response, "25,000")
        self.assertNotContains(response, "Total SMS Allowed")

    @patch('requests.get')
    def test_gateway_timeout_handles_gracefully(self, mock_get):
        """Verifies Dashboard does not crash when gateway times out or fails."""
        mock_get.side_effect = Exception("Gateway Connection Timeout")

        self.client.login(username='dashboard_admin', password='password123')
        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Balance SMS")
        self.assertContains(response, "Balance not available")
