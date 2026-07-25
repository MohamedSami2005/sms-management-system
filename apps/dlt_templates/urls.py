from django.urls import path
from .views import (
    TemplateListView, TemplateDetailView, TemplateCreateView, TemplateUpdateView,
    TemplateToggleStatusView, TemplateDeleteView, TemplateImportView,
    TemplateExportView, TemplatePreviewAjaxView
)

app_name = 'dlt_templates'

urlpatterns = [
    path('', TemplateListView.as_view(), name='list'),
    path('<int:pk>/', TemplateDetailView.as_view(), name='detail'),
    path('create/', TemplateCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', TemplateUpdateView.as_view(), name='edit'),
    path('<int:pk>/toggle-status/', TemplateToggleStatusView.as_view(), name='toggle_status'),
    path('<int:pk>/delete/', TemplateDeleteView.as_view(), name='delete'),
    
    # Import & Export
    path('import/', TemplateImportView.as_view(), name='import'),
    path('export/', TemplateExportView.as_view(), name='export'),
    
    # AJAX Live Preview API
    path('<int:pk>/preview-ajax/', TemplatePreviewAjaxView.as_view(), name='preview_ajax'),
]
