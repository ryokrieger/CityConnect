from django.contrib import admin

from .models import City, Neighborhood, Interest, NotificationRecord


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('city_code', 'city_name', 'country')
    search_fields = ('city_name', 'country')


@admin.register(Neighborhood)
class NeighborhoodAdmin(admin.ModelAdmin):
    list_display = ('postal_code', 'area_name', 'city')
    list_filter = ('city',)
    search_fields = ('area_name',)


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ('interest_name', 'category')
    list_filter = ('category',)
    search_fields = ('interest_name',)


@admin.register(NotificationRecord)
class NotificationRecordAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notif_type', 'is_read', 'created_at')
    list_filter = ('notif_type', 'is_read')
    search_fields = ('recipient__username', 'message')
    readonly_fields = ('created_at',)