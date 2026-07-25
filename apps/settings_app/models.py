from django.db import models
from apps.common.models import TimeStampedModel


class SMSGatewayConfig(TimeStampedModel):
    """
    Configuration settings for HTTP SMS Gateway Provider API.
    """
    provider_name = models.CharField(max_length=100, default='Default HTTP SMS API')
    api_url = models.URLField(help_text="HTTP SMS API Endpoint URL")
    api_key = models.CharField(max_length=255, help_text="API Authentication Key / Token")
    default_sender_id = models.CharField(max_length=10, help_text="Approved Sender ID / Header")
    entity_id = models.CharField(max_length=50, blank=True, help_text="Default DLT Principal Entity ID")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'SMS Gateway Config'
        verbose_name_plural = 'SMS Gateway Configs'

    def __str__(self) -> str:
        return f"{self.provider_name} ({'Active' if self.is_active else 'Inactive'})"
