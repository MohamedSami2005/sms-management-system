import logging
from typing import Dict, Any, List, Tuple
from apps.accounts.models import CustomUser

logger = logging.getLogger('apps.sms')


class StaffFieldMapper:
    """
    Extensible utility for resolving dynamic staff database fields and static values
    for personalized SMS template interpolation.
    """

    # Registry of supported staff database fields: (field_key, display_label)
    SUPPORTED_FIELDS: List[Tuple[str, str]] = [
        ('full_name', 'Staff Name'),
        ('employee_id', 'Employee ID'),
        ('department', 'Department'),
        ('designation', 'Designation / Role'),
        ('email', 'Email'),
        ('mobile', 'Mobile Number'),
        ('username', 'Username'),
    ]

    @classmethod
    def get_supported_fields(cls) -> List[Dict[str, str]]:
        """Returns list of supported staff database fields for UI dropdowns."""
        return [{'key': key, 'label': label} for key, label in cls.SUPPORTED_FIELDS]

    @classmethod
    def resolve_field_value(cls, user: CustomUser, field_key: str) -> str:
        """
        Extracts specific field value from a CustomUser staff instance.
        """
        if not user or not field_key:
            return ""

        if field_key == 'full_name':
            return user.get_full_name() or user.username
        elif field_key == 'employee_id':
            return user.employee_id or ""
        elif field_key == 'department':
            return user.department.name if user.department else ""
        elif field_key == 'designation':
            return user.get_role_display()
        elif field_key == 'email':
            return user.email or ""
        elif field_key == 'mobile':
            return user.phone_number or ""
        elif field_key == 'username':
            return user.username
        
        # Attribute lookup fallback
        return str(getattr(user, field_key, ''))

    @classmethod
    def resolve_variable(cls, user: CustomUser, source_type: str, source_value: str) -> str:
        """
        Resolves a single template variable value for a given user.
        source_type: 'static' or 'field'
        """
        if source_type == 'field':
            return cls.resolve_field_value(user, source_value)
        return str(source_value or '')

    @classmethod
    def resolve_all_variables(
        cls,
        user: CustomUser,
        mapping_config: Dict[str, Dict[str, str]]
    ) -> Dict[str, str]:
        """
        Resolves all template variables for a given user based on mapping config.
        mapping_config format:
        {
            "var_1": {"type": "field", "value": "full_name"},
            "var_2": {"type": "static", "value": "10000"}
        }
        """
        resolved = {}
        for var_key, config in mapping_config.items():
            stype = config.get('type', 'static')
            sval = config.get('value', '')
            resolved[var_key] = cls.resolve_variable(user, stype, sval)
        return resolved
