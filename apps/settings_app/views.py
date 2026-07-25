from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from apps.common.mixins import RoleRequiredMixin
from apps.settings_app.models import SMSGatewayConfig
from apps.sms.services.gateway_service import SMSGatewayService


class SettingsView(LoginRequiredMixin, RoleRequiredMixin, TemplateView):
    template_name = 'settings_app/settings.html'
    allowed_roles = ['ADMIN']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = SMSGatewayConfig.get_active_config()
        context['gateway_config'] = config

        if config:
            # Query Gateway Balance
            gateway_service = SMSGatewayService(config)
            balance_res = gateway_service.get_balance()
            context['balance_result'] = balance_res
        return context


class TestConnectionAjaxView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    AJAX endpoint for testing API connectivity, response latency (ms), and gateway status.
    """
    allowed_roles = ['ADMIN']

    def post(self, request):
        gateway_service = SMSGatewayService()
        result = gateway_service.test_connection()
        return JsonResponse(result)


class BalanceApiAjaxView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    AJAX endpoint for fetching real-time credit balance from active gateway.
    """
    allowed_roles = ['ADMIN']

    def get(self, request):
        gateway_service = SMSGatewayService()
        result = gateway_service.get_balance()
        return JsonResponse({
            'success': result.success,
            'balance': result.balance,
            'gateway_name': result.gateway_name,
            'response_time_ms': result.response_time_ms,
            'error_message': result.error_message
        })
