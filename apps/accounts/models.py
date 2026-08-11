from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class User(AbstractUser):
    GENDER_CHOICES = [('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')]

    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    city = models.ForeignKey('core.City', null=True, blank=True, on_delete=models.SET_NULL)
    neighborhood = models.ForeignKey('core.Neighborhood', null=True, blank=True, on_delete=models.SET_NULL)
    interests = models.ManyToManyField('core.Interest', through='UserInterest', blank=True)
    is_restricted = models.BooleanField(default=False)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['city']),
            models.Index(fields=['neighborhood']),
        ]

    def __str__(self):
        return self.username


class UserInterest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    interest = models.ForeignKey('core.Interest', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'interest')

    def __str__(self):
        return f'{self.user.username} -> {self.interest.interest_name}'


class UserRating(models.Model):
    rater = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_given')
    ratee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_received')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)

    class Meta:
        unique_together = ('rater', 'ratee')

    def __str__(self):
        return f'{self.rater.username} -> {self.ratee.username}: {self.rating}'