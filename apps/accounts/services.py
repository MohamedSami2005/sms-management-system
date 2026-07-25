import logging
from typing import Optional
from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest
from .models import CustomUser

logger = logging.getLogger('django')


class AuthService:
    """
    Service layer providing clean business logic for authentication, security logging, and session control.
    """

    @staticmethod
    def login_user(request: HttpRequest, username: str, password: str, remember_me: bool = True) -> Optional[CustomUser]:
        """
        Authenticates user, creates session, configures 'Remember Me' duration, and logs outcome.
        """
        user = authenticate(request, username=username, password=password)
        if user and user.is_active:
            login(request, user)
            
            # Remember Me session expiry setup: 2 weeks (1,209,600 seconds) vs Browser Close (0)
            if remember_me:
                request.session.set_expiry(1209600)
            else:
                request.session.set_expiry(0)

            logger.info(f"AUTH_SUCCESS | Username: '{username}' | Role: '{user.role}' | IP: {request.META.get('REMOTE_ADDR')}")
            return user
        else:
            logger.warning(f"AUTH_FAILURE | Failed login attempt for username: '{username}' | IP: {request.META.get('REMOTE_ADDR')}")
            return None

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
