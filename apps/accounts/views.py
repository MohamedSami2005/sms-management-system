from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordChangeView,
    PasswordResetView, PasswordResetDoneView,
    PasswordResetConfirmView, PasswordResetCompleteView
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect

from .forms import (
    CustomLoginForm, UserProfileForm, CustomPasswordChangeForm,
    CustomPasswordResetForm, CustomSetPasswordForm
)
from .services import AuthService


class UserLoginView(LoginView):
    """
    Handles user authentication, remember me persistent sessions, and redirect upon login.
    """
    template_name = 'accounts/login.html'
    form_class = CustomLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('dashboard:home')

    def form_valid(self, form):
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
        remember_me = form.cleaned_data.get('remember_me', True)

        user = AuthService.login_user(self.request, username, password, remember_me=remember_me)
        if user:
            messages.success(self.request, f"Welcome back, {user.get_full_name() or user.username}!")
            return redirect(self.get_success_url())
        else:
            messages.error(self.request, "Invalid username or password. Please check your credentials.")
            return self.form_invalid(form)


class UserLogoutView(LogoutView):
    """
    Logs out the current user session.
    """
    next_page = reverse_lazy('accounts:login')

    def dispatch(self, request, *args, **kwargs):
        AuthService.logout_user(request)
        messages.info(request, "You have been successfully logged out.")
        return super().dispatch(request, *args, **kwargs)


class UserProfileView(LoginRequiredMixin, UpdateView):
    """
    Displays and updates staff user profile details.
    """
    template_name = 'accounts/profile.html'
    form_class = UserProfileForm
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Your profile details have been successfully updated.")
        return super().form_valid(form)


class UserPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """
    Allows authenticated users to update their account password.
    """
    template_name = 'accounts/change_password.html'
    form_class = CustomPasswordChangeForm
    success_url = reverse_lazy('accounts:profile')

    def form_valid(self, form):
        messages.success(self.request, "Your password has been changed successfully.")
        return super().form_valid(form)


# --- Password Reset Workflow Views ---

class CustomPasswordResetView(PasswordResetView):
    template_name = 'accounts/forgot_password.html'
    form_class = CustomPasswordResetForm
    email_template_name = 'accounts/email/password_reset_email.html'
    subject_template_name = 'accounts/email/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    form_class = CustomSetPasswordForm
    success_url = reverse_lazy('accounts:password_reset_complete')


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'
