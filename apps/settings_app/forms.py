from django import forms
from django.utils.translation import gettext_lazy as _
from .models import SMSGatewayConfig, HTTPMethodChoices
from apps.common.models import sender_id_validator, dlt_id_validator


class SMSGatewayConfigForm(forms.ModelForm):
    """
    Form for Administrator to configure SMS Gateway credentials and endpoints securely.
    """
    api_key = forms.CharField(
        widget=forms.PasswordInput(render_value=True, attrs={
            'class': 'form-control font-monospace',
            'placeholder': 'Enter API Key / Token',
            'id': 'apiKeyInput'
        }),
        label=_("API Key / Token"),
        help_text=_("Secret API Key required by SMS gateway provider.")
    )

    class Meta:
        model = SMSGatewayConfig
        fields = [
            'provider_name', 'api_url', 'balance_api_url', 'dlr_api_url',
            'api_key', 'default_sender_id', 'default_entity_id', 'route_id',
            'request_method', 'total_sms_allowed', 'timeout', 'response_format', 'is_active'
        ]
        widgets = {
            'provider_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Draft4SMS Provider'}),
            'api_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://text.draft4sms.com/vb/apikey.php'}),
            'balance_api_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://text.draft4sms.com/vb/http-credit.php'}),
            'dlr_api_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://text.draft4sms.com/vb/http-dlr.php'}),
            'default_sender_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CLGEXM'}),
            'default_entity_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1001999988887777666'}),
            'route_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1'}),
            'request_method': forms.Select(attrs={'class': 'form-select'}),
            'total_sms_allowed': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '50000'}),
            'timeout': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '60'}),
            'response_format': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'json'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_default_sender_id(self):
        sender = self.cleaned_data.get('default_sender_id', '').strip().upper()
        return sender

    def clean_timeout(self):
        timeout = self.cleaned_data.get('timeout')
        if not timeout or timeout <= 0:
            raise forms.ValidationError(_("Timeout must be a positive integer greater than 0."))
        return timeout
