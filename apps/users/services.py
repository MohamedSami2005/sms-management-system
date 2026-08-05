import logging
from typing import Tuple
from django.utils import timezone
from apps.users.models import Department, Office, Staff


class OfficeService:
    """
    Business service layer managing administrative offices.
    """

    @staticmethod
    def delete_or_deactivate(office: Office) -> Tuple[bool, str]:
        user_count = office.users.filter(is_deleted=False).count()
        if user_count > 0:
            office.is_active = False
            office.save(update_fields=['is_active'])
            logger.info(f"OFFICE_SOFT_DELETE | Office '{office.code}' deactivated because {user_count} users are assigned.")
            return True, f"Office '{office.name}' was deactivated because {user_count} staff user(s) are assigned."
        else:
            off_name = office.name
            office.delete()
            logger.info(f"OFFICE_HARD_DELETE | Office '{off_name}' permanently deleted.")
            return True, f"Office '{off_name}' was permanently deleted."

    @staticmethod
    def toggle_status(office: Office) -> bool:
        office.is_active = not office.is_active
        office.save(update_fields=['is_active'])
        logger.info(f"OFFICE_STATUS_TOGGLE | Office '{office.code}' active status set to {office.is_active}.")
        return office.is_active
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
        user_count = department.users.filter(is_deleted=False).count()
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
    Business service layer managing staff accounts, roles, scope-based permissions,
    account locking, password resets, and soft deletion.
    """

    @staticmethod
    def create_user(form: any, created_by: CustomUser) -> CustomUser:
        user = form.save(commit=False)
        password = form.cleaned_data.get('password')
        user.set_password(password)
        user.created_by = created_by
        user.save()
        form.save_m2m()
        logger.info(f"USER_CREATE | New user '{user.username}' (Role: {user.role}) created by '{created_by.username}'.")
        return user

    @staticmethod
    def update_user(user: CustomUser, form: any, updated_by: CustomUser) -> CustomUser:
        updated_user = form.save()
        logger.info(f"USER_UPDATE | Account '{updated_user.username}' updated by Administrator '{updated_by.username}'.")
        return updated_user

    @staticmethod
    def toggle_user_status(user: CustomUser, toggled_by: CustomUser) -> bool:
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        action = "activated" if user.is_active else "deactivated"
        logger.info(f"USER_STATUS_TOGGLE | User '{user.username}' was {action} by '{toggled_by.username}'.")
        return user.is_active

    @staticmethod
    def toggle_user_lock(user: CustomUser, locked_by: CustomUser) -> bool:
        user.is_locked = not user.is_locked
        if user.is_locked:
            user.failed_login_attempts = 0
        user.save(update_fields=['is_locked', 'failed_login_attempts'])
        action = "locked" if user.is_locked else "unlocked"
        logger.info(f"USER_LOCK_TOGGLE | User account '{user.username}' was {action} by '{locked_by.username}'.")
        return user.is_locked

    @staticmethod
    def soft_delete_user(user: CustomUser, deleted_by: CustomUser) -> None:
        user.is_deleted = True
        user.is_active = False
        user.save(update_fields=['is_deleted', 'is_active'])
        logger.info(f"USER_SOFT_DELETE | Account '{user.username}' soft-deleted by '{deleted_by.username}'.")

    @staticmethod
    def reset_password(user: CustomUser, new_password: str, reset_by: CustomUser, must_change_password: bool = True) -> None:
        user.set_password(new_password)
        user.must_change_password = must_change_password
        user.password_changed_at = timezone.now()
        user.save(update_fields=['password', 'must_change_password', 'password_changed_at'])
        logger.info(f"ADMIN_PASSWORD_RESET | Password for user '{user.username}' reset by Administrator '{reset_by.username}'.")
