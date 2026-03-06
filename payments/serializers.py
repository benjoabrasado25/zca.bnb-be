"""Payment serializers for ZCA BnB."""

from rest_framework import serializers

from .models import Payment, Refund


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for payment details."""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(
        source='get_payment_method_display',
        read_only=True
    )

    class Meta:
        model = Payment
        fields = [
            'id',
            'xendit_invoice_id',
            'xendit_invoice_url',
            'amount',
            'currency',
            'status',
            'status_display',
            'payment_method',
            'payment_method_display',
            'payment_channel',
            'paid_at',
            'expires_at',
            'created_at',
        ]
        read_only_fields = fields


class PaymentSummarySerializer(serializers.ModelSerializer):
    """Minimal payment info for booking responses."""

    class Meta:
        model = Payment
        fields = [
            'id',
            'xendit_invoice_url',
            'amount',
            'currency',
            'status',
            'expires_at',
        ]
        read_only_fields = fields


class RefundSerializer(serializers.ModelSerializer):
    """Serializer for refund details."""

    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Refund
        fields = [
            'id',
            'amount',
            'reason',
            'status',
            'status_display',
            'refunded_at',
            'created_at',
        ]
        read_only_fields = fields
