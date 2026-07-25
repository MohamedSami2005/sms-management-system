from django.urls import path
from .views import TemplateListView

app_name = 'dlt_templates'

urlpatterns = [
    path('', TemplateListView.as_view(), name='list'),
]
