import logging
from typing import Optional, Tuple
from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest
from django.utils import timezone
from .models import CustomUser

logger = logging.getLogger('django')


class AuthService:
    """
    Service layer providing clean business logic for authentication, security logging,
    account locking, failed attempt counters, and session control.
    """

    @staticmethod
    def login_user(request: HttpRequest, username: str, password: str, remember_me: bool = True) -> Tuple[Optional[CustomUser], str]:
        """
        Authenticates user, checks lock status, manages failed attempts, sets 'Remember Me' session expiry,
        and returns (user_instance, error_message).
        """
        user_qs = CustomUser.objects.filter(username__iexact=username, is_deleted=False)
        target_user = user_qs.first()

        if target_user and target_user.is_locked:
            logger.warning(f"AUTH_LOCKED_ATTEMPT | Locked account attempt for username: '{username}'")
            return None, "Account is locked due to security policy. Please contact an Administrator."

        user = authenticate(request, username=username, password=password)
        if user and user.is_active and not user.is_deleted:
            # Reset failed login counter on success
            if user.failed_login_attempts > 0:
                user.failed_login_attempts = 0
                user.save(update_fields=['failed_login_attempts'])

            login(request, user)
            
            # Remember Me session expiry setup: 2 weeks (1,209,600 seconds) vs Browser Close (0)
            if remember_me:
                request.session.set_expiry(1209600)
            else:
                request.session.set_expiry(0)

            logger.info(f"AUTH_SUCCESS | Username: '{username}' | Role: '{user.role}' | IP: {request.META.get('REMOTE_ADDR')}")
            return user, ""
        else:
            if target_user:
                target_user.failed_login_attempts += 1
                if target_user.failed_login_attempts >= 5:
                    target_user.is_locked = True
                    logger.warning(f"AUTH_AUTO_LOCK | Account '{username}' locked after 5 failed login attempts.")
                target_user.save(update_fields=['failed_login_attempts', 'is_locked'])

            logger.warning(f"AUTH_FAILURE | Failed login attempt for username: '{username}' | IP: {request.META.get('REMOTE_ADDR')}")
            return None, "Invalid username or password. Please check your credentials."

    @staticmethod
    def logout_user(request: HttpRequest) -> None:
        """
        Safely logs out current user and flushes session data.
        """
        if request.user.is_authenticated:
            logger.info(f"AUTH_LOGOUT | User: '{request.user.username}' logged out.")
        logout(request)

    @staticmethod
    def update_user_profile(user: CustomUser, first_name: str, last_name: str, email: str, phone_number: str) -> CustomUser:
        """
        Updates user profile details.
        """
        user.first_name = first_name.strip()
        user.last_name = last_name.strip()
        user.email = email.strip().lower()
        user.phone_number = phone_number.strip()
        user.save(update_fields=['first_name', 'last_name', 'email', 'phone_number'])
        logger.info(f"PROFILE_UPDATE | User: '{user.username}' updated profile information.")
        return user
