from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from Crypto.Hash import SHA
from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA
from django.conf import settings
from django.utils import timezone
from django.core import files
import base64
import logging
import binascii
import json
import email.parser
import email.policy
import markdown2
import talon.quotations
import io
from .. import models, tasks

talon.init()
logger = logging.getLogger(__name__)


@csrf_exempt
def postal(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    orig_sig = request.headers.get("X-Postal-Signature")
    if not orig_sig:
        return HttpResponse(status=400)

    try:
        orig_sig = base64.b64decode(orig_sig)
    except binascii.Error:
        return HttpResponse(status=400)

    own_hash = SHA.new()
    own_hash.update(request.body)
    pubkey_bytes = base64.b64decode(settings.POSTAL_PUBLIC_KEY)
    pubkey = RSA.importKey(pubkey_bytes)
    verifier = PKCS1_v1_5.new(pubkey)
    valid_sig = verifier.verify(own_hash, orig_sig)

    if not valid_sig:
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
    print(message)

    if 'message-id' in message:
        existing_message = models.TicketMessage.objects.filter(email_message_id=message['message-id']).first()
        if existing_message:
            logging.warning(f"Duplicate message, throwing away: {existing_message.email_message_id}")
            return HttpResponse(status=200)
    else:
        logger.warning("No message ID, throwing away")
        return HttpResponse(status=200)

    if 'from' not in message:
        logging.warning("No from, throwing away")
        return HttpResponse(status=200)
    if 'date' not in message:
        logging.warning("No date, throwing away")
        return HttpResponse(status=200)

    message_date = message['date']
    message_date = (
                       message_date.datetime if message_date.datetime else timezone.now()
                   ) if message_date else timezone.now()

    html_body = message.get_body(('html',))
    if not html_body:
        plain_body = message.get_body(('plain',))
        if not plain_body:
            logging.warning(f"No usable body, throwing away")
            return HttpResponse(status=200)
        else:
            plain_body = talon.quotations.extract_from(plain_body.get_content(), plain_body.get_content_type())
            markdown = markdown2.Markdown()
            html_body = markdown.convert(plain_body)
    else:
        html_body = talon.quotations.extract_from(html_body.get_content(), html_body.get_content_type())

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
        new_message = tasks.open_ticket(
            customer, subject, html_body, source=models.Ticket.SOURCE_EMAIL, priority=models.Ticket.PRIORITY_NORMAL,
            verified=False, email_id=message['message-id'], date=message_date
        )
    else:
        new_message = tasks.post_message(ticket, html_body, email_id=message['message-id'], date=message_date)

    for attachment in message.iter_attachments():
        file_name = attachment.get_filename(failobj="Untitled"),
        file = files.base.ContentFile(attachment.get_payload(decode=True), name=file_name)
        message_attachment = models.TicketMessageAttachment(
            message=new_message,
            file_name=file_name,
            file=file
        )
        message_attachment.save()

    return HttpResponse(status=200)
