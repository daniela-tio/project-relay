from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """Project Relay user. Extends Djangos builtin user role so roles and account details can be added without replacing the model later."""
    