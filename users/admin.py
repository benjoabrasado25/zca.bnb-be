"""User admin configuration with host approval workflow."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.sites.models import Site
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken

from .models import User

# Hide django-allauth and sites models from admin
try:
    admin.site.unregister(SocialAccount)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(SocialApp)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(SocialToken)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(EmailAddress)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(Site)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    """Admin configuration for custom User model with host approval."""

    list_display = [
        'username',
        'email',
        'first_name',
        'last_name',
        'user_type',
        'host_status_display',
        'is_verified',
        'is_staff',
        'created_at',
    ]
    list_filter = ['host_status', 'user_type', 'is_verified', 'is_staff', 'is_active']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['-created_at']
    actions = ['approve_hosts', 'reject_hosts', 'make_host', 'make_guest']

    def host_status_display(self, obj):
        """Display host status with color coding."""
        colors = {
            User.HostStatus.NOT_APPLIED: 'gray',
            User.HostStatus.PENDING: 'orange',
            User.HostStatus.APPROVED: 'green',
            User.HostStatus.REJECTED: 'red',
        }
        color = colors.get(obj.host_status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_host_status_display()
        )
    host_status_display.short_description = 'Host Status'
    host_status_display.admin_order_field = 'host_status'

    def get_queryset(self, request):
        """Order by pending hosts first."""
        qs = super().get_queryset(request)
        # Show pending hosts at the top
        from django.db.models import Case, When, Value, IntegerField
        return qs.annotate(
            status_order=Case(
                When(host_status='pending', then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by('status_order', '-created_at')

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
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Profile', {
            'fields': ('email', 'user_type', 'phone_number'),
        }),
    )

    @admin.action(description='✅ Approve selected host applications')
    def approve_hosts(self, request, queryset):
        count = queryset.filter(
            host_status=User.HostStatus.PENDING
        ).update(
            host_status=User.HostStatus.APPROVED,
            host_approved_date=timezone.now(),
            user_type=User.UserType.HOST,
        )
        self.message_user(request, f'{count} host(s) approved.')

    @admin.action(description='❌ Reject selected host applications')
    def reject_hosts(self, request, queryset):
        count = queryset.filter(
            host_status=User.HostStatus.PENDING
        ).update(
            host_status=User.HostStatus.REJECTED,
        )
        self.message_user(request, f'{count} host application(s) rejected.')

    @admin.action(description='🏠 Make selected users a Host')
    def make_host(self, request, queryset):
        count = queryset.update(
            user_type=User.UserType.HOST,
            host_status=User.HostStatus.APPROVED,
            host_approved_date=timezone.now(),
        )
        self.message_user(request, f'{count} user(s) are now hosts.')

    @admin.action(description='👤 Make selected users a Guest')
    def make_guest(self, request, queryset):
        count = queryset.update(
            user_type=User.UserType.GUEST,
            host_status=User.HostStatus.NOT_APPLIED,
        )
        self.message_user(request, f'{count} user(s) are now guests.')
