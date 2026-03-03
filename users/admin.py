"""User admin configuration with host approval workflow."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from unfold.admin import ModelAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    """Admin configuration for custom User model with host approval."""

    list_display = [
        'username',
        'email',
        'first_name',
        'last_name',
        'user_type',
        'host_status',
        'is_verified',
        'is_staff',
    ]
    list_filter = ['user_type', 'host_status', 'is_verified', 'is_staff', 'is_active']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['-created_at']
    actions = ['approve_hosts', 'reject_hosts']

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Profile', {
            'fields': ('user_type', 'phone_number', 'profile_picture', 'bio', 'is_verified'),
        }),
        ('Host Approval', {
            'fields': (
                'host_status',
                'host_application_date',
                'host_approved_date',
                'host_rejection_reason',
            ),
            'classes': ('collapse',),
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Profile', {
            'fields': ('email', 'user_type', 'phone_number'),
        }),
    )

    @admin.action(description='Approve selected host applications')
    def approve_hosts(self, request, queryset):
        count = queryset.filter(
            host_status=User.HostStatus.PENDING
        ).update(
            host_status=User.HostStatus.APPROVED,
            host_approved_date=timezone.now(),
            user_type=User.UserType.HOST,
        )
        self.message_user(request, f'{count} host(s) approved.')

    @admin.action(description='Reject selected host applications')
    def reject_hosts(self, request, queryset):
        count = queryset.filter(
            host_status=User.HostStatus.PENDING
        ).update(
            host_status=User.HostStatus.REJECTED,
        )
        self.message_user(request, f'{count} host application(s) rejected.')
