from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    """FloodSense user with email as the only login identifier."""

    username = None
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=150)
    home_barangay = models.CharField(max_length=150, blank=True)
    disclaimer_version_accepted = models.CharField(max_length=50, blank=True)
    disclaimer_accepted_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    def __str__(self) -> str:
        return self.email

