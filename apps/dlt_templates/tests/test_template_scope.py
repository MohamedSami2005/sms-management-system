from django.test import TestCase
from django.urls import reverse
from apps.accounts.models import CustomUser, Role
from apps.users.models import Office, Department, Staff
from apps.dlt_templates.models import DLTTemplate
from apps.logs.models import SMSLog


class TemplateScopeTestCase(TestCase):
    def setUp(self):
        # Create Offices
        self.admin_office, _ = Office.objects.get_or_create(code="ADMIN", defaults={'name': "Admin Management"})
        self.coe_office, _ = Office.objects.get_or_create(code="COE", defaults={'name': "COE"})
        self.erp_office, _ = Office.objects.get_or_create(code="ERP", defaults={'name': "ERP"})
        self.accounts_office, _ = Office.objects.get_or_create(code="ACCTS", defaults={'name': "Accounts"})

        # Create Roles
        self.admin_role, _ = Role.objects.get_or_create(code='ADMIN', defaults={'name': 'System Admin'})
        self.staff_role, _ = Role.objects.get_or_create(code='STAFF', defaults={'name': 'College Staff'})

        # Create Users
        self.global_admin = CustomUser.objects.create_superuser(
            username="global_admin",
            email="admin@college.edu",
            password="adminpassword123",
            office=self.admin_office,
            role_obj=self.admin_role,
            role='ADMIN'
        )
        self.coe_user = CustomUser.objects.create_user(
            username="coe_user",
            password="userpassword123",
            office=self.coe_office,
            role_obj=self.staff_role,
            role='STAFF'
        )
        self.erp_user = CustomUser.objects.create_user(
            username="erp_user",
            password="userpassword123",
            office=self.erp_office,
            role_obj=self.staff_role,
            role='STAFF'
        )
        self.accounts_user = CustomUser.objects.create_user(
            username="accounts_user",
            password="userpassword123",
            office=self.accounts_office,
            role_obj=self.staff_role,
            role='STAFF'
        )

        # Create Staff Recipients
        self.staff_dept, _ = Department.objects.get_or_create(name="CSE", code="CSE")
        self.staff_recipient = Staff.objects.create(
            name="Supplier Sami",
            mobile_number="8098778622",
            department=self.staff_dept,
            is_active=True
        )

        # Create DLT Templates
        self.coe_template = DLTTemplate.objects.create(
            name="COE Exam Notice",
            dlt_template_id="1107160000000100001",
            entity_id="1001999988887777666",
            header_sender_id="CLGEXM",
            template_content="Dear {#var#}, your exam is on {#var#}.",
            office=self.coe_office,
            is_active=True
        )
        self.coe_template.ensure_primary_office_in_allowed()

        self.erp_template = DLTTemplate.objects.create(
            name="ERP Fee Notice",
            dlt_template_id="1107160000000100002",
            entity_id="1001999988887777666",
            header_sender_id="CLGERP",
            template_content="Dear {#var#}, fee of Rs.{#var#} received.",
            office=self.erp_office,
            is_active=True
        )
        self.erp_template.ensure_primary_office_in_allowed()

        # Create Active Gateway Config for SMS dispatch tests
        from apps.settings_app.models import SMSGatewayConfig
        SMSGatewayConfig.objects.filter(is_active=True).update(is_active=False)
        self.gateway_config = SMSGatewayConfig.objects.create(
            provider_name="Test Gateway",
            api_url="https://text.draft4sms.com/vb/apikey.php",
            api_key="TESTKEY123",
            default_sender_id="CLGEXM",
            is_active=True
        )

    def test_1_newly_created_template_appears_in_scope_table(self):
        """1. Newly created template appears in Scope table row."""
        self.client.force_login(self.global_admin)
        new_tmpl = DLTTemplate.objects.create(
            name="New Admission Template",
            dlt_template_id="1107160000000100099",
            entity_id="1001999988887777666",
            header_sender_id="CLGADM",
            template_content="Welcome to college {#var#}.",
            office=self.coe_office,
            is_active=True
        )
        new_tmpl.ensure_primary_office_in_allowed()
        response = self.client.get(reverse('dlt_templates:scope_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New Admission Template")

    def test_2_existing_template_office_belongs_to_allowed_offices(self):
        """2. Initial template office belongs to Allowed Offices."""
        self.assertTrue(self.coe_template.allowed_offices.filter(pk=self.coe_office.pk).exists())
        self.assertTrue(self.erp_template.allowed_offices.filter(pk=self.erp_office.pk).exists())

    def test_3_admin_can_grant_template_to_multiple_offices_via_ajax(self):
        """3. Admin can grant a template to multiple offices via AJAX toggle endpoint."""
        self.client.force_login(self.global_admin)
        response = self.client.post(
            reverse('dlt_templates:scope_toggle_ajax'),
            data={'template_id': self.coe_template.pk, 'office_id': self.erp_office.pk, 'allowed': 'true'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.coe_template.refresh_from_db()
        self.assertTrue(self.coe_template.allowed_offices.filter(pk=self.coe_office.pk).exists())
        self.assertTrue(self.coe_template.allowed_offices.filter(pk=self.erp_office.pk).exists())

    def test_4_ajax_toggle_can_revoke_office_permission(self):
        """4. Admin can revoke an office permission via AJAX toggle endpoint."""
        self.coe_template.allowed_offices.add(self.erp_office)
        self.client.force_login(self.global_admin)
        response = self.client.post(
            reverse('dlt_templates:scope_toggle_ajax'),
            data={'template_id': self.coe_template.pk, 'office_id': self.erp_office.pk, 'allowed': 'false'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.coe_template.refresh_from_db()
        self.assertFalse(self.coe_template.allowed_offices.filter(pk=self.erp_office.pk).exists())

    def test_5_erp_user_sees_erp_scoped_templates(self):
        """5. ERP user can see ERP-scoped templates."""
        self.client.force_login(self.erp_user)
        response = self.client.get(reverse('dlt_templates:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ERP Fee Notice")

    def test_6_erp_user_sees_coe_template_if_erp_added_to_scope(self):
        """6. ERP user can see a COE template if ERP was added to its scope."""
        self.coe_template.allowed_offices.add(self.erp_office)
        self.client.force_login(self.erp_user)
        response = self.client.get(reverse('dlt_templates:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "COE Exam Notice")

    def test_7_erp_user_cannot_see_coe_only_template(self):
        """7. ERP user cannot see a COE-only template."""
        self.coe_template.allowed_offices.set([self.coe_office])
        self.client.force_login(self.erp_user)
        response = self.client.get(reverse('dlt_templates:list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "COE Exam Notice")

    def test_8_accounts_user_cannot_see_coe_erp_template_unless_added(self):
        """8. Accounts user cannot see COE + ERP template unless Accounts is explicitly added."""
        self.coe_template.allowed_offices.set([self.coe_office, self.erp_office])
        self.client.force_login(self.accounts_user)
        response = self.client.get(reverse('dlt_templates:list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "COE Exam Notice")

        # Now add Accounts to scope
        self.coe_template.allowed_offices.add(self.accounts_office)
        response = self.client.get(reverse('dlt_templates:list'))
        self.assertContains(response, "COE Exam Notice")

    def test_9_single_sms_respects_allowed_offices(self):
        """9. Single SMS template selection respects Allowed Offices matrix."""
        self.coe_template.allowed_offices.set([self.coe_office, self.erp_office])
        self.client.force_login(self.erp_user)
        response = self.client.get(reverse('sms:single'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "COE Exam Notice")
        self.assertContains(response, "ERP Fee Notice")

    def test_10_bulk_sms_respects_allowed_offices(self):
        """10. Bulk SMS template selection respects Allowed Offices matrix."""
        self.coe_template.allowed_offices.set([self.coe_office, self.erp_office])
        session = self.client.session
        session['bulk_sms_staff_ids'] = [self.staff_recipient.pk]
        session.save()

        self.client.force_login(self.erp_user)
        response = self.client.get(reverse('sms:bulk_compose'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "COE Exam Notice")

    def test_11_direct_unauthorized_template_access_rejected(self):
        """11. Direct unauthorized template access via POST manipulation is rejected."""
        self.coe_template.allowed_offices.set([self.coe_office])
        self.client.force_login(self.erp_user)
        response = self.client.post(reverse('sms:single'), {
            'mobile_number': '9876543211',
            'template': str(self.coe_template.pk),
            'var_1_source_type': 'static',
            'var_1_static_val': 'Test'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertIn('template', response.context['form'].errors)

    def test_12_superuser_accesses_all_templates(self):
        """12. Superuser can access all templates regardless of scope."""
        self.client.force_login(self.global_admin)
        response = self.client.get(reverse('dlt_templates:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "COE Exam Notice")
        self.assertContains(response, "ERP Fee Notice")

    def test_13_admin_management_users_manage_all_scopes(self):
        """13. Admin Management users can access Permission Matrix page."""
        self.client.force_login(self.global_admin)
        response = self.client.get(reverse('dlt_templates:scope_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Template Scope Management")

        # Non-admin user gets 403 Forbidden
        self.client.force_login(self.erp_user)
        response = self.client.get(reverse('dlt_templates:scope_list'))
        self.assertEqual(response.status_code, 403)

    def test_14_sms_logs_retain_actual_sender_office(self):
        """14. SMS logs retain the actual sender's Office even when using a cross-office template."""
        self.coe_template.allowed_offices.add(self.erp_office)
        self.client.force_login(self.erp_user)

        response = self.client.post(reverse('sms:single'), {
            'mobile_number': '9876543211',
            'template': str(self.coe_template.pk),
            'var_1_source_type': 'static',
            'var_1_static_val': 'Student',
            'var_2_source_type': 'static',
            'var_2_static_val': 'Tomorrow'
        })
        self.assertEqual(response.status_code, 302)
        log = SMSLog.objects.latest('id')
        self.assertEqual(log.office, self.erp_office)

    def test_15_existing_sms_functionality_continues_working(self):
        """15. Existing SMS functionality continues working."""
        self.client.force_login(self.erp_user)
        response = self.client.post(reverse('sms:single'), {
            'mobile_number': '9876543211',
            'template': str(self.erp_template.pk),
            'var_1_source_type': 'static',
            'var_1_static_val': 'Student',
            'var_2_source_type': 'static',
            'var_2_static_val': '5000'
        })
        self.assertEqual(response.status_code, 302)
        log = SMSLog.objects.latest('id')
        self.assertEqual(log.template, self.erp_template)
        self.assertEqual(log.office, self.erp_office)

    def test_16_new_office_automatically_appears_in_matrix_columns(self):
        """16. Newly created Office automatically appears as a matrix column."""
        self.client.force_login(self.global_admin)
        Office.objects.create(name="Library Test Office", code="LIB_TEST")
        response = self.client.get(reverse('dlt_templates:scope_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LIB_TEST")

    def test_17_unauthorized_user_cannot_toggle_scope_ajax(self):
        """17. Non-admin user cannot invoke AJAX toggle endpoint."""
        self.client.force_login(self.erp_user)
        response = self.client.post(
            reverse('dlt_templates:scope_toggle_ajax'),
            data={'template_id': self.coe_template.pk, 'office_id': self.erp_office.pk, 'allowed': 'true'}
        )
        self.assertEqual(response.status_code, 403)

    def test_18_scope_page_without_filter_shows_all_templates(self):
        """18. Scope page without Office filter shows all templates."""
        self.client.force_login(self.global_admin)
        response = self.client.get(reverse('dlt_templates:scope_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "COE Exam Notice")
        self.assertContains(response, "ERP Fee Notice")

    def test_19_office_filter_lists_only_active_offices(self):
        """19. Office filter lists only active Offices."""
        inactive_off = Office.objects.create(name="Archived Office", code="ARCH", is_active=False)
        self.client.force_login(self.global_admin)
        response = self.client.get(reverse('dlt_templates:scope_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "COE")
        self.assertContains(response, "ERP")
        self.assertNotContains(response, "Archived Office")

    def test_20_selecting_erp_shows_only_templates_allowed_for_erp(self):
        """20. Selecting ERP shows only templates allowed for ERP."""
        self.client.force_login(self.global_admin)
        response = self.client.get(reverse('dlt_templates:scope_list'), {'office': str(self.erp_office.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ERP Fee Notice")
        self.assertNotContains(response, "COE Exam Notice")

    def test_21_selecting_coe_shows_only_templates_allowed_for_coe(self):
        """21. Selecting COE shows only templates allowed for COE."""
        self.client.force_login(self.global_admin)
        response = self.client.get(reverse('dlt_templates:scope_list'), {'office': str(self.coe_office.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "COE Exam Notice")
        self.assertNotContains(response, "ERP Fee Notice")

    def test_22_template_allowed_for_erp_and_coe_appears_in_both_filters(self):
        """22. A template allowed for ERP + COE appears under both filters."""
        self.coe_template.allowed_offices.add(self.erp_office)
        self.client.force_login(self.global_admin)

        resp_erp = self.client.get(reverse('dlt_templates:scope_list'), {'office': str(self.erp_office.pk)})
        self.assertContains(resp_erp, "COE Exam Notice")

        resp_coe = self.client.get(reverse('dlt_templates:scope_list'), {'office': str(self.coe_office.pk)})
        self.assertContains(resp_coe, "COE Exam Notice")

    def test_23_coe_only_template_does_not_appear_when_erp_selected(self):
        """23. A COE-only template does not appear when ERP is selected."""
        self.coe_template.allowed_offices.set([self.coe_office])
        self.client.force_login(self.global_admin)
        response = self.client.get(reverse('dlt_templates:scope_list'), {'office': str(self.erp_office.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "COE Exam Notice")

    def test_24_search_and_office_filter_work_together(self):
        """24. Search + Office filter work together using AND logic."""
        self.client.force_login(self.global_admin)
        response = self.client.get(reverse('dlt_templates:scope_list'), {
            'office': str(self.erp_office.pk),
            'q': 'Fee'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ERP Fee Notice")

        # Search for non-matching string
        response_empty = self.client.get(reverse('dlt_templates:scope_list'), {
            'office': str(self.erp_office.pk),
            'q': 'Exam'
        })
        self.assertNotContains(response_empty, "ERP Fee Notice")
        self.assertNotContains(response_empty, "COE Exam Notice")

    def test_25_existing_ajax_checkbox_permission_updates_continue_working(self):
        """25. Existing AJAX checkbox permission updates continue working."""
        self.client.force_login(self.global_admin)
        response = self.client.post(
            reverse('dlt_templates:scope_toggle_ajax'),
            data={'template_id': self.erp_template.pk, 'office_id': self.coe_office.pk, 'allowed': 'true'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(self.erp_template.allowed_offices.filter(pk=self.coe_office.pk).exists())

    def test_26_inactive_offices_do_not_appear_in_filter(self):
        """26. Inactive Offices do not appear in the filter."""
        Office.objects.create(name="Obsolete Dept", code="OBS", is_active=False)
        self.client.force_login(self.global_admin)
        response = self.client.get(reverse('dlt_templates:scope_list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Obsolete Dept")

    def test_27_unauthorized_users_still_cannot_access_scope_with_office_filter(self):
        """27. Unauthorized users still cannot access Scope page even with office parameter."""
        self.client.force_login(self.erp_user)
        response = self.client.get(reverse('dlt_templates:scope_list'), {'office': str(self.erp_office.pk)})
        self.assertEqual(response.status_code, 403)

    def test_28_template_list_displays_associated_office_and_not_assigned(self):
        """28. Template list displays assigned Office name or Not Assigned when office is NULL."""
        unassigned_tmpl = DLTTemplate.objects.create(
            name="Unassigned DLT Notice",
            dlt_template_id="1107160000000999999",
            entity_id="1001999988887777666",
            header_sender_id="CLGGEN",
            template_content="General notification {#var#}.",
            office=None,
            is_active=True
        )

        self.client.force_login(self.global_admin)
        response = self.client.get(reverse('dlt_templates:list'))
        self.assertEqual(response.status_code, 200)

        # Check Office header is present
        self.assertContains(response, "<th>Office</th>")

        # Check assigned office names are rendered
        self.assertContains(response, "COE")
        self.assertContains(response, "ERP")

        # Check unassigned template renders Not Assigned
        self.assertContains(response, "Not Assigned")
