from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    GENDER_CHOICES = [('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')]

    # Unique at the database level; the signup form also compares case-insensitively.
    email = models.EmailField('email address', unique=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    city = models.ForeignKey(
        'core.City', null=True, blank=True, on_delete=models.SET_NULL, related_name='residents'
    )
    neighborhood = models.ForeignKey(
        'core.Neighborhood', null=True, blank=True, on_delete=models.SET_NULL, related_name='residents'
    )
    interests = models.ManyToManyField('core.Interest', through='UserInterest', blank=True)
    is_restricted = models.BooleanField(default=False)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['city'], name='user_city_idx'),
            models.Index(fields=['neighborhood'], name='user_neighborhood_idx'),
        ]

    def __str__(self):
        return self.username

    def clean(self):
        super().clean()
        if self.neighborhood_id and self.city_id and self.neighborhood.city_id != self.city_id:
            raise ValidationError({'neighborhood': 'This neighborhood does not belong to the selected city.'})


class UserInterest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    interest = models.ForeignKey('core.Interest', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'interest')

    def __str__(self):
        return f'{self.user_id} → {self.interest_id}'