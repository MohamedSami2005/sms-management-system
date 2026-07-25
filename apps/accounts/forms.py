from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm, UserCreationForm, UserChangeForm,
    PasswordChangeForm, PasswordResetForm, SetPasswordForm
)
from django.utils.translation import gettext_lazy as _
from .models import CustomUser


class CustomLoginForm(AuthenticationForm):
    """
    Login form supporting username, password, and 'Remember Me' session persistence.
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your Username',
            'autocomplete': 'username'
        }),
        label=_("Username")
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your Password',
            'autocomplete': 'current-password'
        }),
        label=_("Password")
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_("Remember me on this browser")
    )


class UserProfileForm(forms.ModelForm):
    """
    Form for college staff to update their profile information.
    """
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'})
    )
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10-digit Mobile Number'})
    )

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone_number']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            qs = CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(_("This email address is already registered to another account."))
        return email


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'employee_id', 'department')


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'employee_id', 'department', 'is_active')


class CustomPasswordChangeForm(PasswordChangeForm):
    """
    Form for authenticated users to change their password safely.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class CustomPasswordResetForm(PasswordResetForm):
    """
    Form for requesting a password reset email token.
    """
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your registered Email address'
        })
    )


class CustomSetPasswordForm(SetPasswordForm):
    """
    Form for setting a new password using a valid reset token.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
