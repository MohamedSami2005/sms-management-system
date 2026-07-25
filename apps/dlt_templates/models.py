from django.db import models
from apps.common.models import TimeStampedModel


class DLTTemplate(TimeStampedModel):
    """
    DLT Template registered with Telecom Operator & SMS Gateway.
    """
    name = models.CharField(max_length=150, help_text="Human readable template name")
    dlt_template_id = models.CharField(max_length=50, unique=True, help_text="Registered DLT Content Template ID")
    entity_id = models.CharField(max_length=50, help_text="Registered DLT Principal Entity ID")
    header_sender_id = models.CharField(max_length=10, help_text="Approved Sender ID Header (e.g. CLGEXM)")
    template_content = models.TextField(help_text="DLT template text containing placeholders like {#var#}")
    category = models.CharField(max_length=50, default='Service Implicit', help_text="Transactional, Service Implicit, etc.")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'DLT Template'
        verbose_name_plural = 'DLT Templates'
        ordering = ['name']

    def __str__(self) -> str:
        return f"{self.name} [{self.dlt_template_id}]"
