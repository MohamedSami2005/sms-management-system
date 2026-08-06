import json
import logging
from typing import Dict, Any

from django.views.generic import FormView, ListView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q

from apps.common.mixins import RoleRequiredMixin
from apps.accounts.models import CustomUser, Role
from apps.users.models import Department, Staff
from apps.dlt_templates.models import DLTTemplate
from apps.sms.models import SMSBatch, SMSQueue, SMSStatusChoices
from apps.logs.models import SMSLog

from .forms import SingleSMSForm
from .services import SingleSMSService, BulkSMSService, StaffFieldMapper

logger = logging.getLogger('apps.sms')

ALLOWED_SMS_ROLES = []


class SingleSMSView(LoginRequiredMixin, RoleRequiredMixin, FormView):
    """
    Single SMS Dispatch View.
    Supports staff selection auto-complete, dynamic variable mapping (Static vs Staff DB Field),
    and live message preview sandbox. Reuses StaffFieldMapper and SingleSMSService.
    Enforces Office scope for DLT template selection and log recording.
    """
    template_name = 'sms/single_sms.html'
    form_class = SingleSMSForm
    success_url = reverse_lazy('sms:single')
    allowed_roles = ALLOWED_SMS_ROLES

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['db_fields'] = json.dumps(StaffFieldMapper.get_supported_fields())
        return context

    def form_valid(self, form):
        from apps.common.scopes import get_scoped_queryset
        mobile_number = form.cleaned_data['mobile_number']
        template_form_obj = form.cleaned_data['template']

        # Validate backend scope: ensure template belongs to user's Office
        template = get_object_or_404(
            get_scoped_queryset(self.request.user, DLTTemplate.objects.filter(is_active=True)),
            pk=template_form_obj.pk
        )

        # 1. Resolve staff recipient instance if selected by ID or mobile
        staff_id = self.request.POST.get('staff_id')
        staff_recipient = None
        if staff_id and str(staff_id).isdigit():
            staff_recipient = Staff.objects.filter(id=int(staff_id), is_active=True).first()
            if not staff_recipient:
                staff_recipient = CustomUser.objects.filter(id=int(staff_id), is_active=True).first()

        if not staff_recipient and mobile_number:
            staff_recipient = Staff.objects.filter(mobile_number=mobile_number, is_active=True).first()

        # 2. Extract variable mapping configuration from POST data
        mapping_config = {}
        for key, val in self.request.POST.items():
            if key.startswith('var_') and key.endswith('_source_type'):
                var_pos = key.replace('_source_type', '')  # e.g. 'var_1'
                stype = val
                if stype == 'static':
                    sval = self.request.POST.get(f"{var_pos}_static_val", '')
                else:
                    sval = self.request.POST.get(f"{var_pos}_field_val", 'name')
                mapping_config[var_pos] = {'type': stype, 'value': sval}
            elif key.startswith('var_') and not any(sub in key for sub in ['_source_type', '_static_val', '_field_val']):
                if key not in mapping_config:
                    mapping_config[key] = {'type': 'static', 'value': val}

        # 3. Resolve all template variables via StaffFieldMapper
        variable_values = StaffFieldMapper.resolve_all_variables(staff_recipient, mapping_config)

        # 4. Dispatch single SMS via SingleSMSService (associated with user's Office)
        success, log_entry, gw_result = SingleSMSService.process_and_send(
            user=self.request.user,
            mobile_number=mobile_number,
            template=template,
            variable_values=variable_values,
            department=getattr(self.request.user, 'department', None)
        )

        if success:
            messages.success(
                self.request,
                f"SMS successfully dispatched to {mobile_number}! (Gateway Msg ID: {log_entry.gateway_message_id})"
            )
        else:
            messages.error(
                self.request,
                f"SMS dispatch failed to {mobile_number}: {gw_result.error_message}"
            )

        return super().form_valid(form)


class StaffSearchAjaxView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    AJAX endpoint for searching active staff recipients by Name or Mobile Number.
    Queries the Staff recipient master model. Returns formatted JSON for auto-complete dropdowns.
    """
    allowed_roles = ALLOWED_SMS_ROLES

    def get(self, request):
        query = request.GET.get('q', '').strip()
        qs = Staff.objects.filter(is_active=True).select_related('department')

        if query:
            qs = qs.filter(
                Q(name__icontains=query) |
                Q(mobile_number__icontains=query)
            )

        qs = qs[:20]

        results = []
        for staff in qs:
            full_name = staff.name
            dept_name = staff.department.name if staff.department else 'General'
            mobile = staff.mobile_number or ''
            has_mobile = bool(mobile)

            display_label = f"{full_name} • {dept_name} • {mobile or 'No Phone'}"

            results.append({
                'id': staff.id,
                'name': full_name,
                'department': dept_name,
                'department_id': staff.department_id if staff.department else None,
                'mobile': mobile,
                'has_mobile': has_mobile,
                'display_label': display_label
            })

        return JsonResponse({'results': results})


class BulkSMSStaffSelectionView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    """
    Step 1: Staff Selection Screen.
    Displays paginated table of recipient staff members with search, department filter, and multi-selection checkboxes.
    """
    model = Staff
    template_name = 'sms/bulk_staff_select.html'
    context_object_name = 'staff_list'
    allowed_roles = ALLOWED_SMS_ROLES
    paginate_by = 15

    def get_queryset(self):
        qs = Staff.objects.filter(is_active=True).select_related('department').order_by('name')

        search_query = self.request.GET.get('q', '').strip()
        dept_id = self.request.GET.get('department', '').strip()

        if search_query:
            qs = qs.filter(
                Q(name__icontains=search_query) |
                Q(mobile_number__icontains=search_query)
            )

        if dept_id and dept_id.isdigit():
            qs = qs.filter(department_id=dept_id)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.filter(is_active=True)
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_dept'] = self.request.GET.get('department', '')
        return context

    def post(self, request, *args, **kwargs):
        """Processes selected staff IDs and stores them in session for Step 2."""
        selected_ids = request.POST.getlist('selected_staff_ids')
        if not selected_ids:
            messages.error(request, "Please select at least one staff member to proceed.")
            return redirect('sms:bulk_select')

        request.session['bulk_sms_staff_ids'] = [int(i) for i in selected_ids if i.isdigit()]
        return redirect('sms:bulk_compose')


class BulkSMSComposeView(LoginRequiredMixin, RoleRequiredMixin, TemplateView):
    """
    Step 2: Personalized Bulk SMS Compose Screen.
    Displays selected recipients, DLT Template dropdown (scoped to user's Office), Variable Mapping UI,
    and live recipient sandbox.
    """
    template_name = 'sms/bulk_sms_compose.html'
    allowed_roles = ALLOWED_SMS_ROLES

    def get(self, request, *args, **kwargs):
        from apps.common.scopes import get_scoped_queryset
        staff_ids = request.session.get('bulk_sms_staff_ids', [])
        if not staff_ids:
            messages.warning(request, "No staff members selected. Please select recipients first.")
            return redirect('sms:bulk_select')

        staff_members = Staff.objects.filter(id__in=staff_ids, is_active=True).select_related('department')
        if not staff_members.exists():
            staff_members = CustomUser.objects.filter(id__in=staff_ids).select_related('department')

        dlt_templates = get_scoped_queryset(request.user, DLTTemplate.objects.filter(is_active=True))
        db_fields = StaffFieldMapper.get_supported_fields()

        context = self.get_context_data()
        context['staff_members'] = staff_members
        context['selected_count'] = len(staff_members)
        context['dlt_templates'] = dlt_templates
        context['db_fields'] = db_fields
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        from apps.common.scopes import get_scoped_queryset
        staff_ids = request.session.get('bulk_sms_staff_ids', [])
        if not staff_ids:
            messages.error(request, "Session expired or no recipients selected.")
            return redirect('sms:bulk_select')

        template_id = request.POST.get('template')
        if not template_id or not template_id.isdigit():
            messages.error(request, "Please select a valid DLT Template.")
            return redirect('sms:bulk_compose')

        # Validate backend Office scope: template MUST belong to user's accessible Office
        template = get_object_or_404(
            get_scoped_queryset(request.user, DLTTemplate.objects.filter(is_active=True)),
            pk=template_id
        )

        # Build mapping_config for each variable (var_1, var_2...)
        mapping_config = {}
        for idx in range(1, template.variable_count + 1):
            key = f"var_{idx}"
            stype = request.POST.get(f"{key}_source_type", "static")
            if stype == "field":
                sval = request.POST.get(f"{key}_field_val", "")
            else:
                sval = request.POST.get(f"{key}_static_val", "")
            mapping_config[key] = {"type": stype, "value": sval}

        # Execute Personalized Bulk Dispatch via BulkSMSService
        batch, summary = BulkSMSService.execute_bulk_dispatch(
            user=request.user,
            staff_user_ids=staff_ids,
            template=template,
            mapping_config=mapping_config,
            department=request.user.department
        )

        request.session['last_bulk_batch_id'] = batch.id
        request.session['last_bulk_summary'] = summary

        # Clear session selection
        if 'bulk_sms_staff_ids' in request.session:
            del request.session['bulk_sms_staff_ids']

        messages.success(request, f"Personalized Bulk SMS dispatch complete. Sent: {batch.successful_count}/{batch.total_records}")
        return redirect('sms:bulk_summary', pk=batch.id)


class PersonalizedPreviewAjaxView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    AJAX endpoint for dynamically generating personalized SMS text for a specific staff member
    given a template ID and variable mapping config.
    """
    allowed_roles = ALLOWED_SMS_ROLES

    def post(self, request):
        from apps.common.scopes import get_scoped_queryset
        try:
            body = json.loads(request.body)
            staff_id = body.get('staff_id')
            mobile_number = body.get('mobile_number')
            template_id = body.get('template_id')
            mapping_config = body.get('mapping_config', {})
        except Exception:
            return JsonResponse({'success': False, 'error': 'Invalid JSON body'}, status=400)

        if not template_id:
            return JsonResponse({'success': False, 'error': 'Missing template_id'}, status=400)

        staff = None
        staff_name = ""
        if staff_id:
            staff = Staff.objects.filter(pk=staff_id).first() or CustomUser.objects.filter(pk=staff_id).first()
        elif mobile_number:
            staff = Staff.objects.filter(mobile_number=mobile_number).first()

        if staff:
            staff_name = staff.name if isinstance(staff, Staff) else (staff.get_full_name() or staff.username)

        # Enforce Office scope on template preview
        template = get_object_or_404(get_scoped_queryset(request.user, DLTTemplate.objects.all()), pk=template_id)

        # Resolve personalized variable values for this staff recipient
        personalized_vars = StaffFieldMapper.resolve_all_variables(staff, mapping_config)
        rendered_text = template.preview_message(personalized_vars)

        char_count = len(rendered_text)
        single_credits = DLTTemplate.calculate_sms_credits(rendered_text)

        return JsonResponse({
            'success': True,
            'staff_id': staff.id if staff else None,
            'staff_name': staff_name,
            'rendered_text': rendered_text,
            'char_count': char_count,
        })


class BulkSMSSummaryView(LoginRequiredMixin, RoleRequiredMixin, TemplateView):
    """
    Step 4: Completion Summary Screen.
    Displays dispatch metrics: Total Selected, Sent, Failed, Execution Time, Credits Used, and Failure Details.
    """
    template_name = 'sms/bulk_sms_summary.html'
    allowed_roles = ALLOWED_SMS_ROLES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        batch_id = self.kwargs.get('pk')
        batch = get_object_or_404(SMSBatch, pk=batch_id)
        summary = self.request.session.get('last_bulk_summary', {})

        context['batch'] = batch
        context['summary'] = summary
        context['logs'] = SMSLog.objects.filter(batch=batch).select_related('department')
        return context


class BulkSMSProgressAjaxView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    AJAX endpoint for checking real-time batch progress.
    """
    allowed_roles = ALLOWED_SMS_ROLES

    def get(self, request, pk):
        batch = get_object_or_404(SMSBatch, pk=pk)
        return JsonResponse({
            'batch_id': batch.id,
            'total_records': batch.total_records,
            'processed_records': batch.processed_records,
            'successful_count': batch.successful_count,
            'failed_count': batch.failed_count,
            'status': batch.status,
            'is_completed': batch.status in [SMSStatusChoices.SENT, SMSStatusChoices.DELIVERED, SMSStatusChoices.FAILED]
        })


class SMSQueueView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    """
    SMS Processing Queue & Active Batches view.
    Displays real-time pending, processing, and batch dispatch queues.
    """
    model = SMSQueue
    template_name = 'sms/queue_list.html'
    context_object_name = 'queue_items'
    allowed_roles = ALLOWED_SMS_ROLES
    paginate_by = 15

    def get_queryset(self):
        return SMSQueue.objects.all().select_related('user', 'department', 'template').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['processing_count'] = SMSQueue.objects.filter(status=SMSStatusChoices.PROCESSING).count()
        context['pending_count'] = SMSQueue.objects.filter(status=SMSStatusChoices.PENDING).count()
        context['completed_count'] = SMSQueue.objects.filter(status__in=[SMSStatusChoices.SENT, SMSStatusChoices.DELIVERED]).count()
        return context


# Alias for URL routing compatibility
SMSQueueListView = SMSQueueView
