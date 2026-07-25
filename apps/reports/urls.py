from django.urls import path
from .views import ReportOverviewView

app_name = 'reports'

urlpatterns = [
    path('', ReportOverviewView.as_view(), name='overview'),
]
