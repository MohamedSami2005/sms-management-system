from typing import Optional
from django.db.models import QuerySet, Q
from apps.users.models import Office


def is_global_admin(user) -> bool:
    """
    Returns True if the user has unrestricted global administrative access across all offices.
    Superusers, users with role 'ADMIN', and users assigned to office with code 'ADMIN' or 'ADMIN_MGMT' have global access.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'role', '') == 'ADMIN':
        return True
    user_office = getattr(user, 'office', None) or getattr(user, 'department', None)
    if user_office:
        code_upper = getattr(user_office, 'code', '').upper()
        name_lower = getattr(user_office, 'name', '').lower()
        if code_upper in ['ADMIN', 'ADMIN_MGMT'] or name_lower in ['admin management', 'administrator', 'admin']:
            return True
    return False


def get_scoped_queryset(user, queryset: QuerySet, field_name: str = 'office') -> QuerySet:
    """
    Filters a model QuerySet based on the authenticated user's assigned Office scope.
    - Global Administrators & Superusers receive the full unrestricted QuerySet.
    - Scoped users receive a QuerySet filtered strictly by their assigned Office.
    - Unauthenticated or office-less non-admin users receive an empty QuerySet for security.
    """
    if is_global_admin(user):
        return queryset

    user_office = getattr(user, 'office', None) or getattr(user, 'department', None)
    if not user_office:
        return queryset.none()

    if hasattr(queryset.model, 'allowed_offices'):
        return queryset.filter(Q(allowed_offices=user_office) | Q(office=user_office)).distinct()

    if hasattr(queryset.model, 'office'):
        return queryset.filter(office=user_office)

    if hasattr(queryset.model, 'department'):
        return queryset.filter(department=user_office)

    filter_kwargs = {field_name: user_office}
    return queryset.filter(**filter_kwargs)


def get_user_office(user) -> Optional[Office]:
    """
    Returns the Office assigned to the given application login user.
    """
    if not user or not user.is_authenticated:
        return None
    return getattr(user, 'office', None) or getattr(user, 'department', None)
