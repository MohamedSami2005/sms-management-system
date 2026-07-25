from django.db import models
from apps.common.models import TimeStampedModel


class Department(TimeStampedModel):
    """
    College Department model (e.g. Controller of Examinations, Admissions, Computer Science, etc.)
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, help_text="Unique short code (e.g., COE, ADM, CSE)")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        ordering = ['name']

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"
