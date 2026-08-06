from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

from apps.users.views import ContactImportView

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    return redirect('accounts:login')

urlpatterns = [
    path('', root_redirect, name='root'),
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('users/', include('apps.users.urls', namespace='users')),
    path('contacts/import/', ContactImportView.as_view(), name='contact_import'),
    path('templates/', include('apps.dlt_templates.urls', namespace='dlt_templates')),
    path('sms/', include('apps.sms.urls', namespace='sms')),
    path('logs/', include('apps.logs.urls', namespace='logs')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
    path('settings/', include('apps.settings_app.urls', namespace='settings_app')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
