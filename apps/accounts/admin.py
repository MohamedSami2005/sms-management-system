from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Role
from .forms import CustomUserCreationForm, CustomUserChangeForm


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_system_role', 'created_at')
    list_filter = ('is_system_role', 'code')
    search_fields = ('name', 'code', 'description')
    ordering = ('name',)
    filter_horizontal = ('permissions',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'department', 'phone_number', 'employee_id', 'is_staff', 'is_active')
    list_filter = ('role', 'department', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'employee_id', 'phone_number')
    ordering = ('username',)
    fieldsets = UserAdmin.fieldsets + (
        ('College Metadata & RBAC', {'fields': ('role', 'role_obj', 'department', 'phone_number', 'employee_id')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('College Metadata & RBAC', {'fields': ('role', 'role_obj', 'department', 'phone_number', 'employee_id')}),
    )
