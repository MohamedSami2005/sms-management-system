from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.common.models import AuditModel, sender_id_validator, dlt_id_validator


class HTTPMethodChoices(models.TextChoices):
    GET = 'GET', 'HTTP GET'
    POST = 'POST', 'HTTP POST'


class SMSGatewayConfig(AuditModel):
    """
    Configuration profile for integrating with external HTTP SMS Gateway APIs.
    """
    provider_name = models.CharField(
        max_length=100,
        default='Primary HTTP SMS Gateway',
        verbose_name=_("Provider Name")
    )
    api_url = models.URLField(
        verbose_name=_("SMS Dispatch API URL"),
        help_text=_("HTTP SMS API Endpoint URL (e.g. http://api.sms-provider.com/send)")
    )
    balance_api_url = models.URLField(
        blank=True,
        verbose_name=_("Credit Balance API URL"),
        help_text=_("Optional HTTP API endpoint to check remaining SMS credits.")
    )
    dlr_api_url = models.URLField(
        blank=True,
        verbose_name=_("Delivery Report (DLR) API URL"),
        help_text=_("Optional HTTP API endpoint to fetch status of dispatched SMS.")
    )
    api_key = models.CharField(
        max_length=255,
        verbose_name=_("API Key / Token"),
        help_text=_("API Key or Auth Token required by SMS gateway provider.")
    )
    username = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("API Username"),
        help_text=_("Account username if required by gateway HTTP authentication.")
    )
    password = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("API Password"),
        help_text=_("Account password if required by gateway HTTP authentication.")
    )
    default_sender_id = models.CharField(
        max_length=10,
        validators=[sender_id_validator],
        verbose_name=_("Default Sender ID / Header"),
        help_text=_("Approved 6-letter Header (e.g., CLGEXM).")
    )
    default_entity_id = models.CharField(
        max_length=50,
        blank=True,
        validators=[dlt_id_validator],
        verbose_name=_("Default Principal Entity ID"),
        help_text=_("DLT Registered Principal Entity ID.")
    )
    request_method = models.CharField(
        max_length=10,
        choices=HTTPMethodChoices.choices,
        default=HTTPMethodChoices.POST,
        verbose_name=_("HTTP Request Method")
    )
    http_headers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Custom HTTP Headers"),
        help_text=_("JSON object of custom HTTP request headers (e.g. {\"Authorization\": \"Bearer ...\"})")
    )
    param_mapping = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("API Parameter Mapping JSON"),
        help_text=_("JSON key mapping (e.g. {\"mobile\": \"number\", \"text\": \"msg\", \"template_id\": \"dlt_id\"})")
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active Provider")
    )

    class Meta:
        verbose_name = _("SMS Gateway Config")
        verbose_name_plural = _("SMS Gateway Configs")
        ordering = ['-is_active', '-created_at']

    def save(self, *args, **kwargs):
        # If set to active, deactivate all other gateway configs
        if self.is_active:
            SMSGatewayConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        status_str = "Active" if self.is_active else "Inactive"
        return f"{self.provider_name} [{status_str}]"

    @classmethod
    def get_active_config(cls):
        """Returns the currently active SMS Gateway configuration profile."""
        return cls.objects.filter(is_active=True).first()

    @property
    def masked_api_key(self) -> str:
        """Returns masked API key for safe admin display."""
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "****"
        return f"{self.api_key[:4]}****{self.api_key[-4:]}"
