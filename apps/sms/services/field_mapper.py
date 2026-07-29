import logging
from typing import Dict, Any, List, Tuple, Union
from apps.users.models import Staff
from apps.accounts.models import CustomUser

logger = logging.getLogger('apps.sms')


class StaffFieldMapper:
    """
    Extensible utility for resolving dynamic staff recipient database fields and static values
    for personalized SMS template interpolation.
    """

    # Registry of supported staff recipient fields: (field_key, display_label)
    SUPPORTED_FIELDS: List[Tuple[str, str]] = [
        ('name', 'Staff Name'),
        ('mobile', 'Mobile Number'),
        ('department', 'Department'),
    ]

    @classmethod
    def get_supported_fields(cls) -> List[Dict[str, str]]:
        """Returns list of supported staff recipient fields for UI dropdowns."""
        return [{'key': key, 'label': label} for key, label in cls.SUPPORTED_FIELDS]

    @classmethod
    def resolve_field_value(cls, recipient: Union[Staff, CustomUser], field_key: str) -> str:
        """
        Extracts specific field value from a Staff recipient or CustomUser instance.
        """
        if not recipient or not field_key:
            return ""

        if isinstance(recipient, Staff):
            if field_key in ('name', 'full_name'):
                return recipient.name
            elif field_key in ('mobile', 'phone_number'):
                return recipient.mobile_number
            elif field_key == 'department':
                return recipient.department.name if recipient.department else ""
            return str(getattr(recipient, field_key, ''))
        
        # Fallback for CustomUser
        if field_key in ('name', 'full_name'):
            return recipient.get_full_name() or recipient.username
        elif field_key in ('mobile', 'phone_number'):
            return recipient.phone_number or ""
        elif field_key == 'department':
            return recipient.department.name if recipient.department else ""
        elif field_key == 'employee_id':
            return getattr(recipient, 'employee_id', '') or ""
        elif field_key == 'email':
            return getattr(recipient, 'email', '') or ""
        
        return str(getattr(recipient, field_key, ''))

    @classmethod
    def resolve_variable(cls, recipient: Union[Staff, CustomUser], source_type: str, source_value: str) -> str:
        """
        Resolves a single template variable value for a given staff recipient.
        source_type: 'static' or 'field'
        """
        if source_type == 'field':
            return cls.resolve_field_value(recipient, source_value)
        return str(source_value or '')

    @classmethod
    def resolve_all_variables(
        cls,
        recipient: Union[Staff, CustomUser],
        mapping_config: Dict[str, Dict[str, str]]
    ) -> Dict[str, str]:
        """
        Resolves all template variables for a given recipient based on mapping config.
        """
        resolved = {}
        for var_key, config in mapping_config.items():
            stype = config.get('type', 'static')
            sval = config.get('value', '')
            resolved[var_key] = cls.resolve_variable(recipient, stype, sval)
        return resolved
