"""
Xendit payment gateway integration service.
Handles invoice creation, webhook processing, and refunds.
"""

import hashlib
import hmac
import logging
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import requests
from django.conf import settings
from django.utils import timezone

from .models import Payment, Refund

logger = logging.getLogger(__name__)

XENDIT_BASE_URL = 'https://api.xendit.co'


class XenditError(Exception):
    """Exception for Xendit API errors."""
    pass


def create_invoice(
    booking,
    success_redirect_url: str = None,
    failure_redirect_url: str = None,
):
    """
    Create a Xendit invoice for a booking.

    Args:
        booking: The Booking instance
        success_redirect_url: URL to redirect after successful payment
        failure_redirect_url: URL to redirect after failed payment

    Returns:
        Payment: The created Payment instance
    """
    if not settings.XENDIT_SECRET_KEY:
        raise XenditError("Xendit is not configured")

    # Generate unique external ID
    external_id = f"booking-{booking.id}-{uuid4().hex[:8]}"

    # Calculate amount
    amount = float(booking.total_price)

    # Build invoice payload
    payload = {
        'external_id': external_id,
        'amount': amount,
        'currency': booking.currency,
        'description': f"Booking at {booking.listing.title}",
        'customer': {
            'given_names': booking.guest_name or booking.guest.first_name,
            'email': booking.guest_email or booking.guest.email,
        },
        'customer_notification_preference': {
            'invoice_created': ['email'],
            'invoice_paid': ['email'],
        },
        'payment_methods': [
            'GCASH', 'MAYA', 'BPI', 'BDO',
            'CREDIT_CARD', 'BANK_TRANSFER',
        ],
        'invoice_duration': 86400,  # 24 hours
        'items': [
            {
                'name': booking.listing.title,
                'quantity': booking.nights,
                'price': float(booking.price_per_night),
            }
        ],
    }

    # Add cleaning fee if applicable
    if booking.cleaning_fee and booking.cleaning_fee > 0:
        payload['items'].append({
            'name': 'Cleaning Fee',
            'quantity': 1,
            'price': float(booking.cleaning_fee),
        })

    # Add redirect URLs if provided
    if success_redirect_url:
        payload['success_redirect_url'] = success_redirect_url
    if failure_redirect_url:
        payload['failure_redirect_url'] = failure_redirect_url

    # Call Xendit API
    try:
        response = requests.post(
            f'{XENDIT_BASE_URL}/v2/invoices',
            json=payload,
            auth=(settings.XENDIT_SECRET_KEY, ''),
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"Xendit API error: {e}")
        raise XenditError(f"Failed to create invoice: {e}")

    # Parse expiry date
    expiry_date = None
    if data.get('expiry_date'):
        try:
            expiry_date = timezone.datetime.fromisoformat(
                data['expiry_date'].replace('Z', '+00:00')
            )
        except (ValueError, TypeError):
            expiry_date = timezone.now() + timedelta(hours=24)

    # Create Payment record
    payment = Payment.objects.create(
        booking=booking,
        xendit_invoice_id=data['id'],
        xendit_invoice_url=data['invoice_url'],
        xendit_external_id=external_id,
        amount=Decimal(str(amount)),
        currency=booking.currency,
        status=Payment.Status.PENDING,
        expires_at=expiry_date,
    )

    logger.info(f"Created Xendit invoice {data['id']} for booking {booking.id}")

    return payment


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify Xendit webhook callback signature.

    Args:
        payload: Raw request body bytes
        signature: X-Callback-Token header value

    Returns:
        bool: True if signature is valid
    """
    if not settings.XENDIT_WEBHOOK_TOKEN:
        logger.warning("XENDIT_WEBHOOK_TOKEN not configured")
        return False

    return hmac.compare_digest(signature, settings.XENDIT_WEBHOOK_TOKEN)


def handle_webhook(data: dict) -> Payment:
    """
    Process Xendit webhook callback.

    Args:
        data: Webhook payload data

    Returns:
        Payment: The updated Payment instance
    """
    external_id = data.get('external_id')
    xendit_status = data.get('status', '').upper()

    try:
        payment = Payment.objects.get(xendit_external_id=external_id)
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for external_id: {external_id}")
        raise

    # Map Xendit status to our status
    status_map = {
        'PAID': Payment.Status.PAID,
        'SETTLED': Payment.Status.PAID,
        'EXPIRED': Payment.Status.EXPIRED,
        'FAILED': Payment.Status.FAILED,
    }

    new_status = status_map.get(xendit_status)
    if not new_status:
        logger.warning(f"Unknown Xendit status: {xendit_status}")
        return payment

    # Update payment
    payment.status = new_status
    payment.xendit_callback_data = data

    if new_status == Payment.Status.PAID:
        payment.paid_at = timezone.now()
        payment.payment_method = _map_payment_method(data.get('payment_method', ''))
        payment.payment_channel = data.get('payment_channel', '')

        # Confirm the booking
        from bookings.services import BookingService
        BookingService.confirm_booking(payment.booking)

        logger.info(f"Payment {payment.id} confirmed, booking {payment.booking_id} confirmed")

    payment.save()

    return payment


def _map_payment_method(xendit_method: str) -> str:
    """Map Xendit payment method to our enum."""
    method_map = {
        'EWALLET': Payment.PaymentMethod.OTHER,
        'GCASH': Payment.PaymentMethod.GCASH,
        'MAYA': Payment.PaymentMethod.MAYA,
        'CREDIT_CARD': Payment.PaymentMethod.CREDIT_CARD,
        'DEBIT_CARD': Payment.PaymentMethod.DEBIT_CARD,
        'BANK_TRANSFER': Payment.PaymentMethod.BANK_TRANSFER,
        'DIRECT_DEBIT': Payment.PaymentMethod.BANK_TRANSFER,
        'BPI': Payment.PaymentMethod.BPI,
        'BDO': Payment.PaymentMethod.BDO,
    }
    return method_map.get(xendit_method.upper(), Payment.PaymentMethod.OTHER)


def create_refund(payment: Payment, amount: Decimal = None, reason: str = '') -> Refund:
    """
    Create a refund for a payment.

    Args:
        payment: The Payment instance
        amount: Refund amount (defaults to full amount)
        reason: Reason for refund

    Returns:
        Refund: The created Refund instance
    """
    if not settings.XENDIT_SECRET_KEY:
        raise XenditError("Xendit is not configured")

    if payment.status != Payment.Status.PAID:
        raise XenditError("Can only refund paid payments")

    refund_amount = amount or payment.amount

    # Create refund in Xendit
    payload = {
        'invoice_id': payment.xendit_invoice_id,
        'reason': reason or 'Booking cancelled',
        'amount': float(refund_amount),
    }

    try:
        response = requests.post(
            f'{XENDIT_BASE_URL}/refunds',
            json=payload,
            auth=(settings.XENDIT_SECRET_KEY, ''),
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"Xendit refund error: {e}")
        # Create pending refund record even if API fails
        return Refund.objects.create(
            payment=payment,
            amount=refund_amount,
            reason=reason,
            status=Refund.Status.FAILED,
        )

    # Create Refund record
    refund = Refund.objects.create(
        payment=payment,
        xendit_refund_id=data.get('id'),
        amount=refund_amount,
        reason=reason,
        status=Refund.Status.PENDING,
    )

    # Update payment status
    if refund_amount >= payment.amount:
        payment.status = Payment.Status.REFUNDED
        payment.save()

    logger.info(f"Created refund {refund.id} for payment {payment.id}")

    return refund


def get_invoice_status(xendit_invoice_id: str) -> dict:
    """
    Get the current status of a Xendit invoice.

    Args:
        xendit_invoice_id: The Xendit invoice ID

    Returns:
        dict: Invoice data from Xendit
    """
    if not settings.XENDIT_SECRET_KEY:
        raise XenditError("Xendit is not configured")

    try:
        response = requests.get(
            f'{XENDIT_BASE_URL}/v2/invoices/{xendit_invoice_id}',
            auth=(settings.XENDIT_SECRET_KEY, ''),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to get invoice status: {e}")
        raise XenditError(f"Failed to get invoice status: {e}")
