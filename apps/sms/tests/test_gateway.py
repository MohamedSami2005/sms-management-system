from unittest.mock import patch, MagicMock
from django.test import TestCase

from apps.settings_app.models import SMSGatewayConfig
from apps.sms.services.dto import SMSPayload
from apps.sms.services.gateway_service import SMSGatewayService, DRAFT4SMS_ERROR_CODES
from apps.common.exceptions import SMSGatewayAuthException, SMSGatewayTimeoutException


class Draft4SMSGatewayServiceTestCase(TestCase):
    def setUp(self):
        self.config = SMSGatewayConfig.objects.create(
            provider_name="Draft4SMS Provider Profile",
            api_url="https://text.draft4sms.com/vb/apikey.php",
            balance_api_url="https://text.draft4sms.com/vb/http-credit.php",
            dlr_api_url="https://text.draft4sms.com/vb/http-dlr.php",
            api_key="DRAFT4SMS_TEST_SECRET_KEY_1234567890",
            default_sender_id="CLGEXM",
            default_entity_id="1001999988887777666",
            route_id="1",
            response_format="json",
            is_active=True
        )
        self.service = SMSGatewayService(self.config)
        self.payload = SMSPayload(
            mobile_number="9876543210",
            message_text="Dear Student, your exam schedule is published.",
            dlt_template_id="1107160000000123456",
            entity_id="1001999988887777666",
            header_sender_id="CLGEXM"
        )

    @patch('requests.post')
    def test_draft4sms_send_success_response(self, mock_post):
        """Tests parsing of exact Draft4SMS success response (status='Success', code='011')."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status":"Success","code":"011","messageid":"9876543210123","totnumber":1,"totalcredit":1,"description":"Message Sent Successfully"}'
        mock_post.return_value = mock_resp

        res = self.service.send_single(self.payload)

        self.assertTrue(res.success)
        self.assertEqual(res.gateway_message_id, "9876543210123")
        self.assertEqual(res.totnumber, 1)
        self.assertEqual(res.totalcredit, 1)
        self.assertEqual(res.status_code, 200)

    @patch('requests.post')
    def test_draft4sms_error_code_001_invalid_api_key(self, mock_post):
        """Tests parsing of Draft4SMS error code 001 Invalid API Key."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status":"Failure","code":"001","description":"Invalid API Key"}'
        mock_post.return_value = mock_resp

        res = self.service.send_single(self.payload)

        self.assertFalse(res.success)
        self.assertIn("Invalid API Key", res.error_message)

    @patch('requests.post')
    def test_draft4sms_error_code_008_insufficient_credit(self, mock_post):
        """Tests parsing of Draft4SMS error code 008 Insufficient Credit."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status":"Failure","code":"008","description":"Insufficient Credit"}'
        mock_post.return_value = mock_resp

        res = self.service.send_single(self.payload)

        self.assertFalse(res.success)
        self.assertIn("Insufficient Credit", res.error_message)

    @patch('requests.post')
    def test_draft4sms_http_401_auth_exception(self, mock_post):
        """Tests handling of HTTP 401 Unauthorized authentication failure."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = '{"error":"Unauthorized access"}'
        mock_post.return_value = mock_resp

        res = self.service.send_single(self.payload)

        self.assertFalse(res.success)
        self.assertIn("Authentication failed", res.error_message)

    @patch('time.sleep')
    @patch('requests.post')
    def test_retry_mechanism_exponential_backoff(self, mock_post, mock_sleep):
        """Tests 3 retries with exponential backoff on HTTP 500 error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = 'Internal Gateway Error'
        mock_post.return_value = mock_resp

        res = self.service.send_single(self.payload)

        self.assertEqual(mock_post.call_count, 3)
        self.assertFalse(res.success)

    @patch('requests.get')
    def test_draft4sms_balance_api(self, mock_get):
        """Tests Draft4SMS http-credit.php Balance API response parsing."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status":"Success","code":"011","balance":25000}'
        mock_get.return_value = mock_resp

        res = self.service.get_balance()

        self.assertTrue(res.success)
        self.assertEqual(res.balance, "25000")

    @patch('requests.get')
    def test_draft4sms_dlr_api(self, mock_get):
        """Tests Draft4SMS http-dlr.php DLR status parsing."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status":"DELIVERED","msgid":"9876543210123"}'
        mock_get.return_value = mock_resp

        res = self.service.fetch_dlr("9876543210123")

        self.assertTrue(res.success)
        self.assertEqual(res.dlr_status, "DELIVRD")

    def test_api_key_masking_security(self):
        """Verifies API Key is masked safely."""
        masked = SMSGatewayService.mask_api_key("DRAFT4SMS_TEST_SECRET_KEY_1234567890")
        self.assertNotIn("SECRET_KEY", masked)
        self.assertTrue(masked.startswith("DRAF"))
        self.assertTrue(masked.endswith("7890"))
