from django.urls import path
from .views import SMSLogListView

app_name = 'logs'

urlpatterns = [
    path('', SMSLogListView.as_view(), name='list'),
    path('sms-logs/', SMSLogListView.as_view(), name='sms_logs'),
]
