from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User, UserInterest, UserRating


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('username', 'email', 'city', 'neighborhood', 'is_restricted', 'is_staff')
    list_filter = ('is_restricted', 'is_staff', 'is_active', 'city')
    search_fields = ('username', 'email')

    fieldsets = DjangoUserAdmin.fieldsets + (
        ('CityConnect Profile', {
            'fields': ('gender', 'city', 'neighborhood', 'avatar', 'bio', 'is_restricted'),
        }),
    )


@admin.register(UserInterest)
class UserInterestAdmin(admin.ModelAdmin):
    list_display = ('user', 'interest')
    list_filter = ('interest',)
    search_fields = ('user__username',)


@admin.register(UserRating)
class UserRatingAdmin(admin.ModelAdmin):
    list_display = ('rater', 'ratee', 'rating')
    list_filter = ('rating',)
    search_fields = ('rater__username', 'ratee__username')