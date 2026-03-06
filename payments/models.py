"""Payment models for ZCA BnB."""

from django.db import models


class Payment(models.Model):
    """
    Payment record linked to a booking.
    Integrates with Xendit for payment processing.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'
        EXPIRED = 'expired', 'Expired'

    class PaymentMethod(models.TextChoices):
        GCASH = 'gcash', 'GCash'
        MAYA = 'maya', 'Maya'
        BPI = 'bpi', 'BPI Online'
        BDO = 'bdo', 'BDO Online'
        CREDIT_CARD = 'credit_card', 'Credit Card'
        DEBIT_CARD = 'debit_card', 'Debit Card'
        BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
        OTHER = 'other', 'Other'

    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='payment',
    )

    # Xendit fields
    xendit_invoice_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
    )
    xendit_invoice_url = models.URLField(max_length=500)
    xendit_external_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text='Our reference ID sent to Xendit',
    )

    # Payment details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='PHP')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    payment_method = models.CharField(
        max_length=50,
        choices=PaymentMethod.choices,
        blank=True,
    )
    payment_channel = models.CharField(
        max_length=50,
        blank=True,
        help_text='Specific channel used (e.g., GCASH, MAYA)',
    )

    # Timestamps
    paid_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Xendit webhook data
    xendit_callback_data = models.JSONField(
        null=True,
        blank=True,
        help_text='Raw webhook data from Xendit',
    )

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f"Payment {self.xendit_external_id} - {self.status}"

    @property
    def is_paid(self):
        return self.status == self.Status.PAID

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING


class Refund(models.Model):
    """Refund record for cancelled bookings."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='refunds',
    )
    xendit_refund_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    refunded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'refunds'
        ordering = ['-created_at']

    def __str__(self):
        return f"Refund {self.id} for Payment {self.payment_id}"
