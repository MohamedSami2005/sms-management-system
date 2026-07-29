from django.urls import path
from .views import (
    StaffListView, StaffCreateView, StaffUpdateView, StaffDeleteView,
    DepartmentListView, DepartmentCreateView, DepartmentUpdateView,
    DepartmentToggleStatusView, DepartmentDeleteView,
    SystemUserListView, SystemUserCreateView, SystemUserUpdateView,
    SystemUserToggleStatusView, SystemUserToggleLockView, SystemUserDeleteView,
    SystemUserResetPasswordView
)

app_name = 'users'

urlpatterns = [
    # Staff Directory (SMS Recipient Master) Endpoints
    path('', StaffListView.as_view(), name='staff_list'),
    path('staff/', StaffListView.as_view(), name='staff_list'),
    path('staff/create/', StaffCreateView.as_view(), name='staff_create'),
    path('staff/<int:pk>/edit/', StaffUpdateView.as_view(), name='staff_edit'),
    path('staff/<int:pk>/delete/', StaffDeleteView.as_view(), name='staff_delete'),

    # Department Management Endpoints
    path('departments/', DepartmentListView.as_view(), name='department_list'),
    path('departments/create/', DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/edit/', DepartmentUpdateView.as_view(), name='department_edit'),
    path('departments/<int:pk>/toggle-status/', DepartmentToggleStatusView.as_view(), name='department_toggle_status'),
    path('departments/<int:pk>/delete/', DepartmentDeleteView.as_view(), name='department_delete'),

    # System Users (Application Authentication Accounts) Endpoints
    path('system-users/', SystemUserListView.as_view(), name='system_user_list'),
    path('system-users/create/', SystemUserCreateView.as_view(), name='system_user_create'),
    path('system-users/<int:pk>/edit/', SystemUserUpdateView.as_view(), name='system_user_edit'),
    path('system-users/<int:pk>/toggle-status/', SystemUserToggleStatusView.as_view(), name='system_user_toggle_status'),
    path('system-users/<int:pk>/toggle-lock/', SystemUserToggleLockView.as_view(), name='system_user_toggle_lock'),
    path('system-users/<int:pk>/reset-password/', SystemUserResetPasswordView.as_view(), name='system_user_reset_password'),
    path('system-users/<int:pk>/delete/', SystemUserDeleteView.as_view(), name='system_user_delete'),
]
