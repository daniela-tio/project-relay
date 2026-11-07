from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, FormView, ListView, UpdateView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin
from apps.accounts.forms import SignInForm, UserCreateForm, UserSetPasswordForm, UserUpdateForm, is_last_active_admin
from apps.accounts.models import User
from apps.accounts.permissions import RuleRequiredMixin

class SignInView(SuccessMessageMixin, LoginView):
    """Sign-in page. Will show success message once signed in"""
    
    template_name = "accounts/sign_in.html"
    authentication_form = SignInForm
    success_message = "Signed in successfully."
    
class SignOutView(LogoutView):
    """Signs the user out and confirms it with a message"""
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.success(request, "You have been signed out.")
        return response
    
class UserListView(RuleRequiredMixin, ListView):
    """Lists ever user account. Administrators only"""
    
    permission_rule = "can_manage_users"
    model = User
    ordering = ("username",)
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    
class UserCreateView(RuleRequiredMixin, SuccessMessageMixin, CreateView):
    """Creates a user. Administrators Only"""
    
    permission_rule = "can_manage_users"
    form_class = UserCreateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("user_list")
    success_message = "User %(username)s was created."
    
class UserUpdateView(RuleRequiredMixin, SuccessMessageMixin, UpdateView):
    """Edits a users details, role and status. Administrators Only"""
    
    permission_rule = "can_manage_users"
    model = User
    form_class = UserUpdateForm
    template_name = "accounts/user_form.html"
    context_object_name = "target_user"
    success_url = reverse_lazy("user_list")
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["acting_user"] = self.request.user
        return kwargs

    def get_success_message(self, cleaned_data):
        return f"User {self.object.username} was updated."
    
class UserSetPasswordView(RuleRequiredMixin, FormView):
    """Sets a new password for a user. Administrators Only"""
    
    permission_rule = "can_manage_users"
    form_class = UserSetPasswordForm
    template_name = "accounts/user_set_password.html"
    success_url = reverse_lazy("user_list")
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = get_object_or_404(User, pk=self.kwargs["pk"])
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["target_user"] = context["form"].user
        return context
    
    def form_valid(self, form):
        form.save()
        messages.success(self.request, f"Password updated for {form.user.username}.")
        return super().form_valid(form)
    
class UserDeleteView(RuleRequiredMixin, DeleteView):
    """Deletes a user after confirmation. Administrators Only"""
    
    permission_rule = "can_manage_users"
    model = User
    template_name = "accounts/user_confirm_delete.html"
    context_object_name = "target_user"
    success_url = reverse_lazy("user_list")
    
    def form_valid(self, form):
        if self.object == self.request.user:
            messages.error(self.request, "You cannot delete your own account.")
            return redirect("user_list")
        if self.object.is_administrator and is_last_active_admin(self.object):
            messages.error(self.request, "The only active administrator cannot be deleted.")
            return redirect("user_list")
        messages.success(self.request, f"User {self.object.username} was deleted.")
        return super().form_valid(form)
    
            