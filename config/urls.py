from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include('apps.accounts.urls')),      # signup, login, logout, dashboard, profile
    path('social/', include('apps.social.urls')),
    path('messaging/', include('apps.messaging.urls')),
    path('groups/', include('apps.groups.urls')),
    path('events/', include('apps.events.urls')),
    path('', include('apps.core.urls')),           # search, notifications
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)