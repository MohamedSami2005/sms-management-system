from django import forms
from django.utils.translation import gettext_lazy as _
from apps.users.models import Department, Staff
from apps.accounts.models import CustomUser, RoleChoices, ScopeChoices


class DepartmentForm(forms.ModelForm):
    """
    Form for creating and updating college departments.
    """
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Controller of Examinations'})
    )
    code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. COE'})
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Department duties...'})
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Department
        fields = ['name', 'code', 'description', 'is_active']

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip().upper()
        qs = Department.objects.filter(code=code)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_("A department with this short code already exists."))
        return code

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        qs = Department.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_("A department with this name already exists."))
        return name


class StaffForm(forms.ModelForm):
    """
    Form for creating and editing Staff Recipient Master records.
    Contains ONLY Staff Name, Mobile Number, and Department.
    """
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Staff Name (e.g. Mohamed Sami)'}),
        label=_("Staff Name")
    )
    mobile_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={'class': 'form-control font-monospace', 'placeholder': '10-digit Indian Mobile Number'}),
        label=_("Mobile Number")
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_("Department")
    )

    class Meta:
        model = Staff
        fields = ['name', 'mobile_number', 'department']

    def clean_mobile_number(self):
        mobile = self.cleaned_data.get('mobile_number', '').strip()
        if mobile.startswith('+91'):
            mobile = mobile[3:]
        elif mobile.startswith('91') and len(mobile) == 12:
            mobile = mobile[2:]
        return mobile


class UserCreateForm(forms.ModelForm):
    """
    Form for Administrator to create a new user account with assigned role and department.
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Initial Password'}),
        label=_("Initial Password")
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'}),
        label=_("Confirm Password")
    )
    must_change_password = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_("Force Password Change on First Login")
    )

    class Meta:
        model = CustomUser
        fields = [
            'employee_id', 'username', 'first_name', 'last_name', 'email',
            'phone_number', 'department', 'designation', 'role',
            'is_active', 'must_change_password'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'johndoe'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'john@college.edu'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'John'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Doe'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'designation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Professor / Accountant'}),
            'employee_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'EMP-1001'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '9876543210'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if CustomUser.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(_("This username is already taken."))
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email and CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("This email address is already registered."))
        return email

    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id', '').strip().upper()
        if employee_id and CustomUser.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError(_("This Employee ID is already assigned to another staff member."))
        return employee_id

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        if phone and CustomUser.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError(_("This phone number is already registered to another account."))
        return phone

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', _("Passwords do not match."))
        return cleaned_data


class UserUpdateForm(forms.ModelForm):
    """
    Form for Administrator to edit an existing user account profile, role, and lock status.
    """
    class Meta:
        model = CustomUser
        fields = [
            'employee_id', 'username', 'first_name', 'last_name', 'email',
            'phone_number', 'department', 'designation', 'role',
            'is_active', 'is_locked', 'must_change_password'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_locked': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'must_change_password': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if CustomUser.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("This username is already taken."))
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email and CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("This email address is already registered."))
        return email

    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id', '').strip().upper()
        if employee_id and CustomUser.objects.filter(employee_id=employee_id).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("This Employee ID is already assigned to another staff member."))
        return employee_id

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        if phone and CustomUser.objects.filter(phone_number=phone).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("This phone number is already registered to another account."))
        return phone


class AdminResetPasswordForm(forms.Form):
    """
    Form for Administrator to reset another user's password directly from Web UI.
    """
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New Password'}),
        label=_("New Password")
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'}),
        label=_("Confirm Password")
    )
    must_change_password = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_("Require user to change password on next login")
    )

    def clean(self):
        cleaned_data = super().clean()
        new_pass = cleaned_data.get('new_password')
        confirm_pass = cleaned_data.get('confirm_password')
        if new_pass and confirm_pass and new_pass != confirm_pass:
            self.add_error('confirm_password', _("Passwords do not match."))
        return cleaned_data
