"""
Design Pattern 1 — Decorator Pattern
Applied to: view-level access control.

Each decorator wraps a view function and enforces one access rule before
letting the request through. They compose (see usage in view files), so a
view can stack e.g. @login_required_custom + @group_member_required.
"""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def login_required_custom(view_func):
    """Ensures the user is authenticated before accessing the view."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to continue.")
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    """Ensures the user has admin (staff) privileges."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect('accounts:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def friendship_required(view_func):
    """Ensures a mutual friendship exists between request.user and the target."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from apps.social.models import Friendship
        friend_id = kwargs.get('friend_id') or kwargs.get('user_id')
        if not Friendship.objects.are_friends(request.user.id, friend_id):
            messages.error(request, "You must be friends to access this.")
            return redirect('social:friends')
        return view_func(request, *args, **kwargs)
    return wrapper


def group_member_required(view_func):
    """Ensures the current user is a member of the target group."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from apps.groups.models import GroupMembership
        group_id = kwargs.get('group_id')
        if not GroupMembership.objects.filter(user=request.user, group_id=group_id).exists():
            return redirect('groups:list')
        return view_func(request, *args, **kwargs)
    return wrapper


def rate_limited(max_attempts=5, window_seconds=900):
    """
    Blocks further POST attempts once `max_attempts` failures occur within
    `window_seconds`, using Django's cache framework as the counter store.

    The view itself is responsible for incrementing/clearing the cache key
    (`login_attempts:<username>`) on failed/successful attempts — this
    decorator only checks the current count before letting the request in.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.core.cache import cache
            if request.method == 'POST':
                key = f"login_attempts:{request.POST.get('username', '')}"
                if cache.get(key, 0) >= max_attempts:
                    messages.error(request, "Too many failed login attempts. Please try again in 15 minutes.")
                    return redirect('accounts:login')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator