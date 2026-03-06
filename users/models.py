"""User models for ZCA BnB."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model for ZCA BnB.
    Extends Django's AbstractUser with additional fields.
    """

    class UserType(models.TextChoices):
        GUEST = 'guest', 'Guest'
        HOST = 'host', 'Host'
        BOTH = 'both', 'Both'

    class HostStatus(models.TextChoices):
        NOT_APPLIED = 'not_applied', 'Not Applied'
        PENDING = 'pending', 'Pending Approval'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    user_type = models.CharField(
        max_length=10,
        choices=UserType.choices,
        default=UserType.GUEST,
    )
    phone_number = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True,
    )
    bio = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)

    # Host approval workflow
    host_status = models.CharField(
        max_length=20,
        choices=HostStatus.choices,
        default=HostStatus.NOT_APPLIED,
        help_text='Admin approval status for hosting privileges',
    )
    host_application_date = models.DateTimeField(null=True, blank=True)
    host_approved_date = models.DateTimeField(null=True, blank=True)
    host_rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email or self.username

    @property
    def is_host(self):
        """User is a host only if approved by admin."""
        return (
            self.user_type in [self.UserType.HOST, self.UserType.BOTH] and
            self.host_status == self.HostStatus.APPROVED
        )

    @property
    def is_guest(self):
        return self.user_type in [self.UserType.GUEST, self.UserType.BOTH]

    @property
    def can_create_listing(self):
        """Check if user can create listings (must be approved host)."""
        return self.is_host


class GuestID(models.Model):
    """
    Guest identification document for booking verification.
    Images are stored in private R2 bucket, accessed via proxy endpoint.
    """

    class IDType(models.TextChoices):
        PASSPORT = 'passport', 'Passport'
        DRIVERS_LICENSE = 'drivers_license', "Driver's License"
        NATIONAL_ID = 'national_id', 'National ID'
        OTHER = 'other', 'Other Government ID'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='guest_ids',
    )
    r2_key = models.CharField(
        max_length=500,
        help_text='Private R2 object key (not public URL)',
    )
    id_type = models.CharField(
        max_length=50,
        choices=IDType.choices,
        default=IDType.NATIONAL_ID,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(
        default=False,
        help_text='Has this ID been verified by admin/host',
    )
    is_primary = models.BooleanField(
        default=False,
        help_text='Is this the current active ID for the user',
    )

    class Meta:
        db_table = 'guest_ids'
        ordering = ['-uploaded_at']
        verbose_name = 'Guest ID'
        verbose_name_plural = 'Guest IDs'

    def __str__(self):
        return f"{self.user.email} - {self.get_id_type_display()}"

    def save(self, *args, **kwargs):
        # If this is being set as primary, unset others
        if self.is_primary:
            GuestID.objects.filter(user=self.user, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)
