from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'department', 'employee_id', 'is_staff')
    list_filter = ('role', 'department', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('College Metadata & RBAC', {'fields': ('role', 'phone_number', 'employee_id', 'department')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('College Metadata & RBAC', {'fields': ('role', 'phone_number', 'employee_id', 'department')}),
    )
