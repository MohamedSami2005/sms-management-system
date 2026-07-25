from unittest.mock import patch, MagicMock
from django.test import TestCase

from apps.settings_app.models import SMSGatewayConfig
from apps.sms.services.dto import SMSPayload
from apps.sms.services.gateway_service import SMSGatewayService
from apps.common.exceptions import SMSGatewayAuthException, SMSGatewayTimeoutException


class SMSGatewayServiceTestCase(TestCase):
    def setUp(self):
        self.config = SMSGatewayConfig.objects.create(
            provider_name="Test Gateway",
            api_url="http://api.mock-gateway.com/send",
            api_key="TEST_API_KEY_999",
            default_sender_id="CLGEXM",
            default_entity_id="1001999988887777666",
            is_active=True
        )
        self.service = SMSGatewayService(self.config)
        self.payload = SMSPayload(
            mobile_number="9876543210",
            message_text="Dear Student, your exam is tomorrow.",
            dlt_template_id="1107160000000123456",
            entity_id="1001999988887777666",
            header_sender_id="CLGEXM"
        )

    @patch('requests.post')
    def test_send_single_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status": "success", "message_id": "GW_MSG_12345"}'
        mock_post.return_value = mock_resp

        res = self.service.send_single(self.payload)

        self.assertTrue(res.success)
        self.assertEqual(res.gateway_message_id, "GW_MSG_12345")
        self.assertEqual(res.status_code, 200)

    @patch('requests.post')
    def test_send_single_auth_failure(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = '{"error": "Unauthorized"}'
        mock_post.return_value = mock_resp

        res = self.service.send_single(self.payload)

        self.assertFalse(res.success)
        self.assertIn("Authentication failed", res.error_message)

    @patch('time.sleep')
    @patch('requests.post')
    def test_retry_mechanism_on_500_error(self, mock_post, mock_sleep):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = '{"error": "Internal Server Error"}'
        mock_post.return_value = mock_resp

        res = self.service.send_single(self.payload)

        # Should have attempted 3 times before failing
        self.assertEqual(mock_post.call_count, 3)
        self.assertFalse(res.success)

    @patch('requests.get')
    def test_get_balance_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"balance": 15000}'
        mock_get.return_value = mock_resp

        res = self.service.get_balance()

        self.assertTrue(res.success)
        self.assertEqual(res.balance, "15000")

    @patch('requests.get')
    def test_fetch_dlr_status(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"msgid": "GW_MSG_12345", "status": "DELIVRD"}'
        mock_get.return_value = mock_resp

        res = self.service.fetch_dlr("GW_MSG_12345")

        self.assertTrue(res.success)
        self.assertEqual(res.dlr_status, "DELIVRD")
