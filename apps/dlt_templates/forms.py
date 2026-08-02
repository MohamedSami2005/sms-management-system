from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from apps.common.scopes import is_global_admin
from apps.users.models import Department
from .models import DLTTemplate, TemplateVariable, TemplateCategoryChoices


class DLTTemplateForm(forms.ModelForm):
    """
    Form for creating and editing DLT registered content templates.
    Allows selecting multiple allowed Offices (optional) during template registration/editing.
    """
    allowed_offices = forms.ModelMultipleChoiceField(
        queryset=Department.objects.filter(is_active=True).order_by('name'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label=_("Allowed Offices Scope (Multiple Optional)")
    )

    class Meta:
        model = DLTTemplate
        fields = [
            'name', 'dlt_template_id', 'entity_id', 'header_sender_id',
            'category', 'department', 'allowed_offices', 'template_content', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Semester Exam Fee Notice'}),
            'dlt_template_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1107160000000123456'}),
            'entity_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1001999988887777666'}),
            'header_sender_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CLGEXM'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'template_content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Dear {#var#}, your exam is on {#var#}. Regards, College.'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['department'].label = _("Office (Optional)")
        self.fields['department'].required = False

        if self.instance and self.instance.pk:
            self.fields['allowed_offices'].initial = self.instance.allowed_offices.all()

        if self.user and not is_global_admin(self.user):
            user_office = getattr(self.user, 'department', None)
            if user_office:
                self.fields['department'].queryset = Department.objects.filter(pk=user_office.pk)
                self.fields['department'].initial = user_office
                self.fields['department'].widget.attrs['readonly'] = True

    def clean_dlt_template_id(self):
        dlt_id = self.cleaned_data.get('dlt_template_id', '').strip()
        qs = DLTTemplate.objects.filter(dlt_template_id=dlt_id)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_("A template with this DLT Content Template ID already exists."))
        return dlt_id

    def clean_header_sender_id(self):
        header = self.cleaned_data.get('header_sender_id', '').strip().upper()
        return header

    def clean_department(self):
        dept = self.cleaned_data.get('department')
        if self.user and not is_global_admin(self.user):
            user_office = getattr(self.user, 'department', None)
            if user_office:
                return user_office
        return dept


class TemplateVariableForm(forms.ModelForm):
    class Meta:
        model = TemplateVariable
        fields = ['position', 'name', 'sample_value']
        widgets = {
            'position': forms.HiddenInput(),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Variable Name (e.g. Student Name)'}),
            'sample_value': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sample Value (e.g. Sami)'}),
        }


TemplateVariableFormSet = inlineformset_factory(
    DLTTemplate,
    TemplateVariable,
    form=TemplateVariableForm,
    extra=0,
    can_delete=False
)


class TemplateImportForm(forms.Form):
    """
    Form for uploading Excel or CSV file containing bulk DLT templates.
    """
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls, .csv'}),
        label=_("Select Excel/CSV Template File"),
        help_text=_("Required columns: template_name, dlt_template_id, entity_id, sender_id, template_content, category")
    )


class TemplateScopeForm(forms.ModelForm):
    """
    Form for managing allowed offices for a DLT template (Admin-Only).
    """
    allowed_offices = forms.ModelMultipleChoiceField(
        queryset=Department.objects.filter(is_active=True).order_by('name'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label=_("Allowed Offices")
    )

    class Meta:
        model = DLTTemplate
        fields = ['allowed_offices']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['allowed_offices'].initial = self.instance.allowed_offices.all()

    def clean_allowed_offices(self):
        offices = set(self.cleaned_data.get('allowed_offices') or [])
        if self.instance and self.instance.department:
            offices.add(self.instance.department)
        return list(offices)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            offices = list(self.cleaned_data.get('allowed_offices', []))
            if instance.department and instance.department not in offices:
                offices.append(instance.department)
            instance.allowed_offices.set(offices)
            instance.ensure_primary_office_in_allowed()
        return instance
