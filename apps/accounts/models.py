from django.contrib.auth.models import AbstractUser, Permission
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.common.models import TimeStampedModel, phone_validator


class RoleChoices(models.TextChoices):
    ADMIN = 'ADMIN', _('Administrator')
    COE = 'COE', _('Controller of Examinations')
    ADMISSION = 'ADMISSION', _('Admission Department')
    ACCOUNTS = 'ACCOUNTS', _('Accounts Department')
    PLACEMENT = 'PLACEMENT', _('Placement Department')
    LIBRARY = 'LIBRARY', _('Library Department')
    HOD = 'HOD', _('Head of Department')
    STAFF = 'STAFF', _('College Staff')


class ScopeChoices(models.TextChoices):
    GLOBAL = 'GLOBAL', _('Global (All Departments)')
    DEPARTMENT = 'DEPARTMENT', _('Department Only')
    MULTI_DEPARTMENT = 'MULTI_DEPARTMENT', _('Multiple Departments')


class Role(TimeStampedModel):
    """
    Role definition for System Role-Based Access Control (RBAC).
    Mapped to custom permissions and system choices.
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("Role Name")
    )
    code = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        choices=RoleChoices.choices,
        default=RoleChoices.STAFF,
        verbose_name=_("Role Code")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )
    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="custom_roles",
        verbose_name=_("Assigned Permissions")
    )
    is_system_role = models.BooleanField(
        default=False,
        verbose_name=_("Is System Built-in Role")
    )

    class Meta:
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")
        ordering = ['name']

    def __str__(self) -> str:
        return f"{self.name} [{self.code}]"


class CustomUser(AbstractUser):
    """
    Custom User Model supporting role-based access control, scope-based permissions,
    college department mapping, password change enforcement, and soft deletion.
    """
    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.STAFF,
        db_index=True,
        verbose_name=_("System Role"),
        help_text=_("Designated system access role.")
    )
    role_obj = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name=_("RBAC Role Object")
    )
    department = models.ForeignKey(
        'users.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_("Department"),
        help_text=_("Associated college department.")
    )
    scope_type = models.CharField(
        max_length=30,
        choices=ScopeChoices.choices,
        default=ScopeChoices.GLOBAL,
        verbose_name=_("Data Access Scope"),
        help_text=_("Controls data access boundaries across departments.")
    )
    designation = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Designation / Title"),
        help_text=_("Staff job designation (e.g. Professor, HOD, Accountant).")
    )
    phone_number = models.CharField(
        max_length=15,
        validators=[phone_validator],
        blank=True,
        db_index=True,
        verbose_name=_("Phone Number"),
        help_text=_("Contact mobile number (10 digits).")
    )
    employee_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        verbose_name=_("Employee / Staff ID"),
        help_text=_("Unique College Employee Identification Number.")
    )
    must_change_password = models.BooleanField(
        default=False,
        verbose_name=_("Force Password Change"),
        help_text=_("Requires user to change password on next login.")
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name=_("Account Locked"),
        help_text=_("Prevents user from logging in when locked.")
    )
    failed_login_attempts = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Failed Login Attempts")
    )
    password_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Password Changed Date")
    )
    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users',
        verbose_name=_("Created By Administrator")
    )
    is_deleted = models.BooleanField(
        default=False,
        verbose_name=_("Soft Deleted"),
        help_text=_("Designates whether this user record is soft deleted.")
    )

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['username']
        indexes = [
            models.Index(fields=['role', 'is_active'], name='idx_user_role_active'),
            models.Index(fields=['department', 'role'], name='idx_user_dept_role'),
        ]

    def save(self, *args, **kwargs):
        if self.employee_id:
            self.employee_id = self.employee_id.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        full_name = self.get_full_name()
        display_name = full_name if full_name else self.username
        dept_str = f" - {self.department.code}" if self.department else ""
        return f"{display_name} ({self.get_role_display()}{dept_str})"

    @property
    def is_admin(self) -> bool:
        """Returns True if the user has Administrator privileges."""
        return self.role == RoleChoices.ADMIN or self.is_superuser

    @property
    def display_role(self) -> str:
        """Human readable role title."""
        return self.get_role_display()

    def has_role(self, *roles: str) -> bool:
        """Utility method to check if user matches any of the given roles."""
        if self.is_superuser:
            return True
        return self.role in roles
