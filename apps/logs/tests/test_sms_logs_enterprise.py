from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import CustomUser
from apps.users.models import Department
from apps.dlt_templates.models import DLTTemplate
from apps.logs.models import SMSLog


class EnterpriseSMSLogsTestCase(TestCase):
    def setUp(self):
        self.dept1 = Department.objects.create(name="Accounts Office", code="ACCOUNTS")
        self.dept2 = Department.objects.create(name="Controller of Examinations", code="COE")

        self.admin = CustomUser.objects.create_superuser(
            username="admin_user",
            first_name="System",
            last_name="Admin",
            employee_id="ADM001",
            phone_number="9876543210",
            department=self.dept1,
            role="ADMIN"
        )

        self.tmpl1 = DLTTemplate.objects.create(
            name="Fee Receipt Notice",
            dlt_template_id="1107160000000123456",
            header_sender_id="CLGEXM",
            template_content="Dear {#var#}, fee received.",
            department=self.dept1,
            is_active=True
        )

        self.tmpl2 = DLTTemplate.objects.create(
            name="Exam Schedule Alert",
            dlt_template_id="1107160000000999999",
            header_sender_id="CLGNOT",
            template_content="Dear Student, exam on {#var#}.",
            department=self.dept2,
            is_active=True
        )

        # Create multiple log records for testing filters & pagination
        for i in range(1, 31):
            status = 'SENT' if i % 2 == 1 else 'FAILED'
            dept = self.dept1 if i <= 15 else self.dept2
            tmpl = self.tmpl1 if i <= 15 else self.tmpl2
            SMSLog.objects.create(
                user=self.admin,
                department=dept,
                template=tmpl,
                mobile_number=f"98765432{i:02d}",
                message_content=f"Log message {i}",
                status=status,
                credit_units=1,
                gateway_message_id=f"GW_MSG_{i}"
            )

        self.client = Client()
        self.client.force_login(self.admin)

    def test_logs_list_default_pagination(self):
        """Verifies default per_page is 25 and S.No calculation across pages works."""
        url = reverse('logs:list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        logs = response.context['logs']
        self.assertEqual(len(logs), 25)
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(response.context['paginator'].count, 30)

    def test_logs_list_custom_per_page(self):
        """Verifies per_page selector (10, 50, 100) dynamically adjusts page size."""
        url = reverse('logs:list')
        response = self.client.get(url, {'per_page': '10'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['logs']), 10)

    def test_filter_by_mobile_partial_match(self):
        """Verifies searching mobile number partial match filters results accurately."""
        url = reverse('logs:list')
        response = self.client.get(url, {'mobile': '9876543205'})
        self.assertEqual(response.status_code, 200)
        logs = response.context['logs']
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].mobile_number, '9876543205')

    def test_filter_by_status(self):
        """Verifies filtering by SENT vs FAILED status."""
        url = reverse('logs:list')
        response = self.client.get(url, {'status': 'FAILED', 'per_page': '50'})
        self.assertEqual(response.status_code, 200)
        logs = response.context['logs']
        self.assertEqual(len(logs), 15)
        for log in logs:
            self.assertEqual(log.status, 'FAILED')

    def test_filter_by_office(self):
        """Verifies filtering by Office/Department."""
        url = reverse('logs:list')
        response = self.client.get(url, {'office': str(self.dept2.pk), 'per_page': '50'})
        self.assertEqual(response.status_code, 200)
        logs = response.context['logs']
        self.assertEqual(len(logs), 15)
        for log in logs:
            self.assertEqual(log.department, self.dept2)

    def test_global_search_across_fields(self):
        """Verifies global search query 'Exam' matches template name."""
        url = reverse('logs:list')
        response = self.client.get(url, {'q': 'Exam', 'per_page': '50'})
        self.assertEqual(response.status_code, 200)
        logs = response.context['logs']
        self.assertEqual(len(logs), 15)
        for log in logs:
            self.assertEqual(log.template.name, "Exam Schedule Alert")

    def test_state_preservation_in_querystring(self):
        """Verifies state parameter helper retains active filters when navigating pages."""
        url = reverse('logs:list')
        response = self.client.get(url, {
            'status': 'SENT',
            'mobile': '9876',
            'per_page': '10',
            'page': '1'
        })
        self.assertEqual(response.status_code, 200)
        querystring = response.context['querystring']
        self.assertIn('status=SENT', querystring)
        self.assertIn('mobile=9876', querystring)
        self.assertIn('per_page=10', querystring)
        self.assertNotIn('page=', querystring)

    def test_log_with_null_template_and_null_batch(self):
        """Verifies logs with null template and batch render without template VariableDoesNotExist errors."""
        SMSLog.objects.create(
            user=None,
            department=None,
            template=None,
            batch=None,
            mobile_number="9999999999",
            message_content="Direct alert",
            status="SENT"
        )
        url = reverse('logs:list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
