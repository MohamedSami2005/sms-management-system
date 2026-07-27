from django.urls import path
from .views import (
    SingleSMSView, BulkSMSStaffSelectionView, BulkSMSComposeView,
    PersonalizedPreviewAjaxView, BulkSMSSummaryView, BulkSMSProgressAjaxView,
    SMSQueueListView
)

app_name = 'sms'

urlpatterns = [
    path('single/', SingleSMSView.as_view(), name='single'),
    
    # Bulk Staff SMS Workflow
    path('bulk/select/', BulkSMSStaffSelectionView.as_view(), name='bulk_select'),
    path('bulk/compose/', BulkSMSComposeView.as_view(), name='bulk_compose'),
    path('bulk/preview-personalized-ajax/', PersonalizedPreviewAjaxView.as_view(), name='bulk_preview_personalized_ajax'),
    path('bulk/summary/<int:pk>/', BulkSMSSummaryView.as_view(), name='bulk_summary'),
    path('bulk/progress-ajax/<int:pk>/', BulkSMSProgressAjaxView.as_view(), name='bulk_progress_ajax'),
    
    path('queue/', SMSQueueListView.as_view(), name='queue'),
]
