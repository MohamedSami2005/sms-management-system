from django.db import models
from django.conf import settings
from apps.common.models import TimeStampedModel
from apps.dlt_templates.models import DLTTemplate


class SMSLog(TimeStampedModel):
    """
    Historical log record of dispatched SMS.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='sms_logs')
    template = models.ForeignKey(DLTTemplate, on_delete=models.SET_NULL, null=True, related_name='logs')
    mobile_number = models.CharField(max_length=15)
    message_content = models.TextField()
    status = models.CharField(max_length=20)
    gateway_message_id = models.CharField(max_length=100, blank=True, null=True)
    gateway_response_raw = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'SMS Log'
        verbose_name_plural = 'SMS Logs'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Log to {self.mobile_number} - {self.status}"
