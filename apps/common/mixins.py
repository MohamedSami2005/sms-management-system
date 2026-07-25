from typing import List, Union
from functools import wraps
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages


class RoleRequiredMixin(AccessMixin):
    """
    CBV mixin that verifies the current user has one of the allowed roles.
    """
    allowed_roles: List[str] = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        user_role = getattr(request.user, 'role', None)
        if self.allowed_roles and user_role not in self.allowed_roles:
            messages.error(request, "Access Denied: You do not have permission to access this page.")
            raise PermissionDenied("You do not have permission to access this resource.")

        return super().dispatch(request, *args, **kwargs)


def role_required(allowed_roles: Union[List[str], str]):
    """
    FBV decorator to enforce role requirements.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            user_role = getattr(request.user, 'role', None)
            if user_role not in allowed_roles:
                messages.error(request, "Access Denied: You do not have permission to perform this action.")
                raise PermissionDenied("You do not have permission to access this resource.")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


class CustomPermissionRequiredMixin(AccessMixin):
    """
    CBV mixin that verifies the user has specific Django permissions.
    """
    permission_required: Union[List[str], str] = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        perms = [self.permission_required] if isinstance(self.permission_required, str) else self.permission_required
        if not request.user.has_perms(perms):
            messages.error(request, "Access Denied: Missing required security permission.")
            raise PermissionDenied("Missing required permission.")

        return super().dispatch(request, *args, **kwargs)
