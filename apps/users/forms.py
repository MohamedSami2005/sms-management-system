from typing import Tuple, Optional
from django import forms
from django.utils.translation import gettext_lazy as _
from apps.common.models import phone_validator
from apps.users.models import Department, Staff, Office
from apps.accounts.models import CustomUser, Role, RoleChoices


def resolve_or_create_role(role_raw: str) -> Tuple[str, Optional[Role]]:
    """
    Case-insensitive lookup or automatic creation of system RBAC Role.
    Trims leading/trailing whitespace and prevents duplicates.
    Returns (role_code, role_obj).
    """
    role_str = role_raw.strip()
    if not role_str:
        return ('STAFF', None)

    # 1. Search existing Role model by name or code
    r_obj = Role.objects.filter(name__iexact=role_str).first() or Role.objects.filter(code__iexact=role_str).first()
    if r_obj:
        return (r_obj.code, r_obj)

    # 2. Check built-in RoleChoices
    for choice_code, choice_label in RoleChoices.choices:
        if role_str.lower() in (choice_code.lower(), choice_label.lower()):
            r_obj = Role.objects.filter(code=choice_code).first()
            if not r_obj:
                r_obj = Role.objects.create(
                    name=choice_label,
                    code=choice_code,
                    is_system_role=True
                )
            return (r_obj.code, r_obj)

    # 3. Create new Role dynamically
    clean_code = ''.join(c if c.isalnum() else '_' for c in role_str.upper()).strip('_')
    clean_code = clean_code[:30]
    if not clean_code:
        clean_code = "ROLE"

    existing_code_role = Role.objects.filter(code=clean_code).first()
    if existing_code_role and existing_code_role.name.lower() != role_str.lower():
        suffix = 1
        base_code = clean_code[:24]
        while Role.objects.filter(code=f"{base_code}_{suffix}").exists():
            suffix += 1
        clean_code = f"{base_code}_{suffix}"

    r_obj, _ = Role.objects.get_or_create(
        name=role_str,
        defaults={'code': clean_code, 'is_system_role': False}
    )
    return (r_obj.code, r_obj)





def resolve_or_create_department(dept_raw: str) -> Optional[Department]:
    """
    Case-insensitive lookup or automatic creation of Department (Academic Contact Classification).
    Trims leading/trailing whitespace and prevents duplicates.
    Returns Department instance.
    """
    dept_str = dept_raw.strip()
    if not dept_str:
        return None

    if dept_str.isdigit():
        d_obj = Department.objects.filter(pk=int(dept_str)).first()
        if d_obj:
            return d_obj

    d_obj = Department.objects.filter(name__iexact=dept_str).first() or Department.objects.filter(code__iexact=dept_str).first()
    if d_obj:
        return d_obj

    clean_code = ''.join(c if c.isalnum() else '_' for c in dept_str.upper()).strip('_')
    clean_code = clean_code[:20]
    if not clean_code:
        clean_code = "DEPT"

    existing_code_dept = Department.objects.filter(code=clean_code).first()
    if existing_code_dept and existing_code_dept.name.lower() != dept_str.lower():
        suffix = 1
        base_code = clean_code[:14]
        while Department.objects.filter(code=f"{base_code}_{suffix}").exists():
            suffix += 1
        clean_code = f"{base_code}_{suffix}"

    d_obj, _ = Department.objects.get_or_create(
        name=dept_str,
        defaults={'code': clean_code, 'is_active': True}
    )
    return d_obj


class OfficeForm(forms.ModelForm):
    """
    Form for creating and updating administrative offices (e.g. ERP, COE, Accounts, Placement).
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
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Office duties...'})
    )
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Office
        fields = ['name', 'code', 'description', 'is_active']

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip().upper()
        qs = Office.objects.filter(code=code)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_("An office with this short code already exists."))
        return code

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        qs = Office.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_("An office with this name already exists."))
        return name


class StaffForm(forms.ModelForm):
    """
    Form for creating and editing Contact Master records.
    Contains Contact Name, Mobile Number, and Department (editable combobox text input).
    """
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Contact Name (e.g. Mohamed Sami)'}),
        label=_("Contact Name")
    )
    mobile_number = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={'class': 'form-control font-monospace', 'placeholder': '10-digit Indian Mobile Number', 'id': 'id_mobile_number'}),
        label=_("Mobile Number")
    )

    class Meta:
        model = Staff
        fields = ['name', 'mobile_number']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        init_val = ""
        if self.instance and self.instance.pk and self.instance.department:
            init_val = self.instance.department.name
        self.fields['department'] = forms.CharField(
            max_length=100,
            required=False,
            initial=init_val,
            widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_department', 'placeholder': 'Select or type department...'}),
            label=_("Department")
        )

    def clean_mobile_number(self):
        mobile = self.cleaned_data.get('mobile_number', '').strip()
        if not mobile:
            raise forms.ValidationError(_("Mobile number is required."))
        phone_validator(mobile)
        if mobile.startswith('+91'):
            mobile = mobile[3:]
        elif mobile.startswith('91') and len(mobile) == 12:
            mobile = mobile[2:]
        return mobile

    def clean_department(self):
        dept_raw = self.cleaned_data.get('department', '').strip()
        if not dept_raw:
            return None
        return resolve_or_create_department(dept_raw)

    def save(self, commit=True):
        contact = super().save(commit=False)
        contact.department = self.cleaned_data.get('department')
        if commit:
            contact.save()
        return contact


class UserCreateForm(forms.ModelForm):
    """
    Form for Administrator to create a new CCMS login user account with assigned role and office.
    Supports dynamic role and office creation via editable comboboxes.
    """
    name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Display Name (e.g. Mohamed Sami)'}),
        label=_("Name"),
        help_text=_("User's display name.")
    )
    employee_id = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'EMP-1001'}),
        label=_("Employee ID"),
        help_text=_("Unique identifier.")
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'john@college.edu'}),
        label=_("Email Address"),
        help_text=_("Used for password reset and notifications.")
    )
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '9876543210 (Optional)', 'id': 'id_phone_number'}),
        label=_("Mobile Number"),
        help_text=_("Useful for OTP/alerts.")
    )
    role = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_role', 'placeholder': 'Select or type role...'}),
        label=_("Role")
    )
    office = forms.ModelChoiceField(
        queryset=Office.objects.filter(is_active=True).order_by('name'),
        required=True,
        empty_label=_("Select Office"),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_office'}),
        label=_("Office")
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Initial Password'}),
        label=_("Password"),
        help_text=_("Initial password.")
    )
    confirm_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'}),
        label=_("Confirm Password"),
        help_text=_("Must match Password.")
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
            'employee_id', 'username', 'email',
            'phone_number', 'is_active', 'must_change_password'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'johndoe'}),
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
        if not employee_id:
            raise forms.ValidationError(_("Employee ID is required."))
        if CustomUser.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError(_("This Employee ID is already assigned to another staff member."))
        return employee_id

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        if phone:
            phone_validator(phone)
            if CustomUser.objects.filter(phone_number=phone).exists():
                raise forms.ValidationError(_("This phone number is already registered to another account."))
            if phone.startswith('+91'):
                phone = phone[3:]
            elif phone.startswith('91') and len(phone) == 12:
                phone = phone[2:]
        return phone

    def clean_role(self):
        role_raw = self.cleaned_data.get('role', '').strip()
        if not role_raw:
            raise forms.ValidationError(_("Role is required."))
        role_code, r_obj = resolve_or_create_role(role_raw)
        self.cleaned_role_obj = r_obj
        return role_code

    def clean_office(self):
        office_obj = self.cleaned_data.get('office')
        if not office_obj or not Office.objects.filter(pk=office_obj.pk, is_active=True).exists():
            raise forms.ValidationError(_("Please select a valid existing active Office from the master list."))
        return office_obj

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', _("Passwords do not match."))
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        raw_name = self.cleaned_data.get('name', '').strip()
        if raw_name:
            parts = raw_name.split(' ', 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ''
        if hasattr(self, 'cleaned_role_obj') and self.cleaned_role_obj:
            user.role_obj = self.cleaned_role_obj
        user.role = self.cleaned_data.get('role')
        user.office = self.cleaned_data.get('office')
        if commit:
            user.save()
        return user


class UserUpdateForm(forms.ModelForm):
    """
    Form for Administrator to edit an existing CCMS user account profile, role, and status.
    Supports dynamic role and office creation via editable comboboxes.
    """
    name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label=_("Name"),
        help_text=_("User's display name.")
    )
    employee_id = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label=_("Employee ID"),
        help_text=_("Unique identifier.")
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        label=_("Email Address"),
        help_text=_("Used for password reset and notifications.")
    )
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_phone_number'}),
        label=_("Mobile Number"),
        help_text=_("Useful for OTP/alerts.")
    )
    role = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_role', 'placeholder': 'Select or type role...'}),
        label=_("Role")
    )
    office = forms.ModelChoiceField(
        queryset=Office.objects.filter(is_active=True).order_by('name'),
        required=True,
        empty_label=_("Select Office"),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_office'}),
        label=_("Office")
    )

    class Meta:
        model = CustomUser
        fields = [
            'employee_id', 'username', 'email',
            'phone_number', 'is_active', 'is_locked', 'must_change_password'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_locked': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'must_change_password': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            display_name = self.instance.get_full_name() or self.instance.username
            self.fields['name'].initial = display_name

            if self.instance.role_obj:
                self.fields['role'].initial = self.instance.role_obj.name
            else:
                self.fields['role'].initial = self.instance.display_role

            if self.instance.office:
                self.fields['office'].initial = self.instance.office.pk

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
        if not employee_id:
            raise forms.ValidationError(_("Employee ID is required."))
        if CustomUser.objects.filter(employee_id=employee_id).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("This Employee ID is already assigned to another staff member."))
        return employee_id

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        if phone:
            phone_validator(phone)
            if CustomUser.objects.filter(phone_number=phone).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError(_("This phone number is already registered to another account."))
            if phone.startswith('+91'):
                phone = phone[3:]
            elif phone.startswith('91') and len(phone) == 12:
                phone = phone[2:]
        return phone

    def clean_role(self):
        role_raw = self.cleaned_data.get('role', '').strip()
        if not role_raw:
            raise forms.ValidationError(_("Role is required."))
        role_code, r_obj = resolve_or_create_role(role_raw)
        self.cleaned_role_obj = r_obj
        return role_code

    def clean_office(self):
        office_obj = self.cleaned_data.get('office')
        if not office_obj or not Office.objects.filter(pk=office_obj.pk, is_active=True).exists():
            raise forms.ValidationError(_("Please select a valid existing active Office from the master list."))
        return office_obj

    def save(self, commit=True):
        user = super().save(commit=False)
        raw_name = self.cleaned_data.get('name', '').strip()
        if raw_name:
            parts = raw_name.split(' ', 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ''
        if hasattr(self, 'cleaned_role_obj') and self.cleaned_role_obj:
            user.role_obj = self.cleaned_role_obj
        user.role = self.cleaned_data.get('role')
        user.office = self.cleaned_data.get('office')
        if commit:
            user.save()
        return user


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


def resolve_or_create_role(role_raw: str) -> Tuple[str, Optional[Role]]:
    """
    Case-insensitive lookup or automatic creation of system RBAC Role.
    Trims leading/trailing whitespace and prevents duplicates.
    Returns (role_code, role_obj).
    """
    role_str = role_raw.strip()
    if not role_str:
        return ('STAFF', None)

    # 1. Search existing Role model by name or code
    r_obj = Role.objects.filter(name__iexact=role_str).first() or Role.objects.filter(code__iexact=role_str).first()
    if r_obj:
        return (r_obj.code, r_obj)

    # 2. Check built-in RoleChoices
    for choice_code, choice_label in RoleChoices.choices:
        if role_str.lower() in (choice_code.lower(), choice_label.lower()):
            r_obj = Role.objects.filter(code=choice_code).first()
            if not r_obj:
                r_obj = Role.objects.create(
                    name=choice_label,
                    code=choice_code,
                    is_system_role=True
                )
            return (r_obj.code, r_obj)

    # 3. Create new Role dynamically
    clean_code = ''.join(c if c.isalnum() else '_' for c in role_str.upper()).strip('_')
    clean_code = clean_code[:30]
    if not clean_code:
        clean_code = "ROLE"

    existing_code_role = Role.objects.filter(code=clean_code).first()
    if existing_code_role and existing_code_role.name.lower() != role_str.lower():
        suffix = 1
        base_code = clean_code[:24]
        while Role.objects.filter(code=f"{base_code}_{suffix}").exists():
            suffix += 1
        clean_code = f"{base_code}_{suffix}"

    r_obj, _ = Role.objects.get_or_create(
        name=role_str,
        defaults={'code': clean_code, 'is_system_role': False}
    )
    return (r_obj.code, r_obj)


def resolve_or_create_department(dept_raw: str) -> Optional[Department]:
    """
    Case-insensitive lookup or automatic creation of Department (Office).
    Trims leading/trailing whitespace and prevents duplicates.
    Returns Department instance.
    """
    dept_str = dept_raw.strip()
    if not dept_str:
        return None

    if dept_str.isdigit():
        d_obj = Department.objects.filter(pk=int(dept_str)).first()
        if d_obj:
            return d_obj

    d_obj = Department.objects.filter(name__iexact=dept_str).first() or Department.objects.filter(code__iexact=dept_str).first()
    if d_obj:
        return d_obj

    # Create new Department (Office) dynamically
    clean_code = ''.join(c if c.isalnum() else '_' for c in dept_str.upper()).strip('_')
    clean_code = clean_code[:20]
    if not clean_code:
        clean_code = "OFFICE"

    existing_code_dept = Department.objects.filter(code=clean_code).first()
    if existing_code_dept and existing_code_dept.name.lower() != dept_str.lower():
        suffix = 1
        base_code = clean_code[:14]
        while Department.objects.filter(code=f"{base_code}_{suffix}").exists():
            suffix += 1
        clean_code = f"{base_code}_{suffix}"

    d_obj, _ = Department.objects.get_or_create(
        name=dept_str,
        defaults={'code': clean_code, 'is_active': True}
    )
    return d_obj


class DepartmentForm(forms.ModelForm):
    """
    Form for creating and updating college offices / departments.
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
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Office duties...'})
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



