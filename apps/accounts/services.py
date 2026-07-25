import logging
from typing import Optional
from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest
from .models import CustomUser

logger = logging.getLogger('django')


class AuthService:
    """
    Service layer for handling authentication and session management.
    """

    @staticmethod
    def login_user(request: HttpRequest, username: str, password: str) -> Optional[CustomUser]:
        user = authenticate(request, username=username, password=password)
        if user and user.is_active:
            login(request, user)
            logger.info(f"User '{username}' logged in successfully.")
            return user
        logger.warning(f"Failed login attempt for username '{username}'.")
        return None

    @staticmethod
    def logout_user(request: HttpRequest) -> None:
        if request.user.is_authenticated:
            logger.info(f"User '{request.user.username}' logged out.")
        logout(request)
