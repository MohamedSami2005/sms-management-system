from django.db import models
from django.conf import settings
from apps.common.models import TimeStampedModel
from apps.dlt_templates.models import DLTTemplate


class SMSStatusChoices(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PROCESSING = 'PROCESSING', 'Processing'
    SENT = 'SENT', 'Sent'
    DELIVERED = 'DELIVERED', 'Delivered'
    FAILED = 'FAILED', 'Failed'


class SMSBatch(TimeStampedModel):
    """
    Tracks a bulk SMS dispatch job uploaded via CSV/Excel.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sms_batches')
    template = models.ForeignKey(DLTTemplate, on_delete=models.PROTECT, related_name='batches')
    file_name = models.CharField(max_length=255)
    total_records = models.PositiveIntegerField(default=0)
    processed_records = models.PositiveIntegerField(default=0)
    successful_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=SMSStatusChoices.choices, default=SMSStatusChoices.PENDING)

    class Meta:
        verbose_name = 'SMS Batch'
        verbose_name_plural = 'SMS Batches'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Batch #{self.id} - {self.file_name} ({self.status})"


class SMSQueue(TimeStampedModel):
    """
    Individual SMS item waiting or currently processing in the dispatch queue.
    """
    batch = models.ForeignKey(SMSBatch, on_delete=models.CASCADE, null=True, blank=True, related_name='queue_items')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='queued_sms')
    template = models.ForeignKey(DLTTemplate, on_delete=models.PROTECT, related_name='queued_messages')
    mobile_number = models.CharField(max_length=15)
    message_content = models.TextField()
    status = models.CharField(max_length=20, choices=SMSStatusChoices.choices, default=SMSStatusChoices.PENDING)
    gateway_message_id = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'SMS Queue Item'
        verbose_name_plural = 'SMS Queue Items'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"SMS to {self.mobile_number} [{self.status}]"
