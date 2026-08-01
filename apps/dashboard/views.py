from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from .services import DashboardService


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        metrics = DashboardService.get_summary_metrics(user=self.request.user)
        context.update(metrics)
        return context
