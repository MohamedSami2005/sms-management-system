from django import forms
from django.utils.translation import gettext_lazy as _
from apps.common.models import phone_validator
from apps.dlt_templates.models import DLTTemplate
from apps.users.models import Department
from apps.accounts.models import CustomUser


class SingleSMSForm(forms.Form):
    """
    Form for single SMS dispatch supporting Staff Lookup and dynamic template parameters.
    """
    staff = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'staffSelect'}),
        label=_("Select Recipient Staff")
    )
    mobile_number = forms.CharField(
        max_length=15,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'form-control font-monospace',
            'id': 'mobileNumberInput',
            'placeholder': 'Auto-populated from selected staff'
        }),
        label=_("Recipient Mobile Number")
    )
    template = forms.ModelChoiceField(
        queryset=DLTTemplate.objects.filter(is_active=True),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'dltTemplateSelect'}),
        label=_("Select Approved DLT Template")
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            from apps.common.scopes import get_scoped_queryset
            self.fields['template'].queryset = get_scoped_queryset(user, DLTTemplate.objects.filter(is_active=True))

    def clean_mobile_number(self):
        mobile = self.cleaned_data.get('mobile_number', '').strip()
        # Remove country code prefix +91 or 91 if entered
        if mobile.startswith('+91'):
            mobile = mobile[3:]
        elif mobile.startswith('91') and len(mobile) == 12:
            mobile = mobile[2:]
        return mobile

    def clean_template(self):
        template = self.cleaned_data.get('template')
        if not template or not template.is_active:
            raise forms.ValidationError(_("The selected DLT Template is inactive or invalid."))
        return template
