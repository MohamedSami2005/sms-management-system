from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import CustomUser, Role
from apps.users.models import Department, Staff
from apps.dlt_templates.models import DLTTemplate
from apps.settings_app.models import SMSGatewayConfig
from apps.sms.services.single_sms import SingleSMSService


class SingleSMSStaffLookupTestCase(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Computer Science", code="CSE")
        self.role = Role.objects.create(name="ADMIN", code="ADMIN")

        self.admin = CustomUser.objects.create_superuser(
            username="admin_user",
            first_name="System",
            last_name="Admin",
            employee_id="ADM001",
            phone_number="9876543210",
            department=self.dept,
            role="ADMIN"
        )

        self.staff1 = Staff.objects.create(
            name="Mohamed Sami",
            mobile_number="8098778622",
            department=self.dept
        )
        self.staff2 = Staff.objects.create(
            name="Abdul Qadir",
            mobile_number="9876543211",
            department=self.dept
        )

        self.config = SMSGatewayConfig.objects.create(
            provider_name="Test Gateway",
            api_url="https://text.draft4sms.com/vb/apikey.php",
            api_key="TEST_API_KEY_999",
            default_sender_id="CLGEXM",
            is_active=True
        )

        self.template = DLTTemplate.objects.create(
            name="Fee Receipt",
            dlt_template_id="1107160000000123456",
            header_sender_id="CLGEXM",
            template_content="Dear {#var#}, fee of Rs.{#var#} received.",
            is_active=True
        )

        self.client = Client()
        self.client.force_login(self.admin)

    def test_staff_search_ajax_by_name(self):
        """Verifies AJAX search by staff name returns matching staff JSON."""
        url = reverse('sms:staff_search_ajax')
        response = self.client.get(url, {'q': 'sam'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(len(data['results']) > 0)
        self.assertEqual(data['results'][0]['name'], 'Mohamed Sami')
        self.assertEqual(data['results'][0]['mobile'], '8098778622')

    def test_staff_search_ajax_by_mobile(self):
        """Verifies AJAX search by mobile number returns matching staff JSON."""
        url = reverse('sms:staff_search_ajax')
        response = self.client.get(url, {'q': '8098'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['results'][0]['mobile'], '8098778622')

    @patch('requests.post')
    def test_single_sms_dispatch_with_staff_mobile(self, mock_post):
        """Verifies Single SMS view process_and_send works using auto-populated staff mobile number."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status":"Success","code":"011","messageid":"GW_SINGLE_123"}'
        mock_post.return_value = mock_resp

        url = reverse('sms:single')
        post_data = {
            'mobile_number': self.staff1.mobile_number,
            'template': self.template.pk,
            'var_1': 'Mohamed Sami',
            'var_2': '25000'
        }

        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
