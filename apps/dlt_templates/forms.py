from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from .models import DLTTemplate, TemplateVariable, TemplateCategoryChoices


class DLTTemplateForm(forms.ModelForm):
    """
    Form for creating and editing DLT registered content templates.
    """
    class Meta:
        model = DLTTemplate
        fields = [
            'name', 'dlt_template_id', 'entity_id', 'header_sender_id',
            'category', 'department', 'template_content', 'is_active'
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
