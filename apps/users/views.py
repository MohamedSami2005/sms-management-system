from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.db.models import Q

from apps.common.mixins import RoleRequiredMixin
from apps.accounts.models import CustomUser, Role, RoleChoices, ScopeChoices
from .models import Department, Staff
from .forms import DepartmentForm, StaffForm, UserCreateForm, UserUpdateForm, AdminResetPasswordForm
from .services import DepartmentService, UserService

ALLOWED_STAFF_MANAGEMENT_ROLES = ['ADMIN', 'COE', 'ADMISSION', 'ACCOUNTS', 'PLACEMENT']


# --- Staff Directory (SMS Recipient Master) Views ---

class StaffListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    """
    Staff Directory Master displaying recipient staff members.
    Clean recipient table with auto-generated S.No based on pagination.
    """
    model = Staff
    template_name = 'users/staff_list.html'
    context_object_name = 'staff_members'
    allowed_roles = ALLOWED_STAFF_MANAGEMENT_ROLES
    paginate_by = 15

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True).select_related('department').order_by('name')
        query = self.request.GET.get('q', '').strip()
        dept_filter = self.request.GET.get('department', '').strip()

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(mobile_number__icontains=query)
            )
        if dept_filter and dept_filter.isdigit():
            queryset = queryset.filter(department_id=dept_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_dept'] = self.request.GET.get('department', '')
        context['departments'] = Department.objects.filter(is_active=True)
        return context


class StaffCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    """
    Creates a new recipient staff member in the Staff Directory.
    """
    model = Staff
    form_class = StaffForm
    template_name = 'users/staff_form.html'
    success_url = reverse_lazy('users:staff_list')
    allowed_roles = ALLOWED_STAFF_MANAGEMENT_ROLES

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f"Staff recipient '{form.instance.name}' added to directory successfully.")
        return super().form_valid(form)


class StaffUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    """
    Updates recipient staff member details.
    """
    model = Staff
    form_class = StaffForm
    template_name = 'users/staff_form.html'
    success_url = reverse_lazy('users:staff_list')
    allowed_roles = ALLOWED_STAFF_MANAGEMENT_ROLES

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f"Staff recipient '{form.instance.name}' updated successfully.")
        return super().form_valid(form)


class StaffDeleteView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    Deletes or deactivates a recipient staff record.
    """
    allowed_roles = ALLOWED_STAFF_MANAGEMENT_ROLES

    def post(self, request, pk):
        staff = get_object_or_404(Staff, pk=pk)
        name = staff.name
        staff.delete()
        messages.success(request, f"Staff member '{name}' removed from directory.")
        return redirect('users:staff_list')


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


# --- System Users (Application Login Accounts) Views ---

import json

class SystemUserListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    """
    Administrator System User Directory displaying application login accounts.
    Only accessible by System Administrators.
    """
    model = CustomUser
    template_name = 'users/system_user_list.html'
    context_object_name = 'users'
    allowed_roles = ['ADMIN']
    paginate_by = 12

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_deleted=False).select_related('department', 'created_by', 'role_obj').order_by('-date_joined')
        query = self.request.GET.get('q')
        role_filter = self.request.GET.get('role')
        dept_filter = self.request.GET.get('department')
        status_filter = self.request.GET.get('status')

        if query:
            queryset = queryset.filter(
                Q(username__icontains=query) | Q(first_name__icontains=query) |
                Q(last_name__icontains=query) | Q(email__icontains=query) |
                Q(employee_id__icontains=query) | Q(phone_number__icontains=query)
            )
        if role_filter:
            queryset = queryset.filter(
                Q(role=role_filter) | Q(role_obj__name__iexact=role_filter) | Q(role_obj__code__iexact=role_filter)
            )
        if dept_filter:
            if dept_filter.isdigit():
                queryset = queryset.filter(department_id=int(dept_filter))
            else:
                queryset = queryset.filter(department__name__iexact=dept_filter)
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
        context['selected_status'] = self.request.GET.get('status', '')

        role_names = list(Role.objects.values_list('name', flat=True))
        for code, label in RoleChoices.choices:
            if str(label) not in role_names:
                role_names.append(str(label))
        role_names.sort()

        context['roles'] = [(r, r) for r in role_names]
        context['departments'] = Department.objects.filter(is_active=True)
        return context


class SystemUserCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    """
    Creates a new login user account.
    """
    model = CustomUser
    form_class = UserCreateForm
    template_name = 'users/system_user_form.html'
    success_url = reverse_lazy('users:system_user_list')
    allowed_roles = ['ADMIN']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role_names = list(Role.objects.values_list('name', flat=True))
        for code, label in RoleChoices.choices:
            if str(label) not in role_names:
                role_names.append(str(label))
        role_names.sort()

        office_names = list(Department.objects.filter(is_active=True).values_list('name', flat=True))
        office_names.sort()

        context['existing_roles_json'] = json.dumps(role_names)
        context['existing_offices_json'] = json.dumps(office_names)
        return context

    def form_valid(self, form):
        user = UserService.create_user(form, created_by=self.request.user)
        messages.success(self.request, f"System User account for '{user.get_full_name() or user.username}' ({user.get_role_display()}) created successfully.")
        return redirect(self.success_url)


class SystemUserUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    """
    Updates an existing system login account.
    """
    model = CustomUser
    form_class = UserUpdateForm
    template_name = 'users/system_user_form.html'
    success_url = reverse_lazy('users:system_user_list')
    allowed_roles = ['ADMIN']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role_names = list(Role.objects.values_list('name', flat=True))
        for code, label in RoleChoices.choices:
            if str(label) not in role_names:
                role_names.append(str(label))
        role_names.sort()

        office_names = list(Department.objects.filter(is_active=True).values_list('name', flat=True))
        office_names.sort()

        context['existing_roles_json'] = json.dumps(role_names)
        context['existing_offices_json'] = json.dumps(office_names)
        return context

    def form_valid(self, form):
        user = UserService.update_user(self.object, form, updated_by=self.request.user)
        messages.success(self.request, f"System User account '{user.username}' updated successfully.")
        return redirect(self.success_url)


class SystemUserToggleStatusView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = ['ADMIN']

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk, is_deleted=False)
        if user == request.user:
            messages.error(request, "You cannot deactivate your own Administrator account.")
            return redirect('users:system_user_list')

        new_status = UserService.toggle_user_status(user, toggled_by=request.user)
        status_str = "activated" if new_status else "deactivated"
        messages.success(request, f"User account '{user.username}' has been {status_str}.")
        return redirect('users:system_user_list')


class SystemUserToggleLockView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = ['ADMIN']

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk, is_deleted=False)
        if user == request.user:
            messages.error(request, "You cannot lock your own Administrator account.")
            return redirect('users:system_user_list')

        is_locked = UserService.toggle_user_lock(user, locked_by=request.user)
        lock_str = "locked" if is_locked else "unlocked"
        messages.success(request, f"User account '{user.username}' has been {lock_str}.")
        return redirect('users:system_user_list')


class SystemUserDeleteView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = ['ADMIN']

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk, is_deleted=False)
        if user == request.user:
            messages.error(request, "You cannot delete your own Administrator account.")
            return redirect('users:system_user_list')

        username = user.username
        UserService.soft_delete_user(user, deleted_by=request.user)
        messages.info(request, f"User account '{username}' has been soft deleted.")
        return redirect('users:system_user_list')


class SystemUserResetPasswordView(LoginRequiredMixin, RoleRequiredMixin, View):
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
        return redirect('users:system_user_list')
