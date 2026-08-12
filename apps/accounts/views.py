from django.contrib import messages
from django.contrib.auth import login, logout
from django.core.cache import cache
from django.shortcuts import redirect, render

from apps.core.decorators import login_required_custom, rate_limited
from apps.core.services import services

from .forms import LoginForm, SignupForm

LOGIN_ATTEMPT_WINDOW_SECONDS = 900  # 15 minutes — matches @rate_limited default


def index_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    return redirect('accounts:login')


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            services.email.send_welcome(user)
            login(request, user)
            messages.success(request, f'Welcome to CityConnect, {user.username}!')
            return redirect('accounts:dashboard')
    else:
        form = SignupForm()

    return render(request, 'accounts/signup.html', {'form': form})


@rate_limited(max_attempts=5, window_seconds=LOGIN_ATTEMPT_WINDOW_SECONDS)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        attempts_key = f"login_attempts:{request.POST.get('username', '')}"

        if form.is_valid():
            user = form.get_user()

            if user.is_restricted:
                messages.error(request, 'Your account has been restricted. Please contact support.')
                return render(request, 'accounts/login.html', {'form': form})

            cache.delete(attempts_key)
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('accounts:dashboard')
        else:
            cache.set(attempts_key, cache.get(attempts_key, 0) + 1, LOGIN_ATTEMPT_WINDOW_SECONDS)
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('accounts:login')


@login_required_custom
def dashboard_view(request):
    return render(request, 'accounts/dashboard.html', {'user': request.user})