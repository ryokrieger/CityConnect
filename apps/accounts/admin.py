from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User, UserInterest


class UserInterestInline(admin.TabularInline):
    model = UserInterest
    extra = 0


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('username', 'email', 'city', 'is_restricted', 'is_staff')
    list_filter = DjangoUserAdmin.list_filter + ('is_restricted', 'city')
    list_select_related = ('city',)
    inlines = [UserInterestInline]
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('CityConnect profile', {
            'fields': ('gender', 'city', 'neighborhood', 'bio', 'avatar', 'is_restricted'),
        }),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (None, {'fields': ('email', 'gender', 'city', 'neighborhood')}),
    )