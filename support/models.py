import secrets
import django_keycloak_auth.models
import as207960_utils.models
import django.core.exceptions
from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from phonenumber_field.modelfields import PhoneNumberField
import lxml.html.clean


class Customer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="customer")
    is_agent = models.BooleanField(blank=True, null=False, default=False)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(db_index=True)
    phone = PhoneNumberField(blank=True, null=True)
    phone_ext = models.CharField(max_length=64, blank=True, null=True, verbose_name="Phone extension")
    pushover_user_key = models.CharField(max_length=255, blank=True, null=True)
    emails_blocked = models.BooleanField(blank=True, null=False, default=False)

    def __str__(self):
        return f"{self.full_name} - {self.email}"

    def save(self, *args, **kwargs):
        if self.user:
            self.full_name = f"{self.user.first_name} {self.user.last_name}"
            self.email = self.user.email
        super().save(*args, **kwargs)

    @classmethod
    def get_by_email(cls, email, name=None):
        customer = Customer.objects.filter(email=email).first()
        if customer:
            if name:
                customer.full_name = name
                customer.save()
            return customer
        else:
            customer = Customer.objects.create(email=email, full_name=name)
            return customer


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(instance, **_kwargs):
    try:
        instance.customer.save()
    except django.core.exceptions.ObjectDoesNotExist:
        customer = Customer.objects.filter(email=instance.email).first()
        if customer:
            customer.user = instance
            customer.save()
        else:
            Customer.objects.create(user=instance)


@receiver(user_logged_in)
def update_permissions(request, **_kwargs):
    request.user.customer.is_agent = "support.view_ticket" in request.user.get_all_permissions()


def make_ticket_ref():
    while True:
        possible_ref = secrets.token_hex(4).upper()
        try:
            ticket = Ticket.objects.filter(ref=possible_ref).first()
            if not ticket:
                return possible_ref
        except django.db.ProgrammingError:
            return possible_ref


class Ticket(models.Model):
    STATE_OPEN = "O"
    STATE_CLOSED = "C"
    STATES = (
        (STATE_OPEN, "Open"),
        (STATE_CLOSED, "Closed")
    )

    SOURCE_PHONE = "P"
    SOURCE_WEB = "W"
    SOURCE_EMAIL = "E"
    SOURCE_OTHER = "O"
    SOURCE_INTERNAL = "I"
    SOURCES = (
        (SOURCE_PHONE, "Phone"),
        (SOURCE_WEB, "Web"),
        (SOURCE_EMAIL, "Email"),
        (SOURCE_OTHER, "Other"),
        (SOURCE_INTERNAL, "Internal"),
    )

    PRIORITY_LOW = "L"
    PRIORITY_NORMAL = "N"
    PRIORITY_HIGH = "H"
    PRIORITY_EMERGENCY = "E"
    PRIORITIES = (
        (PRIORITY_LOW, "Low"),
        (PRIORITY_NORMAL, "Normal"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_EMERGENCY, "Emergency"),
    )

    id = as207960_utils.models.TypedUUIDField("support_ticket", primary_key=True)
    ref = models.CharField(max_length=64, db_index=True, default=make_ticket_ref)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    customer_verified = models.BooleanField(blank=True, null=False, default=False)
    verification_token = models.TextField(blank=True, null=True)
    state = models.CharField(max_length=1, choices=STATES, default=STATE_OPEN)
    source = models.CharField(max_length=1, choices=SOURCES, default=SOURCE_OTHER)
    priority = models.CharField(max_length=1, choices=PRIORITIES, default=PRIORITY_NORMAL)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    due_date = models.DateTimeField(blank=True, null=True)
    subject = models.CharField(max_length=255)
    deleted = models.BooleanField(blank=True, null=False, default=False)

    def first_message(self):
        return self.messages.order_by('date').first()

    def last_message(self):
        return self.messages.order_by('-date').first()

    def last_customer_message(self, exclude_id=None):
        messages = self.messages.filter(type=TicketMessage.TYPE_CUSTOMER).order_by('-date')
        if exclude_id:
            messages = messages.exclude(id=exclude_id)
        return messages.first()

    def last_response(self, exclude_id=None):
        messages = self.messages.filter(type=TicketMessage.TYPE_RESPONSE).order_by('-date')
        if exclude_id:
            messages = messages.exclude(id=exclude_id)
        return messages.first()

    def last_message_id(self, exclude_id=None):
        messages = self.messages.filter(email_message_id__isnull=False).order_by('-date')
        if exclude_id:
            messages = messages.exclude(email_message_id=exclude_id)
        last_message = messages.first()
        if last_message:
            return last_message.email_message_id
        return None

    def message_ids(self, exclude_id=None):
        messages = self.messages.filter(email_message_id__isnull=False).order_by('-date')
        if exclude_id:
            messages = messages.exclude(email_message_id=exclude_id)
        return list(messages.values_list('email_message_id', flat=True))


class TicketMessage(models.Model):
    TYPE_CUSTOMER = "C"
    TYPE_RESPONSE = "R"
    TYPE_NOTE = "N"
    TYPE_SYSTEM = "S"
    TYPE_SYSTEM_RESPONSE = "E"
    TYPES = (
        (TYPE_CUSTOMER, "Customer"),
        (TYPE_RESPONSE, "Response"),
        (TYPE_NOTE, "Note"),
        (TYPE_SYSTEM, "System"),
        (TYPE_SYSTEM_RESPONSE, "System Response"),
    )

    id = as207960_utils.models.TypedUUIDField("support_ticketmessage", primary_key=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    type = models.CharField(max_length=1, choices=TYPES)
    date = models.DateTimeField()
    message = models.TextField()
    email_message_id = models.TextField(blank=True, null=True)

    @property
    def message_safe(self):
        doc = lxml.html.document_fromstring(self.message)
        cleaner = lxml.html.clean.Cleaner(style=True, inline_style=False)
        clean_doc = cleaner.clean_html(doc)
        return lxml.html.tostring(clean_doc).decode()

    class Meta:
        ordering = ['date']


class TicketMessageAttachment(models.Model):
    id = as207960_utils.models.TypedUUIDField("support_ticketattachment", primary_key=True)
    message = models.ForeignKey(TicketMessage, on_delete=models.CASCADE)
    file_name = models.TextField(blank=True, null=True)
    file = models.FileField()


class VerificationSession(models.Model):
    id = as207960_utils.models.TypedUUIDField("support_verificationsession", primary_key=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    stripe_session = models.CharField(max_length=255)
