import json
import logging
from datetime import timedelta
from typing import Dict, Any

from django.utils import timezone
from django.db.models import Count, Sum, Q, Max

from apps.accounts.models import CustomUser
from apps.users.models import Department, Staff
from apps.dlt_templates.models import DLTTemplate
from apps.sms.models import SMSBatch, SMSQueue, SMSStatusChoices
from apps.logs.models import SMSLog
from apps.settings_app.models import SMSGatewayConfig
from apps.sms.services.gateway_service import SMSGatewayService
from apps.common.scopes import get_scoped_queryset, is_global_admin

logger = logging.getLogger('apps.dashboard')


class DashboardService:
    """
    Real-time enterprise dashboard analytics service layer with Office scope data isolation.
    Retrieves dynamic database counters, aggregations, gateway diagnostics,
    and Chart.js trend datasets with optimized queries.
    """

    @classmethod
    def get_summary_metrics(cls, user=None) -> Dict[str, Any]:
        now = timezone.now()
        today = now.date()

        # Office Scoped Base Querysets
        log_qs = get_scoped_queryset(user, SMSLog.objects.all())
        tmpl_qs = get_scoped_queryset(user, DLTTemplate.objects.filter(is_active=True))
        queue_qs = get_scoped_queryset(user, SMSQueue.objects.all())
        batch_qs = get_scoped_queryset(user, SMSBatch.objects.all())

        # 1. System & Recipient Summary Counters
        total_staff = Staff.objects.filter(is_active=True).count()
        if total_staff == 0:
            total_staff = CustomUser.objects.filter(is_active=True).count()

        total_departments = Department.objects.filter(is_active=True).count() if is_global_admin(user) else (1 if getattr(user, 'department', None) else 0)
        active_templates = tmpl_qs.count()

        total_sms_sent = log_qs.filter(status__in=['SENT', 'DELIVRD', 'Success']).count()
        failed_sms = log_qs.filter(status__in=['FAILED', 'REJECTD', 'UNDELIV', 'Failure']).count()
        pending_queue = queue_qs.filter(status='QUEUED').count()
        processing_batches = batch_qs.filter(status=SMSStatusChoices.PROCESSING).count()

        today_count = log_qs.filter(created_at__date=today).count()
        month_count = log_qs.filter(created_at__year=now.year, created_at__month=now.month).count()

        # 2. SMS Status Overview
        delivered_count = total_sms_sent
        failed_count = failed_sms
        pending_count = pending_queue

        # 3. Recent SMS Activity (Latest 10)
        recent_activities = log_qs.select_related(
            'user', 'template', 'department'
        ).order_by('-created_at')[:10]

        # 4. Recent Bulk SMS Batches (Latest 5)
        recent_batches = batch_qs.select_related(
            'user', 'template', 'department'
        ).order_by('-started_at')[:5]

        # 5. Department-wise SMS Usage Aggregation
        dept_usage_qs = log_qs.filter(department__isnull=False).values(
            'department__name', 'department__code'
        ).annotate(
            total_sent=Count('id', filter=Q(status__in=['SENT', 'DELIVRD', 'Success'])),
            failed_count=Count('id', filter=Q(status__in=['FAILED', 'REJECTD', 'UNDELIV', 'Failure'])),
            total_credits=Sum('credit_units')
        ).order_by('-total_sent')[:5]

        dept_usage_list = []
        dept_chart_labels = []
        dept_chart_sent = []
        for d in dept_usage_qs:
            dept_name = d['department__name'] or d['department__code'] or 'General'
            sent_val = d['total_sent'] or 0
            dept_usage_list.append({
                'name': dept_name,
                'total_sent': sent_val,
                'failed_count': d['failed_count'] or 0,
                'total_credits': d['total_credits'] or 0
            })
            dept_chart_labels.append(dept_name)
            dept_chart_sent.append(sent_val)

        # 6. Top DLT Templates by Usage
        top_templates_qs = log_qs.filter(template__isnull=False).values(
            'template__name', 'template__department__name'
        ).annotate(
            times_used=Count('id'),
            last_used=Max('created_at')
        ).order_by('-times_used')[:5]

        # 7. Gateway Status & Balance
        active_config = SMSGatewayConfig.objects.filter(is_active=True).first()
        credit_balance = "N/A"
        gateway_status = "Disconnected"

        if active_config:
            gateway_status = "Connected"
            try:
                gw_service = SMSGatewayService(active_config)
                bal_resp = gw_service.get_balance()
                if bal_resp.success and bal_resp.balance:
                    credit_balance = str(bal_resp.balance)
                else:
                    credit_balance = "Balance not available"
            except Exception as e:
                logger.warning(f"DASHBOARD_GW_BALANCE_ERR | {str(e)}")
                credit_balance = "Balance not available"

        # 8. Recent Login Activity (Latest 5)
        recent_logins_qs = CustomUser.objects.filter(last_login__isnull=False)
        if not is_global_admin(user) and getattr(user, 'department', None):
            recent_logins_qs = recent_logins_qs.filter(department=user.department)

        recent_logins = recent_logins_qs.select_related('department', 'role_obj').order_by('-last_login')[:5]

        # 9. Last 7 Days Daily Dispatch Trend Dataset for Chart.js
        last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        date_labels = [d.strftime('%b %d') for d in last_7_days]
        daily_sent_data = []
        daily_failed_data = []

        for d in last_7_days:
            s_count = log_qs.filter(created_at__date=d, status__in=['SENT', 'DELIVRD', 'Success']).count()
            f_count = log_qs.filter(created_at__date=d, status__in=['FAILED', 'REJECTD', 'UNDELIV', 'Failure']).count()
            daily_sent_data.append(s_count)
            daily_failed_data.append(f_count)

        chart_data = {
            'date_labels': json.dumps(date_labels),
            'daily_sent_data': json.dumps(daily_sent_data),
            'daily_failed_data': json.dumps(daily_failed_data),
            'dept_labels': json.dumps(dept_chart_labels),
            'dept_sent_counts': json.dumps(dept_chart_sent),
            'success_vs_fail_data': json.dumps([delivered_count, failed_count])
        }

        return {
            'total_staff': total_staff,
            'total_departments': total_departments,
            'active_templates': active_templates,
            'total_sms_sent': total_sms_sent,
            'failed_sms': failed_sms,
            'pending_queue': pending_queue,
            'processing_batches': processing_batches,
            'today_count': today_count,
            'month_count': month_count,
            'delivered_count': delivered_count,
            'failed_count': failed_count,
            'pending_count': pending_count,
            'credit_balance': credit_balance,
            'active_config': active_config,
            'gateway_status': gateway_status,
            'recent_activities': recent_activities,
            'recent_batches': recent_batches,
            'dept_usage_list': dept_usage_list,
            'top_templates': top_templates_qs,
            'recent_logins': recent_logins,
            'chart_data': chart_data
        }
