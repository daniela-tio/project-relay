from functools import wraps
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

def rule_required(rule):
    """Decorator for function based views. 
    
    The user must be signed in and the named rule must be true. Otherwise 403 Forbidden is returned
    """
    
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not getattr(request.user, rule, False):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator

class RuleRequiredMixin(LoginRequiredMixin):
    """Mixin for class based views. Sets permission_rule to a User property name."""
    
    permission_rule = None
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permissions() # Redirects to sign in
        if not getattr(request.user, self.permission_rule, False):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)