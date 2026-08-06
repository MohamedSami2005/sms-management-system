from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import CustomUser, Role
from apps.users.models import Department, Staff, Office
from apps.dlt_templates.models import DLTTemplate
from apps.logs.models import SMSLog


class OfficeAccessScopeTestCase(TestCase):
    def setUp(self):
        # 1. Setup Offices
        self.admin_office, _ = Office.objects.get_or_create(
            code='ADMIN',
            defaults={'name': "Admin Management", 'is_active': True}
        )
        self.erp_office, _ = Office.objects.get_or_create(code="ERP", defaults={'name': "ERP Office", 'is_active': True})
        self.coe_office, _ = Office.objects.get_or_create(code="COE", defaults={'name': "COE Office", 'is_active': True})

        # 2. Setup Roles
        self.admin_role = Role.objects.create(code='ADMIN', name='System Admin')
        self.staff_role = Role.objects.create(code='STAFF', name='Staff Member')

        # 3. Setup Users
        self.admin_user = CustomUser.objects.create_superuser(
            username="global_admin",
            password="AdminPassword@123",
            first_name="Global",
            last_name="Admin",
            employee_id="ADM001",
            phone_number="9876543210",
            office=self.admin_office,
            role="ADMIN",
            role_obj=self.admin_role
        )

        self.erp_user = CustomUser.objects.create_user(
            username="erp_user",
            password="UserPassword@123",
            first_name="ERP",
            last_name="Staff",
            employee_id="ERP001",
            phone_number="9876543211",
            office=self.erp_office,
            role="STAFF",
            role_obj=self.staff_role
        )

        self.coe_user = CustomUser.objects.create_user(
            username="coe_user",
            password="UserPassword@123",
            first_name="COE",
            last_name="Staff",
            employee_id="COE001",
            phone_number="9876543212",
            office=self.coe_office,
            role="STAFF",
            role_obj=self.staff_role
        )

        # 4. Setup DLT Templates
        self.erp_template = DLTTemplate.objects.create(
            name="ERP Fee Notice",
            dlt_template_id="1107160000000100001",
            header_sender_id="CLGERP",
            template_content="Dear {#var#}, ERP fee notice.",
            office=self.erp_office,
            is_active=True
        )

        self.coe_template = DLTTemplate.objects.create(
            name="COE Exam Schedule",
            dlt_template_id="1107160000000100002",
            header_sender_id="CLGCOE",
            template_content="Dear {#var#}, COE exam schedule.",
            office=self.coe_office,
            is_active=True
        )

        # 5. Setup SMS Logs
        self.erp_log = SMSLog.objects.create(
            user=self.erp_user,
            office=self.erp_office,
            template=self.erp_template,
            mobile_number="9876543211",
            message_content="ERP Test Log",
            status="SENT"
        )

        self.coe_log = SMSLog.objects.create(
            user=self.coe_user,
            office=self.coe_office,
            template=self.coe_template,
            mobile_number="9876543212",
            message_content="COE Test Log",
            status="SENT"
        )

        # 6. Setup Staff Recipient
        self.staff_recipient = Staff.objects.create(
            name="Mohamed Sami",
            mobile_number="8098778622",
            is_active=True
        )

        self.client = Client()

    def test_1_erp_user_sees_erp_templates(self):
        """1. ERP user sees ERP templates in Template List."""
        self.client.force_login(self.erp_user)
        response = self.client.get(reverse('dlt_templates:list'))
        self.assertEqual(response.status_code, 200)
        templates = response.context['templates']
        self.assertIn(self.erp_template, templates)

    def test_2_erp_user_cannot_see_coe_templates(self):
        """2. ERP user cannot see COE templates in Template List."""
        self.client.force_login(self.erp_user)
        response = self.client.get(reverse('dlt_templates:list'))
        self.assertEqual(response.status_code, 200)
        templates = response.context['templates']
        self.assertNotIn(self.coe_template, templates)

    def test_3_coe_user_sees_coe_templates(self):
        """3. COE user sees COE templates in Template List."""
        self.client.force_login(self.coe_user)
        response = self.client.get(reverse('dlt_templates:list'))
        self.assertEqual(response.status_code, 200)
        templates = response.context['templates']
        self.assertIn(self.coe_template, templates)
        self.assertNotIn(self.erp_template, templates)

    def test_4_admin_management_user_sees_all_templates(self):
        """4. Admin Management user sees all templates across offices."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('dlt_templates:list'))
        self.assertEqual(response.status_code, 200)
        templates = response.context['templates']
        self.assertIn(self.erp_template, templates)
        self.assertIn(self.coe_template, templates)

    def test_5_erp_user_can_only_select_erp_templates_in_single_sms(self):
        """5. ERP user form queryset contains only ERP templates in Single SMS."""
        self.client.force_login(self.erp_user)
        response = self.client.get(reverse('sms:single'))
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        template_qs = form.fields['template'].queryset
        self.assertIn(self.erp_template, template_qs)
        self.assertNotIn(self.coe_template, template_qs)

    def test_6_erp_user_cannot_send_using_coe_template_direct_post(self):
        """6. ERP user submitting a COE template ID via direct POST manipulation is rejected safely without dispatching."""
        self.client.force_login(self.erp_user)
        initial_log_count = SMSLog.objects.count()
        response = self.client.post(reverse('sms:single'), {
            'mobile_number': '9876543211',
            'template': str(self.coe_template.pk),
            'var_1_source_type': 'static',
            'var_1_static_val': 'Test'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertIn('template', response.context['form'].errors)
        self.assertEqual(SMSLog.objects.count(), initial_log_count)

    def test_7_erp_sms_logs_visible_to_erp_user(self):
        """7. ERP SMS logs are visible to ERP user."""
        self.client.force_login(self.erp_user)
        response = self.client.get(reverse('logs:list'))
        self.assertEqual(response.status_code, 200)
        logs = response.context['logs']
        self.assertIn(self.erp_log, logs)

    def test_8_coe_sms_logs_not_visible_to_erp_user(self):
        """8. COE SMS logs are not visible to ERP user."""
        self.client.force_login(self.erp_user)
        response = self.client.get(reverse('logs:list'))
        self.assertEqual(response.status_code, 200)
        logs = response.context['logs']
        self.assertNotIn(self.coe_log, logs)

    def test_9_admin_management_user_sees_all_sms_logs(self):
        """9. Admin Management user sees all SMS logs."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('logs:list'))
        self.assertEqual(response.status_code, 200)
        logs = response.context['logs']
        self.assertIn(self.erp_log, logs)
        self.assertIn(self.coe_log, logs)

    def test_10_erp_user_cannot_access_coe_template_detail_edit_delete(self):
        """10. ERP user cannot access COE template detail/edit/delete endpoints (returns 404)."""
        self.client.force_login(self.erp_user)
        detail_url = reverse('dlt_templates:detail', kwargs={'pk': self.coe_template.pk})
        edit_url = reverse('dlt_templates:edit', kwargs={'pk': self.coe_template.pk})
        delete_url = reverse('dlt_templates:delete', kwargs={'pk': self.coe_template.pk})

        self.assertEqual(self.client.get(detail_url).status_code, 404)
        self.assertEqual(self.client.get(edit_url).status_code, 404)
        self.assertEqual(self.client.post(delete_url).status_code, 404)

    def test_11_sms_sent_by_erp_user_records_erp_office_in_smslog(self):
        """11. Single SMS sent by ERP user gets ERP Office recorded in SMSLog."""
        self.client.force_login(self.erp_user)
        from unittest.mock import patch
        from apps.sms.services.dto import GatewayResult

        with patch('apps.sms.services.gateway_service.SMSGatewayService.send_single') as mock_send:
            mock_send.return_value = GatewayResult(success=True, status_code=200, gateway_message_id="GW_TEST_SCOPE_100")
            response = self.client.post(reverse('sms:single'), {
                'mobile_number': '9876543211',
                'template': str(self.erp_template.pk),
                'var_1_source_type': 'static',
                'var_1_static_val': 'Sami'
            })
            self.assertIn(response.status_code, [200, 302])

            new_log = SMSLog.objects.filter(gateway_message_id="GW_TEST_SCOPE_100").first()
            self.assertIsNotNone(new_log)
            self.assertEqual(new_log.office, self.erp_office)

    def test_12_bulk_sms_continues_working_with_personalized_variables(self):
        """12. Bulk SMS continues working with personalized variables under Office scope."""
        self.client.force_login(self.erp_user)
        session = self.client.session
        session['bulk_sms_staff_ids'] = [self.staff_recipient.id]
        session.save()

        from unittest.mock import patch
        from apps.sms.services.dto import GatewayResult

        with patch('apps.sms.services.gateway_service.SMSGatewayService.send_single') as mock_send:
            mock_send.return_value = GatewayResult(success=True, status_code=200, gateway_message_id="GW_BULK_SCOPE_200")
            response = self.client.post(reverse('sms:bulk_compose'), {
                'template': str(self.erp_template.pk),
                'var_1_source_type': 'field',
                'var_1_field_val': 'name'
            })
            self.assertEqual(response.status_code, 302)

            batch_id = self.client.session.get('last_bulk_batch_id')
            self.assertIsNotNone(batch_id)
            log = SMSLog.objects.filter(batch_id=batch_id).first()
            self.assertIsNotNone(log)
            self.assertEqual(log.office, self.erp_office)

    def test_13_existing_sms_functionality_remains_unaffected(self):
        """13. Staff recipient search and preview endpoints function properly."""
        self.client.force_login(self.erp_user)
        response = self.client.get(reverse('sms:staff_search_ajax'), {'q': 'Sami'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Mohamed Sami', response.content.decode())

    def test_14_existing_admin_superuser_access_remains_unrestricted(self):
        """14. Existing admin/superuser access remains unrestricted across dashboard and templates."""
        self.client.force_login(self.admin_user)
        dash_response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(dash_response.status_code, 200)
        tmpl_response = self.client.get(reverse('dlt_templates:list'))
        self.assertEqual(tmpl_response.status_code, 200)
        self.assertEqual(len(tmpl_response.context['templates']), 2)
