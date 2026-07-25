from django.urls import path
from .views import UserListView, DepartmentListView

app_name = 'users'

urlpatterns = [
    path('', UserListView.as_view(), name='user_list'),
    path('departments/', DepartmentListView.as_view(), name='department_list'),
]
