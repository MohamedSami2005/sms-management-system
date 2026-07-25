import json
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.db.models import Q

from apps.common.mixins import RoleRequiredMixin
from apps.users.models import Department
from .models import DLTTemplate, TemplateVariable, TemplateCategoryChoices
from .forms import DLTTemplateForm, TemplateVariableFormSet, TemplateImportForm
from .services import TemplateService, TemplateImportService, TemplateExportService


ALLOWED_TEMPLATE_ROLES = ['ADMIN', 'COE', 'ADMISSION', 'ACCOUNTS', 'PLACEMENT']


class TemplateListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = DLTTemplate
    template_name = 'dlt_templates/template_list.html'
    context_object_name = 'templates'
    allowed_roles = ALLOWED_TEMPLATE_ROLES
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('department')
        query = self.request.GET.get('q')
        cat_filter = self.request.GET.get('category')
        dept_filter = self.request.GET.get('department')
        status_filter = self.request.GET.get('status')
        header_filter = self.request.GET.get('header')

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(dlt_template_id__icontains=query) |
                Q(header_sender_id__icontains=query) | Q(template_content__icontains=query)
            )
        if cat_filter:
            queryset = queryset.filter(category=cat_filter)
        if dept_filter:
            queryset = queryset.filter(department_id=dept_filter)
        if status_filter:
            if status_filter == 'active':
                queryset = queryset.filter(is_active=True)
            elif status_filter == 'inactive':
                queryset = queryset.filter(is_active=False)
        if header_filter:
            queryset = queryset.filter(header_sender_id__iexact=header_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_cat'] = self.request.GET.get('category', '')
        context['selected_dept'] = self.request.GET.get('department', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_header'] = self.request.GET.get('header', '')
        
        context['categories'] = TemplateCategoryChoices.choices
        context['departments'] = Department.objects.filter(is_active=True)
        context['sender_headers'] = DLTTemplate.objects.values_list('header_sender_id', flat=True).distinct()
        return context


class TemplateDetailView(LoginRequiredMixin, RoleRequiredMixin, DetailView):
    model = DLTTemplate
    template_name = 'dlt_templates/template_detail.html'
    context_object_name = 'template'
    allowed_roles = ALLOWED_TEMPLATE_ROLES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template = self.object
        default_preview = template.preview_message()
        context['preview_text'] = default_preview
        context['char_count'] = len(default_preview)
        context['sms_credits'] = DLTTemplate.calculate_sms_credits(default_preview)
        context['variables'] = template.variables.order_by('position')
        return context


class TemplateCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    model = DLTTemplate
    form_class = DLTTemplateForm
    template_name = 'dlt_templates/template_form.html'
    success_url = reverse_lazy('dlt_templates:list')
    allowed_roles = ALLOWED_TEMPLATE_ROLES

    def form_valid(self, form):
        template = TemplateService.save_template(form, user=self.request.user)
        messages.success(self.request, f"DLT Template '{template.name}' created and variables extracted successfully.")
        return redirect('dlt_templates:detail', pk=template.pk)


class TemplateUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    model = DLTTemplate
    form_class = DLTTemplateForm
    template_name = 'dlt_templates/template_form.html'
    allowed_roles = ALLOWED_TEMPLATE_ROLES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['variable_formset'] = TemplateVariableFormSet(self.request.POST, instance=self.object)
        else:
            self.object.sync_variables()
            context['variable_formset'] = TemplateVariableFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['variable_formset']

        if formset.is_valid():
            template = TemplateService.save_template(form, user=self.request.user)
            formset.save()
            messages.success(self.request, f"DLT Template '{template.name}' updated successfully.")
            return redirect('dlt_templates:detail', pk=template.pk)
        else:
            return self.render_to_response(self.get_context_data(form=form))


class TemplateToggleStatusView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = ALLOWED_TEMPLATE_ROLES

    def post(self, request, pk):
        template = get_object_or_404(DLTTemplate, pk=pk)
        new_status = TemplateService.toggle_status(template)
        status_str = "activated" if new_status else "deactivated"
        messages.success(request, f"DLT Template '{template.name}' has been {status_str}.")
        return redirect('dlt_templates:list')


class TemplateDeleteView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = ALLOWED_TEMPLATE_ROLES

    def post(self, request, pk):
        template = get_object_or_404(DLTTemplate, pk=pk)
        _, msg = TemplateService.delete_or_deactivate(template)
        messages.info(request, msg)
        return redirect('dlt_templates:list')


class TemplateImportView(LoginRequiredMixin, RoleRequiredMixin, FormView):
    form_class = TemplateImportForm
    template_name = 'dlt_templates/template_import.html'
    success_url = reverse_lazy('dlt_templates:list')
    allowed_roles = ALLOWED_TEMPLATE_ROLES

    def form_valid(self, form):
        file = form.cleaned_data['file']
        imported_count, skipped_count, errors = TemplateImportService.import_from_file(file, user=self.request.user)

        if imported_count > 0:
            messages.success(self.request, f"Successfully imported {imported_count} DLT templates.")
        if skipped_count > 0:
            messages.warning(self.request, f"Skipped {skipped_count} row(s) during import due to duplicate IDs or errors.")

        self.request.session['import_errors'] = errors
        return redirect('dlt_templates:list')


class TemplateExportView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = ALLOWED_TEMPLATE_ROLES

    def get(self, request):
        export_format = request.GET.get('format', 'excel')
        queryset = DLTTemplate.objects.all().select_related('department')

        if export_format == 'csv':
            return TemplateExportService.export_csv(queryset)
        else:
            return TemplateExportService.export_excel(queryset)


class TemplatePreviewAjaxView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    JSON API view returning dynamic interpolated message preview, character count, and estimated SMS credits.
    """
    allowed_roles = ALLOWED_TEMPLATE_ROLES

    def post(self, request, pk):
        template = get_object_or_404(DLTTemplate, pk=pk)
        try:
            body = json.loads(request.body)
            sample_values = body.get('sample_values', {})
        except Exception:
            sample_values = {}

        preview_text = template.preview_message(sample_values)
        char_count = len(preview_text)
        sms_credits = DLTTemplate.calculate_sms_credits(preview_text)

        return JsonResponse({
            'preview_text': preview_text,
            'char_count': char_count,
            'sms_credits': sms_credits,
            'is_unicode': any(ord(c) > 127 for c in preview_text)
        })
