"""Payment admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Payment, Refund


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = [
        'id',
        'booking',
        'amount',
        'currency',
        'status',
        'payment_method',
        'paid_at',
        'created_at',
    ]
    list_filter = ['status', 'payment_method', 'currency']
    search_fields = [
        'xendit_invoice_id',
        'xendit_external_id',
        'booking__guest__email',
    ]
    readonly_fields = [
        'xendit_invoice_id',
        'xendit_external_id',
        'xendit_invoice_url',
        'xendit_callback_data',
        'created_at',
        'updated_at',
    ]
    ordering = ['-created_at']


@admin.register(Refund)
class RefundAdmin(ModelAdmin):
    list_display = [
        'id',
        'payment',
        'amount',
        'status',
        'refunded_at',
        'created_at',
    ]
    list_filter = ['status']
    readonly_fields = ['xendit_refund_id', 'created_at']
    ordering = ['-created_at']
