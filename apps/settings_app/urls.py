from django.urls import path
from .views import (
    SettingsView, GatewayConfigCreateView, GatewayConfigUpdateView,
    GatewayConfigActivateView, GatewayConfigDeleteView,
    TestConnectionAjaxView, BalanceApiAjaxView
)

app_name = 'settings_app'

urlpatterns = [
    path('', SettingsView.as_view(), name='index'),
    path('create/', GatewayConfigCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', GatewayConfigUpdateView.as_view(), name='edit'),
    path('<int:pk>/activate/', GatewayConfigActivateView.as_view(), name='activate'),
    path('<int:pk>/delete/', GatewayConfigDeleteView.as_view(), name='delete'),
    
    # AJAX Diagnostics
    path('test-connection/', TestConnectionAjaxView.as_view(), name='test_connection'),
    path('balance/', BalanceApiAjaxView.as_view(), name='balance'),
]
