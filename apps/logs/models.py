from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.common.models import TimeStampedModel, phone_validator
from apps.dlt_templates.models import DLTTemplate
from apps.sms.models import SMSBatch, SMSStatusChoices


class SMSLog(TimeStampedModel):
    """
    Historical immutable audit log record of dispatched SMS and gateway delivery reports (DLR).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_logs',
        verbose_name=_("Dispatched By User")
    )
    department = models.ForeignKey(
        'users.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_logs',
        verbose_name=_("Department")
    )
    template = models.ForeignKey(
        DLTTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_logs',
        verbose_name=_("DLT Template")
    )
    batch = models.ForeignKey(
        SMSBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_logs',
        verbose_name=_("Associated SMS Batch")
    )
    mobile_number = models.CharField(
        max_length=15,
        validators=[phone_validator],
        db_index=True,
        verbose_name=_("Mobile Number")
    )
    message_content = models.TextField(
        verbose_name=_("Dispatched SMS Text")
    )
    status = models.CharField(
        max_length=20,
        choices=SMSStatusChoices.choices,
        db_index=True,
        verbose_name=_("Dispatch Status")
    )
    credit_units = models.PositiveIntegerField(
        default=1,
        verbose_name=_("SMS Credit Units")
    )
    gateway_message_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_("Gateway Transaction ID")
    )
    gateway_status_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Gateway Return Status Code")
    )
    gateway_response_raw = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Raw HTTP Gateway Response")
    )
    dlr_status = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_("DLR Delivery Report Status"),
        help_text=_("Delivery report status returned from SMS gateway (DELIVRD, REJECTD, UNDELIV, EXPIRED)")
    )
    dlr_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("DLR Delivery Timestamp")
    )

    class Meta:
        verbose_name = _("SMS Log")
        verbose_name_plural = _("SMS Logs")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at', 'status'], name='idx_log_created_status'),
            models.Index(fields=['mobile_number', 'created_at'], name='idx_log_mobile_created'),
            models.Index(fields=['department', 'created_at'], name='idx_log_dept_created'),
            models.Index(fields=['gateway_message_id'], name='idx_log_gw_msg_id'),
        ]

    def __str__(self) -> str:
        return f"Log #{self.id} -> {self.mobile_number} [{self.get_status_display()}]"
