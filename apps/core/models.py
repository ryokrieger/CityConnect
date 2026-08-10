from django.conf import settings
from django.db import models


class City(models.Model):
    city_code = models.IntegerField(primary_key=True)
    city_name = models.CharField(max_length=50)
    country = models.CharField(max_length=50)

    class Meta:
        ordering = ['city_name']

    def __str__(self):
        return self.city_name


class Neighborhood(models.Model):
    postal_code = models.IntegerField(primary_key=True)
    area_name = models.CharField(max_length=100)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='neighborhoods')

    class Meta:
        ordering = ['area_name']

    def __str__(self):
        return f'{self.area_name} ({self.city.city_name})'


class Interest(models.Model):
    interest_name = models.CharField(max_length=100)
    category = models.CharField(max_length=50)

    class Meta:
        ordering = ['category', 'interest_name']

    def __str__(self):
        return self.interest_name


class NotificationRecord(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notif_type = models.CharField(max_length=50)
    message = models.TextField()
    url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f'{self.notif_type} -> {self.recipient}'