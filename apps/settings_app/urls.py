from django.urls import path
from .views import SettingsView, TestConnectionAjaxView, BalanceApiAjaxView

app_name = 'settings_app'

urlpatterns = [
    path('', SettingsView.as_view(), name='index'),
    path('test-connection/', TestConnectionAjaxView.as_view(), name='test_connection'),
    path('balance/', BalanceApiAjaxView.as_view(), name='balance'),
]
