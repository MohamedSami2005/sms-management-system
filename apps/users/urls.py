from django.urls import path
from .views import (
    StaffListView, StaffCreateView, StaffUpdateView, StaffDeleteView,
    OfficeListView, OfficeCreateView, OfficeUpdateView, OfficeToggleStatusView, OfficeDeleteView,
    SystemUserListView, SystemUserCreateView, SystemUserUpdateView,
    SystemUserToggleStatusView, SystemUserToggleLockView, SystemUserDeleteView,
    SystemUserResetPasswordView
)

app_name = 'users'

urlpatterns = [
    # Contacts Master Endpoints
    path('', StaffListView.as_view(), name='staff_list'),
    path('staff/', StaffListView.as_view(), name='staff_list'),
    path('staff/create/', StaffCreateView.as_view(), name='staff_create'),
    path('staff/<int:pk>/edit/', StaffUpdateView.as_view(), name='staff_edit'),
    path('staff/<int:pk>/delete/', StaffDeleteView.as_view(), name='staff_delete'),

    # Office Management (Administrative Access Scope) Endpoints
    path('offices/', OfficeListView.as_view(), name='office_list'),
    path('offices/create/', OfficeCreateView.as_view(), name='office_create'),
    path('offices/<int:pk>/edit/', OfficeUpdateView.as_view(), name='office_edit'),
    path('offices/<int:pk>/toggle-status/', OfficeToggleStatusView.as_view(), name='office_toggle_status'),
    path('offices/<int:pk>/delete/', OfficeDeleteView.as_view(), name='office_delete'),

    # System Users (Application Authentication Accounts) Endpoints
    path('system-users/', SystemUserListView.as_view(), name='system_user_list'),
    path('system-users/create/', SystemUserCreateView.as_view(), name='system_user_create'),
    path('system-users/<int:pk>/edit/', SystemUserUpdateView.as_view(), name='system_user_edit'),
    path('system-users/<int:pk>/toggle-status/', SystemUserToggleStatusView.as_view(), name='system_user_toggle_status'),
    path('system-users/<int:pk>/toggle-lock/', SystemUserToggleLockView.as_view(), name='system_user_toggle_lock'),
    path('system-users/<int:pk>/reset-password/', SystemUserResetPasswordView.as_view(), name='system_user_reset_password'),
    path('system-users/<int:pk>/delete/', SystemUserDeleteView.as_view(), name='system_user_delete'),
]
