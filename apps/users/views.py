from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.db.models import Q

from apps.common.mixins import RoleRequiredMixin
from apps.accounts.models import CustomUser, RoleChoices, ScopeChoices
from .models import Department
from .forms import DepartmentForm, UserCreateForm, UserUpdateForm, AdminResetPasswordForm
from .services import DepartmentService, UserService


# --- Department Views ---

class DepartmentListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = Department
    template_name = 'users/department_list.html'
    context_object_name = 'departments'
    allowed_roles = ['ADMIN']
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(code__icontains=query) | Q(description__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context


class DepartmentCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'users/department_form.html'
    success_url = reverse_lazy('users:department_list')
    allowed_roles = ['ADMIN']

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f"Department '{form.instance.name}' created successfully.")
        return super().form_valid(form)


class DepartmentUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'users/department_form.html'
    success_url = reverse_lazy('users:department_list')
    allowed_roles = ['ADMIN']

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f"Department '{form.instance.name}' updated successfully.")
        return super().form_valid(form)


class DepartmentToggleStatusView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = ['ADMIN']

    def post(self, request, pk):
        department = get_object_or_404(Department, pk=pk)
        new_status = DepartmentService.toggle_status(department)
        status_label = "activated" if new_status else "deactivated"
        messages.success(request, f"Department '{department.name}' has been {status_label}.")
        return redirect('users:department_list')


class DepartmentDeleteView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = ['ADMIN']

    def post(self, request, pk):
        department = get_object_or_404(Department, pk=pk)
        _, msg = DepartmentService.delete_or_deactivate(department)
        messages.info(request, msg)
        return redirect('users:department_list')


# --- Web-Based User Administration Views ---

class UserListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    """
    Administrator User Directory displaying personnel details, system roles, scope,
    last login, failed attempts, and administrative actions.
    """
    model = CustomUser
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    allowed_roles = ['ADMIN']
    paginate_by = 12

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_deleted=False).select_related('department', 'created_by', 'role_obj').order_by('-date_joined')
        query = self.request.GET.get('q')
        role_filter = self.request.GET.get('role')
        dept_filter = self.request.GET.get('department')
        scope_filter = self.request.GET.get('scope')
        status_filter = self.request.GET.get('status')

        if query:
            queryset = queryset.filter(
                Q(username__icontains=query) | Q(first_name__icontains=query) |
                Q(last_name__icontains=query) | Q(email__icontains=query) |
                Q(employee_id__icontains=query) | Q(phone_number__icontains=query)
            )
        if role_filter:
            queryset = queryset.filter(role=role_filter)
        if dept_filter:
            queryset = queryset.filter(department_id=dept_filter)
        if scope_filter:
            queryset = queryset.filter(scope_type=scope_filter)
        if status_filter:
            if status_filter == 'active':
                queryset = queryset.filter(is_active=True, is_locked=False)
            elif status_filter == 'inactive':
                queryset = queryset.filter(is_active=False)
            elif status_filter == 'locked':
                queryset = queryset.filter(is_locked=True)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_role'] = self.request.GET.get('role', '')
        context['selected_dept'] = self.request.GET.get('department', '')
        context['selected_scope'] = self.request.GET.get('scope', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['roles'] = RoleChoices.choices
        context['scopes'] = ScopeChoices.choices
        context['departments'] = Department.objects.filter(is_active=True)
        return context


class UserCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    """
    Web-based User Creation form for Administrators.
    """
    model = CustomUser
    form_class = UserCreateForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('users:user_list')
    allowed_roles = ['ADMIN']

    def form_valid(self, form):
        user = UserService.create_user(form, created_by=self.request.user)
        messages.success(self.request, f"User account for '{user.get_full_name() or user.username}' ({user.get_role_display()}) created successfully.")
        return redirect(self.success_url)


class UserUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    """
    Web-based User Profile & Role Update form for Administrators.
    """
    model = CustomUser
    form_class = UserUpdateForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('users:user_list')
    allowed_roles = ['ADMIN']

    def form_valid(self, form):
        user = UserService.update_user(self.object, form, updated_by=self.request.user)
        messages.success(self.request, f"User account '{user.username}' updated successfully.")
        return redirect(self.success_url)


class UserToggleStatusView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    Activates or Deactivates a user account.
    """
    allowed_roles = ['ADMIN']

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk, is_deleted=False)
        if user == request.user:
            messages.error(request, "You cannot deactivate your own Administrator account.")
            return redirect('users:user_list')

        new_status = UserService.toggle_user_status(user, toggled_by=request.user)
        status_str = "activated" if new_status else "deactivated"
        messages.success(request, f"User account '{user.username}' has been {status_str}.")
        return redirect('users:user_list')


class UserToggleLockView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    Locks or Unlocks a user account.
    """
    allowed_roles = ['ADMIN']

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk, is_deleted=False)
        if user == request.user:
            messages.error(request, "You cannot lock your own Administrator account.")
            return redirect('users:user_list')

        is_locked = UserService.toggle_user_lock(user, locked_by=request.user)
        lock_str = "locked" if is_locked else "unlocked"
        messages.success(request, f"User account '{user.username}' has been {lock_str}.")
        return redirect('users:user_list')


class UserDeleteView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    Soft-deletes a user account.
    """
    allowed_roles = ['ADMIN']

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk, is_deleted=False)
        if user == request.user:
            messages.error(request, "You cannot delete your own Administrator account.")
            return redirect('users:user_list')

        username = user.username
        UserService.soft_delete_user(user, deleted_by=request.user)
        messages.info(request, f"User account '{username}' has been soft deleted.")
        return redirect('users:user_list')


class UserAdminResetPasswordView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    Web-based Password Reset endpoint allowing Administrators to set a user's password directly.
    """
    allowed_roles = ['ADMIN']

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk, is_deleted=False)
        form = AdminResetPasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data.get('new_password')
            must_change = form.cleaned_data.get('must_change_password', True)
            UserService.reset_password(user, new_password, reset_by=request.user, must_change_password=must_change)
            messages.success(request, f"Password for '{user.username}' reset successfully.")
        else:
            messages.error(request, "Password reset failed. Please ensure both passwords match.")
        return redirect('users:user_list')
