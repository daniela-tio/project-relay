from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """Project Relay users have one of three roles"""
    
    class Role(models.TextChoices):
        ADMINISTRATOR = "admin", "Administrator"
        PROJECT_MANAGER = "pm", "Project Manager"
        TECHNICIAN = "tech", "Technician"
        
    role = models.CharField(
        max_length = 10, choices = Role.choices, default = Role.TECHNICIAN
    )
    
    @classmethod
    def normalize_username(cls, username):
        """usernames are stored and compared in lowercase"""
        return super().normalize_username(username).lower()
    
    def save(self, *args, **kwargs):
        self.username = self.normalize_username(self.username)
        super().save(*args, **kwargs)
    
    # Role checks
    @property
    def is_administrator(self):
        return self.is_superuser or self.role == self.Role.ADMINISTRATOR
    
    @property
    def is_project_manager(self):
        return self.role == self.Role.PROJECT_MANAGER
    
    # Permission Rules
    @property
    def can_manage_users(self):
        return self.is_administrator
    
    @property
    def can_manage_portfolio(self):
        return self.is_administrator
    
    @property
    def can_edit_project_data(self):
        return self.is_administrator or self.is_project_manager
    
    @property
    def can_delete_project_data(self):
        return self.is_administrator or self.is_project_manager
    
    @property
    def can_update_tasks(self):
        return True # Every role is able to update tasks
    
    