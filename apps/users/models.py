from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.common.models import AuditModel, phone_validator


class Department(AuditModel):
    """
    College Department model (e.g. Controller of Examinations, Admissions, Placement Cell, Accounts).
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Department Name"),
        help_text=_("Full name of the department (e.g., Controller of Examinations)")
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name=_("Department Code"),
        help_text=_("Unique short code in uppercase (e.g., COE, ADM, ACCTS, CSE)")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Brief description of department responsibilities.")
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Designates whether this department is active.")
    )

    class Meta:
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")
        ordering = ['name']
        indexes = [
            models.Index(fields=['code', 'is_active'], name='idx_dept_code_active'),
        ]

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper().strip()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    @property
    def user_count(self) -> int:
        """Returns total active users in this department."""
        return self.users.filter(is_active=True, is_deleted=False).count()

    @property
    def recipient_count(self) -> int:
        """Returns total active staff recipients in this department."""
        return self.staff_recipients.filter(is_active=True).count()


class Staff(AuditModel):
    """
    Staff Recipient Master model.
    Pure recipient dataset for SMS dispatches (Single SMS, Personalized Bulk SMS, Notifications).
    Staff members do NOT authenticate into CCMS.
    """
    name = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name=_("Staff Name"),
        help_text=_("Full name of the recipient staff member.")
    )
    mobile_number = models.CharField(
        max_length=15,
        validators=[phone_validator],
        db_index=True,
        verbose_name=_("Mobile Number"),
        help_text=_("10-digit Indian Mobile Number for SMS delivery.")
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_recipients',
        verbose_name=_("Department")
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active")
    )

    class Meta:
        verbose_name = _("Staff Recipient")
        verbose_name_plural = _("Staff Recipients")
        ordering = ['name']
        indexes = [
            models.Index(fields=['name', 'mobile_number'], name='idx_staff_name_mobile'),
            models.Index(fields=['department', 'is_active'], name='idx_staff_dept_active'),
        ]

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.strip()
        if self.mobile_number:
            self.mobile_number = self.mobile_number.strip()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        dept_str = f" ({self.department.code})" if self.department else ""
        return f"{self.name}{dept_str} - {self.mobile_number}"

    @property
    def get_full_name(self) -> str:
        """Compatibility property for template duck-typing."""
        return self.name

    @property
    def phone_number(self) -> str:
        """Compatibility property for template duck-typing."""
        return self.mobile_number

    @property
    def username(self) -> str:
        """Compatibility property for template duck-typing."""
        return self.name
