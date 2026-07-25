from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.common.models import AuditModel


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
        return self.users.filter(is_active=True).count()
