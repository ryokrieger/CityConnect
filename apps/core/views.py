from django.shortcuts import render
from django.views.decorators.http import require_safe


@require_safe
def home(request):
    """Public landing page."""
    return render(request, 'core/home.html')


@require_safe
def about(request):
    """Public about page."""
    return render(request, 'core/about.html')