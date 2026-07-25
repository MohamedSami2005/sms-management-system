from django.db import models
from django.core.validators import RegexValidator
from django.conf import settings
from django.utils.translation import gettext_lazy as _

# Indian 10-digit mobile number validator (optionally starting with +91 or 91)
phone_validator = RegexValidator(
    regex=r'^(?:\+91|91)?[6789]\d{9}$',
    message=_("Mobile number must be a valid 10-digit Indian number, optionally prefixed with +91 or 91.")
)

# DLT Template ID validator (11 to 19 digits string)
dlt_id_validator = RegexValidator(
    regex=r'^\d{11,19}$',
    message=_("DLT Template ID must be an 11 to 19 digit numerical string.")
)

# Sender ID / Header validator (6 uppercase alpha characters)
sender_id_validator = RegexValidator(
    regex=r'^[A-Z]{6}$',
    message=_("Sender ID (Header) must consist of exactly 6 uppercase letters (e.g. CLGEXM).")
)


class TimeStampedModel(models.Model):
    """
    Abstract base class providing self-updating created_at and updated_at fields.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )

    class Meta:
        abstract = True


class AuditModel(TimeStampedModel):
    """
    Abstract base class providing timestamping and user audit tracking.
    """
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        verbose_name=_("Created By")
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated",
        verbose_name=_("Updated By")
    )

    class Meta:
        abstract = True
