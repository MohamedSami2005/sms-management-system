from django.urls import path
from .views import SMSLogListView, SMSLogExportView, SMSLogExportPreviewView

app_name = 'logs'

urlpatterns = [
    path('', SMSLogListView.as_view(), name='list'),
    path('sms-logs/', SMSLogListView.as_view(), name='sms_logs'),
    path('sms/export/', SMSLogExportView.as_view(), name='export'),
    path('sms/preview-export-ajax/', SMSLogExportPreviewView.as_view(), name='preview_export_ajax'),
]
