from django.urls import path
from .views import SingleSMSView, BulkSMSView, SMSQueueListView

app_name = 'sms'

urlpatterns = [
    path('single/', SingleSMSView.as_view(), name='single'),
    path('bulk/', BulkSMSView.as_view(), name='bulk'),
    path('queue/', SMSQueueListView.as_view(), name='queue'),
]
