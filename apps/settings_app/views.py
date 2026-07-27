from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from apps.common.mixins import RoleRequiredMixin
from .models import SMSGatewayConfig
from .forms import SMSGatewayConfigForm
from apps.sms.services.gateway_service import SMSGatewayService

ADMIN_ONLY = ['ADMIN']


class SettingsView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    """
    Main Settings Dashboard listing all SMS Gateway configurations.
    Enforces Administrator role access control (HTTP 403 for non-admins).
    """
    model = SMSGatewayConfig
    template_name = 'settings_app/settings.html'
    context_object_name = 'configs'
    allowed_roles = ADMIN_ONLY

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_config = SMSGatewayConfig.get_active_config()
        context['active_config'] = active_config
        
        if active_config:
            # Query active gateway balance
            service = SMSGatewayService(active_config)
            context['balance_result'] = service.get_balance()
        return context


class GatewayConfigCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    """Create new SMS Gateway configuration profile."""
    model = SMSGatewayConfig
    form_class = SMSGatewayConfigForm
    template_name = 'settings_app/settings_form.html'
    success_url = reverse_lazy('settings_app:index')
    allowed_roles = ADMIN_ONLY

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f"Gateway profile '{form.instance.provider_name}' created successfully.")
        return super().form_valid(form)


class GatewayConfigUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    """Update existing SMS Gateway configuration profile."""
    model = SMSGatewayConfig
    form_class = SMSGatewayConfigForm
    template_name = 'settings_app/settings_form.html'
    success_url = reverse_lazy('settings_app:index')
    allowed_roles = ADMIN_ONLY

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f"Gateway profile '{form.instance.provider_name}' updated successfully.")
        return super().form_valid(form)


class GatewayConfigActivateView(LoginRequiredMixin, RoleRequiredMixin, View):
    """Activate chosen gateway profile (deactivates all others)."""
    allowed_roles = ADMIN_ONLY

    def post(self, request, pk):
        config = get_object_or_404(SMSGatewayConfig, pk=pk)
        config.is_active = True
        config.save()
        messages.success(request, f"Activated '{config.provider_name}' as the active SMS Gateway profile.")
        return redirect('settings_app:index')


class GatewayConfigDeleteView(LoginRequiredMixin, RoleRequiredMixin, DeleteView):
    """Delete a gateway configuration profile."""
    model = SMSGatewayConfig
    success_url = reverse_lazy('settings_app:index')
    allowed_roles = ADMIN_ONLY

    def form_valid(self, form):
        messages.success(self.request, "Gateway configuration profile deleted successfully.")
        return super().form_valid(form)


class TestConnectionAjaxView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    AJAX endpoint testing SMS Gateway connectivity using saved active credentials.
    """
    allowed_roles = ADMIN_ONLY

    def post(self, request):
        config = SMSGatewayConfig.get_active_config()
        if not config:
            return JsonResponse({'success': False, 'error_message': 'No active Gateway configuration profile found.'})

        service = SMSGatewayService(config)
        result = service.test_connection()
        return JsonResponse(result)


class BalanceApiAjaxView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    AJAX endpoint fetching real-time credit balance from active gateway.
    """
    allowed_roles = ADMIN_ONLY

    def get(self, request):
        config = SMSGatewayConfig.get_active_config()
        if not config:
            return JsonResponse({'success': False, 'balance': 'N/A', 'error_message': 'No active Gateway configuration profile found.'})

        service = SMSGatewayService(config)
        res = service.get_balance()
        return JsonResponse({
            'success': res.success,
            'balance': res.balance,
            'gateway_name': res.gateway_name,
            'response_time_ms': res.response_time_ms,
            'error_message': res.error_message
        })
