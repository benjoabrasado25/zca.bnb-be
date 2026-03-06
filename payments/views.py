"""Payment views for ZCA BnB."""

import json
import logging

from django.http import HttpResponse
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment
from .serializers import PaymentSerializer
from .services import handle_webhook, verify_webhook_signature, get_invoice_status

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing payment details."""

    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter payments to user's own bookings."""
        return Payment.objects.filter(
            booking__guest=self.request.user
        ).select_related('booking', 'booking__listing')

    @action(detail=True, methods=['get'], url_path='check-status')
    def check_status(self, request, pk=None):
        """
        Check the current status of a payment with Xendit.
        Useful for polling after redirect back from payment page.
        """
        payment = self.get_object()

        # If already paid or failed, return current status
        if payment.status != Payment.Status.PENDING:
            return Response(PaymentSerializer(payment).data)

        # Check with Xendit
        try:
            xendit_data = get_invoice_status(payment.xendit_invoice_id)
            xendit_status = xendit_data.get('status', '').upper()

            if xendit_status in ['PAID', 'SETTLED']:
                # Process as if webhook received
                handle_webhook(xendit_data)
                payment.refresh_from_db()

        except Exception as e:
            logger.error(f"Failed to check payment status: {e}")

        return Response(PaymentSerializer(payment).data)


class XenditWebhookView(APIView):
    """
    Webhook endpoint for Xendit payment notifications.
    POST /api/payments/webhook/xendit/
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        # Get callback token from header
        callback_token = request.headers.get('X-Callback-Token', '')

        # Verify signature
        if not verify_webhook_signature(request.body, callback_token):
            logger.warning("Invalid Xendit webhook signature")
            return HttpResponse(status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse(status=400)

        logger.info(f"Received Xendit webhook: {data.get('external_id')} - {data.get('status')}")

        try:
            handle_webhook(data)
        except Payment.DoesNotExist:
            logger.error(f"Payment not found: {data.get('external_id')}")
            # Return 200 to prevent Xendit from retrying
            return HttpResponse(status=200)
        except Exception as e:
            logger.exception(f"Error processing webhook: {e}")
            return HttpResponse(status=500)

        return HttpResponse(status=200)
