from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import SMSLog


class SMSLogListView(LoginRequiredMixin, ListView):
    model = SMSLog
    template_name = 'logs/log_list.html'
    context_object_name = 'logs'
    paginate_by = 20
