import json
import logging
from typing import Dict, Any

from django.views.generic import FormView, ListView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
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
        from apps.common.scopes import get_scoped_queryset
        from apps.users.models import Office
        scoped_templates = get_scoped_queryset(self.request.user, DLTTemplate.objects.filter(is_active=True)).select_related('office')
        context['db_fields'] = json.dumps(StaffFieldMapper.get_supported_fields())
        context['dlt_templates'] = scoped_templates
        context['offices'] = Office.objects.filter(is_active=True).order_by('name')
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


def _get_bulk_sms_context(request):
    """Prepares template metadata, office filters, and session Excel data for Bulk SMS workflow."""
    import json
    from apps.common.scopes import get_scoped_queryset
    from apps.users.models import Office

    dlt_templates = get_scoped_queryset(
        request.user,
        DLTTemplate.objects.filter(is_active=True)
    ).select_related('office').prefetch_related('variables')

    offices = Office.objects.filter(is_active=True).order_by('name')

    templates_list = []
    for t in dlt_templates:
        vars_list = []
        for v in t.variables.all().order_by('position'):
            vars_list.append({
                'position': v.position,
                'name': v.name or f"Variable {v.position}",
                'sample_value': v.sample_value or f"Sample {v.position}"
            })
        if not vars_list:
            placeholders = t.extract_variable_placeholders()
            for idx, p in enumerate(placeholders, start=1):
                vars_list.append({
                    'position': idx,
                    'name': f"Variable {idx}",
                    'sample_value': f"Sample {idx}"
                })

        templates_list.append({
            'id': t.id,
            'name': t.name,
            'dlt_template_id': t.dlt_template_id,
            'header_sender_id': t.header_sender_id,
            'category_display': t.get_category_display() if hasattr(t, 'get_category_display') else t.category,
            'template_content': t.template_content,
            'office_id': t.office_id,
            'office_name': t.office.name if t.office else 'All Offices',
            'variable_count': t.variable_count,
            'variables': vars_list
        })

    preview_data = request.session.get('bulk_excel_data')
    preview_data_json = json.dumps(preview_data) if preview_data else "null"

    return {
        'dlt_templates': dlt_templates,
        'offices': offices,
        'templates_json': json.dumps(templates_list),
        'preview_data': preview_data,
        'preview_data_json': preview_data_json,
        'bulk_sms_source': request.session.get('bulk_sms_source', 'excel')
    }


class BulkSMSStaffSelectionView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    Primary Personalized Bulk SMS Workflow View.
    Serves 5-Step progressive interface driven primarily by dynamic Excel/CSV recipient import.
    """
    template_name = 'sms/bulk_staff_select.html'
    allowed_roles = ALLOWED_SMS_ROLES

    def get(self, request, *args, **kwargs):
        context = _get_bulk_sms_context(request)
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        from .services.excel_import import BulkExcelImportService
        from apps.common.scopes import get_scoped_queryset

        # File Upload Action
        if 'excel_file' in request.FILES:
            excel_file = request.FILES['excel_file']
            parsed_data, errors = BulkExcelImportService.parse_excel(excel_file)
            if errors:
                for err in errors:
                    messages.error(request, err)
            else:
                request.session['bulk_sms_source'] = 'excel'
                request.session['bulk_excel_data'] = parsed_data
                if 'bulk_sms_staff_ids' in request.session:
                    del request.session['bulk_sms_staff_ids']
                messages.success(
                    request,
                    f"File parsed successfully! Found {parsed_data['valid_count']} valid recipient(s) across {len(parsed_data['all_headers'])} columns."
                )
            context = _get_bulk_sms_context(request)
            return render(request, self.template_name, context)

        # Dispatch Submission Action
        template_id = request.POST.get('template')
        if not template_id or not template_id.isdigit():
            messages.error(request, "Please select a valid DLT Template.")
            context = _get_bulk_sms_context(request)
            return render(request, self.template_name, context)

        excel_data = request.session.get('bulk_excel_data', {})
        excel_rows = excel_data.get('rows', [])
        if not excel_rows:
            messages.error(request, "Please upload an Excel/CSV file with valid recipients before sending Bulk SMS.")
            context = _get_bulk_sms_context(request)
            return render(request, self.template_name, context)

        template = get_object_or_404(
            get_scoped_queryset(request.user, DLTTemplate.objects.filter(is_active=True)),
            pk=template_id
        )

        mapping_config = {}
        for idx in range(1, template.variable_count + 1):
            key = f"var_{idx}"
            stype = request.POST.get(f"{key}_source_type", "field")
            sval = request.POST.get(f"{key}_field_val") or request.POST.get(f"{key}_static_val", "")
            mapping_config[key] = {"type": stype, "value": sval}

        batch, summary = BulkSMSService.execute_bulk_dispatch(
            user=request.user,
            staff_user_ids=[],
            template=template,
            mapping_config=mapping_config,
            department=request.user.department,
            excel_rows=excel_rows
        )

        request.session['last_bulk_batch_id'] = batch.id
        request.session['last_bulk_summary'] = summary
        if 'bulk_excel_data' in request.session:
            del request.session['bulk_excel_data']

        messages.success(request, f"Bulk SMS dispatch complete. Sent: {batch.successful_count}/{batch.total_records}")
        return redirect('sms:bulk_summary', pk=batch.id)


class BulkSMSExcelImportView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    Excel Upload view for Bulk SMS.
    Parses dynamic Excel headers, validates mobile numbers, shows preview/validation errors,
    and sets session temporary data for compose workflow without creating Contact records.
    """
    template_name = 'sms/bulk_excel_import.html'
    allowed_roles = ALLOWED_SMS_ROLES

    def get(self, request):
        return render(request, self.template_name, {
            'preview_data': request.session.get('bulk_excel_data')
        })

    def post(self, request):
        from .services.excel_import import BulkExcelImportService
        if 'excel_file' not in request.FILES:
            messages.error(request, "Please select an Excel or CSV file (.xlsx, .xls, .csv) to upload.")
            return render(request, self.template_name)

        excel_file = request.FILES['excel_file']
        parsed_data, errors = BulkExcelImportService.parse_excel(excel_file)

        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, self.template_name)

        # Save temporary data to session
        request.session['bulk_sms_source'] = 'excel'
        request.session['bulk_excel_data'] = parsed_data
        if 'bulk_sms_staff_ids' in request.session:
            del request.session['bulk_sms_staff_ids']

        messages.success(
            request,
            f"Spreadsheet parsed successfully! Found {parsed_data['valid_count']} valid recipient(s) across {len(parsed_data['all_headers'])} columns."
        )

        return render(request, self.template_name, {
            'preview_data': parsed_data
        })


class BulkSMSExcelSampleView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    Downloads sample Excel template for Bulk SMS Excel import.
    """
    allowed_roles = ALLOWED_SMS_ROLES

    def get(self, request):
        from .services.excel_import import BulkExcelImportService
        return BulkExcelImportService.generate_sample_excel()


class BulkSMSComposeView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    Redirects legacy compose endpoint to the primary 5-Step Bulk SMS Workflow.
    """
    allowed_roles = ALLOWED_SMS_ROLES

    def get(self, request, *args, **kwargs):
        return redirect('sms:bulk_select')

    def post(self, request, *args, **kwargs):
        return redirect('sms:bulk_select')


class PersonalizedPreviewAjaxView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    AJAX endpoint for dynamically generating personalized SMS text for a specific staff member or Excel row
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

        source = request.session.get('bulk_sms_source', 'database')
        target_recipient = None
        staff_name = ""

        if source == 'excel':
            excel_data = request.session.get('bulk_excel_data', {})
            rows = excel_data.get('rows', [])
            if staff_id and str(staff_id).isdigit():
                idx = int(staff_id) - 1
                if 0 <= idx < len(rows):
                    target_recipient = rows[idx]
            if not target_recipient and mobile_number:
                for r in rows:
                    if r.get('__normalized_mobile') == mobile_number:
                        target_recipient = r
                        break
            if not target_recipient and rows:
                target_recipient = rows[0]

            if target_recipient:
                staff_name = target_recipient.get('__normalized_name', 'Excel Recipient')
        else:
            if staff_id:
                target_recipient = Staff.objects.filter(pk=staff_id).first() or CustomUser.objects.filter(pk=staff_id).first()
            elif mobile_number:
                target_recipient = Staff.objects.filter(mobile_number=mobile_number).first()

            if target_recipient:
                staff_name = target_recipient.name if isinstance(target_recipient, Staff) else (target_recipient.get_full_name() or target_recipient.username)

        template = get_object_or_404(get_scoped_queryset(request.user, DLTTemplate.objects.all()), pk=template_id)

        personalized_vars = StaffFieldMapper.resolve_all_variables(target_recipient, mapping_config)
        rendered_text = template.preview_message(personalized_vars)

        char_count = len(rendered_text)
        single_credits = DLTTemplate.calculate_sms_credits(rendered_text)

        return JsonResponse({
            'success': True,
            'staff_id': staff_id,
            'staff_name': staff_name,
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
        from django.db.models import Sum
        context = super().get_context_data(**kwargs)
        batch_id = self.kwargs.get('pk')
        batch = get_object_or_404(SMSBatch, pk=batch_id)
        summary = self.request.session.get('last_bulk_summary', {})

        logs = SMSLog.objects.filter(batch=batch).select_related('department')
        failed_logs = logs.filter(status=SMSStatusChoices.FAILED)

        total_credits = summary.get('total_credits_used')
        if total_credits is None:
            total_credits = logs.aggregate(total=Sum('credit_units'))['total'] or 0

        execution_time = summary.get('execution_time_seconds')
        if execution_time is None:
            if batch.started_at and batch.completed_at:
                execution_time = round((batch.completed_at - batch.started_at).total_seconds(), 1)
            else:
                execution_time = 0.0
        else:
            execution_time = round(float(execution_time), 1)

        if summary.get('success_percentage') is not None:
            success_percentage = summary.get('success_percentage')
        else:
            success_percentage = round((batch.successful_count / batch.total_records * 100), 1) if batch.total_records > 0 else 0.0

        context['batch'] = batch
        context['summary'] = summary
        context['logs'] = logs
        context['failed_logs'] = failed_logs
        context['total_credits'] = total_credits
        context['execution_time'] = execution_time
        context['success_percentage'] = success_percentage
        return context


class BulkSMSStartAjaxView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    AJAX endpoint to initialize an SMSBatch record before starting dispatch.
    Returns batch_id so client can poll real-time progress.
    """
    allowed_roles = ALLOWED_SMS_ROLES

    def post(self, request):
        from apps.common.scopes import get_scoped_queryset
        from django.utils import timezone

        template_id = request.POST.get('template')
        if not template_id or not template_id.isdigit():
            return JsonResponse({'success': False, 'error': "Please select a valid DLT Template."}, status=400)

        template = get_object_or_404(
            get_scoped_queryset(request.user, DLTTemplate.objects.filter(is_active=True)),
            pk=template_id
        )

        source = request.session.get('bulk_sms_source', 'database')
        if source == 'excel':
            excel_data = request.session.get('bulk_excel_data', {})
            excel_rows = excel_data.get('rows', [])
            if not excel_rows:
                return JsonResponse({'success': False, 'error': "Session expired or no Excel recipients found."}, status=400)
            total_count = len(excel_rows)
            file_label = f"Bulk Excel - {template.name}"
        else:
            staff_ids = request.session.get('bulk_sms_staff_ids', [])
            if not staff_ids:
                return JsonResponse({'success': False, 'error': "Session expired or no recipients selected."}, status=400)

            staff_members = list(Staff.objects.filter(id__in=staff_ids).select_related('department'))
            if not staff_members:
                staff_members = list(CustomUser.objects.filter(id__in=staff_ids).select_related('department'))
            total_count = len(staff_members)
            file_label = f"Personalized Bulk SMS - {template.name}"

        dept = request.user.department
        batch = SMSBatch.objects.create(
            user=request.user,
            department=dept,
            template=template,
            file_name=f"{file_label} ({total_count} Recipients)",
            total_records=total_count,
            processed_records=0,
            successful_count=0,
            failed_count=0,
            status=SMSStatusChoices.PROCESSING,
            started_at=timezone.now()
        )

        return JsonResponse({'success': True, 'batch_id': batch.id, 'total_records': total_count})


class BulkSMSExecuteAjaxView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    AJAX endpoint to execute personalized bulk SMS dispatch for an initialized SMSBatch.
    """
    allowed_roles = ALLOWED_SMS_ROLES

    def post(self, request, pk):
        batch = get_object_or_404(SMSBatch, pk=pk)
        source = request.session.get('bulk_sms_source', 'database')
        excel_rows = None
        staff_ids = []

        if source == 'excel':
            excel_data = request.session.get('bulk_excel_data', {})
            excel_rows = excel_data.get('rows', [])
        else:
            staff_ids = request.session.get('bulk_sms_staff_ids', [])
            if not staff_ids:
                staff_ids = list(Staff.objects.filter(is_active=True).values_list('id', flat=True))

        template = batch.template

        mapping_config = {}
        for idx in range(1, template.variable_count + 1):
            key = f"var_{idx}"
            stype = request.POST.get(f"{key}_source_type", "static")
            if stype == "field":
                sval = request.POST.get(f"{key}_field_val", "")
            else:
                sval = request.POST.get(f"{key}_static_val", "")
            mapping_config[key] = {"type": stype, "value": sval}

        batch, summary = BulkSMSService.execute_bulk_dispatch(
            user=request.user,
            staff_user_ids=staff_ids,
            template=template,
            mapping_config=mapping_config,
            department=request.user.department,
            existing_batch=batch,
            excel_rows=excel_rows
        )

        request.session['last_bulk_batch_id'] = batch.id
        request.session['last_bulk_summary'] = summary

        if 'bulk_sms_staff_ids' in request.session:
            del request.session['bulk_sms_staff_ids']
        if 'bulk_excel_data' in request.session:
            del request.session['bulk_excel_data']

        return JsonResponse({
            'success': True,
            'batch_id': batch.id,
            'redirect_url': f"/sms/bulk/summary/{batch.id}/",
            'summary': summary
        })


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
