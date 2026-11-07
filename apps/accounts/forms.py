from django.contrib.auth.forms import AuthenticationForm

class SignInForm(AuthenticationForm):
    
    def clean_username(self):
        return self.cleaned_username["username"].lower()