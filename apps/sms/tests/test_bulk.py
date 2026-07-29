from unittest.mock import patch, MagicMock
from django.test import TestCase

from apps.accounts.models import CustomUser, Role
from apps.users.models import Department, Staff
from apps.dlt_templates.models import DLTTemplate
from apps.settings_app.models import SMSGatewayConfig
from apps.sms.services.bulk_sms import BulkSMSService
from apps.sms.services.field_mapper import StaffFieldMapper
from apps.logs.models import SMSLog


class PersonalizedBulkSMSGatewayTestCase(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Computer Science", code="CSE")
        
        self.user1 = CustomUser.objects.create_superuser(
            username="admin_user",
            first_name="System",
            last_name="Admin",
            phone_number="9999999999",
            department=self.dept
        )

        self.staff1 = Staff.objects.create(
            name="Mohamed Sami",
            mobile_number="9876543210",
            department=self.dept
        )
        self.staff2 = Staff.objects.create(
            name="Abdul Qadir",
            mobile_number="9876543211",
            department=self.dept
        )
        self.staff3_no_phone = Staff.objects.create(
            name="Prof Jaffer",
            mobile_number="",  # Missing phone number
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
            name="Claim Notification",
            dlt_template_id="1107160000000123456",
            entity_id="1001999988887777666",
            header_sender_id="CLGEXM",
            template_content="Prof. {#var#}, your claim of Rs.{#var#} has been credited.",
            is_active=True
        )

    def test_staff_field_mapper_resolution(self):
        """Verifies StaffFieldMapper resolves Staff recipient attributes and static values accurately."""
        mapping = {
            "var_1": {"type": "field", "value": "name"},
            "var_2": {"type": "static", "value": "10000"}
        }
        res1 = StaffFieldMapper.resolve_all_variables(self.staff1, mapping)
        self.assertEqual(res1["var_1"], "Mohamed Sami")
        self.assertEqual(res1["var_2"], "10000")

        res2 = StaffFieldMapper.resolve_all_variables(self.staff2, mapping)
        self.assertEqual(res2["var_1"], "Abdul Qadir")
        self.assertEqual(res2["var_2"], "10000")

    @patch('requests.post')
    def test_personalized_bulk_dispatch_success(self, mock_post):
        """Tests personalized bulk dispatch where each recipient receives an individually interpolated SMS."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status":"Success","code":"011","messageid":"GW_BATCH_123"}'
        mock_post.return_value = mock_resp

        staff_ids = [self.staff1.id, self.staff2.id]
        mapping_config = {
            "var_1": {"type": "field", "value": "name"},
            "var_2": {"type": "static", "value": "10000"}
        }

        batch, summary = BulkSMSService.execute_bulk_dispatch(
            user=self.user1,
            staff_user_ids=staff_ids,
            template=self.template,
            mapping_config=mapping_config,
            department=self.dept
        )

        self.assertEqual(batch.total_records, 2)
        self.assertEqual(batch.successful_count, 2)
        self.assertEqual(batch.failed_count, 0)
        self.assertEqual(summary['success_percentage'], 100.0)

        # Verify individual SMSLog text content is personalized
        log1 = SMSLog.objects.get(batch=batch, mobile_number="9876543210")
        self.assertIn("Prof. Mohamed Sami, your claim of Rs.10000 has been credited.", log1.message_content)

        log2 = SMSLog.objects.get(batch=batch, mobile_number="9876543211")
        self.assertIn("Prof. Abdul Qadir, your claim of Rs.10000 has been credited.", log2.message_content)

    @patch('requests.post')
    def test_bulk_dispatch_continues_on_individual_failure(self, mock_post):
        """Verifies batch continues sending to remaining staff if one recipient has missing mobile."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status":"Success","code":"011","messageid":"GW_BATCH_999"}'
        mock_post.return_value = mock_resp

        staff_ids = [self.staff1.id, self.staff3_no_phone.id, self.staff2.id]
        mapping_config = {
            "var_1": {"type": "field", "value": "name"},
            "var_2": {"type": "static", "value": "15000"}
        }

        batch, summary = BulkSMSService.execute_bulk_dispatch(
            user=self.user1,
            staff_user_ids=staff_ids,
            template=self.template,
            mapping_config=mapping_config,
            department=self.dept
        )

        self.assertEqual(batch.total_records, 3)
        self.assertEqual(batch.successful_count, 2)
        self.assertEqual(batch.failed_count, 1)
        self.assertIn("Missing mobile number", summary['failure_reasons'][0])
