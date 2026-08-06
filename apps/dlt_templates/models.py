import re

from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.common.models import AuditModel, TimeStampedModel, dlt_id_validator, sender_id_validator


class TemplateCategoryChoices(models.TextChoices):
    SERVICE_IMPLICIT = 'SERVICE_IMPLICIT', _('Service Implicit (Transactional OTPs, Alerts)')
    SERVICE_EXPLICIT = 'SERVICE_EXPLICIT', _('Service Explicit (Updates, Notices)')
    TRANSACTIONAL = 'TRANSACTIONAL', _('Transactional (Banking/OTP)')
    PROMOTIONAL = 'PROMOTIONAL', _('Promotional')


class DLTTemplate(AuditModel):
    """
    DLT Registered Content Template model.
    Matches telecom provider DLT registration specifications.
    """
    name = models.CharField(
        max_length=150,
        db_index=True,
        verbose_name=_("Template Name"),
        help_text=_("Human readable descriptive template title.")
    )
    dlt_template_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        validators=[dlt_id_validator],
        verbose_name=_("DLT Content Template ID"),
        help_text=_("11 to 19 digit DLT registered content template ID.")
    )
    entity_id = models.CharField(
        max_length=50,
        db_index=True,
        validators=[dlt_id_validator],
        verbose_name=_("DLT Principal Entity ID"),
        help_text=_("College DLT Registered Entity ID.")
    )
    header_sender_id = models.CharField(
        max_length=10,
        db_index=True,
        validators=[sender_id_validator],
        verbose_name=_("Sender ID (Header)"),
        help_text=_("Approved 6-character Header/Sender ID (e.g., CLGEXM).")
    )
    template_content = models.TextField(
        verbose_name=_("Template Content"),
        help_text=_("Exact DLT approved template text. Use {#var#} or {#val#} for variables.")
    )
    category = models.CharField(
        max_length=30,
        choices=TemplateCategoryChoices.choices,
        default=TemplateCategoryChoices.SERVICE_IMPLICIT,
        db_index=True,
        verbose_name=_("Template Category")
    )
    office = models.ForeignKey(
        'users.Office',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dlt_templates',
        verbose_name=_("Office"),
        help_text=_("Administrative office template belongs to.")
    )
    department = models.ForeignKey(
        'users.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dlt_templates',
        verbose_name=_("Legacy Primary Office"),
        help_text=_("Legacy department/office template belongs to.")
    )
    allowed_offices = models.ManyToManyField(
        'users.Office',
        blank=True,
        related_name='allowed_dlt_templates',
        db_table='dlt_template_office_scope',
        verbose_name=_("Allowed Offices Scope"),
        help_text=_("Offices permitted to view and use this template.")
    )
    consent_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Consent ID")
    )
    template_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Template Type")
    )
    sample_content = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Sample Content")
    )
    jio_status = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("JIO Status")
    )
    registered_by = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name=_("Registered By")
    )
    approval_date = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Approval Date")
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active")
    )

    class Meta:
        verbose_name = _("DLT Template")
        verbose_name_plural = _("DLT Templates")
        ordering = ['name']
        indexes = [
            models.Index(fields=['dlt_template_id', 'is_active'], name='idx_tmpl_id_active'),
            models.Index(fields=['category', 'is_active'], name='idx_tmpl_cat_active'),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.dlt_template_id})"

    def ensure_primary_office_in_allowed(self):
        """Initializes allowed_offices with primary office if allowed_offices is empty."""
        target_office = self.office
        if target_office and self.pk and not self.allowed_offices.exists():
            self.allowed_offices.add(target_office)

    def get_allowed_offices_display(self) -> str:
        """Returns comma-separated string of allowed office codes/names."""
        offices = list(self.allowed_offices.all())
        if not offices and self.department:
            return self.department.code or self.department.name
        return ", ".join([o.code or o.name for o in offices])

    def extract_variable_placeholders(self) -> list[str]:
        """
        Extracts all {#var#}, {#val#}, {#...#}, or {1}, {2} variable placeholders from template_content.
        """
        if not self.template_content:
            return []
        pattern = r'\{#[^#]*#\}|\{\d+\}'
        return re.findall(pattern, self.template_content)

    @property
    def variable_count(self) -> int:
        """Returns the number of dynamic variables in the template."""
        return len(self.extract_variable_placeholders())

    def sync_variables(self) -> list['TemplateVariable']:
        """
        Automatically extracts variable placeholders from content and synchronizes TemplateVariable records.
        """
        placeholders = self.extract_variable_placeholders()
        existing_vars = {v.position: v for v in self.variables.all()}
        new_vars = []

        for idx, p in enumerate(placeholders, start=1):
            if idx in existing_vars:
                var_obj = existing_vars[idx]
            else:
                var_obj = TemplateVariable(
                    template=self,
                    position=idx,
                    name=f"Variable {idx}",
                    sample_value="Sample"
                )
                var_obj.save()
            new_vars.append(var_obj)

        # Delete any leftover positions if template content variable count decreased
        self.variables.filter(position__gt=len(placeholders)).delete()
        return new_vars

    def preview_message(self, sample_values: dict | list = None) -> str:
        """
        Renders interpolated template text by replacing {#var#} placeholders with sample values.
        """
        if not self.template_content:
            return ""

        content = self.template_content
        placeholders = self.extract_variable_placeholders()

        if not sample_values:
            # Fallback to stored TemplateVariable sample values or default position labels
            var_objs = list(self.variables.order_by('position'))
            sample_values = [
                v.sample_value or v.name or f"Var{v.position}"
                for v in var_objs
            ]

        if isinstance(sample_values, list):
            for idx, p in enumerate(placeholders):
                val = str(sample_values[idx]) if idx < len(sample_values) else p
                content = content.replace(p, val, 1)
        elif isinstance(sample_values, dict):
            for idx, p in enumerate(placeholders, start=1):
                val = str(sample_values.get(f"var_{idx}") or sample_values.get(str(idx)) or p)
                content = content.replace(p, val, 1)

        return content

    @staticmethod
    def calculate_sms_credits(text: str) -> int:
        """
        Calculates SMS credit consumption based on GSM 7-bit vs Unicode encoding standards.
        GSM 7-bit: 160 chars per SMS (multi-part: 153 chars/SMS).
        Unicode: 70 chars per SMS (multi-part: 67 chars/SMS).
        """
        if not text:
            return 0
        try:
            text.encode('latin-1')
            is_unicode = False
        except UnicodeEncodeError:
            is_unicode = True

        length = len(text)
        if not is_unicode:
            if length <= 160:
                return 1
            return (length + 152) // 153
        else:
            if length <= 70:
                return 1
            return (length + 66) // 67


class TemplateVariable(TimeStampedModel):
    """
    Explicit definition and schema metadata for dynamic variables within a DLT Template.
    """
    template = models.ForeignKey(
        DLTTemplate,
        on_delete=models.CASCADE,
        related_name='variables',
        verbose_name=_("DLT Template")
    )
    position = models.PositiveIntegerField(
        verbose_name=_("Variable Position"),
        help_text=_("Order of occurrence in template (1, 2, 3...)")
    )
    name = models.CharField(
        max_length=50,
        verbose_name=_("Variable Name"),
        help_text=_("Descriptive variable identifier (e.g. student_name, exam_date, amount)")
    )
    sample_value = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Sample Value"),
        help_text=_("Example value for preview rendering.")
    )

    class Meta:
        verbose_name = _("Template Variable")
        verbose_name_plural = _("Template Variables")
        ordering = ['template', 'position']
        constraints = [
            models.UniqueConstraint(
                fields=['template', 'position'],
                name='unique_template_variable_position'
            )
        ]

    def __str__(self) -> str:
        return f"{self.template.name} - Var #{self.position} ({self.name})"
