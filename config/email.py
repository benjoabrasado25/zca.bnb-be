"""
Email service using Resend for transactional emails.
"""

import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def send_email(
    to: str | list[str],
    subject: str,
    html: str,
    from_email: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> dict | None:
    """
    Send an email using Resend.

    Args:
        to: Email address or list of addresses
        subject: Email subject
        html: HTML content of the email
        from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)
        reply_to: Reply-to address

    Returns:
        dict with 'id' on success, None on failure
    """
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured, skipping email send")
        return None

    import resend
    resend.api_key = settings.RESEND_API_KEY

    # Ensure 'to' is a list
    if isinstance(to, str):
        to = [to]

    params = {
        "from": from_email or settings.DEFAULT_FROM_EMAIL,
        "to": to,
        "subject": subject,
        "html": html,
    }

    if reply_to:
        params["reply_to"] = reply_to

    try:
        response = resend.Emails.send(params)
        logger.info(f"Email sent successfully: {response.get('id')}")
        return response
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return None


def send_booking_confirmation(booking) -> dict | None:
    """
    Send booking confirmation email to the guest.
    """
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #05a7c7; padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0;">Booking Confirmed!</h1>
        </div>
        <div style="padding: 20px; background: #f9fafb;">
            <p>Hi {booking.user.first_name or booking.user.username},</p>
            <p>Your booking has been confirmed. Here are the details:</p>

            <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="margin-top: 0; color: #05a7c7;">{booking.listing.title}</h3>
                <p><strong>Check-in:</strong> {booking.check_in.strftime('%B %d, %Y')}</p>
                <p><strong>Check-out:</strong> {booking.check_out.strftime('%B %d, %Y')}</p>
                <p><strong>Guests:</strong> {booking.num_guests}</p>
                <p><strong>Total:</strong> ₱{booking.total_price:,.2f}</p>
            </div>

            <p>Your host will reach out with check-in instructions closer to your arrival date.</p>

            <p style="margin-top: 30px;">
                <a href="{settings.FRONTEND_URL}/my-bookings"
                   style="background: #05a7c7; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                    View My Bookings
                </a>
            </p>
        </div>
        <div style="padding: 20px; text-align: center; color: #6b7280; font-size: 12px;">
            <p>© StaySuitePH. All rights reserved.</p>
        </div>
    </div>
    """

    return send_email(
        to=booking.user.email,
        subject=f"Booking Confirmed - {booking.listing.title}",
        html=html,
    )


def send_booking_notification_to_host(booking) -> dict | None:
    """
    Send notification email to host when they receive a new booking.
    """
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #059669; padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0;">New Booking!</h1>
        </div>
        <div style="padding: 20px; background: #f9fafb;">
            <p>Hi {booking.listing.host.first_name or booking.listing.host.username},</p>
            <p>You have a new booking for <strong>{booking.listing.title}</strong>!</p>

            <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="margin-top: 0; color: #059669;">Guest Details</h3>
                <p><strong>Name:</strong> {booking.user.first_name} {booking.user.last_name or ''}</p>
                <p><strong>Email:</strong> {booking.user.email}</p>
                <p><strong>Check-in:</strong> {booking.check_in.strftime('%B %d, %Y')}</p>
                <p><strong>Check-out:</strong> {booking.check_out.strftime('%B %d, %Y')}</p>
                <p><strong>Guests:</strong> {booking.num_guests}</p>
                <p><strong>Total:</strong> ₱{booking.total_price:,.2f}</p>
            </div>

            {f'<div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin: 20px 0;"><strong>Message from guest:</strong><p style="margin-bottom: 0;">{booking.message_to_host}</p></div>' if booking.message_to_host else ''}

            <p style="margin-top: 30px;">
                <a href="{settings.FRONTEND_URL}/hosting/reservations"
                   style="background: #059669; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                    View Reservations
                </a>
            </p>
        </div>
        <div style="padding: 20px; text-align: center; color: #6b7280; font-size: 12px;">
            <p>© StaySuitePH. All rights reserved.</p>
        </div>
    </div>
    """

    return send_email(
        to=booking.listing.host.email,
        subject=f"New Booking - {booking.listing.title}",
        html=html,
    )


def send_contact_form_email(
    name: str,
    email: str,
    subject: str,
    message: str,
) -> dict | None:
    """
    Send contact form submission to support.
    """
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #05a7c7; padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0;">New Contact Form Submission</h1>
        </div>
        <div style="padding: 20px; background: #f9fafb;">
            <div style="background: white; padding: 20px; border-radius: 8px;">
                <p><strong>From:</strong> {name}</p>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Subject:</strong> {subject}</p>
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 15px 0;">
                <p><strong>Message:</strong></p>
                <p style="white-space: pre-wrap;">{message}</p>
            </div>
        </div>
    </div>
    """

    return send_email(
        to="support@staysuiteph.com",
        subject=f"Contact Form: {subject}",
        html=html,
        reply_to=email,
    )


def send_host_application_received(user) -> dict | None:
    """
    Send confirmation to user that their host application was received.
    """
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #05a7c7; padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0;">Application Received!</h1>
        </div>
        <div style="padding: 20px; background: #f9fafb;">
            <p>Hi {user.first_name or user.username},</p>
            <p>Thank you for applying to become a host on StaySuitePH!</p>
            <p>We've received your application and our team will review it within 24-48 hours.</p>
            <p>We'll notify you by email once your application has been approved.</p>

            <p style="margin-top: 30px;">Best regards,<br>The StaySuitePH Team</p>
        </div>
        <div style="padding: 20px; text-align: center; color: #6b7280; font-size: 12px;">
            <p>© StaySuitePH. All rights reserved.</p>
        </div>
    </div>
    """

    return send_email(
        to=user.email,
        subject="Host Application Received - StaySuitePH",
        html=html,
    )


def send_host_application_approved(user) -> dict | None:
    """
    Send notification that host application was approved.
    """
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #059669; padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0;">Congratulations!</h1>
        </div>
        <div style="padding: 20px; background: #f9fafb;">
            <p>Hi {user.first_name or user.username},</p>
            <p>Great news! Your host application has been <strong>approved</strong>!</p>
            <p>You can now start listing your properties on StaySuitePH and begin receiving bookings.</p>

            <p style="margin-top: 30px;">
                <a href="{settings.FRONTEND_URL}/hosting"
                   style="background: #059669; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                    Go to Host Dashboard
                </a>
            </p>

            <p style="margin-top: 30px;">Welcome to the StaySuitePH host community!</p>
        </div>
        <div style="padding: 20px; text-align: center; color: #6b7280; font-size: 12px;">
            <p>© StaySuitePH. All rights reserved.</p>
        </div>
    </div>
    """

    return send_email(
        to=user.email,
        subject="Host Application Approved! 🎉 - StaySuitePH",
        html=html,
    )
