from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
import base64
import logging
import binascii
import json
import email.parser
import email.policy
import markdown2
import io
import uuid
import bs4
import mimetypes
import cryptography.hazmat.primitives.asymmetric.padding
import cryptography.hazmat.primitives.serialization
import cryptography.hazmat.primitives.hashes
import cryptography.exceptions
import stripe
import stripe.identity
from .. import models, tasks, middleware

logger = logging.getLogger(__name__)


@csrf_exempt
@middleware.try_login_exempt
def postal_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    orig_sig = request.headers.get("X-Postal-Signature")
    if not orig_sig:
        return HttpResponse(status=400)

    try:
        orig_sig = base64.b64decode(orig_sig)
    except binascii.Error:
        return HttpResponse(status=400)

    pubkey_bytes = base64.b64decode(settings.POSTAL_PUBLIC_KEY)
    pubkey = cryptography.hazmat.primitives.serialization.load_der_public_key(pubkey_bytes)
    try:
        pubkey.verify(
            orig_sig, request.body,
            cryptography.hazmat.primitives.asymmetric.padding.PKCS1v15(),
            cryptography.hazmat.primitives.hashes.SHA1()
        )
    except cryptography.exceptions.InvalidSignature:
        return HttpResponse(status=401)

    try:
        req_body = json.loads(request.body.decode())
    except (json.JSONDecodeError, UnicodeError):
        return HttpResponse(status=400)

    logger.info(
        f"Got email webhook; from: {req_body.get('mail_from')}, to: {req_body.get('rcpt_to')}"
    )

    msg_bytes = base64.b64decode(req_body.get("message"))

    message = email.parser.BytesParser(_class=email.message.EmailMessage, policy=email.policy.SMTPUTF8)\
        .parsebytes(msg_bytes)

    if 'message-id' in message:
        existing_message = models.TicketMessage.objects.filter(email_message_id=message['message-id']).first()
        if existing_message:
            logging.warning(f"Duplicate message, throwing away: {existing_message.email_message_id}")
            return HttpResponse(status=204)
    else:
        logger.warning("No message ID, throwing away")
        return HttpResponse(status=204)

    if 'from' not in message:
        logging.warning("No from, throwing away")
        return HttpResponse(status=204)
    if 'date' not in message:
        logging.warning("No date, throwing away")
        return HttpResponse(status=204)

    if 'auto-submitted' in message:
        if message['auto-submitted'] in ('auto-generated', 'auto-replied'):
            logging.warning("Automatically generated message, throwing away")
            return HttpResponse(status=204)

    message_date = message['date']
    message_date = (
                       message_date.datetime if message_date.datetime else timezone.now()
                   ) if message_date else timezone.now()

    attachments = []
    attachment_cid_map = {}

    for attachment in message.iter_attachments():
        file_name = attachment.get_filename(failobj="Untitled")
        file_ext = mimetypes.guess_extension(attachment.get_content_type())
        content_id = attachment["content-id"]
        disk_file_name = models.TicketMessageAttachment.file.field.generate_filename(
            None, f"{str(uuid.uuid4().hex)}{file_ext}"
        )
        content = io.BytesIO(attachment.get_payload(decode=True))
        final_name = models.TicketMessageAttachment.file.field.storage.save(
            disk_file_name, content, max_length=models.TicketMessageAttachment.file.field.max_length
        )
        file_url = models.TicketMessageAttachment.file.field.storage.url(final_name)
        attachments.append({
            "file_name": file_name,
            "disk_file_name": final_name,
        })
        if content_id:
            content_id = str(content_id)
            if content_id.startswith("<") and content_id.endswith(">"):
                content_id = content_id[1:-1]
                attachment_cid_map[content_id] = file_url

    html_body = message.get_body(('html',))
    if not html_body:
        plain_body = message.get_body(('plain',))
        if not plain_body:
            logging.warning(f"No usable body, throwing away")
            return HttpResponse(status=200)
        else:
            plain_body = plain_body.get_content()
            markdown = markdown2.Markdown()
            html_body = markdown.convert(plain_body)
    else:
        html_body = html_body.get_content()

    soup = bs4.BeautifulSoup(html_body, 'html.parser')

    def replace_url(tag: str, attr: str):
        for img_tag in soup.find_all(tag):
            src = img_tag[attr]
            if src.startswith("cid:"):
                cid = src[4:]
                new_url = attachment_cid_map.get(cid)
                if new_url:
                    img_tag[attr] = new_url

    replace_url('img', 'src')
    replace_url('script', 'src')
    replace_url('link', 'href')
    replace_url('audio', 'src')
    replace_url('video', 'src')
    replace_url('iframe', 'src')
    replace_url('embed', 'src')
    replace_url('source', 'src')

    html_body = str(soup)

    references = message['references']
    in_reply_to = message['in-reply-to']
    ticket = None

    if in_reply_to:
        ticket = models.Ticket.objects.filter(
            Q(messages__email_message_id=in_reply_to.strip()) &
            ~Q(state=models.Ticket.STATE_CLOSED)
        ).first()
    if not ticket and references:
        references = list(map(lambda r: r.strip(), references.split(" ")))
        ticket = models.Ticket.objects.filter(
            Q(messages__email_message_id__in=references) &
            ~Q(state=models.Ticket.STATE_CLOSED)
        ).first()

    if not ticket:
        from_address = message['from'].addresses[0]
        subject = message['subject'] if message['subject'] else "No subject"
        customer = models.Customer.get_by_email(from_address.addr_spec, from_address.display_name)
        if customer.emails_blocked:
            tasks.send_email_blocked.delay(customer.id, message['message-id'])
            return HttpResponse(status=204)

        new_message = tasks.open_ticket(
            customer, subject, html_body, source=models.Ticket.SOURCE_EMAIL, priority=models.Ticket.PRIORITY_NORMAL,
            verified=False, email_id=message['message-id'], date=message_date
        )
    else:
        new_message = tasks.post_message(ticket, html_body, email_id=message['message-id'], date=message_date)

    for attachment in attachments:
        message_attachment = models.TicketMessageAttachment(
            message=new_message,
            file_name=attachment["file_name"]
        )
        message_attachment.file.name = attachment["disk_file_name"]
        message_attachment.save()

    return HttpResponse(status=204)


@csrf_exempt
@middleware.try_login_exempt
def stripe_webhook(request):
    try:
        event = stripe.Webhook.construct_event(
            request.body,
            request.headers.get("Stripe-Signature"),
            settings.STRIPE_ENDPOINT_SECRET
        )
    except ValueError as e:
        raise e
    except stripe.error.SignatureVerificationError as e:
        raise e

    if event['type'] in (
            'identity.verification_session.requires_input',
            'identity.verification_session.verified'
    ):
        stripe_verification_session = event['data']['object']
        verification_successful = event['type'] == 'identity.verification_session.verified'
    else:
        return HttpResponse(status=400)

    verification_session = models.VerificationSession.objects\
        .filter(stripe_session=stripe_verification_session['id']).first()
    if not verification_session:
        return HttpResponse(status=204)

    if verification_successful:
        stripe_verification_session = stripe.identity.VerificationSession.retrieve(
            stripe_verification_session['id'],
            expand=['verified_outputs']
        )

        message = "<p>Verification successful</p><p>"

        if stripe_verification_session['verified_outputs'].get("first_name"):
            message += f"First name: {stripe_verification_session['verified_outputs']['first_name']}<br>"
        if stripe_verification_session['verified_outputs'].get("last_name"):
            message += f"Last name: {stripe_verification_session['verified_outputs']['last_name']}<br>"
        if stripe_verification_session['verified_outputs'].get("address"):
            address = []
            if stripe_verification_session['verified_outputs']['address'].get("line1"):
                address.append(stripe_verification_session['verified_outputs']['address']['line1'])
            if stripe_verification_session['verified_outputs']['address'].get("line2"):
                address.append(stripe_verification_session['verified_outputs']['address']['line2'])
            if stripe_verification_session['verified_outputs']['address'].get("city"):
                address.append(stripe_verification_session['verified_outputs']['address']['city'])
            if stripe_verification_session['verified_outputs']['address'].get("state"):
                address.append(stripe_verification_session['verified_outputs']['address']['state'])
            if stripe_verification_session['verified_outputs']['address'].get("postal_code"):
                address.append(stripe_verification_session['verified_outputs']['address']['postal_code'])
            if stripe_verification_session['verified_outputs']['address'].get("country"):
                address.append(stripe_verification_session['verified_outputs']['address']['country'])
            message += f"Address: {', '.join(address)}<br>"

        message += "</p>"

        ticket_message = models.TicketMessage(
            ticket=verification_session.ticket,
            type=models.TicketMessage.TYPE_SYSTEM_RESPONSE,
            message=message,
            date=timezone.now()
        )
        ticket_message.save()

        tasks.send_notification.delay(
            verification_session.ticket.id,
            f"Verification successful",
            f"Identity verification successful on ticket #{verification_session.ticket.ref}",
            int(ticket_message.date.timestamp())
        )

    else:
        ticket_message = models.TicketMessage(
            ticket=verification_session.ticket,
            type=models.TicketMessage.TYPE_SYSTEM_RESPONSE,
            message="<p>Verification failed</p>",
            date=timezone.now()
        )
        ticket_message.save()

        tasks.send_notification.delay(
            verification_session.ticket.id,
            f"Verification failed",
            f"Identity verification failed on ticket #{verification_session.ticket.ref}",
            int(ticket_message.date.timestamp())
        )

    return HttpResponse(status=204)
