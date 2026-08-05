from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.common.models import AuditModel, TimeStampedModel, phone_validator
from apps.dlt_templates.models import DLTTemplate


class SMSStatusChoices(models.TextChoices):
    PENDING = 'PENDING', _('Pending')
    PROCESSING = 'PROCESSING', _('Processing')
    SENT = 'SENT', _('Sent to Gateway')
    DELIVERED = 'DELIVERED', _('Delivered')
    FAILED = 'FAILED', _('Failed')


class SMSBatch(AuditModel):
    """
    Tracks a bulk SMS dispatch job uploaded via CSV or Excel spreadsheet.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sms_batches',
        verbose_name=_("Dispatched By User")
    )
    office = models.ForeignKey(
        'users.Office',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_batches',
        verbose_name=_("Office")
    )
    department = models.ForeignKey(
        'users.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_batches',
        verbose_name=_("Department")
    )
    template = models.ForeignKey(
        DLTTemplate,
        on_delete=models.PROTECT,
        related_name='batches',
        verbose_name=_("DLT Template Used")
    )
    file_name = models.CharField(
        max_length=255,
        verbose_name=_("Uploaded File Name")
    )
    file_path = models.FileField(
        upload_to='bulk_uploads/%Y/%m/%d/',
        blank=True,
        null=True,
        verbose_name=_("Saved Upload File")
    )
    total_records = models.PositiveIntegerField(
        default=0,
        db_index=True,
        verbose_name=_("Total Records")
    )
    processed_records = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Processed Records")
    )
    successful_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Successful SMS Count")
    )
    failed_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Failed SMS Count")
    )
    status = models.CharField(
        max_length=20,
        choices=SMSStatusChoices.choices,
        default=SMSStatusChoices.PENDING,
        db_index=True,
        verbose_name=_("Batch Status")
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Dispatch Started At")
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Dispatch Completed At")
    )

    class Meta:
        verbose_name = _("SMS Batch")
        verbose_name_plural = _("SMS Batches")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_batch_status_created'),
            models.Index(fields=['user', 'created_at'], name='idx_batch_user_created'),
        ]

    def __str__(self) -> str:
        return f"Batch #{self.id} - {self.file_name} ({self.get_status_display()})"

    @property
    def progress_percentage(self) -> float:
        """Returns the completion percentage of the batch dispatch."""
        if self.total_records == 0:
            return 0.0
        return round((self.processed_records / self.total_records) * 100, 2)


class SMSQueue(TimeStampedModel):
    """
    Individual SMS message waiting or currently processing in the queue.
    """
    batch = models.ForeignKey(
        SMSBatch,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='queue_items',
        verbose_name=_("Associated SMS Batch")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='queued_sms',
        verbose_name=_("Dispatched By User")
    )
    office = models.ForeignKey(
        'users.Office',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='queued_sms',
        verbose_name=_("Office")
    )
    department = models.ForeignKey(
        'users.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='queued_sms',
        verbose_name=_("Department")
    )
    template = models.ForeignKey(
        DLTTemplate,
        on_delete=models.PROTECT,
        related_name='queued_messages',
        verbose_name=_("DLT Template")
    )
    mobile_number = models.CharField(
        max_length=15,
        validators=[phone_validator],
        db_index=True,
        verbose_name=_("Recipient Mobile Number")
    )
    message_content = models.TextField(
        verbose_name=_("Interpolated SMS Content")
    )
    variable_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Template Variable Data"),
        help_text=_("Key-value pair dictionary of template variables applied.")
    )
    status = models.CharField(
        max_length=20,
        choices=SMSStatusChoices.choices,
        default=SMSStatusChoices.PENDING,
        db_index=True,
        verbose_name=_("Queue Status")
    )
    credit_units = models.PositiveIntegerField(
        default=1,
        verbose_name=_("SMS Credit Units Consumed")
    )
    gateway_message_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_("Gateway Message ID / Reference")
    )
    gateway_response_raw = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Raw Gateway API Response")
    )
    retry_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Dispatch Retry Attempts")
    )
    scheduled_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_("Scheduled Dispatch Time")
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Sent At")
    )

    class Meta:
        verbose_name = _("SMS Queue Item")
        verbose_name_plural = _("SMS Queue Items")
        ordering = ['scheduled_at', 'id']
        indexes = [
            models.Index(fields=['status', 'scheduled_at'], name='idx_queue_status_sched'),
            models.Index(fields=['mobile_number', 'status'], name='idx_queue_mobile_status'),
            models.Index(fields=['gateway_message_id'], name='idx_queue_gw_id'),
        ]

    def __str__(self) -> str:
        return f"SMS #{self.id} -> {self.mobile_number} [{self.get_status_display()}]"
