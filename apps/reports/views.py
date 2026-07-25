from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin


class ReportOverviewView(LoginRequiredMixin, TemplateView):
    template_name = 'reports/overview.html'
