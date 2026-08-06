from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from apps.common.scopes import get_scoped_queryset, is_global_admin
from apps.dlt_templates.models import DLTTemplate
from apps.users.models import Department
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
                Q(batch__sender_id__iexact=sender_filter)
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
                Q(batch__sender_id__icontains=global_query) |
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
        get_params = request_get.copy()
        if 'page' in get_params:
            del get_params['page']
        context['querystring'] = get_params.urlencode()

        return context
