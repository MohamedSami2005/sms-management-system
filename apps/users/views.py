from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.common.mixins import RoleRequiredMixin
from apps.accounts.models import CustomUser
from .models import Department


class UserListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = CustomUser
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    allowed_roles = ['ADMIN']
    paginate_by = 10


class DepartmentListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = Department
    template_name = 'users/department_list.html'
    context_object_name = 'departments'
    allowed_roles = ['ADMIN']
