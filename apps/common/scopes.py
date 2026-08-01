from typing import Optional
from django.db.models import QuerySet
from apps.users.models import Department


def is_global_admin(user) -> bool:
    """
    Returns True if the user has unrestricted global administrative access across all offices.
    Superusers, users with role 'ADMIN', and users assigned to 'Admin Management' office have global access.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'role', '') == 'ADMIN':
        return True
    if getattr(user, 'department', None):
        name_lower = user.department.name.lower()
        code_upper = user.department.code.upper()
        if name_lower in ['admin management', 'administrator', 'admin'] or code_upper in ['ADMIN_MGMT', 'ADMIN']:
            return True
    return False


def get_scoped_queryset(user, queryset: QuerySet, field_name: str = 'department') -> QuerySet:
    """
    Filters a model QuerySet based on the authenticated user's assigned Office (Department) scope.
    - Global Administrators & Superusers receive the full unrestricted QuerySet.
    - Scoped users receive a QuerySet filtered strictly by their assigned Office.
    - Unauthenticated or office-less non-admin users receive an empty QuerySet for security.
    """
    if is_global_admin(user):
        return queryset

    user_office = getattr(user, 'department', None)
    if not user_office:
        return queryset.none()

    if hasattr(queryset.model, 'allowed_offices') and field_name == 'department':
        return queryset.filter(allowed_offices=user_office).distinct()

    filter_kwargs = {field_name: user_office}
    return queryset.filter(**filter_kwargs)


def get_user_office(user) -> Optional[Department]:
    """
    Returns the Department (Office) assigned to the given application login user.
    """
    if not user or not user.is_authenticated:
        return None
    return getattr(user, 'department', None)
