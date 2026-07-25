from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import DLTTemplate


class TemplateListView(LoginRequiredMixin, ListView):
    model = DLTTemplate
    template_name = 'dlt_templates/template_list.html'
    context_object_name = 'templates'
    paginate_by = 10
