import json
from django.views.generic import FormView, ListView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q

from apps.common.mixins import RoleRequiredMixin
from apps.accounts.models import CustomUser, Role
from apps.users.models import Department
from apps.dlt_templates.models import DLTTemplate
from apps.logs.models import SMSLog
from .models import SMSQueue, SMSBatch, SMSStatusChoices
from .forms import SingleSMSForm
from .services.single_sms import SingleSMSService
from .services.bulk_sms import BulkSMSService
from .services.field_mapper import StaffFieldMapper

ALLOWED_SMS_ROLES = ['ADMIN', 'COE', 'ADMISSION', 'ACCOUNTS', 'PLACEMENT', 'STAFF']


class SingleSMSView(LoginRequiredMixin, RoleRequiredMixin, FormView):
    """
    Handles single SMS dispatch workflow.
    """
    template_name = 'sms/single_sms.html'
    form_class = SingleSMSForm
    success_url = reverse_lazy('sms:single')
    allowed_roles = ALLOWED_SMS_ROLES

    def get_initial(self):
        initial = super().get_initial()
        if hasattr(self.request.user, 'department') and self.request.user.department:
            initial['department'] = self.request.user.department
        return initial

    def form_valid(self, form):
        mobile_number = form.cleaned_data['mobile_number']
        template = form.cleaned_data['template']
        department = form.cleaned_data.get('department') or self.request.user.department

        var_dict = {}
        for idx in range(1, template.variable_count + 1):
            key = f"var_{idx}"
            var_dict[key] = self.request.POST.get(key, '').strip()

        success, log_entry, gw_result = SingleSMSService.process_and_send(
            user=self.request.user,
            mobile_number=mobile_number,
            template=template,
            variable_values=var_dict,
            department=department
        )

        context = self.get_context_data(form=form)
        context['dispatch_attempted'] = True
        context['dispatch_success'] = success
        context['log_entry'] = log_entry
        context['gw_result'] = gw_result

        if success:
            messages.success(self.request, f"SMS dispatched successfully to {mobile_number}. Gateway Msg ID: {gw_result.gateway_message_id}")
        else:
            messages.error(self.request, f"SMS dispatch failed. Reason: {gw_result.error_message}")

        return self.render_to_response(context)


class BulkSMSStaffSelectionView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    """
    Step 1: Staff Selection Screen.
    Displays paginated table of staff members with search, filters, and multi-selection checkboxes.
    """
    model = CustomUser
    template_name = 'sms/bulk_staff_select.html'
    context_object_name = 'staff_list'
    allowed_roles = ALLOWED_SMS_ROLES
    paginate_by = 15

    def get_queryset(self):
        qs = CustomUser.objects.all().select_related('department', 'role_obj').order_by('-date_joined')
        
        search_query = self.request.GET.get('q', '').strip()
        dept_id = self.request.GET.get('department', '').strip()
        role_id = self.request.GET.get('role', '').strip()
        status_val = self.request.GET.get('status', '').strip()

        if search_query:
            qs = qs.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(username__icontains=search_query) |
                Q(employee_id__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(phone_number__icontains=search_query)
            )

        if dept_id and dept_id.isdigit():
            qs = qs.filter(department_id=dept_id)

        if role_id:
            if role_id.isdigit():
                qs = qs.filter(role_obj_id=role_id)
            else:
                qs = qs.filter(role=role_id)

        if status_val == 'active':
            qs = qs.filter(is_active=True)
        elif status_val == 'inactive':
            qs = qs.filter(is_active=False)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.filter(is_active=True)
        context['roles'] = Role.objects.all()
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_dept'] = self.request.GET.get('department', '')
        context['selected_role'] = self.request.GET.get('role', '')
        context['selected_status'] = self.request.GET.get('status', '')
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
    Displays selected recipients, DLT Template dropdown, Variable Mapping UI (Static vs Staff DB Field),
    and live "Preview As" recipient sandbox.
    """
    template_name = 'sms/bulk_sms_compose.html'
    allowed_roles = ALLOWED_SMS_ROLES

    def get(self, request, *args, **kwargs):
        staff_ids = request.session.get('bulk_sms_staff_ids', [])
        if not staff_ids:
            messages.warning(request, "No staff members selected. Please select recipients first.")
            return redirect('sms:bulk_select')

        staff_members = CustomUser.objects.filter(id__in=staff_ids).select_related('department', 'role_obj')
        dlt_templates = DLTTemplate.objects.filter(is_active=True)
        db_fields = StaffFieldMapper.get_supported_fields()

        context = self.get_context_data()
        context['staff_members'] = staff_members
        context['selected_count'] = len(staff_members)
        context['dlt_templates'] = dlt_templates
        context['db_fields'] = db_fields
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        staff_ids = request.session.get('bulk_sms_staff_ids', [])
        if not staff_ids:
            messages.error(request, "Session expired or no recipients selected.")
            return redirect('sms:bulk_select')

        template_id = request.POST.get('template')
        if not template_id or not template_id.isdigit():
            messages.error(request, "Please select a valid DLT Template.")
            return redirect('sms:bulk_compose')

        template = get_object_or_404(DLTTemplate, pk=template_id, is_active=True)

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
        try:
            body = json.loads(request.body)
            staff_id = body.get('staff_id')
            template_id = body.get('template_id')
            mapping_config = body.get('mapping_config', {})
        except Exception:
            return JsonResponse({'success': False, 'error': 'Invalid JSON body'}, status=400)

        if not staff_id or not template_id:
            return JsonResponse({'success': False, 'error': 'Missing staff_id or template_id'}, status=400)

        staff = get_object_or_404(CustomUser, pk=staff_id)
        template = get_object_or_404(DLTTemplate, pk=template_id)

        # Resolve personalized variable values for this staff recipient
        personalized_vars = StaffFieldMapper.resolve_all_variables(staff, mapping_config)
        rendered_text = template.preview_message(personalized_vars)

        char_count = len(rendered_text)
        single_credits = DLTTemplate.calculate_sms_credits(rendered_text)

        return JsonResponse({
            'success': True,
            'staff_id': staff.id,
            'staff_name': staff.get_full_name() or staff.username,
            'employee_id': staff.employee_id or 'N/A',
            'rendered_text': rendered_text,
            'char_count': char_count,
            'single_credits': single_credits
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
        batch = get_object_or_404(SMSBatch.objects.select_related('user', 'template', 'department'), pk=batch_id)
        
        logs = SMSLog.objects.filter(batch=batch).order_by('-created_at')
        failed_logs = logs.filter(status=SMSStatusChoices.FAILED)
        
        total = batch.total_records
        success_pct = round((batch.successful_count / total * 100), 1) if total > 0 else 0.0
        total_credits = sum(log.credit_units for log in logs)
        
        exec_time = 0.0
        if batch.started_at and batch.completed_at:
            exec_time = round((batch.completed_at - batch.started_at).total_seconds(), 2)

        context['batch'] = batch
        context['logs'] = logs
        context['failed_logs'] = failed_logs
        context['success_percentage'] = success_pct
        context['total_credits'] = total_credits
        context['execution_time'] = exec_time
        return context


class BulkSMSProgressAjaxView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    AJAX Endpoint returning real-time progress JSON of an SMSBatch job.
    """
    allowed_roles = ALLOWED_SMS_ROLES

    def get(self, request, pk):
        batch = get_object_or_404(SMSBatch, pk=pk)
        return JsonResponse({
            'batch_id': batch.id,
            'status': batch.status,
            'total_records': batch.total_records,
            'processed_records': batch.processed_records,
            'successful_count': batch.successful_count,
            'failed_count': batch.failed_count,
            'progress_percentage': batch.progress_percentage
        })


class SMSQueueListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = SMSQueue
    template_name = 'sms/queue_list.html'
    context_object_name = 'queue_items'
    allowed_roles = ALLOWED_SMS_ROLES
    paginate_by = 15


class StaffSearchAjaxView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    AJAX endpoint for searching active staff personnel by Name, Employee ID, Username, Email,
    or Mobile Number. Returns formatted JSON for auto-complete dropdowns.
    """
    allowed_roles = ALLOWED_SMS_ROLES

    def get(self, request):
        query = request.GET.get('q', '').strip()
        qs = CustomUser.objects.filter(is_active=True).select_related('department', 'role_obj')

        if query:
            qs = qs.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(username__icontains=query) |
                Q(employee_id__icontains=query) |
                Q(email__icontains=query) |
                Q(phone_number__icontains=query)
            )

        qs = qs[:20]

        results = []
        for staff in qs:
            full_name = staff.get_full_name() or staff.username
            emp_id = staff.employee_id or 'N/A'
            dept_name = staff.department.name if staff.department else 'General'
            mobile = staff.phone_number or ''
            has_mobile = bool(mobile)

            display_label = f"{emp_id} • {full_name} • {dept_name} • {mobile or 'No Phone'}"

            results.append({
                'id': staff.id,
                'name': full_name,
                'username': staff.username,
                'employee_id': emp_id,
                'department': dept_name,
                'department_id': staff.department_id if staff.department else None,
                'role': staff.get_role_display(),
                'mobile': mobile,
                'email': staff.email or 'N/A',
                'has_mobile': has_mobile,
                'display_label': display_label
            })

        return JsonResponse({'results': results})
