from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import SMSQueue, SMSBatch


class SingleSMSView(LoginRequiredMixin, TemplateView):
    template_name = 'sms/single_sms.html'


class BulkSMSView(LoginRequiredMixin, TemplateView):
    template_name = 'sms/bulk_sms.html'


class SMSQueueListView(LoginRequiredMixin, ListView):
    model = SMSQueue
    template_name = 'sms/queue_list.html'
    context_object_name = 'queue_items'
    paginate_by = 15
