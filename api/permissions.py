"""Scope-based permissions for REST API v1."""

from django.conf import settings
from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.agent_services import account_allowed_scopes, can_agent_write, is_write_scope


def token_has_scope(token, scope):
    return scope in (getattr(token, "scopes", None) or [])


def scope_allowed(token, user, scope):
    """Token scope AND live account scopes must both grant access."""
    if token is None:
        return False
    return token_has_scope(token, scope) and scope in account_allowed_scopes(user)


def request_has_scope(request, scope):
    """Check scope for token auth; session auth bypasses scope checks."""
    if request.method in SAFE_METHODS:
        return True
    user = request.user
    if not user or not user.is_authenticated:
        return False
    token = getattr(request, "api_token", None)
    if token is None:
        return True
    if is_write_scope(scope) and not can_agent_write(user):
        return False
    return scope_allowed(token, user, scope)


class IsReadOnlyOrAuthenticated(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)


class HasApiScope(BasePermission):
    """Require a specific scope for write operations when using bearer tokens."""

    def __init__(self, scope):
        self.scope = scope

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if not getattr(settings, "API_WRITES_ENABLED", True):
            return False
        return request_has_scope(request, self.scope)


def scoped_permission(scope):
    """Return a permission class for DRF permission_classes (not an instance)."""
    class _ScopedPermission(HasApiScope):
        def __init__(self):
            super().__init__(scope)

    _ScopedPermission.__name__ = f"HasApiScope_{scope.replace(':', '_')}"
    return _ScopedPermission
