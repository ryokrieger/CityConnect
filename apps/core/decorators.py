"""Decorator Pattern — view-level access control and login throttling.

Decorators compose from the outside in, e.g.::

    @login_required_custom
    @admin_required
    def admin_dashboard(request): ...
"""
from functools import wraps

from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect


def login_required_custom(view_func):
    """Ensures the user is authenticated before accessing the view."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to continue.')
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
    """Ensures a mutual friendship exists between request.user and the target.

    The target id is read from the URL kwargs (`friend_id` or `user_id`).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from apps.social.models import Friendship

        friend_id = kwargs.get('friend_id') or kwargs.get('user_id')
        if friend_id is None or not Friendship.objects.are_friends(request.user.id, friend_id):
            messages.error(request, 'You must be friends to access this.')
            return redirect('social:friends')
        return view_func(request, *args, **kwargs)
    return wrapper


def group_member_required(view_func):
    """Ensures the current user is a member of the target group (`group_id`)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from apps.groups.models import GroupMembership

        group_id = kwargs.get('group_id')
        if not GroupMembership.objects.filter(user=request.user, group_id=group_id).exists():
            return redirect('groups:list')
        return view_func(request, *args, **kwargs)
    return wrapper


# --- Login rate limiting ----------------------------------------------------
# Counters live in Django's cache (a database table in this project, so every
# serverless instance shares them). The decorator only *checks*; the login
# view calls the two helpers below to record failures and clear the counter.

def _attempt_key(username):
    return f'login_attempts:{(username or "").strip().lower()}'


def register_failed_attempt(username, window_seconds=900):
    """Increment the failure counter for `username`; the TTL starts on the first failure."""
    key = _attempt_key(username)
    cache.add(key, 0, timeout=window_seconds)
    try:
        return cache.incr(key)
    except ValueError:  # key expired between add() and incr()
        cache.set(key, 1, timeout=window_seconds)
        return 1


def reset_attempts(username):
    """Clear the failure counter after a successful login."""
    cache.delete(_attempt_key(username))


def rate_limited(max_attempts=5, window_seconds=900):
    """Blocks further attempts once `max_attempts` failures occur within `window_seconds`.

    The view must call ``register_failed_attempt(username, window_seconds)`` on
    every failed login and ``reset_attempts(username)`` on success.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.method == 'POST':
                key = _attempt_key(request.POST.get('username', ''))
                if cache.get(key, 0) >= max_attempts:
                    messages.error(
                        request,
                        'Too many failed login attempts. Please try again in 15 minutes.',
                    )
                    return redirect('accounts:login')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator