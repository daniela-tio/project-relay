from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm, UserCreationForm
from apps.core.forms import TablerFormMixin

User = get_user_model()

def is_last_active_admin(user):
    """True if there are no other admin users other than this user"""
    others = User.objects.filter(
        is_active = True, role = User.Role.ADMINISTRATOR
    ).exclude(pk=user.pk)
    return not others.exists()


class SignInForm(AuthenticationForm):
    """Sign in form that ignores the capitalisation of usernames"""
    
    def clean_username(self):
        return User.normalize_username(self.cleaned_data["username"])
    
class UserCreateForm(TablerFormMixin, UserCreationForm):
    """Form for an Administrator to create a user account"""
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "role")
        
    def clean_username(self):
        username = User.normalize_username(self.cleaned_data["username"])
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username
    
class UserUpdateForm(TablerFormMixin, forms.ModelForm):
    """Form for an Administrator to update a users details"""
    
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "role", "is_active")
        labels = {"is_active": "Account active"}
        
    def __init__(self, *args, acting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acting_user = acting_user
        
    def clean(self):
        cleaned_data = super().clean()
        user = self.instance
        losing_admin = user.is_administrator and (
            cleaned_data.get("role") != User.Role.ADMINISTRATOR or not cleaned_data.get("is_active")
        )
        if losing_admin and user == self.acting_user:
            raise forms.ValidationError("You cannot remove your own administrator access.")
        if losing_admin and is_last_active_admin(user):
            raise forms.ValidationError("This is the only active administrator. Their access cannot be removed.")
        
        return cleaned_data

class UserSetPasswordForm(TablerFormMixin, SetPasswordForm):
    """Lets Administrators set a new password for users"""