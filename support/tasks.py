import html2text
from . import models
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.shortcuts import reverse
from celery import shared_task
import requests
import secrets
import django_keycloak_auth.clients


def get_feedback_url(description: str, reference: str):
    if settings.FEEDBACK_URL == "none":
        return None
    access_token = django_keycloak_auth.clients.get_access_token()
    r = requests.post(f"{settings.FEEDBACK_URL}/api/feedback_request/", json={
        "description": description,
        "action_reference": reference
    }, headers={
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    })
    r.raise_for_status()
    data = r.json()
    return data["public_url"]


def make_ticket_email(ticket: models.Ticket, message_id=None) -> EmailMultiAlternatives:
    headers = {}

    last_message_id = ticket.last_message_id(exclude_id=message_id)
    message_ids = ticket.message_ids(exclude_id=message_id)

    if last_message_id:
        headers["In-Reply-To"] = f"{last_message_id}"
    if message_ids:
        headers["References"] = " ".join(message_ids)
    if message_id:
        headers["Message-ID"] = f"{message_id}"

    email = EmailMultiAlternatives(
        to=[ticket.customer.email],
        headers=headers
    )
    return email


@shared_task(
    autoretry_for=(Exception,), retry_backoff=1, retry_backoff_max=60, max_retries=None, default_retry_delay=3
)
def send_open_ticket_email(ticket_id, verified: bool):
    ticket = models.Ticket.objects.get(id=ticket_id)

    verification_url = None
    if not verified:
        ticket.verification_token = secrets.token_urlsafe(64)
        ticket.save()
        verification_url = settings.EXTERNAL_URL_BASE + reverse('verify_ticket', args=(ticket.verification_token,))

    context = {
        "name": ticket.customer.full_name,
        "ticket_ref": ticket.ref,
        "verification_url": verification_url,
        "support_form_url": settings.EXTERNAL_URL_BASE + reverse("new_ticket")
    }
    html_content = render_to_string("support_email/ticket_opened.html", context)
    txt_content = render_to_string("support_email/ticket_opened.txt", context)

    email = make_ticket_email(ticket)
    email.subject = 'Ticket opened'
    email.body = txt_content
    email.attach_alternative(html_content, "text/html")
    email.send()


def open_ticket(
        customer: models.Customer, subject: str, html_message: str, source: str, priority: str, verified: bool = False,
        email_id: str = None, date=None
):
    ticket = models.Ticket(
        customer=customer,
        customer_verified=verified,
        source=source,
        priority=priority,
        subject=subject
    )

    ticket.save()

    ticket_message = models.TicketMessage(
        ticket=ticket,
        type=models.TicketMessage.TYPE_CUSTOMER,
        message=html_message,
        date=timezone.now() if not date else date,
        email_message_id=email_id
    )
    ticket_message.save()

    send_open_ticket_email.delay(ticket.id, verified)

    return ticket_message


def post_message(ticket: models.Ticket, message: str, email_id: str = None, date=None):
    ticket_message = models.TicketMessage(
        ticket=ticket,
        type=models.TicketMessage.TYPE_CUSTOMER,
        message=message,
        date=timezone.now() if not date else date,
        email_message_id=email_id
    )
    ticket_message.save()

    return ticket_message


@shared_task(
    autoretry_for=(Exception,), retry_backoff=1, retry_backoff_max=60, max_retries=None, default_retry_delay=3
)
def send_reply_email(message_id):
    ticket_message = models.TicketMessage.objects.get(id=message_id)
    email = make_ticket_email(ticket_message.ticket, ticket_message.email_message_id)

    h = html2text.HTML2Text()
    h.unicode_snob = True

    context = {
        "message_html": ticket_message.message,
        "message_txt": h.handle(ticket_message.message),
    }
    html_content = render_to_string("support_email/ticket_message.html", context)
    txt_content = render_to_string("support_email/ticket_message.txt", context)

    email.subject = f'Re: {ticket_message.ticket.subject}'
    email.body = txt_content
    email.attach_alternative(html_content, "text/html")
    email.send()


def post_reply(ticket: models.Ticket, message: str, agent):
    message = f"<p>Hi {ticket.customer.full_name},</p>\r\n{message}\r\n<p>Thanks,<br/>{agent.first_name}</p>"

    ticket_message = models.TicketMessage(
        ticket=ticket,
        type=models.TicketMessage.TYPE_RESPONSE,
        message=message,
        date=timezone.now()
    )
    ticket_message.email_message_id = f"<{ticket_message.id}@support.glauca.digital>"
    ticket_message.save()

    send_reply_email.delay(ticket_message.id)


def post_note(ticket: models.Ticket, message: str):
    ticket_message = models.TicketMessage(
        ticket=ticket,
        type=models.TicketMessage.TYPE_NOTE,
        message=message,
        date=timezone.now()
    )
    ticket_message.save()


def claim_ticket(ticket: models.Ticket, agent):
    ticket_message = models.TicketMessage(
        ticket=ticket,
        type=models.TicketMessage.TYPE_NOTE,
        message=f"Ticket claimed by {agent.first_name} {agent.last_name}",
        date=timezone.now()
    )
    ticket_message.save()
    ticket.assigned_to = agent
    ticket.save()


@shared_task(
    autoretry_for=(Exception,), retry_backoff=1, retry_backoff_max=60, max_retries=None, default_retry_delay=3
)
def send_close_ticket_email(ticket_id):
    ticket = models.Ticket.objects.get(id=ticket_id)
    feedback_url = get_feedback_url(ticket.subject, ticket.id)

    context = {
        "name": ticket.customer.full_name,
        "ticket_ref": ticket.ref,
        "feedback_url": feedback_url
    }
    html_content = render_to_string("support_email/ticket_closed.html", context)
    txt_content = render_to_string("support_email/ticket_closed.txt", context)

    email = make_ticket_email(ticket)
    email.subject = f'Ticket closed - {ticket.subject}'
    email.body = txt_content
    email.attach_alternative(html_content, "text/html")
    email.send()


def close_ticket(ticket: models.Ticket, message: str = ""):
    ticket.state = ticket.STATE_CLOSED
    ticket.save()

    ticket_message = models.TicketMessage(
        ticket=ticket,
        type=models.TicketMessage.TYPE_NOTE,
        message=f"<p>Ticket closed.</p>{message}",
        date=timezone.now()
    )
    ticket_message.save()

    send_close_ticket_email.delay(ticket.id)


def reopen_ticket(ticket: models.Ticket, message: str = ""):
    ticket.state = ticket.STATE_OPEN
    ticket.save()

    ticket_message = models.TicketMessage(
        ticket=ticket,
        type=models.TicketMessage.TYPE_NOTE,
        message=f"<p>Ticket reopened.</p>{message}",
        date=timezone.now()
    )
    ticket_message.save()
