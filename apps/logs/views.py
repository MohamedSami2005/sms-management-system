import io
import re
from datetime import datetime
from django.views.generic import ListView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from apps.common.scopes import get_scoped_queryset, is_global_admin
from apps.dlt_templates.models import DLTTemplate
from apps.accounts.models import CustomUser
from apps.users.models import Department, Staff
from .models import SMSLog


class SMSLogListView(LoginRequiredMixin, ListView):
    """
    Enterprise SMS Logs view providing multi-column filtering, global search,
    custom pagination sizing, state preservation, and backend Office scope data isolation.
    """
    model = SMSLog
    template_name = 'logs/log_list.html'
    context_object_name = 'logs'
    paginate_by = 50

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', '').strip()
        if per_page in ['10', '25', '50', '100']:
            return int(per_page)
        return self.paginate_by

    def get_queryset(self):
        # 1. Enforce Office scope on base SMSLog queryset
        queryset = get_scoped_queryset(
            self.request.user,
            super().get_queryset().select_related(
                'user', 'department', 'template', 'batch', 'user__department'
            ).order_by('-created_at')
        )

        start_date = self.request.GET.get('start_date', '').strip()
        end_date = self.request.GET.get('end_date', '').strip()
        mobile_filter = self.request.GET.get('mobile', '').strip()
        template_filter = self.request.GET.get('template', '').strip()
        status_filter = self.request.GET.get('status', '').strip()
        sender_filter = self.request.GET.get('sender', '').strip()
        office_filter = self.request.GET.get('office', '').strip()
        global_query = self.request.GET.get('q', '').strip()

        # Date Range Filter
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

        # Recipient Mobile Filter (partial match)
        if mobile_filter:
            queryset = queryset.filter(mobile_number__icontains=mobile_filter)

        # Template Filter
        if template_filter:
            if template_filter.isdigit():
                queryset = queryset.filter(template_id=int(template_filter))
            else:
                queryset = queryset.filter(template__name__icontains=template_filter)

        # Status Filter
        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)

        # Sender Filter
        if sender_filter:
            queryset = queryset.filter(
                Q(template__header_sender_id__iexact=sender_filter) |
                Q(batch__template__header_sender_id__iexact=sender_filter)
            )

        # Office Filter (Allowed for Global Admin; for normal user base queryset is already locked)
        if office_filter:
            if office_filter.isdigit():
                queryset = queryset.filter(
                    Q(department_id=int(office_filter)) | Q(user__department_id=int(office_filter))
                )
            else:
                queryset = queryset.filter(
                    Q(department__name__icontains=office_filter) | Q(user__department__name__icontains=office_filter)
                )

        # Global Search across Mobile, Template, Sender, Office, Status (Scoped to user's Office)
        if global_query:
            queryset = queryset.filter(
                Q(mobile_number__icontains=global_query) |
                Q(template__name__icontains=global_query) |
                Q(template__template_content__icontains=global_query) |
                Q(template__header_sender_id__icontains=global_query) |
                Q(batch__template__header_sender_id__icontains=global_query) |
                Q(department__name__icontains=global_query) |
                Q(user__department__name__icontains=global_query) |
                Q(status__icontains=global_query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request_get = self.request.GET.copy()
        user = self.request.user

        context['start_date'] = request_get.get('start_date', '')
        context['end_date'] = request_get.get('end_date', '')
        context['mobile'] = request_get.get('mobile', '')
        context['selected_template'] = request_get.get('template', '')
        context['selected_status'] = request_get.get('status', '')
        context['selected_sender'] = request_get.get('sender', '')
        context['search_query'] = request_get.get('q', '')
        context['per_page'] = request_get.get('per_page', '25')

        # Office Filter Dropdown scoping
        if is_global_admin(user):
            context['offices'] = Department.objects.filter(is_active=True)
            context['selected_office'] = request_get.get('office', '')
            context['templates'] = DLTTemplate.objects.filter(is_active=True)
            dlt_senders = list(DLTTemplate.objects.values_list('header_sender_id', flat=True).distinct())
            context['senders'] = sorted(list(set(s for s in dlt_senders if s)))
        else:
            user_office = getattr(user, 'department', None)
            if user_office:
                context['offices'] = Department.objects.filter(pk=user_office.pk)
                context['selected_office'] = str(user_office.pk)
                context['templates'] = DLTTemplate.objects.filter(department=user_office, is_active=True)
                dlt_senders = list(DLTTemplate.objects.filter(department=user_office).values_list('header_sender_id', flat=True).distinct())
                context['senders'] = sorted(list(set(s for s in dlt_senders if s)))
            else:
                context['offices'] = Department.objects.none()
                context['selected_office'] = ''
                context['templates'] = DLTTemplate.objects.none()
                context['senders'] = []

        # Preserve state helper for pagination links
        get_params = self.request.GET.copy()
        get_params.pop('page', None)
        context['querystring'] = get_params.urlencode()

        return context


from django.http import HttpResponse, JsonResponse


class SMSLogExportPreviewView(LoginRequiredMixin, View):
    """
    AJAX Preview view for SMS Audit Log Export.
    Returns JSON response containing preview metadata, record count, and structured rows.
    """
    def get(self, request, *args, **kwargs):
        period = request.GET.get('period', 'all').strip().lower()
        from_date_str = request.GET.get('from_date', '').strip()
        to_date_str = request.GET.get('to_date', '').strip()

        data = get_export_dataset(request.user, period, from_date_str, to_date_str)
        if not data['success']:
            return JsonResponse({'success': False, 'error': data['error']})

        return JsonResponse({
            'success': True,
            'period_display': data['period_display'],
            'total_count': data['total_count'],
            'rows': data['rows_data']
        })


class SMSLogExportView(LoginRequiredMixin, View):
    """
    Dedicated view for generating and downloading SMS Audit Logs Excel (.xlsx) report.
    Uses get_export_dataset to guarantee 100% data consistency with Export Preview.
    """
    def get(self, request, *args, **kwargs):
        period = request.GET.get('period', 'all').strip().lower()
        from_date_str = request.GET.get('from_date', '').strip()
        to_date_str = request.GET.get('to_date', '').strip()

        data = get_export_dataset(request.user, period, from_date_str, to_date_str)

        if not data['success']:
            messages.error(request, data['error'])
            return redirect('logs:list')

        # Build openpyxl workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "SMS Logs"
        ws.views.sheetView[0].showGridLines = True

        # Styles
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1A365D", end_color="1A365D", fill_type="solid")
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        border_thin = Side(border_style="thin", color="CBD5E1")
        cell_border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)

        # Write 6 exact headers: S.No, Name, Mobile Number, SMS Template, Sent Date, Delivery Status
        headers = ["S.No", "Name", "Mobile Number", "SMS Template", "Sent Date", "Delivery Status"]
        ws.append(headers)

        for col_idx, _ in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = cell_border
        ws.row_dimensions[1].height = 24

        # Populate rows
        for row_info in data['rows_data']:
            row_data = [
                row_info['s_no'],
                row_info['name'],
                row_info['mobile'],
                row_info['sms_template'],
                row_info['sent_date'],
                row_info['delivery_status']
            ]
            ws.append(row_data)

            row_idx = row_info['s_no'] + 1
            ws.row_dimensions[row_idx].height = 20

            ws.cell(row=row_idx, column=1).alignment = center_align
            ws.cell(row=row_idx, column=2).alignment = left_align
            ws.cell(row=row_idx, column=3).alignment = center_align
            ws.cell(row=row_idx, column=4).alignment = left_align
            ws.cell(row=row_idx, column=5).alignment = center_align
            ws.cell(row=row_idx, column=6).alignment = center_align

            for col_idx in range(1, 7):
                ws.cell(row=row_idx, column=col_idx).border = cell_border

        # Auto-fit column widths
        col_widths = {'A': 8, 'B': 24, 'C': 16, 'D': 28, 'E': 22, 'F': 16}
        for col_letter, width in col_widths.items():
            ws.column_dimensions[col_letter].width = width

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{data["filename"]}"'
        return response


def _parse_export_date(date_str):
    if not date_str:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _resolve_export_recipient_name(log, staff_map, user_map):
    mobile = log.mobile_number
    if mobile in staff_map:
        return staff_map[mobile]
    if mobile in user_map:
        return user_map[mobile]

    if log.message_content:
        match = re.search(r'(?:Dear|Prof\.|Dr\.|Mr\.|Mrs\.|Ms\.)\s+([^,.\n]+)', log.message_content, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted and len(extracted) < 50:
                return extracted

    return "Recipient"


def _resolve_export_delivery_status(log):
    if log.dlr_status in ['DELIVRD', 'DELIVERED']:
        return "Delivered"
    if log.status in ['SENT', 'Success'] or log.dlr_status in ['SENT', 'Success']:
        return "Sent"
    if log.status in ['FAILED', 'REJECTD', 'UNDELIV', 'Failure'] or log.dlr_status in ['FAILED', 'REJECTD', 'UNDELIV', 'Failure']:
        return "Failed"
    if log.status == 'QUEUED':
        return "Queued"
    return "Pending"


def get_export_dataset(user, period, from_date_str, to_date_str):
    """
    Shared helper for both Export Preview and Excel File Download.
    """
    queryset = get_scoped_queryset(
        user,
        SMSLog.objects.all().select_related(
            'user', 'office', 'department', 'template', 'batch'
        ).order_by('-created_at')
    )

    today_local = timezone.localtime(timezone.now()).date()
    period_display = "All Records"
    filename = "SMS_Logs_All.xlsx"

    if period == 'today':
        start_dt = timezone.make_aware(datetime.combine(today_local, datetime.min.time()))
        end_dt = timezone.make_aware(datetime.combine(today_local, datetime.max.time()))
        queryset = queryset.filter(created_at__range=(start_dt, end_dt))
        period_display = f"Today — {today_local.strftime('%d/%m/%Y')}"
        filename = f"SMS_Logs_Today_{today_local.strftime('%Y-%m-%d')}.xlsx"

    elif period == 'custom':
        if not from_date_str or not to_date_str:
            return {
                'success': False,
                'error': "Both From Date and To Date are required for Custom Date Range export.",
                'period_display': '',
                'filename': '',
                'logs_list': [],
                'rows_data': [],
                'total_count': 0
            }

        from_date = _parse_export_date(from_date_str)
        to_date = _parse_export_date(to_date_str)

        if not from_date or not to_date:
            return {
                'success': False,
                'error': "Invalid date format provided. Please use DD/MM/YYYY or YYYY-MM-DD.",
                'period_display': '',
                'filename': '',
                'logs_list': [],
                'rows_data': [],
                'total_count': 0
            }

        if from_date > to_date:
            return {
                'success': False,
                'error': "From Date cannot be after To Date.",
                'period_display': '',
                'filename': '',
                'logs_list': [],
                'rows_data': [],
                'total_count': 0
            }

        start_dt = timezone.make_aware(datetime.combine(from_date, datetime.min.time()))
        end_dt = timezone.make_aware(datetime.combine(to_date, datetime.max.time()))
        queryset = queryset.filter(created_at__range=(start_dt, end_dt))

        if from_date == to_date:
            period_display = from_date.strftime('%d/%m/%Y')
            filename = f"SMS_Logs_{from_date.strftime('%Y-%m-%d')}.xlsx"
        else:
            period_display = f"{from_date.strftime('%d/%m/%Y')} → {to_date.strftime('%d/%m/%Y')}"
            filename = f"SMS_Logs_{from_date.strftime('%Y-%m-%d')}_to_{to_date.strftime('%Y-%m-%d')}.xlsx"

    logs_list = list(queryset)
    total_count = len(logs_list)

    if total_count == 0:
        return {
            'success': False,
            'error': "No SMS logs found for the selected period.",
            'period_display': period_display,
            'filename': filename,
            'logs_list': [],
            'rows_data': [],
            'total_count': 0
        }

    mobile_numbers = set(log.mobile_number for log in logs_list if log.mobile_number)

    staff_map = dict(
        Staff.objects.filter(mobile_number__in=mobile_numbers)
        .values_list('mobile_number', 'name')
    )
    user_map = {}
    for u in CustomUser.objects.filter(phone_number__in=mobile_numbers):
        user_map[u.phone_number] = u.get_full_name() or u.username

    rows_data = []
    for idx, log in enumerate(logs_list, start=1):
        name = _resolve_export_recipient_name(log, staff_map, user_map)
        mobile = log.mobile_number or "—"
        sms_template = log.template.name if log.template else "—"
        sent_dt = timezone.localtime(log.created_at).strftime("%d/%m/%Y %I:%M %p")
        deliv_status = _resolve_export_delivery_status(log)

        rows_data.append({
            's_no': idx,
            'name': name,
            'mobile': mobile,
            'sms_template': sms_template,
            'sent_date': sent_dt,
            'delivery_status': deliv_status
        })

    return {
        'success': True,
        'error': None,
        'period_display': period_display,
        'filename': filename,
        'logs_list': logs_list,
        'rows_data': rows_data,
        'total_count': total_count
    }


