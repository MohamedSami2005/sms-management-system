from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.common.mixins import RoleRequiredMixin


class SettingsView(LoginRequiredMixin, RoleRequiredMixin, TemplateView):
    template_name = 'settings_app/settings.html'
    allowed_roles = ['ADMIN']
