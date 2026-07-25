import logging
from typing import Tuple
from apps.users.models import Department
from apps.accounts.models import CustomUser

logger = logging.getLogger('django')


class DepartmentService:
    """
    Business service layer managing college departments.
    """

    @staticmethod
    def delete_or_deactivate(department: Department) -> Tuple[bool, str]:
        """
        Deletes department if no users are associated; soft-deactivates if users are assigned.
        """
        user_count = department.users.count()
        if user_count > 0:
            department.is_active = False
            department.save(update_fields=['is_active'])
            logger.info(f"DEPT_SOFT_DELETE | Department '{department.code}' deactivated because {user_count} users are assigned.")
            return True, f"Department '{department.name}' was deactivated because {user_count} staff user(s) are assigned."
        else:
            dept_name = department.name
            department.delete()
            logger.info(f"DEPT_HARD_DELETE | Department '{dept_name}' permanently deleted.")
            return True, f"Department '{dept_name}' was permanently deleted."

    @staticmethod
    def toggle_status(department: Department) -> bool:
        department.is_active = not department.is_active
        department.save(update_fields=['is_active'])
        logger.info(f"DEPT_STATUS_TOGGLE | Department '{department.code}' active status set to {department.is_active}.")
        return department.is_active


class UserService:
    """
    Business service layer managing staff accounts, roles, and password resets.
    """

    @staticmethod
    def create_user(form: any, created_by: CustomUser) -> CustomUser:
        user = form.save(commit=False)
        password = form.cleaned_data.get('password')
        user.set_password(password)
        user.save()
        form.save_m2m()
        logger.info(f"USER_CREATE | New user '{user.username}' ({user.role}) created by '{created_by.username}'.")
        return user

    @staticmethod
    def toggle_user_status(user: CustomUser) -> bool:
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        action = "activated" if user.is_active else "deactivated/locked"
        logger.info(f"USER_STATUS_TOGGLE | User '{user.username}' was {action}.")
        return user.is_active

    @staticmethod
    def reset_password(user: CustomUser, new_password: str) -> None:
        user.set_password(new_password)
        user.save(update_fields=['password'])
        logger.info(f"ADMIN_PASSWORD_RESET | Password reset for user '{user.username}'.")
