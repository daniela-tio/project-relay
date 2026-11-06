from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin

class SignInView(SuccessMessageMixin, LoginView):
    """Sign-in page. Will show success message once signed in"""
    
    template_name = "accounts/sign_in.html"
    success_message = "Signed in successfully"
    
class SignOutView(LogoutView):
    """Signs the user out and confirms it with a message"""
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.success(request, "You have been signed out.")
        return response