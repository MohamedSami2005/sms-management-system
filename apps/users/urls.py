from django.urls import path
from .views import (
    UserListView, UserCreateView, UserUpdateView, UserToggleStatusView, UserAdminResetPasswordView,
    DepartmentListView, DepartmentCreateView, DepartmentUpdateView,
    DepartmentToggleStatusView, DepartmentDeleteView
)

app_name = 'users'

urlpatterns = [
    # User Management Endpoints
    path('', UserListView.as_view(), name='user_list'),
    path('create/', UserCreateView.as_view(), name='user_create'),
    path('<int:pk>/edit/', UserUpdateView.as_view(), name='user_edit'),
    path('<int:pk>/toggle-status/', UserToggleStatusView.as_view(), name='user_toggle_status'),
    path('<int:pk>/reset-password/', UserAdminResetPasswordView.as_view(), name='user_reset_password'),

    # Department Management Endpoints
    path('departments/', DepartmentListView.as_view(), name='department_list'),
    path('departments/create/', DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/edit/', DepartmentUpdateView.as_view(), name='department_edit'),
    path('departments/<int:pk>/toggle-status/', DepartmentToggleStatusView.as_view(), name='department_toggle_status'),
    path('departments/<int:pk>/delete/', DepartmentDeleteView.as_view(), name='department_delete'),
]
