from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class RoleChoices(models.TextChoices):
    ADMIN = 'ADMIN', _('Administrator')
    COE = 'COE', _('Controller of Examinations')
    ADMISSION = 'ADMISSION', _('Admission Department')
    ACCOUNTS = 'ACCOUNTS', _('Accounts Department')
    PLACEMENT = 'PLACEMENT', _('Placement Department')
    STAFF = 'STAFF', _('College Staff')


class CustomUser(AbstractUser):
    """
    Custom User Model supporting role-based access control and college staff metadata.
    """
    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.STAFF,
        help_text=_("Designated system access role.")
    )
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        help_text=_("Contact phone number.")
    )
    employee_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        help_text=_("College Staff / Employee ID.")
    )
    department = models.ForeignKey(
        'users.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text=_("Associated college department.")
    )

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['username']

    def __str__(self) -> str:
        full_name = self.get_full_name()
        return f"{full_name or self.username} ({self.get_role_display()})"

    @property
    def is_admin(self) -> bool:
        return self.role == RoleChoices.ADMIN or self.is_superuser
